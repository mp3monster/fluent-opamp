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
    resolve_web_port,
)

YAML_KEYWORD_LITERALS = {
    "null",
    "Null",
    "NULL",
    "~",
    "true",
    "True",
    "TRUE",
    "false",
    "False",
    "FALSE",
    "yes",
    "Yes",
    "YES",
    "no",
    "No",
    "NO",
    "on",
    "On",
    "ON",
    "off",
    "Off",
    "OFF",
    ".nan",
    ".NaN",
    ".NAN",
    ".inf",
    ".Inf",
    ".INF",
    "-.inf",
    "-.Inf",
    "-.INF",
}


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


@pytest.mark.asyncio
async def test_health_and_versions() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    health = await client.get("/config-service/api/v1/health")
    assert health.status_code == 200
    body = await health.get_json()
    assert body["ok"] is True
    assert body["read_only"] is False

    versions = await client.get("/config-service/api/v1/versions")
    assert versions.status_code == 200
    v_body = await versions.get_json()
    assert "versions" in v_body
    assert "5.0.4" in v_body["versions"]
    assert v_body["config_type"] == "fluentbit"

    fluentd_versions = await client.get("/config-service/api/v1/versions?config_type=fluentd")
    assert fluentd_versions.status_code == 200
    fluentd_body = await fluentd_versions.get_json()
    assert fluentd_body["config_type"] == "fluentd"
    assert "1.19" in fluentd_body["versions"]
    assert fluentd_body["default"] == "1.19"

    ui = await client.get("/config-service/ui")
    assert ui.status_code == 200
    ui_html = (await ui.get_data()).decode("utf-8")
    assert "/config-service/ui/assets/opamp_logo.png" in ui_html
    assert "/config-service/ui/assets/config_editor_icon.png" in ui_html
    assert "/config-service/ui/assets/config_ui_helpers.js" in ui_html
    assert "/config-service/ui/assets/config_ui_comments.js" in ui_html
    assert "/config-service/ui/assets/config_ui_plugins.js" in ui_html
    assert "/config-service/ui/assets/config_ui_sections.js" in ui_html
    assert "/config-service/ui/assets/config_ui_env.js" in ui_html
    assert "/config-service/ui/assets/config_ui.js" in ui_html
    assert 'id="validation-include-toggle"' in ui_html
    assert "Include loaded files" in ui_html
    assert 'id="env-panel"' in ui_html
    assert "Environment Variables" in ui_html
    assert 'id="metadata-env-panel"' in ui_html
    assert "Metadata as Environment Variables" in ui_html
    assert 'id="header-comments-input"' in ui_html

    logo = await client.get("/config-service/ui/assets/opamp_logo.png")
    assert logo.status_code == 200

    favicon = await client.get("/config-service/ui/assets/config_editor_icon.png")
    assert favicon.status_code == 200

    svc = await client.get("/config-service/api/v1/service-options/5.0.4")
    assert svc.status_code == 200
    svc_body = await svc.get_json()
    assert svc_body["section"] == "service"
    assert isinstance(svc_body["options"], list)
    daemon_option = next(item for item in svc_body["options"] if item["name"] == "daemon")
    assert daemon_option["data_type"] == "enum"
    assert daemon_option["called_enum_options"] == ["on", "off"]
    dns_mode_option = next(item for item in svc_body["options"] if item["name"] == "dns.mode")
    assert dns_mode_option["data_type"] == "enum"
    assert dns_mode_option["called_enum_options"] == ["UDP", "TCP"]
    dns_resolver_option = next(item for item in svc_body["options"] if item["name"] == "dns.resolver")
    assert dns_resolver_option["data_type"] == "enum"
    assert dns_resolver_option["called_enum_options"] == ["LEGACY", "ASYNC"]
    http_server_option = next(item for item in svc_body["options"] if item["name"] == "http_server")
    assert http_server_option["data_type"] == "enum"
    assert http_server_option["called_enum_options"] == ["on", "off"]
    hot_reload_option = next(item for item in svc_body["options"] if item["name"] == "hot_reload")
    assert hot_reload_option["data_type"] == "enum"
    assert hot_reload_option["called_enum_options"] == ["on", "off"]

    parser_options = await client.get("/config-service/api/v1/parser-options/5.0.4")
    assert parser_options.status_code == 200
    parser_body = await parser_options.get_json()
    assert parser_body["section"] == "parsers"
    assert "json" in parser_body["parser_formats"]
    assert "regex" in parser_body["parser_formats"]
    regex_fields = parser_body["parser_formats"]["regex"]["fields"]
    assert any(field["name"] == "regex" and field["required"] is True for field in regex_fields)
    assert "docker" in parser_body["builtin_parser_names"]

    catalog = await client.get("/config-service/api/v1/catalog/5.0.4")
    assert catalog.status_code == 200
    catalog_body = await catalog.get_json()
    assert "route" in catalog_body["common"]
    assert catalog_body["common"]["route"]["supported_sections"] == ["inputs"]
    s3_fields = catalog_body["plugins"]["outputs"]["s3"]["fields"]
    net_dns_mode = next(item for item in s3_fields if item["name"] == "net.dns.mode")
    assert net_dns_mode["data_type"] == "enum"
    assert net_dns_mode["called_enum_options"] == ["UDP", "TCP"]
    azure_kusto_fields = catalog_body["plugins"]["outputs"]["azure_kusto"]["fields"]
    net_dns_resolver = next(item for item in azure_kusto_fields if item["name"] == "net.dns.resolver")
    assert net_dns_resolver["data_type"] == "enum"
    assert net_dns_resolver["called_enum_options"] == ["LEGACY", "ASYNC"]

    issue_codes = await client.get("/config-service/api/v1/issue-codes")
    assert issue_codes.status_code == 200
    issue_body = await issue_codes.get_json()
    assert "codes" in issue_body
    assert "missing_required_field" in issue_body["codes"]
    assert "missing_match_selector" in issue_body["codes"]


