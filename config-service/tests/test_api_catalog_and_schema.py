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

"""Config-service catalog and schema API test coverage.

Test-case reference: config-service/docs/TEST_CASES.md
"""

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
    assert 'id="dry-run-btn"' in ui_html
    assert "Use Included files" in ui_html
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
