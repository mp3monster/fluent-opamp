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
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config_service.app import create_app
from config_service.runtime_config import (
    ENV_CONFIG_TOOL_CONFIG_PATH,
    resolve_log_level_name,
    resolve_read_only,
    resolve_ui_base_css_path,
    resolve_ui_collapsed_sections,
    resolve_validation_agent_entries,
    resolve_web_port,
)


def test_resolve_web_port_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "opamp.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": {"webui_port": 8123},
                "config_service": {"web_port": 8124},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPAMP_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("CONFIG_SERVICE_WEB_PORT", raising=False)
    assert resolve_web_port() == 8124

    monkeypatch.setenv("CONFIG_SERVICE_WEB_PORT", "8125")
    assert resolve_web_port() == 8125

def test_resolve_ui_base_css_path_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "opamp.json"
    config_path.write_text(
        json.dumps(
            {
                "config_service": {"ui_base_css_path": "/ui/assets/base.css"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPAMP_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("CONFIG_SERVICE_UI_BASE_CSS_PATH", raising=False)
    assert resolve_ui_base_css_path() == "/ui/assets/base.css"

    monkeypatch.setenv("CONFIG_SERVICE_UI_BASE_CSS_PATH", "/env/base.css")
    assert resolve_ui_base_css_path() == "/env/base.css"

def test_resolve_read_only_from_config_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {"read_only": True},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    assert resolve_read_only() is True

def test_resolve_log_level_name_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {"log_level": "warning"},
                "provider": {"log_level": "error"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    monkeypatch.delenv("CONFIG_TOOL_LOG_LEVEL", raising=False)
    assert resolve_log_level_name() == "WARNING"

    monkeypatch.setenv("CONFIG_TOOL_LOG_LEVEL", "debug")
    assert resolve_log_level_name() == "DEBUG"

def test_resolve_ui_collapsed_sections_from_config_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {"ui_collapsed_sections": ["service", "parsers"]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    assert resolve_ui_collapsed_sections() == ["service", "parsers"]

def test_resolve_ui_collapsed_sections_defaults_to_empty_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {"read_only": False},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    assert resolve_ui_collapsed_sections() == []

def test_resolve_validation_agent_entries_from_config_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {
                    "agent_validation": {
                        "entries": [
                            {
                                "agent_type": "fluentbit",
                                "agent_version": "5.0.4",
                                "command_path": "fluent-bit",
                                "command_args": ["--dry-run", "-c", "{config_path}"],
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    entries = resolve_validation_agent_entries()
    assert len(entries) == 1
    assert entries[0]["agent_type"] == "fluentbit"
    assert entries[0]["agent_version"] == "5.0.4"


def test_resolve_validation_agent_entries_defaults_to_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {"read_only": False},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    assert resolve_validation_agent_entries() == []

def test_create_app_applies_resolved_log_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config-service.json"
    config_path.write_text(
        json.dumps(
            {
                "config-tool": {"log_level": "debug"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_CONFIG_TOOL_CONFIG_PATH, str(config_path))
    monkeypatch.delenv("CONFIG_TOOL_LOG_LEVEL", raising=False)

    app = create_app(mode="standalone")

    assert app.logger.level == logging.DEBUG