def test_fluent_bit_catalogs_have_no_other_yaml_keyword_plugin_name_conflicts() -> None:
    base = Path(__file__).resolve().parents[1] / "json-definitions"
    conflicts: list[tuple[str, str, str]] = []
    for path in sorted(base.glob("fluent-bit-*-all-plugins-catalog.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        for section, plugins in body.get("plugins", {}).items():
            for plugin_name in plugins.keys():
                if plugin_name in YAML_KEYWORD_LITERALS:
                    conflicts.append((path.name, section, plugin_name))

    assert conflicts == [
        ("fluent-bit-3.2.10-all-plugins-catalog.json", "outputs", "null"),
        ("fluent-bit-4.2.4-all-plugins-catalog.json", "outputs", "null"),
        ("fluent-bit-5.0.4-all-plugins-catalog.json", "outputs", "null"),
    ]


def test_fluent_bit_catalogs_include_router_fields_for_all_plugins() -> None:
    base = Path(__file__).resolve().parents[1] / "json-definitions"
    missing: list[tuple[str, str, str, str]] = []
    for path in sorted(base.glob("fluent-bit-*-all-plugins-catalog.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        plugins = payload.get("plugins", {})

        for section, field_name in (("inputs", "tag"), ("filters", "match"), ("filters", "match_regex"), ("outputs", "match"), ("outputs", "match_regex")):
            section_plugins = plugins.get(section, {})
            if not isinstance(section_plugins, dict):
                continue
            for plugin_name, plugin_def in section_plugins.items():
                fields = plugin_def.get("fields", [])
                names = {field.get("name") for field in fields if isinstance(field, dict)}
                if field_name not in names:
                    missing.append((path.name, section, plugin_name, field_name))

    assert missing == []


def test_fluent_bit_older_catalogs_require_tag_for_inputs_except_forward() -> None:
    base = Path(__file__).resolve().parents[1] / "json-definitions"
    missing_required: list[tuple[str, str]] = []
    for version in ("3.2.10", "4.2.4"):
        path = base / f"fluent-bit-{version}-all-plugins-catalog.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        inputs = payload.get("plugins", {}).get("inputs", {})
        for plugin_name, plugin_def in inputs.items():
            if plugin_name == "forward":
                continue
            fields = [field for field in plugin_def.get("fields", []) if isinstance(field, dict)]
            tag_field = next((field for field in fields if field.get("name") == "tag"), None)
            if not isinstance(tag_field, dict) or tag_field.get("required") is not True:
                missing_required.append((version, plugin_name))

    assert missing_required == []


def test_fluentd_catalogs_expose_match_directive_argument_for_filters_and_outputs() -> None:
    base = Path(__file__).resolve().parents[1] / "json-definitions"
    mismatches: list[tuple[str, str, str, str]] = []
    for path in sorted(base.glob("fluentd-*-all-plugins-catalog.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        plugins = payload.get("plugins", {})
        for section in ("filters", "outputs"):
            section_plugins = plugins.get(section, {})
            if not isinstance(section_plugins, dict):
                continue
            for plugin_name, plugin_def in section_plugins.items():
                directive_argument = plugin_def.get("directive_argument")
                argument_name = ""
                if isinstance(directive_argument, dict):
                    argument_name = str(directive_argument.get("name") or "")
                if argument_name != "match":
                    mismatches.append((path.name, section, plugin_name, argument_name))

    assert mismatches == []


@pytest.mark.asyncio
async def test_client_error_endpoint_logs_ui_errors(capsys: pytest.CaptureFixture[str]) -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    response = await client.post(
        "/config-service/api/v1/client-errors",
        json={
            "kind": "window_error",
            "message": "Render button handler exploded",
            "source": "config_ui.js",
            "path": "http://localhost:8080/config-service/ui",
            "stack": "Error: Render button handler exploded\n    at onClick (config_ui.js:10:2)",
            "line": 10,
            "column": 2,
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True

    captured = capsys.readouterr()
    assert "UI ERROR" in captured.err
    assert "Render button handler exploded" in captured.err


@pytest.mark.asyncio
async def test_ui_css_override_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_SERVICE_UI_CSS_OVERRIDE_PATH", "/ui/assets/web_ui.css")
    monkeypatch.setenv("CONFIG_SERVICE_UI_BASE_CSS_PATH", "/ui/assets/base.css")
    app = create_app(mode="standalone")
    client = app.test_client()
    ui = await client.get("/config-service/ui")
    assert ui.status_code == 200
    html = (await ui.get_data()).decode("utf-8")
    assert 'href="/ui/assets/base.css"' in html
    assert "/ui/assets/web_ui.css" in html


@pytest.mark.asyncio
async def test_config_service_help_page_served() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()
    response = await client.get("/config-service/ui/docs/help")
    assert response.status_code == 200
    html = (await response.get_data()).decode("utf-8")
    assert "Config Service Help" in html
    assert "Main Building Blocks" in html
    assert "Icon Buttons" in html
    assert "Color Use" in html
    assert "Route" in html
    assert "Processors" in html


@pytest.mark.asyncio
async def test_metadata_env_help_page_served() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()
    response = await client.get("/config-service/ui/docs/metadata-env")
    assert response.status_code == 200
    html = (await response.get_data()).decode("utf-8")
    assert "Metadata as Environment Variables" in html
    assert "Preset Metadata Options" in html
    assert 'id="header-comments"' in html


@pytest.mark.asyncio
async def test_top_level_help_link_is_rendered() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()
    response = await client.get("/config-service/ui")
    assert response.status_code == 200
    html = (await response.get_data()).decode("utf-8")
    assert 'href="/config-service/ui/docs/help"' in html
    assert 'aria-label="Open UI help in a new tab"' in html
    assert ">Help</a>" in html


@pytest.mark.asyncio
async def test_ui_routes_disable_cache_in_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENABLE_DEV_FEATURES", "1")
    app = create_app(mode="standalone")
    client = app.test_client()

    ui = await client.get("/config-service/ui")
    assert ui.status_code == 200
    assert ui.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    html = (await ui.get_data()).decode("utf-8")
    assert "/config-service/ui/assets/config_ui.css?v=" in html
    assert "/config-service/ui/assets/config_ui_plugins.js?v=" in html
    assert "/config-service/ui/assets/config_ui_sections.js?v=" in html
    assert "/config-service/ui/assets/config_ui_env.js?v=" in html
    assert "/config-service/ui/assets/config_ui.js?v=" in html

    asset = await client.get("/config-service/ui/assets/config_ui.js")
    assert asset.status_code == 200
    assert asset.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"


@pytest.mark.asyncio
async def test_render_yaml_includes_parsers_before_pipeline() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "service": {},
            "parsers": [
                {
                    "name": "custom_json",
                    "format": "json",
                    "time_key": "timestamp",
                }
            ],
            "pipeline": {
                "inputs": [],
                "filters": [],
                "outputs": [],
            },
        }
    }

    response = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert response.status_code == 200
    body = await response.get_json()
    rendered = body["yaml"]
    assert "parsers:" in rendered
    assert "pipeline:" not in rendered
    assert rendered.index("parsers:") < rendered.index("-\n    name: custom_json")


@pytest.mark.asyncio
async def test_validate_accepts_builtin_and_custom_parser_references() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "parsers": [
                {
                    "name": "app_json",
                    "format": "json",
                    "time_key": "timestamp",
                }
            ],
            "pipeline": {
                "inputs": [
                    {
                        "name": "tcp",
                        "chunk_size": 32,
                        "parser": "app_json",
                    },
                    {
                        "name": "tcp",
                        "chunk_size": 32,
                        "parser": "docker",
                    },
                ],
                "filters": [],
                "outputs": [{"name": "null"}],
            },
        },
        "profile": "strict",
    }

    response = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_render_yaml_translates_route_object_to_native_routes_block() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [
                    {
                        "name": "tail",
                        "path": "/var/log/app.log",
                        "tag": "app.logs",
                        "route": {
                            "per_record_routing": True,
                            "logs": [
                                {
                                    "name": "error_logs",
                                    "condition": {
                                        "op": "and",
                                        "rules": [
                                            {"context": "body", "field": "$level", "op": "eq", "value": "error"}
                                        ],
                                    },
                                    "to": {"outputs": ["error_destination"]},
                                }
                            ],
                        },
                    }
                ],
                "filters": [],
                "outputs": [
                    {"name": "stdout", "alias": "error_destination"}
                ],
            }
        }
    }

    response = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert response.status_code == 200
    body = await response.get_json()
    rendered = body["yaml"]
    assert "route:" not in rendered
    assert "routes:" in rendered
    assert "per_record_routing: true" in rendered
    assert "outputs:" in rendered
    assert "error_destination" in rendered


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_maps_native_routes_to_internal_route() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    yaml_text = """
pipeline:
  inputs:
    - name: tail
      path: /var/log/app.log
      tag: app.logs
      routes:
        logs:
          - name: error_logs
            condition:
              op: and
              rules:
                - field: "$level"
                  op: eq
                  value: error
            to:
              outputs:
                - error_destination
  outputs:
    - name: stdout
      alias: error_destination
""".strip()

    response = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": yaml_text},
    )
    assert response.status_code == 200
    body = await response.get_json()
    route = body["config"]["pipeline"]["inputs"][0]["route"]
    assert "logs" in route
    assert route["logs"][0]["name"] == "error_logs"
    assert route["logs"][0]["to"]["outputs"] == ["error_destination"]


