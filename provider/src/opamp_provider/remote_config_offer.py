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

"""Provider helpers for building and validating queued AgentRemoteConfig offers."""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import yaml
from defusedxml import ElementTree as xml_etree

from opamp_provider.command_interface import (
    CommandObjectInterface,
    CommandParameterSchemaInterface,
)
from opamp_provider.proto import opamp_pb2

LOGGER = logging.getLogger(__name__)
TEXT_PLAIN_CONTENT_TYPE = "text/plain"
YAML_CONTENT_TYPE = "application/x-yaml"
XML_CONTENT_TYPE = "application/xml"
FLUENTBIT_CONFIG_TYPE = "fluentbit"
FLUENTD_CONFIG_TYPE = "fluentd"
CONFIG_EDITOR_VALIDATION_MODE = "config_editor"
BASIC_VALIDATION_MODE = "basic"
YAML_SUFFIXES = {".yaml", ".yml"}
XML_SUFFIXES = {".xml"}
JSON_SUFFIXES = {".json"}
FLUENTD_SUFFIXES = {".conf"}
JSON_CONTENT_TYPES = {"application/json", "text/json"}
YAML_CONTENT_TYPES = {
    "application/yaml",
    "application/x-yaml",
    "text/yaml",
    "text/x-yaml",
}
XML_CONTENT_TYPES = {"application/xml", "text/xml"}


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RemoteConfigValidationSettings:
    """Optional richer validation hints supplied by the UI/API caller."""

    config_type: str | None = None
    version: str | None = None
    profile: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> RemoteConfigValidationSettings:
        """Normalize optional validation settings from request payload data."""
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("validation must be an object when provided")
        config_type = str(payload.get("config_type", "")).strip().lower() or None
        version = str(payload.get("version", "")).strip() or None
        profile = str(payload.get("profile", "")).strip() or None
        return cls(config_type=config_type, version=version, profile=profile)


@dataclass(frozen=True)
class RemoteConfigSelectionSpec:
    """Ordered remote-config selection item returned from the catalog callback flow."""

    source_path: pathlib.Path
    target_name: str

    @property
    def filename(self) -> str:
        """Return the basename displayed in the provider selection list."""
        return self.source_path.name


@dataclass(frozen=True)
class RemoteConfigFileSpec:
    """Normalized remote-config file descriptor used during validation/build."""

    source_path: pathlib.Path
    target_name: str
    content_type: str
    body: bytes
    validation_kind: str

    @property
    def size_bytes(self) -> int:
        """Return the file-body length in bytes."""
        return len(self.body)


class RemoteConfigOfferCommand(CommandObjectInterface, CommandParameterSchemaInterface):
    """Concrete command-style helper that builds OpAMP `AgentRemoteConfig` offers."""

    def __init__(
        self,
        *,
        command_time: datetime | None = None,
        key_values: dict[str, str] | None = None,
    ) -> None:
        """Initialize default routing metadata and optional key/value context."""
        self._command_time = command_time or _utc_now()
        merged = self._default_key_values()
        if key_values:
            merged.update(key_values)
        self._key_values = merged

    def _default_key_values(self) -> dict[str, str]:
        """Return default metadata describing this remote-config offer."""
        return {
            "classifier": "remote_config",
            "action": "apply_config",
        }

    def get_command_classifier(self) -> str:
        """Return provider routing classifier metadata."""
        return "remote_config"

    def get_command_time(self) -> datetime:
        """Return command creation time."""
        return self._command_time

    def get_command_description(self) -> str:
        """Return a human-readable command description."""
        return "Queue AgentRemoteConfig offer"

    def getdisplayname(self) -> str:
        """Return a UI-friendly command display name."""
        return "Remote Config Offer"

    def set_key_value_dictionary(self, key_values: dict[str, str]) -> None:
        """Replace metadata values while preserving defaults."""
        merged = self._default_key_values()
        merged.update(key_values)
        self._key_values = merged

    def get_key_value_dictionary(self) -> dict[str, str]:
        """Return a copy of stored metadata values."""
        return dict(self._key_values)

    def get_capability_fqdn(self) -> str | None:
        """Return no custom capability because this is not a custom command."""
        return None

    def isOpAMPStandard(self) -> bool:
        """Return whether this is an OpAMP-standard command."""
        return False

    def get_user_parameter_schema(self) -> list[dict[str, str | bool]]:
        """Return minimal parameter metadata for API/UI discovery."""
        return [
            {
                "parametername": "files",
                "type": "array",
                "description": "List of source config files to include in the remote offer.",
                "isrequired": True,
            },
            {
                "parametername": "validation",
                "type": "object",
                "description": "Optional config-editor validation hints.",
                "isrequired": False,
            },
        ]

    def build_remote_config(
        self,
        file_specs: list[RemoteConfigFileSpec],
        *,
        include_hash: bool,
    ) -> opamp_pb2.AgentRemoteConfig:
        """Build an `AgentRemoteConfig` payload from normalized file specs."""
        remote_config = opamp_pb2.AgentRemoteConfig()
        for file_spec in file_specs:
            config_file = remote_config.config.config_map[file_spec.target_name]
            config_file.body = file_spec.body
            config_file.content_type = file_spec.content_type
        if include_hash:
            remote_config.config_hash = self.calculate_config_hash(remote_config.config)
        return remote_config

    @staticmethod
    def calculate_config_hash(config: opamp_pb2.AgentConfigMap) -> bytes:
        """Return a SHA-256 digest for deterministic config-map bytes."""
        serialized = config.SerializeToString(deterministic=True)
        return hashlib.sha256(serialized).digest()


