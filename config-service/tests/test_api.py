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
    assert "/config-service/ui/assets/config_ui.js" in ui_html

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
async def test_meta_comments_help_page_served() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()
    response = await client.get("/config-service/ui/docs/meta-comments")
    assert response.status_code == 200
    html = (await response.get_data()).decode("utf-8")
    assert "_meta" in html
    assert "comment_lines" in html
    assert "field_comment_lines" in html


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
async def test_service_section_meta_help_link_is_rendered() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()
    response = await client.get("/config-service/ui")
    assert response.status_code == 200
    html = (await response.get_data()).decode("utf-8")
    assert 'href="/config-service/ui/docs/meta-comments"' in html
    assert 'title="Open help for comments and field comments."' in html
    assert "/config-service/ui/assets/config_editor_icon.png" in html


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
    assert "/config-service/ui/assets/config_ui.js?v=" in html

    asset = await client.get("/config-service/ui/assets/config_ui.js")
    assert asset.status_code == 200
    assert asset.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"


@pytest.mark.asyncio
async def test_validate_and_render_yaml() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    payload = {
        "config": {
            "pipeline": {
                "inputs": [
                    {
                        "name": "forward",
                        "port": 24224,
                        "_meta": {
                            "comment_lines": ["ingress", "primary listener"],
                            "field_comment_lines": {
                                "port": ["Listener port", "Matches upstream sender"],
                            },
                        },
                    }
                ],
                "filters": [],
                "outputs": [{"name": "stdout"}],
            },
            "_meta": {
                "comment_lines": ["Root pipeline config"],
            },
        },
    }

    resp = await client.post("/config-service/api/v1/validate/5.0.4", json=payload)
    assert resp.status_code in (200, 400)
    body = await resp.get_json()
    assert "errors" in body
    if body["errors"]:
        orders = [issue["order"] for issue in body["errors"]]
        assert orders == sorted(orders)

    yaml_resp = await client.post(
        "/config-service/api/v1/render/yaml/5.0.4",
        json={**payload, "include_comments": True},
    )
    assert yaml_resp.status_code == 200
    yaml_body = await yaml_resp.get_json()
    assert yaml_body["ok"] is True
    assert "# Root pipeline config" in yaml_body["yaml"]
    assert "# ingress" in yaml_body["yaml"]
    assert "# primary listener" in yaml_body["yaml"]
    assert "# Listener port" in yaml_body["yaml"]
    assert "pipeline:" in yaml_body["yaml"]
    assert "filters:" not in yaml_body["yaml"]


@pytest.mark.asyncio
async def test_schema_includes_meta_comment_support() -> None:
    app = create_app(mode="standalone")
    client = app.test_client()

    resp = await client.post("/config-service/api/v1/schema/5.0.4", json={"strict": True})
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["ok"] is True
    config_props = body["schema"]["properties"]["config"]["properties"]
    assert "parsers" in config_props
    assert config_props["parsers"]["type"] == "array"
    assert "_meta" in body["schema"]["properties"]["config"]["properties"]["pipeline"]["properties"]
    input_items = config_props["pipeline"]["properties"]["inputs"]["items"]["oneOf"]
    assert any("route" in schema["properties"] for schema in input_items)
    assert any("_meta" in schema["properties"] for schema in input_items)


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
    assert parsed_body["config"]["pipeline"]["outputs"][0]["name"] == "copy"

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