@pytest.mark.asyncio
async def test_validate_route_output_reference_and_enablement() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [
                    {
                        "name": "tcp",
                        "chunk_size": 32,
                        "route": {
                            "per_record_routing": False,
                            "logs": [
                                {
                                    "name": "error_logs",
                                    "condition": {
                                        "op": "and",
                                        "rules": [
                                            {"field": "$level", "op": "eq", "value": "error"}
                                        ],
                                    },
                                    "to": {"outputs": ["missing_destination"]},
                                }
                            ],
                        },
                    }
                ],
                "filters": [],
                "outputs": [{"name": "null", "alias": "known_destination"}],
            }
        },
        "profile": "strict",
    }

    response = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    codes = {issue["code"] for issue in body["errors"]}
    severities = {issue["code"]: issue["severity"] for issue in body["errors"]}
    assert "unknown_route_output_reference" in codes
    assert "route_not_enabled" in codes
    assert severities["unknown_route_output_reference"] == "warning"
    assert severities["route_not_enabled"] == "warning"


@pytest.mark.asyncio
async def test_validate_rejects_unknown_parser_reference_and_duplicate_parser_name() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "parsers": [
                {
                    "name": "dup_parser",
                    "format": "json",
                },
                {
                    "name": "dup_parser",
                    "format": "regex",
                    "regex": "^(?<msg>.*)$",
                },
            ],
            "pipeline": {
                "inputs": [
                    {
                        "name": "tcp",
                        "chunk_size": 32,
                        "parser": "missing_parser",
                    }
                ],
                "filters": [],
                "outputs": [{"name": "null"}],
            },
        },
        "profile": "strict",
    }

    response = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    codes = {issue["code"] for issue in body["errors"]}
    assert "duplicate_parser_name" in codes
    assert "unknown_parser_reference" in codes
    severities = {issue["severity"] for issue in body["errors"]}
    assert severities == {"warning"}


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_loads_parsers() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    yaml_text = """
parsers:
  - name: app_json
    format: json
    time_key: timestamp
pipeline:
  inputs:
    - name: tcp
      chunk_size: 32
      parser: app_json
  outputs:
    - name: null
""".strip()

    response = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": yaml_text},
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["config"]["parsers"][0]["name"] == "app_json"
    assert body["config"]["parsers"][0]["format"] == "json"
    assert body["config"]["pipeline"]["inputs"][0]["parser"] == "app_json"


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_recursively_loads_includes(tmp_path: Path) -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    grandchild = tmp_path / "grandchild.yaml"
    grandchild.write_text(
        """
parsers:
  - name: app_json
    format: json
""".strip(),
        encoding="utf-8",
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        """
includes:
  - grandchild.yaml
pipeline:
  outputs:
    - name: null
""".strip(),
        encoding="utf-8",
    )
    root = tmp_path / "root.yaml"
    root.write_text(
        """
includes:
  - child.yaml
pipeline:
  inputs:
    - name: tcp
      chunk_size: 32
      parser: app_json
""".strip(),
        encoding="utf-8",
    )

    response = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={
            "text": root.read_text(encoding="utf-8"),
            "source_path": str(root),
            "resolve_includes": True,
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["config"]["includes"] == ["child.yaml"]
    assert len(body["included_documents"]) == 1
    child_doc = body["included_documents"][0]
    assert child_doc["resolved_path"].endswith("child.yaml")
    assert child_doc["config"]["pipeline"]["outputs"][0]["name"] == "null"
    assert len(child_doc["included_documents"]) == 1
    grandchild_doc = child_doc["included_documents"][0]
    assert grandchild_doc["resolved_path"].endswith("grandchild.yaml")
    assert grandchild_doc["config"]["parsers"][0]["name"] == "app_json"


@pytest.mark.asyncio
async def test_validate_can_merge_recursive_includes_without_mutation(tmp_path: Path) -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    grandchild = tmp_path / "grandchild.yaml"
    grandchild.write_text(
        """
parsers:
  - name: app_json
    format: json
""".strip(),
        encoding="utf-8",
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        """
includes:
  - grandchild.yaml
pipeline:
  outputs:
    - name: null
""".strip(),
        encoding="utf-8",
    )
    root = tmp_path / "root.yaml"
    root.write_text(
        """
includes:
  - child.yaml
pipeline:
  inputs:
    - name: tcp
      chunk_size: 32
      parser: app_json
""".strip(),
        encoding="utf-8",
    )

    parse_response = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={
            "text": root.read_text(encoding="utf-8"),
            "source_path": str(root),
            "resolve_includes": True,
        },
    )
    assert parse_response.status_code == 200
    parse_body = await parse_response.get_json()
    root_config = parse_body["config"]
    included_documents = parse_body["included_documents"]
    root_before = json.loads(json.dumps(root_config))
    includes_before = json.loads(json.dumps(included_documents))

    plain_validate = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json={"config": root_config, "included_documents": included_documents},
    )
    assert plain_validate.status_code == 200
    plain_body = await plain_validate.get_json()
    assert any(item["code"] == "unknown_parser_reference" for item in plain_body["errors"])

    merged_validate = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json={
            "config": root_config,
            "included_documents": included_documents,
            "merge_includes_for_validation": True,
        },
    )
    assert merged_validate.status_code == 200
    merged_body = await merged_validate.get_json()
    assert not any(item["code"] == "unknown_parser_reference" for item in merged_body["errors"])

    assert root_config == root_before
    assert included_documents == includes_before


