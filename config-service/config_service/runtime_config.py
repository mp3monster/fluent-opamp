from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ENV_OPAMP_CONFIG_PATH = "OPAMP_CONFIG_PATH"
ENV_CONFIG_SERVICE_WEB_PORT = "CONFIG_SERVICE_WEB_PORT"
ENV_CONFIG_SERVICE_UI_BASE_CSS_PATH = "CONFIG_SERVICE_UI_BASE_CSS_PATH"
CFG_CONFIG_SERVICE = "config_service"
CFG_CONFIG_SERVICE_WEB_PORT = "web_port"
CFG_CONFIG_SERVICE_UI_BASE_CSS_PATH = "ui_base_css_path"
CFG_PROVIDER = "provider"
CFG_PROVIDER_WEBUI_PORT = "webui_port"
DEFAULT_CONFIG_SERVICE_WEB_PORT = 8080
DEFAULT_CONFIG_SERVICE_UI_BASE_CSS_PATH = "/config-service/ui/assets/config_ui.css"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_effective_config_path() -> Path:
    configured = os.environ.get(ENV_OPAMP_CONFIG_PATH, "").strip()
    if configured:
        return Path(configured)
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


def resolve_web_port() -> int:
    env_value = os.environ.get(ENV_CONFIG_SERVICE_WEB_PORT, "").strip()
    if env_value:
        return _coerce_port(env_value, DEFAULT_CONFIG_SERVICE_WEB_PORT)

    raw = _load_json(get_effective_config_path())
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
    config_service_raw = raw.get(CFG_CONFIG_SERVICE, {})
    if isinstance(config_service_raw, dict):
        configured = str(config_service_raw.get(CFG_CONFIG_SERVICE_UI_BASE_CSS_PATH, "")).strip()
        if configured:
            return configured

    return DEFAULT_CONFIG_SERVICE_UI_BASE_CSS_PATH
