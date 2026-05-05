from __future__ import annotations

from quart import Quart

from config_service.routes.api import create_api_blueprint
from config_service.services.catalog_service import CatalogService
from config_service.services.fluentd_config_service import FluentdConfigService
from config_service.services.rule_engine_service import RuleEngineService
from config_service.services.rules_registry_service import RulesRegistryService
from config_service.services.schema_service import SchemaService
from config_service.services.service_definition_service import ServiceDefinitionService
from config_service.services.validation_service import ValidationService
from config_service.services.yaml_render_service import YamlRenderService
from pathlib import Path


def register_config_service_feature(opamp_app: Quart) -> None:
    """Mount config-service routes/services into an existing OpAMP Quart app."""
    repo_root = Path(__file__).resolve().parents[1]
    catalog_service = CatalogService(repo_root / "config" / "catalog-registry.json")
    catalog_service.load_all_catalogs()
    service_definition_service = ServiceDefinitionService(
        repo_root / "config" / "service-registry.json"
    )
    service_definition_service.load_all()
    rules_registry_service = RulesRegistryService(repo_root / "config" / "validation-rules-registry.json")
    rule_engine_service = RuleEngineService(rules_registry_service)
    validation_service = ValidationService(rule_engine_service)

    opamp_app.extensions["config_service:catalog_service"] = catalog_service
    opamp_app.extensions["config_service:rules_registry_service"] = rules_registry_service
    opamp_app.extensions["config_service:rule_engine_service"] = rule_engine_service
    opamp_app.extensions["config_service:service_definition_service"] = service_definition_service
    opamp_app.extensions["config_service:schema_service"] = SchemaService()
    opamp_app.extensions["config_service:validation_service"] = validation_service
    opamp_app.extensions["config_service:yaml_render_service"] = YamlRenderService()
    opamp_app.extensions["config_service:fluentd_config_service"] = FluentdConfigService()

    # Also expose under un-prefixed keys for route handlers that run in this app context.
    opamp_app.extensions["catalog_service"] = catalog_service
    opamp_app.extensions["rules_registry_service"] = rules_registry_service
    opamp_app.extensions["rule_engine_service"] = rule_engine_service
    opamp_app.extensions["service_definition_service"] = service_definition_service
    opamp_app.extensions["schema_service"] = SchemaService()
    opamp_app.extensions["validation_service"] = validation_service
    opamp_app.extensions["yaml_render_service"] = YamlRenderService()
    opamp_app.extensions["fluentd_config_service"] = FluentdConfigService()
    opamp_app.config["CONFIG_SERVICE_MODE"] = "embedded"

    opamp_app.register_blueprint(create_api_blueprint(), url_prefix="/config-service/api/v1")