@pytest.mark.asyncio
async def test_render_can_include_rendered_include_files_without_mutation() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    root_config = {
        "service": {},
        "parsers": [],
        "pipeline": {
            "inputs": [{"name": "tcp", "chunk_size": 32}],
            "filters": [],
            "outputs": [],
        },
        "labels": [],
        "workers": [],
        "includes": ["child.yaml"],
    }
    included_documents = [
        {
            "include_path": "child.yaml",
            "resolved_path": "/tmp/child.yaml",
            "ok": True,
            "errors": [],
            "config": {
                "service": {},
                "parsers": [
                    {
                        "name": "app_json",
                        "format": "json",
                    }
                ],
                "pipeline": {
                    "inputs": [],
                    "filters": [],
                    "outputs": [{"name": "null"}],
                },
                "labels": [],
                "workers": [],
                "includes": [],
            },
            "included_documents": [],
        }
    ]
    root_before = json.loads(json.dumps(root_config))
    includes_before = json.loads(json.dumps(included_documents))

    response = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json={
            "config": root_config,
            "included_documents": included_documents,
            "render_included_files": True,
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert len(body["included_files"]) == 1
    include_render = body["included_files"][0]
    assert include_render["include_path"] == "child.yaml"
    assert "parsers:" in include_render["yaml"]
    assert "name: null" in include_render["yaml"]

    assert root_config == root_before
    assert included_documents == includes_before


def test_include_document_service_does_not_mutate_inputs() -> None:
    app = create_app(mode="standalone")
    include_document_service = app.extensions["include_document_service"]
    yaml_render_service = app.extensions["yaml_render_service"]
    fluentd_config_service = app.extensions["fluentd_config_service"]

    root_config = {
        "service": {},
        "parsers": [],
        "pipeline": {"inputs": [{"name": "tcp", "parser": "app_json"}], "filters": [], "outputs": []},
        "labels": [],
        "workers": [],
        "includes": ["child.yaml"],
    }
    included_documents = [
        {
            "include_path": "child.yaml",
            "resolved_path": "/tmp/child.yaml",
            "ok": True,
            "errors": [],
            "config": {
                "service": {},
                "parsers": [{"name": "app_json", "format": "json"}],
                "pipeline": {"inputs": [], "filters": [], "outputs": [{"name": "null"}]},
                "labels": [],
                "workers": [],
                "includes": [],
            },
            "included_documents": [],
        }
    ]
    root_before = json.loads(json.dumps(root_config))
    includes_before = json.loads(json.dumps(included_documents))

    merged = include_document_service.merge_for_validation(
        config=root_config,
        included_documents=included_documents,
    )
    rendered = include_document_service.render_included_documents(
        config_type="fluentbit",
        included_documents=included_documents,
        include_comments=False,
        yaml_render_service=yaml_render_service,
        fluentd_config_service=fluentd_config_service,
    )

    assert merged["parsers"][0]["name"] == "app_json"
    assert rendered[0]["include_path"] == "child.yaml"
    assert root_config == root_before
    assert included_documents == includes_before


@pytest.mark.asyncio
async def test_render_yaml_omits_empty_optional_sections() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "service": {},
            "pipeline": {
                "inputs": [{"name": "forward", "port": 24224}],
                "filters": [],
                "outputs": [{"name": "stdout"}],
            },
            "labels": [],
            "workers": [],
            "includes": [],
        }
    }

    yaml_resp = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert yaml_resp.status_code == 200
    yaml_body = await yaml_resp.get_json()
    assert yaml_body["ok"] is True
    assert "filters:" not in yaml_body["yaml"]
    assert "labels:" not in yaml_body["yaml"]
    assert "workers:" not in yaml_body["yaml"]
    assert "includes:" not in yaml_body["yaml"]
    assert "service:" not in yaml_body["yaml"]