def normalize_ui_remote_config_file_specs(files_payload: object) -> list[RemoteConfigFileSpec]:
    """Normalize UI/API file descriptors into concrete remote-config file specs."""
    selection_specs = normalize_ui_remote_config_selection_specs(files_payload)
    file_specs: list[RemoteConfigFileSpec] = []
    for index, selection_spec in enumerate(selection_specs):
        item = files_payload[index]
        source_path = selection_spec.source_path
        target_name = selection_spec.target_name
        explicit_content_type = _extract_explicit_content_type(item)
        file_specs.append(
            RemoteConfigFileSpec(
                source_path=source_path,
                target_name=target_name,
                content_type=_resolve_ui_remote_config_content_type(
                    source_path=source_path,
                    explicit_content_type=explicit_content_type,
                ),
                body=source_path.read_bytes(),
                validation_kind=_detect_validation_kind(
                    source_path=source_path,
                    explicit_content_type=explicit_content_type,
                ),
            )
        )
    return file_specs


def normalize_ui_remote_config_selection_specs(
    files_payload: object,
) -> list[RemoteConfigSelectionSpec]:
    """Normalize UI/API file descriptors into ordered callback-safe selection items."""
    if not isinstance(files_payload, list) or not files_payload:
        raise ValueError("files must be a non-empty list")

    selection_specs: list[RemoteConfigSelectionSpec] = []
    seen_target_names: set[str] = set()
    for item in files_payload:
        source_path, target_name, _ = _normalize_file_item(item)
        resolved_source_path = source_path.resolve()
        if not resolved_source_path.is_file():
            raise ValueError(f"source file does not exist: {source_path}")
        lowered_target_name = target_name.casefold()
        if lowered_target_name in seen_target_names:
            raise ValueError(
                f"duplicate remote config target name is not allowed: {target_name}"
            )
        seen_target_names.add(lowered_target_name)
        selection_specs.append(
            RemoteConfigSelectionSpec(
                source_path=resolved_source_path,
                target_name=target_name,
            )
        )
    return selection_specs


def validate_ui_remote_config_files(
    file_specs: list[RemoteConfigFileSpec],
    *,
    app_extensions: Mapping[str, Any],
    validation_payload: object = None,
) -> list[dict[str, str]]:
    """Validate all files before they are queued into one remote-config payload."""
    settings = RemoteConfigValidationSettings.from_payload(validation_payload)
    results: list[dict[str, str]] = []
    for file_spec in file_specs:
        validation_mode = _validate_one_file(
            file_spec=file_spec,
            app_extensions=app_extensions,
            settings=settings,
        )
        results.append(
            {
                "target_name": file_spec.target_name,
                "validation_mode": validation_mode,
            }
        )
    return results


def config_editor_validation_available(app_extensions: Mapping[str, Any]) -> bool:
    """Return whether embedded config-service validation helpers are mounted."""
    return "validation_service" in app_extensions and "catalog_service" in app_extensions


