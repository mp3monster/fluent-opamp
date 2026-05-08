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

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from quart import Quart, Response, jsonify, request, send_from_directory

from config_service.auth_integration import evaluate_ui_http_auth
from config_service.routes.api import create_api_blueprint
from config_service.runtime_config import (
    ENV_CONFIG_TOOL_CONFIG_PATH,
    resolve_log_level_name,
    resolve_read_only,
    resolve_ui_base_css_path,
    resolve_ui_css_overrides,
    resolve_web_port,
)
from config_service.services.catalog_service import CatalogService
from config_service.services.fluentbit_yaml_config_service import FluentBitYamlConfigService
from config_service.services.fluentd_config_service import FluentdConfigService
from config_service.services.issue_code_service import IssueCodeService
from config_service.services.parser_definition_service import ParserDefinitionService
from config_service.services.rule_engine_service import RuleEngineService
from config_service.services.rules_registry_service import RulesRegistryService
from config_service.services.schema_service import SchemaService
from config_service.services.service_definition_service import ServiceDefinitionService
from config_service.services.validation_service import ValidationService
from config_service.services.yaml_render_service import YamlRenderService

CONFIG_SERVICE_UI_CSS_OVERRIDE_PATH_ENV = "CONFIG_SERVICE_UI_CSS_OVERRIDE_PATH"
CONFIG_SERVICE_UI_CSS_OVERRIDES_ENV = "CONFIG_SERVICE_UI_CSS_OVERRIDES"
CONFIG_SERVICE_UI_CSS_OVERRIDES_KEY = "CONFIG_SERVICE_UI_CSS_OVERRIDES"
_ENV_TRUE_VALUES = {"1", "true", "yes", "on"}


def _config_service_root() -> Path:
    module_dir = Path(__file__).resolve().parent
    source_root = module_dir.parents[1]
    if (source_root / "config").is_dir() and (source_root / "json-definitions").is_dir():
        return source_root
    for candidate in (module_dir, Path(sys.prefix) / "config_service"):
        if (candidate / "config").is_dir():
            return candidate
    return source_root


def _resolve_css_overrides(app: Quart) -> list[str]:
    configured_runtime = resolve_ui_css_overrides()
    if configured_runtime:
        return configured_runtime

    configured = app.config.get(CONFIG_SERVICE_UI_CSS_OVERRIDES_KEY)
    if isinstance(configured, str):
        return [value.strip() for value in configured.split(",") if value.strip()]
    if isinstance(configured, (list, tuple)):
        return [str(value).strip() for value in configured if str(value).strip()]

    plural_env = os.environ.get(CONFIG_SERVICE_UI_CSS_OVERRIDES_ENV, "")
    if plural_env.strip():
        return [value.strip() for value in plural_env.split(",") if value.strip()]

    single_env = os.environ.get(CONFIG_SERVICE_UI_CSS_OVERRIDE_PATH_ENV, "").strip()
    if single_env:
        return [single_env]
    return []


def _app_enable_dev_features_enabled() -> bool:
    raw_value = os.environ.get("APP_ENABLE_DEV_FEATURES", "")
    normalized = str(raw_value or "").strip().lower()
    return normalized in _ENV_TRUE_VALUES


def _apply_no_cache_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _asset_suffix() -> str:
    if not _app_enable_dev_features_enabled():
        return ""
    return "?v=" + str(int(Path(__file__).stat().st_mtime_ns))


def _append_suffix(url: str, suffix: str) -> str:
    if not suffix:
        return url
    joiner = "&" if "?" in url else "?"
    return url + joiner + suffix.lstrip("?")