@pytest.mark.asyncio
async def test_render_yaml_omits_empty_inputs_outputs_and_pipeline() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "service": {},
            "pipeline": {
                "inputs": [],
                "filters": [],
                "outputs": [],
            },
            "labels": [],
            "workers": [],
            "includes": [],
        }
    }

    yaml_resp = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert yaml_resp.status_code == 200
    yaml_body = await yaml_resp.get_json()
    assert yaml_body["ok"] is True
    assert "service:" not in yaml_body["yaml"]
    assert "pipeline:" not in yaml_body["yaml"]
    assert "inputs:" not in yaml_body["yaml"]
    assert "filters:" not in yaml_body["yaml"]
    assert "outputs:" not in yaml_body["yaml"]
    assert yaml_body["yaml"].strip() == ""


@pytest.mark.asyncio
async def test_fluentbit_processors_validate_and_render() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [
                    {
                        "name": "tail",
                        "path": "/var/log/example.log",
                        "processors": {
                            "logs": [
                                {
                                    "name": "content_modifier",
                                    "action": "upsert",
                                    "context": "body",
                                    "key": "environment",
                                    "value": "dev",
                                }
                            ]
                        },
                    }
                ],
                "filters": [],
                "outputs": [
                    {
                        "name": "stdout",
                        "match": "*",
                        "processors": {
                            "logs": [
                                {
                                    "name": "sql",
                                    "query": "SELECT * FROM STREAM;",
                                }
                            ]
                        },
                    }
                ],
            }
        }
    }

    validate_resp = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert validate_resp.status_code in (200, 400)
    validate_body = await validate_resp.get_json()
    assert "errors" in validate_body

    schema_resp = await client.post(
        "/config-service/api/v1/schema/5.0.4?config_type=fluentbit",
        json={"strict": True},
    )
    assert schema_resp.status_code == 200
    schema_body = await schema_resp.get_json()
    input_schema = schema_body["schema"]["properties"]["config"]["properties"]["pipeline"]["properties"]["inputs"]["items"]
    assert "oneOf" in input_schema

    yaml_resp = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json={**payload, "include_comments": False},
    )
    assert yaml_resp.status_code == 200
    yaml_body = await yaml_resp.get_json()
    assert "processors:" in yaml_body["yaml"]
    assert "content_modifier" in yaml_body["yaml"]


@pytest.mark.asyncio
async def test_validate_requires_match_or_match_regex_when_both_fields_exist() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [{"name": "dummy"}],
                "filters": [],
                "outputs": [{"name": "null"}],
            }
        }
    }

    resp = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert resp.status_code in (200, 400)
    body = await resp.get_json()
    assert "errors" in body
    selector_errors = [item for item in body["errors"] if item["code"] == "missing_match_selector"]
    assert selector_errors
    assert selector_errors[0]["path"] == "$.config.pipeline.outputs[0]"