def _normalize_file_item(
    item: object,
) -> tuple[pathlib.Path, str, str | None]:
    """Normalize one incoming file descriptor into path/name/type primitives."""
    if isinstance(item, str):
        source_path = pathlib.Path(item).expanduser()
        target_name = source_path.name
        explicit_content_type = None
    elif isinstance(item, dict):
        raw_source_path = item.get("source_path") or item.get("path")
        if not raw_source_path:
            raise ValueError("each file item requires source_path")
        source_path = pathlib.Path(str(raw_source_path)).expanduser()
        target_name = str(
            item.get("target_name")
            or item.get("target_path")
            or item.get("filename")
            or source_path.name
        ).strip()
        explicit_content_type = str(item.get("content_type", "")).strip() or None
    else:
        raise ValueError("each file item must be a string path or object")

    if not target_name:
        raise ValueError("target file name cannot be blank")
    return source_path, target_name, explicit_content_type


def _extract_explicit_content_type(item: object) -> str | None:
    """Return one explicit content type from an incoming UI/API file descriptor."""
    if not isinstance(item, dict):
        return None
    return str(item.get("content_type", "")).strip() or None


def _resolve_ui_remote_config_content_type(
    *,
    source_path: pathlib.Path,
    explicit_content_type: str | None,
) -> str:
    """Return the UI-facing content type policy for one remote-config file."""
    if explicit_content_type:
        return explicit_content_type
    suffix = source_path.suffix.lower()
    if suffix in YAML_SUFFIXES:
        return YAML_CONTENT_TYPE
    if suffix in XML_SUFFIXES:
        return XML_CONTENT_TYPE
    return TEXT_PLAIN_CONTENT_TYPE


def _detect_validation_kind(
    *,
    source_path: pathlib.Path,
    explicit_content_type: str | None,
) -> str:
    """Infer which validation routine should be used for one file."""
    normalized_content_type = str(explicit_content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type in JSON_CONTENT_TYPES:
        return "json"
    if normalized_content_type in YAML_CONTENT_TYPES:
        return "yaml"
    if normalized_content_type in XML_CONTENT_TYPES:
        return "xml"
    suffix = source_path.suffix.lower()
    if suffix in JSON_SUFFIXES:
        return "json"
    if suffix in YAML_SUFFIXES:
        return "yaml"
    if suffix in XML_SUFFIXES:
        return "xml"
    return "text"


def _validate_one_file(
    *,
    file_spec: RemoteConfigFileSpec,
    app_extensions: Mapping[str, Any],
    settings: RemoteConfigValidationSettings,
) -> str:
    """Validate one file using config-service when possible, otherwise basic parsing."""
    body_text = _decode_utf8_text(file_spec=file_spec)
    editor_config_type = _infer_editor_config_type(file_spec=file_spec, settings=settings)
    if editor_config_type and config_editor_validation_available(app_extensions):
        _validate_with_config_editor(
            file_spec=file_spec,
            body_text=body_text,
            app_extensions=app_extensions,
            settings=settings,
            config_type=editor_config_type,
        )
        return CONFIG_EDITOR_VALIDATION_MODE
    _validate_with_basic_parser(
        file_spec=file_spec,
        body_text=body_text,
    )
    return BASIC_VALIDATION_MODE


def _decode_utf8_text(*, file_spec: RemoteConfigFileSpec) -> str:
    """Decode a queued file as UTF-8 text, rejecting binary/invalid data."""
    try:
        return file_spec.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"remote config file '{file_spec.target_name}' is not valid UTF-8 text"
        ) from exc


def _infer_editor_config_type(
    *,
    file_spec: RemoteConfigFileSpec,
    settings: RemoteConfigValidationSettings,
) -> str | None:
    """Infer the config-service config type for the provided file when possible."""
    if settings.config_type:
        return settings.config_type
    suffix = file_spec.source_path.suffix.lower()
    if suffix in FLUENTD_SUFFIXES:
        return FLUENTD_CONFIG_TYPE
    if file_spec.validation_kind in {"json", "yaml"}:
        return FLUENTBIT_CONFIG_TYPE
    return None


def _validate_with_config_editor(
    *,
    file_spec: RemoteConfigFileSpec,
    body_text: str,
    app_extensions: Mapping[str, Any],
    settings: RemoteConfigValidationSettings,
    config_type: str,
) -> None:
    """Run richer config-service validation for compatible config files."""
    version = _resolve_validation_version(
        config_type=config_type,
        app_extensions=app_extensions,
        requested_version=settings.version,
    )
    validation_payload = _build_editor_validation_payload(
        file_spec=file_spec,
        body_text=body_text,
        app_extensions=app_extensions,
        config_type=config_type,
    )
    catalog_service = app_extensions["catalog_service"]
    validation_service = app_extensions["validation_service"]
    catalog_payload = catalog_service.get_catalog(version, config_type=config_type)
    parser_definition = None
    if config_type == FLUENTBIT_CONFIG_TYPE and "parser_definition_service" in app_extensions:
        parser_definition = app_extensions["parser_definition_service"].get_definition(
            version,
            config_type=FLUENTBIT_CONFIG_TYPE,
        )
    result = validation_service.validate(
        version=version,
        payload=validation_payload,
        catalog=catalog_payload,
        profile=settings.profile,
        parser_definition=parser_definition,
    )
    if result.get("ok"):
        return
    raise ValueError(
        "config-editor validation failed for "
        f"'{file_spec.target_name}': {_summarize_issues(result.get('errors', []))}"
    )


