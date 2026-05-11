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

from pathlib import Path

from quart import Quart

from config_service.routes.api import create_api_blueprint
from config_service.services.catalog_service import CatalogService
from config_service.services.fluentbit_yaml_config_service import FluentBitYamlConfigService
from config_service.services.fluentd_config_service import FluentdConfigService
from config_service.services.issue_code_service import IssueCodeService
from config_service.services.include_document_service import IncludeDocumentService
from config_service.services.parser_definition_service import ParserDefinitionService
from config_service.services.rule_engine_service import RuleEngineService
from config_service.services.rules_registry_service import RulesRegistryService
from config_service.services.schema_service import SchemaService
from config_service.services.service_definition_service import ServiceDefinitionService
from config_service.services.ui_document_service import UiDocumentService
from config_service.services.validation_service import ValidationService
from config_service.services.yaml_render_service import YamlRenderService


def register_config_service_feature(opamp_app: Quart) -> None:
    """Mount config-service routes/services into an existing OpAMP Quart app."""
    module_dir = Path(__file__).resolve().parent
    repo_root = module_dir.parent if (module_dir.parent / "config").is_dir() else module_dir
    catalog_service = CatalogService(repo_root / "config" / "catalog-registry.json")
    catalog_service.load_all_catalogs()
    service_definition_service = ServiceDefinitionService(
        repo_root / "config" / "service-registry.json"
    )
    service_definition_service.load_all()
    parser_definition_service = ParserDefinitionService(repo_root / "config" / "parser-registry.json")
    parser_definition_service.load_all()
    issue_code_service = IssueCodeService(repo_root / "config" / "issue-code-messages.json")
    issue_code_service.load()
    rules_registry_service = RulesRegistryService(repo_root / "config" / "validation-rules-registry.json")
    rule_engine_service = RuleEngineService(rules_registry_service)
    validation_service = ValidationService(rule_engine_service)
    fluentbit_yaml_config_service = FluentBitYamlConfigService()
    fluentd_config_service = FluentdConfigService()
    include_document_service = IncludeDocumentService(
        fluentbit_yaml_config_service=fluentbit_yaml_config_service,
        fluentd_config_service=fluentd_config_service,
    )

    opamp_app.extensions["config_service:catalog_service"] = catalog_service
    opamp_app.extensions["config_service:rules_registry_service"] = rules_registry_service
    opamp_app.extensions["config_service:rule_engine_service"] = rule_engine_service
    opamp_app.extensions["config_service:service_definition_service"] = service_definition_service
    opamp_app.extensions["config_service:parser_definition_service"] = parser_definition_service
    opamp_app.extensions["config_service:issue_code_service"] = issue_code_service
    opamp_app.extensions["config_service:schema_service"] = SchemaService()
    opamp_app.extensions["config_service:validation_service"] = validation_service
    opamp_app.extensions["config_service:yaml_render_service"] = YamlRenderService()
    opamp_app.extensions["config_service:ui_document_service"] = UiDocumentService()
    opamp_app.extensions["config_service:fluentbit_yaml_config_service"] = fluentbit_yaml_config_service
    opamp_app.extensions["config_service:fluentd_config_service"] = fluentd_config_service
    opamp_app.extensions["config_service:include_document_service"] = include_document_service

    # Also expose under un-prefixed keys for route handlers that run in this app context.
    opamp_app.extensions["catalog_service"] = catalog_service
    opamp_app.extensions["rules_registry_service"] = rules_registry_service
    opamp_app.extensions["rule_engine_service"] = rule_engine_service
    opamp_app.extensions["service_definition_service"] = service_definition_service
    opamp_app.extensions["parser_definition_service"] = parser_definition_service
    opamp_app.extensions["issue_code_service"] = issue_code_service
    opamp_app.extensions["schema_service"] = SchemaService()
    opamp_app.extensions["validation_service"] = validation_service
    opamp_app.extensions["yaml_render_service"] = YamlRenderService()
    opamp_app.extensions["ui_document_service"] = UiDocumentService()
    opamp_app.extensions["fluentbit_yaml_config_service"] = fluentbit_yaml_config_service
    opamp_app.extensions["fluentd_config_service"] = fluentd_config_service
    opamp_app.extensions["include_document_service"] = include_document_service
    opamp_app.config["CONFIG_SERVICE_MODE"] = "embedded"

    opamp_app.register_blueprint(create_api_blueprint(), url_prefix="/config-service/api/v1")