@pytest.mark.asyncio
async def test_validate_accepts_match_or_match_regex_when_either_is_present() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [{"name": "dummy"}],
                "filters": [{"name": "grep", "regex": "message error", "match_regex": "^app\\."}],
                "outputs": [{"name": "null", "match": "*"}],
            }
        }
    }

    resp = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert resp.status_code in (200, 400)
    body = await resp.get_json()
    assert "errors" in body
    assert not [item for item in body["errors"] if item["code"] == "missing_match_selector"]


@pytest.mark.asyncio
async def test_lua_code_validation_returns_normalized_errors() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [{"name": "forward", "port": 24224}],
                "filters": [
                    {
                        "name": "lua",
                        "call": "cb_filter",
                        "code": "function cb_filter(tag, timestamp, record) return 0, timestamp, record",
                    }
                ],
                "outputs": [{"name": "stdout"}],
            }
        }
    }

    resp = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert resp.status_code in (200, 400)
    body = await resp.get_json()
    assert "errors" in body
    lua_errors = [item for item in body["errors"] if item["code"] == "lua_syntax_error"]
    assert lua_errors
    assert lua_errors[0]["path"] == "$.config.pipeline.filters[0].code"
    assert "Lua syntax error" in lua_errors[0]["message"]


@pytest.mark.asyncio
async def test_sql_code_validation_returns_normalized_errors() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [
                    {
                        "name": "dummy",
                        "dummy": '{"http.url": "https://fluentbit.io"}',
                        "processors": {
                            "logs": [
                                {
                                    "name": "sql",
                                    "query": "SELECT FROM STREAM;",
                                }
                            ]
                        },
                    }
                ],
                "filters": [],
                "outputs": [{"name": "stdout"}],
            }
        }
    }

    resp = await client.post(
        "/config-service/api/v1/validate/5.0.4?config_type=fluentbit",
        json=payload,
    )
    assert resp.status_code in (200, 400)
    body = await resp.get_json()
    assert "errors" in body
    sql_errors = [item for item in body["errors"] if item["code"] == "sql_syntax_error"]
    assert sql_errors
    assert sql_errors[0]["path"] == "$.config.pipeline.inputs[0].processors.logs[0].query"
    assert "SQL syntax error" in sql_errors[0]["message"]


@pytest.mark.asyncio
async def test_parse_and_render_fluentd_config() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    sample_conf = """
<system>
  log_level info
</system>

<source>
  @type tail
  tag app.logs
  path /var/log/app.log
  <parse>
    @type json
  </parse>
</source>

<filter app.**>
  @type grep
  <regexp>
    key message
    pattern error
  </regexp>
</filter>

<match app.**>
  @type copy
  <store>
    @type stdout
  </store>
</match>
""".strip()

    parsed_resp = await client.post(
        "/config-service/api/v1/parse/fluentd/1.19",
        json={"text": sample_conf},
    )
    assert parsed_resp.status_code == 200
    parsed_body = await parsed_resp.get_json()
    assert parsed_body["ok"] is True
    assert parsed_body["config"]["service"]["log_level"] == "info"
    assert parsed_body["config"]["pipeline"]["inputs"][0]["name"] == "tail"
    assert parsed_body["config"]["pipeline"]["filters"][0]["match"] == "app.**"
    assert parsed_body["config"]["pipeline"]["outputs"][0]["name"] == "copy"
    assert parsed_body["config"]["pipeline"]["outputs"][0]["match"] == "app.**"

    rendered_resp = await client.post(
        "/config-service/api/v1/render/fluentd/1.19",
        json={"config": parsed_body["config"]},
    )
    assert rendered_resp.status_code == 200
    rendered_body = await rendered_resp.get_json()
    assert rendered_body["ok"] is True
    assert "<source>" in rendered_body["text"]
    assert "<match app.**>" in rendered_body["text"]


@pytest.mark.asyncio
async def test_schema_endpoint_supports_fluentd() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post("/config-service/api/v1/schema/1.19?config_type=fluentd", json={"strict": True})
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["ok"] is True
    assert "labels" in body["schema"]["properties"]["config"]["properties"]
    filter_plugins = body["schema"]["properties"]["config"]["properties"]["pipeline"]["properties"]["filters"]["items"]["oneOf"]
    grep_schema = next(
        item
        for item in filter_plugins
        if item.get("properties", {}).get("name", {}).get("const") == "grep"
    )
    assert "match" in grep_schema["properties"]
    assert "allOf" in grep_schema


@pytest.mark.asyncio
async def test_validate_fluentd_accepts_match_and_legacy_directive_arg() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    base_config = {
        "service": {"log_level": "info"},
        "pipeline": {
            "inputs": [{"name": "tail", "tag": "app.logs", "path": "/var/log/app.log"}],
            "filters": [],
            "outputs": [{"name": "stdout"}],
        },
    }

    canonical = json.loads(json.dumps(base_config))
    canonical["pipeline"]["outputs"][0]["match"] = "app.**"
    canonical_resp = await client.post(
        "/config-service/api/v1/validate/1.19?config_type=fluentd",
        json={"config": canonical},
    )
    assert canonical_resp.status_code == 200
    canonical_body = await canonical_resp.get_json()
    assert canonical_body["ok"] is True

    legacy = json.loads(json.dumps(base_config))
    legacy["pipeline"]["outputs"][0]["directive_arg"] = "app.**"
    legacy_resp = await client.post(
        "/config-service/api/v1/validate/1.19?config_type=fluentd",
        json={"config": legacy},
    )
    assert legacy_resp.status_code == 200
    legacy_body = await legacy_resp.get_json()
    assert legacy_body["ok"] is True