def _configure_logging() -> None:
    level_name = resolve_log_level_name()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def create_app(*, mode: str = "standalone") -> Quart:
    _configure_logging()
    app = Quart(__name__)
    app.config["CONFIG_SERVICE_MODE"] = mode
    app.config["CONFIG_SERVICE_READ_ONLY"] = resolve_read_only()
    app.logger.setLevel(getattr(logging, resolve_log_level_name(), logging.INFO))

    repo_root = _config_service_root()
    provider_src = repo_root.parent / "provider" / "src"
    if provider_src.exists() and str(provider_src) not in sys.path:
        sys.path.insert(0, str(provider_src))

    catalog_registry_path = repo_root / "config" / "catalog-registry.json"
    service_registry_path = repo_root / "config" / "service-registry.json"
    parser_registry_path = repo_root / "config" / "parser-registry.json"
    issue_codes_path = repo_root / "config" / "issue-code-messages.json"
    rules_registry_path = repo_root / "config" / "validation-rules-registry.json"

    catalog_service = CatalogService(catalog_registry_path)
    catalog_service.load_all_catalogs()
    service_definition_service = ServiceDefinitionService(service_registry_path)
    service_definition_service.load_all()
    parser_definition_service = ParserDefinitionService(parser_registry_path)
    parser_definition_service.load_all()
    issue_code_service = IssueCodeService(issue_codes_path)
    issue_code_service.load()

    rules_registry_service = RulesRegistryService(rules_registry_path)
    rule_engine_service = RuleEngineService(rules_registry_service)
    validation_service = ValidationService(rule_engine_service)

    app.extensions["catalog_service"] = catalog_service
    app.extensions["rules_registry_service"] = rules_registry_service
    app.extensions["rule_engine_service"] = rule_engine_service
    app.extensions["service_definition_service"] = service_definition_service
    app.extensions["parser_definition_service"] = parser_definition_service
    app.extensions["issue_code_service"] = issue_code_service
    app.extensions["schema_service"] = SchemaService()
    app.extensions["validation_service"] = validation_service
    app.extensions["yaml_render_service"] = YamlRenderService()
    app.extensions["fluentbit_yaml_config_service"] = FluentBitYamlConfigService()
    app.extensions["fluentd_config_service"] = FluentdConfigService()

    if mode == "standalone":
        @app.before_request
        async def enforce_ui_bearer_auth() -> tuple[object, int] | None:
            result = evaluate_ui_http_auth(
                path=request.path,
                method=request.method,
                authorization_header=request.headers.get("Authorization"),
                remote_addr=request.remote_addr,
            )
            if result.allowed:
                return None
            response = jsonify({"error": result.error})
            if result.www_authenticate:
                response.headers["WWW-Authenticate"] = result.www_authenticate
            return response, result.status_code

    html_dir = Path(__file__).resolve().with_name("html")

    @app.get("/config-service/ui")
    async def config_service_ui() -> Response:
        css_overrides = _resolve_css_overrides(app)
        base_css_path = resolve_ui_base_css_path()
        asset_suffix = _asset_suffix()
        html_template = (html_dir / "config_ui.html").read_text(encoding="utf-8")
        rendered = html_template.replace(
            "__CONFIG_SERVICE_UI_CSS_OVERRIDES__",
            json.dumps(css_overrides),
        )
        rendered = rendered.replace(
            "__CONFIG_SERVICE_UI_BASE_CSS_PATH__",
            _append_suffix(base_css_path, asset_suffix),
        )
        rendered = rendered.replace(
            "__CONFIG_SERVICE_UI_ASSET_SUFFIX__",
            asset_suffix,
        )
        response = Response(rendered, mimetype="text/html")
        if _app_enable_dev_features_enabled():
            return _apply_no_cache_headers(response)
        return response

    @app.get("/config-service/ui/docs/meta-comments")
    async def config_service_ui_meta_comments_help() -> Response:
        base_css_path = resolve_ui_base_css_path()
        asset_suffix = _asset_suffix()
        html_template = (html_dir / "meta_comments_help.html").read_text(encoding="utf-8")
        rendered = html_template.replace(
            "__CONFIG_SERVICE_UI_BASE_CSS_PATH__",
            _append_suffix(base_css_path, asset_suffix),
        )
        rendered = rendered.replace(
            "__CONFIG_SERVICE_UI_ASSET_SUFFIX__",
            asset_suffix,
        )
        response = Response(rendered, mimetype="text/html")
        if _app_enable_dev_features_enabled():
            return _apply_no_cache_headers(response)
        return response

    @app.get("/config-service/ui/docs/help")
    async def config_service_ui_help() -> Response:
        base_css_path = resolve_ui_base_css_path()
        asset_suffix = _asset_suffix()
        html_template = (html_dir / "config_ui_help.html").read_text(encoding="utf-8")
        rendered = html_template.replace(
            "__CONFIG_SERVICE_UI_BASE_CSS_PATH__",
            _append_suffix(base_css_path, asset_suffix),
        )
        rendered = rendered.replace(
            "__CONFIG_SERVICE_UI_ASSET_SUFFIX__",
            asset_suffix,
        )
        response = Response(rendered, mimetype="text/html")
        if _app_enable_dev_features_enabled():
            return _apply_no_cache_headers(response)
        return response

    @app.get("/config-service/ui/assets/<path:filename>")
    async def config_service_ui_assets(filename: str) -> Response:
        response = await send_from_directory(html_dir, filename)
        if _app_enable_dev_features_enabled():
            return _apply_no_cache_headers(response)
        return response

    app.register_blueprint(create_api_blueprint(), url_prefix="/config-service/api/v1")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Config Service standalone server")
    parser.add_argument("--config-path", type=str, help="Path to config-service JSON configuration file")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, help="Override listen port")
    args = parser.parse_args()

    if args.config_path:
        os.environ[ENV_CONFIG_TOOL_CONFIG_PATH] = args.config_path

    app = create_app(mode="standalone")
    app.run(host=args.host, port=args.port or resolve_web_port(), debug=True)


if __name__ == "__main__":
    main()