def _resolve_validation_version(
    *,
    config_type: str,
    app_extensions: Mapping[str, Any],
    requested_version: str | None,
) -> str:
    """Resolve the config-service version to use for rich validation."""
    if requested_version:
        return requested_version
    catalog_service = app_extensions["catalog_service"]
    return str(catalog_service.get_default_version(config_type=config_type))


def _build_editor_validation_payload(
    *,
    file_spec: RemoteConfigFileSpec,
    body_text: str,
    app_extensions: Mapping[str, Any],
    config_type: str,
) -> dict[str, Any]:
    """Convert text config into the normalized payload expected by config-service."""
    if config_type == FLUENTD_CONFIG_TYPE:
        if "fluentd_config_service" not in app_extensions:
            raise ValueError("config editor is missing fluentd validation support")
        parsed_payload = app_extensions["fluentd_config_service"].parse(body_text)
        return _extract_parsed_config_payload(
            file_spec=file_spec,
            parsed_payload=parsed_payload,
        )

    if file_spec.validation_kind == "json":
        parsed_config = json.loads(body_text)
        if not isinstance(parsed_config, dict):
            raise ValueError(
                f"remote config file '{file_spec.target_name}' JSON root must be an object"
            )
        return {"config": parsed_config}

    if file_spec.validation_kind == "yaml":
        if "fluentbit_yaml_config_service" not in app_extensions:
            raise ValueError("config editor is missing fluentbit YAML validation support")
        parsed_payload = app_extensions["fluentbit_yaml_config_service"].parse(body_text)
        return _extract_parsed_config_payload(
            file_spec=file_spec,
            parsed_payload=parsed_payload,
        )

    raise ValueError(
        f"config-editor validation is not supported for '{file_spec.target_name}'"
    )


def _extract_parsed_config_payload(
    *,
    file_spec: RemoteConfigFileSpec,
    parsed_payload: object,
) -> dict[str, Any]:
    """Validate a parsed config-service payload and return its config section."""
    if not isinstance(parsed_payload, dict):
        raise ValueError(
            f"parsed config payload for '{file_spec.target_name}' was not an object"
        )
    issues = parsed_payload.get("errors", [])
    if _has_error_issue(issues):
        raise ValueError(
            "config parsing failed for "
            f"'{file_spec.target_name}': {_summarize_issues(issues)}"
        )
    config = parsed_payload.get("config")
    if not isinstance(config, dict):
        raise ValueError(
            f"parsed config payload for '{file_spec.target_name}' does not contain a config object"
        )
    return {"config": config}


def _has_error_issue(issues: object) -> bool:
    """Return whether an issue list contains any error-severity entry."""
    if not isinstance(issues, list):
        return False
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("severity", "error")).lower() == "error":
            return True
    return False


def _summarize_issues(issues: object) -> str:
    """Return a compact human-readable summary from structured issue payloads."""
    if not isinstance(issues, list) or not issues:
        return "unknown validation failure"
    messages: list[str] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        message = str(issue.get("message", "")).strip()
        if message:
            messages.append(message)
        if len(messages) == 3:
            break
    return "; ".join(messages) or "unknown validation failure"


def _validate_with_basic_parser(
    *,
    file_spec: RemoteConfigFileSpec,
    body_text: str,
) -> None:
    """Validate one file using the same lightweight parser approach as the client."""
    if file_spec.validation_kind == "json":
        try:
            json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"remote config file '{file_spec.target_name}' contains invalid JSON: {exc}"
            ) from exc
        return
    if file_spec.validation_kind == "xml":
        try:
            xml_etree.fromstring(body_text)
        except xml_etree.ParseError as exc:
            raise ValueError(
                f"remote config file '{file_spec.target_name}' contains invalid XML: {exc}"
            ) from exc
        return
    if file_spec.validation_kind == "yaml":
        try:
            yaml.safe_load(body_text)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"remote config file '{file_spec.target_name}' contains invalid YAML: {exc}"
            ) from exc