@pytest.mark.asyncio
async def test_validate_request_errors_are_normalized() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post("/config-service/api/v1/validate/5.0.4", json={})
    assert resp.status_code == 400
    body = await resp.get_json()
    assert body["ok"] is False
    assert body["errors"][0]["order"] == 1
    assert body["errors"][0]["code"] == "pydantic_validation_error"


@pytest.mark.asyncio
async def test_catalog_and_service_endpoints_return_not_found_for_unknown_versions() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    catalog_resp = await client.get("/config-service/api/v1/catalog/9.9.9?config_type=fluentbit")
    assert catalog_resp.status_code == 404
    catalog_body = await catalog_resp.get_json()
    assert catalog_body["ok"] is False

    service_resp = await client.get("/config-service/api/v1/service-options/9.9.9?config_type=fluentbit")
    assert service_resp.status_code == 404
    service_body = await service_resp.get_json()
    assert service_body["ok"] is False


@pytest.mark.asyncio
async def test_service_options_accepts_config_type_aliases_and_unique_fallback() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    alias_resp = await client.get("/config-service/api/v1/service-options/5.0.4?config_type=fluent-bit")
    assert alias_resp.status_code == 200
    alias_body = await alias_resp.get_json()
    assert alias_body["engine"] == "fluentbit"
    assert isinstance(alias_body.get("options"), list)
    assert len(alias_body["options"]) > 0

    fallback_resp = await client.get("/config-service/api/v1/service-options/1.19?config_type=fluent-bit")
    assert fallback_resp.status_code == 200
    fallback_body = await fallback_resp.get_json()
    assert fallback_body["engine"] == "fluentd"
    assert isinstance(fallback_body.get("options"), list)
    assert len(fallback_body["options"]) > 0


@pytest.mark.asyncio
async def test_schema_endpoint_rejects_invalid_payload() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post("/config-service/api/v1/schema/5.0.4", json={"strict": "not-a-bool"})
    assert resp.status_code == 400
    body = await resp.get_json()
    assert body["ok"] is False
    assert isinstance(body["error"], list)


@pytest.mark.asyncio
async def test_parse_fluentd_returns_parser_errors_for_invalid_conf() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post(
        "/config-service/api/v1/parse/fluentd/1.19",
        json={"text": "<source>\n  @type tail\n"},
    )
    assert resp.status_code == 400
    body = await resp.get_json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == "fluentd_parse_error"
    assert body["errors"][0]["source"] == "parser"


@pytest.mark.asyncio
async def test_parse_fluentd_rejects_empty_file() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post(
        "/config-service/api/v1/parse/fluentd/1.19",
        json={"text": "   \n\t  "},
    )
    assert resp.status_code == 400
    body = await resp.get_json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == "empty_input_file"


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_loads_supported_sections_and_reports_ignored_ones() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    sample_yaml = """
service:
  flush_interval: 5
pipeline:
  inputs:
    - name: dummy
      tag: sample
  outputs:
    - name: stdout
  processors:
    - name: ignored
plugins:
  custom:
    - path: ./custom.so
""".strip()

    resp = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": sample_yaml},
    )
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["ok"] is False
    assert body["config"]["service"]["flush_interval"] == 5
    assert body["config"]["pipeline"]["inputs"][0]["name"] == "dummy"
    assert body["config"]["pipeline"]["outputs"][0]["name"] == "stdout"
    assert body["config"]["pipeline"]["filters"] == []

    codes = [item["code"] for item in body["errors"]]
    assert "fluentbit_yaml_ignored_section" in codes
    assert any(item["path"] == "$.pipeline.processors" for item in body["errors"])
    assert any(item["path"] == "$.plugins" for item in body["errors"])


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_preserves_null_plugin_name_and_string_enums() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    sample_yaml = """
service:
  daemon: on
  http_server: off
pipeline:
  outputs:
    - name: null
      match: '*'
""".strip()

    resp = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": sample_yaml},
    )
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["config"]["service"]["daemon"] == "on"
    assert body["config"]["service"]["http_server"] == "off"
    assert body["config"]["pipeline"]["outputs"][0]["name"] == "null"
    assert not body["errors"]


@pytest.mark.asyncio
async def test_parse_and_render_fluentbit_yaml_env_section_round_trips() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    sample_yaml = """
env:
  FLUSH_INTERVAL: 1
  STDOUT_FMT: json_lines
service:
  flush: ${FLUSH_INTERVAL}
pipeline:
  inputs:
    - name: random
  outputs:
    - name: stdout
      match: '*'
      format: ${STDOUT_FMT}
""".strip()

    parse_resp = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": sample_yaml},
    )
    assert parse_resp.status_code == 200
    parse_body = await parse_resp.get_json()
    assert parse_body["config"]["env"]["FLUSH_INTERVAL"] == 1
    assert parse_body["config"]["env"]["STDOUT_FMT"] == "json_lines"
    assert parse_body["config"]["service"]["flush"] == "${FLUSH_INTERVAL}"
    assert parse_body["config"]["pipeline"]["outputs"][0]["format"] == "${STDOUT_FMT}"

    render_resp = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json={"config": parse_body["config"], "include_comments": False},
    )
    assert render_resp.status_code == 200
    render_body = await render_resp.get_json()
    rendered_yaml = render_body["yaml"]
    assert "env:" in rendered_yaml
    assert "FLUSH_INTERVAL: 1" in rendered_yaml
    assert "STDOUT_FMT: json_lines" in rendered_yaml
    assert "flush: ${FLUSH_INTERVAL}" in rendered_yaml
    assert "format: ${STDOUT_FMT}" in rendered_yaml


