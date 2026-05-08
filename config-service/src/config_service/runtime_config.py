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

import json
import os
import sys
from pathlib import Path
from typing import Any

ENV_CONFIG_TOOL_CONFIG_PATH = "CONFIG_TOOL_CONFIG_PATH"
ENV_OPAMP_CONFIG_PATH = "OPAMP_CONFIG_PATH"
ENV_CONFIG_SERVICE_WEB_PORT = "CONFIG_SERVICE_WEB_PORT"
ENV_CONFIG_SERVICE_UI_BASE_CSS_PATH = "CONFIG_SERVICE_UI_BASE_CSS_PATH"
ENV_CONFIG_TOOL_LOG_LEVEL = "CONFIG_TOOL_LOG_LEVEL"
CFG_CONFIG_TOOL = "config-tool"
CFG_CONFIG_TOOL_WEB_PORT = "web_port"
CFG_CONFIG_TOOL_UI_BASE_CSS_PATH = "ui_base_css_path"
CFG_CONFIG_TOOL_LOG_LEVEL = "log_level"
CFG_CONFIG_TOOL_UI_CSS_OVERRIDES = "ui_css_overrides"
CFG_CONFIG_TOOL_READ_ONLY = "read_only"
CFG_CONFIG_SERVICE = "config_service"
CFG_CONFIG_SERVICE_WEB_PORT = "web_port"
CFG_CONFIG_SERVICE_UI_BASE_CSS_PATH = "ui_base_css_path"
CFG_PROVIDER = "provider"
CFG_PROVIDER_LOG_LEVEL = "log_level"
CFG_PROVIDER_WEBUI_PORT = "webui_port"
DEFAULT_CONFIG_SERVICE_WEB_PORT = 8080
DEFAULT_CONFIG_SERVICE_UI_BASE_CSS_PATH = "/config-service/ui/assets/config_ui.css"
DEFAULT_CONFIG_TOOL_CONFIG_PATH = "config-service.json"
DEFAULT_CONFIG_TOOL_LOG_LEVEL = "INFO"


def _config_service_root() -> Path:
    module_dir = Path(__file__).resolve().parent
    source_root = module_dir.parents[1]
    if (source_root / "config").is_dir() and (source_root / "json-definitions").is_dir():
        return source_root
    for candidate in (module_dir, Path(sys.prefix) / "config_service"):
        if (candidate / "config").is_dir():
            return candidate
    return source_root


def _repo_root() -> Path:
    return _config_service_root().parent


def get_effective_config_path(config_path: str | None = None) -> Path:
    configured = str(config_path or "").strip()
    if configured:
        return Path(configured)

    configured = os.environ.get(ENV_CONFIG_TOOL_CONFIG_PATH, "").strip()
    if configured:
        return Path(configured)

    configured = os.environ.get(ENV_OPAMP_CONFIG_PATH, "").strip()
    if configured:
        return Path(configured)

    default_tool_path = _config_service_root() / "config" / DEFAULT_CONFIG_TOOL_CONFIG_PATH
    if default_tool_path.is_file():
        return default_tool_path

    return _repo_root() / "config" / "opamp.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _coerce_port(value: Any, default: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    return port if port > 0 else default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_web_port() -> int:
    env_value = os.environ.get(ENV_CONFIG_SERVICE_WEB_PORT, "").strip()
    if env_value:
        return _coerce_port(env_value, DEFAULT_CONFIG_SERVICE_WEB_PORT)

    raw = _load_json(get_effective_config_path())
    config_tool_raw = raw.get(CFG_CONFIG_TOOL, {})
    if isinstance(config_tool_raw, dict) and CFG_CONFIG_TOOL_WEB_PORT in config_tool_raw:
        return _coerce_port(
            config_tool_raw.get(CFG_CONFIG_TOOL_WEB_PORT),
            DEFAULT_CONFIG_SERVICE_WEB_PORT,
        )

    config_service_raw = raw.get(CFG_CONFIG_SERVICE, {})
    if isinstance(config_service_raw, dict) and CFG_CONFIG_SERVICE_WEB_PORT in config_service_raw:
        return _coerce_port(
            config_service_raw.get(CFG_CONFIG_SERVICE_WEB_PORT),
            DEFAULT_CONFIG_SERVICE_WEB_PORT,
        )

    provider_raw = raw.get(CFG_PROVIDER, {})
    if isinstance(provider_raw, dict):
        return _coerce_port(
            provider_raw.get(CFG_PROVIDER_WEBUI_PORT),
            DEFAULT_CONFIG_SERVICE_WEB_PORT,
        )

    return DEFAULT_CONFIG_SERVICE_WEB_PORT


def resolve_ui_base_css_path() -> str:
    env_value = os.environ.get(ENV_CONFIG_SERVICE_UI_BASE_CSS_PATH, "").strip()
    if env_value:
        return env_value

    raw = _load_json(get_effective_config_path())
    config_tool_raw = raw.get(CFG_CONFIG_TOOL, {})
    if isinstance(config_tool_raw, dict):
        configured = str(config_tool_raw.get(CFG_CONFIG_TOOL_UI_BASE_CSS_PATH, "")).strip()
        if configured:
            return configured

    config_service_raw = raw.get(CFG_CONFIG_SERVICE, {})
    if isinstance(config_service_raw, dict):
        configured = str(config_service_raw.get(CFG_CONFIG_SERVICE_UI_BASE_CSS_PATH, "")).strip()
        if configured:
            return configured

    return DEFAULT_CONFIG_SERVICE_UI_BASE_CSS_PATH


def resolve_ui_css_overrides() -> list[str]:
    raw = _load_json(get_effective_config_path())
    config_tool_raw = raw.get(CFG_CONFIG_TOOL, {})
    if isinstance(config_tool_raw, dict):
        configured = config_tool_raw.get(CFG_CONFIG_TOOL_UI_CSS_OVERRIDES, [])
        if isinstance(configured, str):
            return [value.strip() for value in configured.split(",") if value.strip()]
        if isinstance(configured, list):
            return [str(value).strip() for value in configured if str(value).strip()]
    return []


def resolve_read_only() -> bool:
    raw = _load_json(get_effective_config_path())
    config_tool_raw = raw.get(CFG_CONFIG_TOOL, {})
    if isinstance(config_tool_raw, dict):
        return _coerce_bool(config_tool_raw.get(CFG_CONFIG_TOOL_READ_ONLY), False)
    return False


def resolve_log_level_name() -> str:
    env_value = os.environ.get(ENV_CONFIG_TOOL_LOG_LEVEL, "").strip()
    if env_value:
        return str(env_value).strip().upper()

    raw = _load_json(get_effective_config_path())
    config_tool_raw = raw.get(CFG_CONFIG_TOOL, {})
    if isinstance(config_tool_raw, dict):
        configured = str(config_tool_raw.get(CFG_CONFIG_TOOL_LOG_LEVEL, "")).strip()
        if configured:
            return configured.upper()

    provider_raw = raw.get(CFG_PROVIDER, {})
    if isinstance(provider_raw, dict):
        configured = str(provider_raw.get(CFG_PROVIDER_LOG_LEVEL, "")).strip()
        if configured:
            return configured.upper()

    return DEFAULT_CONFIG_TOOL_LOG_LEVEL
