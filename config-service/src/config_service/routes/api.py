#!/usr/bin/env python3
# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import os
import sys
from http import HTTPStatus
from typing import Any

from pydantic import ValidationError
from quart import Blueprint, current_app, jsonify, request

from config_service.models.contracts import (
    ParseTextRequest,
    RenderTextRequest,
    RenderYamlRequest,
    SchemaOptions,
    ValidateRequest,
)

APP_ENABLE_DEV_FEATURES_ENV = "APP_ENABLE_DEV_FEATURES"
_ENV_TRUE_VALUES = {"1", "true", "yes", "on"}


def _app_enable_dev_features_enabled() -> bool:
    raw_value = os.environ.get(APP_ENABLE_DEV_FEATURES_ENV, "")
    normalized = str(raw_value or "").strip().lower()
    return normalized in _ENV_TRUE_VALUES


def _normalize_pydantic_issues(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, error in enumerate(errors, start=1):
        loc = error.get("loc", ())
        if isinstance(loc, (list, tuple)):
            path = "$." + ".".join(str(part) for part in loc if part != "body")
        else:
            path = "$"
        path = path if path != "$." else "$"
        normalized.append(
            {
                "order": index,
                "code": "pydantic_validation_error",
                "path": path,
                "message": str(error.get("msg") or "Request validation error"),
                "severity": "error",
                "source": "schema",
                "detail_type": str(error.get("type") or "validation_error"),
            }
        )
    return normalized


def create_api_blueprint() -> Blueprint:
    bp = Blueprint("config_service_api", __name__)

    @bp.post("/client-errors")
    async def client_errors() -> Any:
        body = await request.get_json(silent=True) or {}
        message = str(body.get("message") or "Unknown UI error").strip()
        kind = str(body.get("kind") or "runtime_error").strip()
        source = str(body.get("source") or "browser").strip()
        path = str(body.get("path") or request.headers.get("Referer") or "").strip()
        stack = str(body.get("stack") or "").strip()
        line = body.get("line")
        column = body.get("column")
        user_agent = request.headers.get("User-Agent", "")

        log_message = (
            f"UI ERROR | kind={kind} | source={source} | path={path or '-'} | "
            f"line={line if line is not None else '-'} | column={column if column is not None else '-'} | "
            f"message={message}"
        )
        if user_agent:
            log_message += f" | user_agent={user_agent}"
        if stack:
            log_message += f"\n{stack}"

        current_app.logger.error(log_message)
        print(log_message, file=sys.stderr, flush=True)
        return jsonify({"ok": True})

    @bp.get("/health")
    async def health() -> Any:
        return jsonify(
            {
                "ok": True,
                "mode": current_app.config.get("CONFIG_SERVICE_MODE", "standalone"),
                "app_enable_dev_features": _app_enable_dev_features_enabled(),
                "read_only": bool(current_app.config.get("CONFIG_SERVICE_READ_ONLY", False)),
            }
        )

    @bp.get("/versions")
    async def versions() -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        config_type = request.args.get("config_type", "fluentbit")
        try:
            default_version = catalog_service.get_default_version(config_type=config_type)
        except ValueError:
            default_version = ""
        return jsonify(
            {
                "config_type": config_type,
                "versions": catalog_service.get_versions(config_type=config_type),
                "default": default_version,
                "supported_config_types": catalog_service.get_supported_config_types(),
            }
        )

    @bp.get("/catalog/<version>")
    async def catalog(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        config_type = request.args.get("config_type")
        try:
            payload = catalog_service.get_catalog(version, config_type=config_type)
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND
        return jsonify(payload)

    @bp.get("/service-options/<version>")
    async def service_options(version: str) -> Any:
        service_definition_service = current_app.extensions["service_definition_service"]
        config_type = request.args.get("config_type")
        try:
            payload = service_definition_service.get_definition(version, config_type=config_type)
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND
        return jsonify(payload)

    @bp.get("/parser-options/<version>")
    async def parser_options(version: str) -> Any:
        parser_definition_service = current_app.extensions["parser_definition_service"]
        config_type = request.args.get("config_type", "fluentbit")
        try:
            payload = parser_definition_service.get_definition(version, config_type=config_type)
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND
        return jsonify(payload)

    @bp.get("/issue-codes")
    async def issue_codes() -> Any:
        issue_code_service = current_app.extensions["issue_code_service"]
        return jsonify(issue_code_service.get_all())

    @bp.post("/catalog/<version>/validate")
    async def validate_catalog(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        try:
            result = catalog_service.validate_catalog_for_version(version)
        except (KeyError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.BAD_REQUEST
        return jsonify(result)

    @bp.post("/schema/<version>")
    async def schema(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        schema_service = current_app.extensions["schema_service"]
        parser_definition_service = current_app.extensions["parser_definition_service"]
        body = await request.get_json(silent=True) or {}
        config_type = request.args.get("config_type")
        try:
            options = SchemaOptions.model_validate(body)
            catalog_payload = catalog_service.get_catalog(version, config_type=config_type)
        except ValidationError as exc:
            return jsonify({"ok": False, "error": exc.errors()}), HTTPStatus.BAD_REQUEST
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND
        parser_definition = None
        if str(config_type or "fluentbit").lower() == "fluentbit":
            parser_definition = parser_definition_service.get_definition(version, config_type="fluentbit")
        schema_payload = schema_service.compile_schema(
            catalog_payload,
            strict_mode=options.strict,
            parser_definition=parser_definition,
        )
        return jsonify({"ok": True, "schema": schema_payload})

    @bp.post("/validate/<version>")
    async def validate(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        parser_definition_service = current_app.extensions["parser_definition_service"]
        validation_service = current_app.extensions["validation_service"]
        body = await request.get_json(silent=True) or {}
        config_type = request.args.get("config_type")
        try:
            req = ValidateRequest.model_validate(body)
            catalog_payload = catalog_service.get_catalog(version, config_type=config_type)
        except ValidationError as exc:
            return jsonify({"ok": False, "errors": _normalize_pydantic_issues(exc.errors())}), HTTPStatus.BAD_REQUEST
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND

        parser_definition = None
        if str(config_type or "fluentbit").lower() == "fluentbit":
            parser_definition = parser_definition_service.get_definition(version, config_type="fluentbit")
        result = validation_service.validate(
            version=version,
            payload=req.model_dump(),
            catalog=catalog_payload,
            profile=req.profile,
            parser_definition=parser_definition,
        )
        return jsonify(result), HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST

    @bp.post("/render/yaml/<version>")
    async def render_yaml(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        yaml_render_service = current_app.extensions["yaml_render_service"]
        body = await request.get_json(silent=True) or {}
        config_type = request.args.get("config_type", "fluentbit")
        try:
            req = RenderYamlRequest.model_validate(body)
            catalog_service.get_catalog(version, config_type=config_type)
        except ValidationError as exc:
            return jsonify({"ok": False, "error": exc.errors()}), HTTPStatus.BAD_REQUEST
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND

        yaml_text = yaml_render_service.render(
            payload=req.model_dump(), include_comments=req.include_comments
        )
        return jsonify({"ok": True, "yaml": yaml_text})

    @bp.post("/parse/fluentd/<version>")
    async def parse_fluentd(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        fluentd_config_service = current_app.extensions["fluentd_config_service"]
        body = await request.get_json(silent=True) or {}
        try:
            req = ParseTextRequest.model_validate(body)
            catalog_service.get_catalog(version, config_type="fluentd")
        except ValidationError as exc:
            return jsonify({"ok": False, "errors": _normalize_pydantic_issues(exc.errors())}), HTTPStatus.BAD_REQUEST
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND
        if not req.text.strip():
            return jsonify(
                {
                    "ok": False,
                    "errors": [
                        {
                            "order": 1,
                            "code": "empty_input_file",
                            "path": "$",
                            "message": "The configuration file is empty.",
                            "severity": "error",
                            "source": "parser",
                        }
                    ],
                }
            ), HTTPStatus.BAD_REQUEST
        try:
            config_payload = fluentd_config_service.parse(req.text)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [{"order": 1, "code": "fluentd_parse_error", "path": "$", "message": str(exc), "severity": "error", "source": "parser"}]}), HTTPStatus.BAD_REQUEST
        return jsonify({"ok": True, "config": config_payload})

    @bp.post("/parse/fluentbit/<version>")
    async def parse_fluentbit(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        fluentbit_yaml_config_service = current_app.extensions["fluentbit_yaml_config_service"]
        body = await request.get_json(silent=True) or {}
        try:
            req = ParseTextRequest.model_validate(body)
            catalog_service.get_catalog(version, config_type="fluentbit")
        except ValidationError as exc:
            return jsonify({"ok": False, "errors": _normalize_pydantic_issues(exc.errors())}), HTTPStatus.BAD_REQUEST
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND

        try:
            result = fluentbit_yaml_config_service.parse(req.text)
        except ValueError as exc:
            message = str(exc)
            code = "empty_input_file" if "empty" in message.lower() else "fluentbit_yaml_parse_error"
            return (
                jsonify(
                    {
                        "ok": False,
                        "errors": [
                            {
                                "order": 1,
                                "code": code,
                                "path": "$",
                                "message": message,
                                "severity": "error",
                                "source": "parser",
                            }
                        ],
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )
        return jsonify(result)

    @bp.post("/render/fluentd/<version>")
    async def render_fluentd(version: str) -> Any:
        catalog_service = current_app.extensions["catalog_service"]
        fluentd_config_service = current_app.extensions["fluentd_config_service"]
        body = await request.get_json(silent=True) or {}
        try:
            req = RenderTextRequest.model_validate(body)
            catalog_service.get_catalog(version, config_type="fluentd")
        except ValidationError as exc:
            return jsonify({"ok": False, "errors": _normalize_pydantic_issues(exc.errors())}), HTTPStatus.BAD_REQUEST
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), HTTPStatus.NOT_FOUND
        rendered = fluentd_config_service.render(req.config)
        return jsonify({"ok": True, "text": rendered})

    return bp