@pytest.mark.asyncio
async def test_parse_and_render_fluentbit_yaml_metadata_env_round_trips() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    sample_yaml = """
env:
  LOG_LEVEL: info
  _metadata.config_version: cfg-123
  _metadata.configuration_date: 2026-05-09
pipeline:
  inputs:
    - name: random
  outputs:
    - name: stdout
      match: '*'
""".strip()

    parse_resp = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": sample_yaml},
    )
    assert parse_resp.status_code == 200
    parse_body = await parse_resp.get_json()
    assert parse_body["config"]["env"]["LOG_LEVEL"] == "info"
    assert parse_body["config"]["env"]["_metadata.config_version"] == "cfg-123"
    parsed_date_value = str(parse_body["config"]["env"]["_metadata.configuration_date"])
    assert "2026" in parsed_date_value
    assert "09" in parsed_date_value

    render_resp = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json={"config": parse_body["config"], "include_comments": False},
    )
    assert render_resp.status_code == 200
    render_body = await render_resp.get_json()
    rendered_yaml = render_body["yaml"]
    assert "_metadata.config_version: cfg-123" in rendered_yaml
    assert "_metadata.configuration_date:" in rendered_yaml


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_reports_invalid_env_section_type() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    sample_yaml = """
env:
  - FLUSH_INTERVAL=1
pipeline:
  inputs:
    - name: random
""".strip()

    resp = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": sample_yaml},
    )
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["ok"] is False
    assert any(item["path"] == "$.env" for item in body["errors"])
    assert body["config"]["env"] == {}


@pytest.mark.asyncio
async def test_parse_fluentbit_yaml_rejects_empty_file() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post(
        "/config-service/api/v1/parse/fluentbit/5.0.4",
        json={"text": " \n  "},
    )
    assert resp.status_code == 400
    body = await resp.get_json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == "empty_input_file"


@pytest.mark.asyncio
async def test_render_fluentd_rejects_invalid_request_payload() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post("/config-service/api/v1/render/fluentd/1.19", json={})
    assert resp.status_code == 400
    body = await resp.get_json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == "pydantic_validation_error"


@pytest.mark.asyncio
async def test_ui_prepare_file_extracts_header_metadata_and_line_map() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    text = (
        "# config-service: config_type=fluentbit\n"
        "# config-service: version=5.0.4\n"
        "# Owned by Team A\n"
        "\n"
        "pipeline:\n"
        "  inputs:\n"
        "    - name: tail\n"
    )

    response = await client.post(
        "/config-service/api/v1/ui/prepare-file",
        json={
            "text": text,
            "file_name": "example.yaml",
            "config_type": "fluentbit",
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert body["config_type"] == "fluentbit"
    assert body["version"] == "5.0.4"
    assert body["header_comments"] == "Owned by Team A"
    assert body["body"].startswith("pipeline:")
    assert body["source_line_map"]["$.pipeline"] >= 1


@pytest.mark.asyncio
async def test_render_yaml_returns_backend_composed_rendered_output() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    response = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json={
            "config": {
                "pipeline": {
                    "inputs": [{"name": "tail", "path": "/var/log/app.log"}],
                    "filters": [],
                    "outputs": [{"name": "stdout"}],
                },
            },
            "header_comments": "Owned by Team A\nValidated before deploy",
            "render_included_files": True,
            "included_documents": [
                {
                    "include_path": "child.yaml",
                    "ok": True,
                    "config": {
                        "pipeline": {
                            "inputs": [],
                            "filters": [],
                            "outputs": [{"name": "null"}],
                        },
                    },
                    "included_documents": [],
                }
            ],
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert body["rendered_output"].startswith("# Owned by Team A\n# Validated before deploy\n")
    assert "# Included file: child.yaml" in body["rendered_output"]


@pytest.mark.asyncio
async def test_render_fluentd_returns_backend_composed_rendered_output() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    response = await client.post(
        "/config-service/api/v1/render/fluentd/1.19",
        json={
            "config": {
                "service": {"log_level": "info"},
                "pipeline": {"inputs": [], "filters": [], "outputs": []},
            },
            "header_comments": "Owned by Team A",
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert body["rendered_output"].startswith("# Owned by Team A\n")


@pytest.mark.asyncio
async def test_render_yaml_can_include_config_service_header_in_rendered_output() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    response = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4?config_type=fluentbit",
        json={
            "config": {
                "pipeline": {
                    "inputs": [{"name": "tail", "path": "/var/log/app.log"}],
                    "filters": [],
                    "outputs": [{"name": "stdout"}],
                },
            },
            "header_comments": "Owned by Team A",
            "include_config_header": True,
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert body["rendered_output"].startswith(
        "# Owned by Team A\n# config-service: config_type=fluentbit\n# config-service: version=5.0.4\n"
    )


@pytest.mark.asyncio
async def test_render_fluentd_can_include_config_service_header_in_rendered_output() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    response = await client.post(
        "/config-service/api/v1/render/fluentd/1.19",
        json={
            "config": {
                "service": {"log_level": "info"},
                "pipeline": {"inputs": [], "filters": [], "outputs": []},
            },
            "header_comments": "Owned by Team A",
            "include_config_header": True,
        },
    )
    assert response.status_code == 200
    body = await response.get_json()
    assert body["ok"] is True
    assert body["rendered_output"].startswith(
        "# Owned by Team A\n# config-service: config_type=fluentd\n# config-service: version=1.19\n"
    )
