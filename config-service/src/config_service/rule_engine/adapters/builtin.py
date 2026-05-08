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

import re
from typing import Any

from config_service.rule_engine.base import RuleAdapter, RuleContext


def _iter_pipeline_plugins(config: dict[str, Any]):
    """Yield concrete plugin objects from the main pipeline for rule checks."""
    pipeline = config.get("pipeline", {})
    for section in ("inputs", "filters", "outputs"):
        items = pipeline.get(section, [])
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if isinstance(item, dict):
                    yield section, idx, item


def _catalog_plugin(catalog: dict[str, Any], section: str, name: str) -> dict[str, Any] | None:
    """Look up a plugin definition in the loaded catalog."""
    return catalog.get("plugins", {}).get(section, {}).get(name)


def _issue(code: str, path: str, message: str, severity: str = "error", source: str = "rules") -> dict[str, Any]:
    """Create a consistently-shaped rule-engine issue payload."""
    return {
        "code": code,
        "path": path,
        "message": message,
        "severity": severity,
        "source": source,
    }


class CatalogRequiredFieldsAdapter(RuleAdapter):
    """Mirror catalog-required plugin fields into rule-engine validation."""

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Report plugin instances that are missing catalog-mandated fields."""
        issues: list[dict[str, Any]] = []
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get("name", ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue
            required_fields = [f["name"] for f in plugin_def.get("fields", []) if f.get("required") is True]
            for field_name in required_fields:
                if field_name not in plugin_instance:
                    issues.append(
                        _issue(
                            "missing_required_field",
                            f"$.pipeline.{section}[{idx}].{field_name}",
                            f"Required field '{field_name}' is missing for plugin '{plugin_name}'.",
                        )
                    )
        return issues


class DataTypeEnforcementAdapter(RuleAdapter):
    """Enforce simple runtime Python types derived from catalog field metadata."""

    TYPE_MAP = {
        "string": str,
        "code": str,
        "integer": int,
        "boolean": bool,
        "float": (int, float),
        "number": (int, float),
        "duration": str,
        "size": str,
        "array": list,
        "list": list,
        "object": dict,
        "map": dict,
    }

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Reject values whose in-memory types drift from the catalog contract."""
        issues: list[dict[str, Any]] = []
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get("name", ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue
            fields_by_name = {f["name"]: f for f in plugin_def.get("fields", [])}
            for key, value in plugin_instance.items():
                if key == "name" or key not in fields_by_name:
                    continue
                data_type = str(fields_by_name[key].get("data_type", "string")).lower()
                expected = self.TYPE_MAP.get(data_type)
                if expected is None:
                    continue
                if data_type in {"integer", "float", "number"} and isinstance(value, bool):
                    issues.append(
                        _issue(
                            "invalid_type",
                            f"$.pipeline.{section}[{idx}].{key}",
                            f"Field '{key}' expects {data_type}, got boolean.",
                        )
                    )
                    continue
                if not isinstance(value, expected):
                    issues.append(
                        _issue(
                            "invalid_type",
                            f"$.pipeline.{section}[{idx}].{key}",
                            f"Field '{key}' expects {data_type}.",
                        )
                    )
        return issues


class DependencyConstraintsAdapter(RuleAdapter):
    """Placeholder for future catalog-level dependency rules."""

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Return no issues until cross-field dependency rules are implemented."""
        return []


class ValidationRuleConstraintsAdapter(RuleAdapter):
    """Interpret simple inline validation rules such as ranges and regexes."""

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Apply field-level validation rules after structural checks have passed."""
        issues: list[dict[str, Any]] = []
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get("name", ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue

            fields_by_name = {f["name"]: f for f in plugin_def.get("fields", [])}
            for key, value in plugin_instance.items():
                if key == "name" or key not in fields_by_name:
                    continue
                rule = fields_by_name[key].get("validation_rule")
                if not isinstance(rule, dict):
                    continue
                kind = rule.get("kind")
                path = f"$.pipeline.{section}[{idx}].{key}"

                if kind == "range" and isinstance(value, (int, float)) and not isinstance(value, bool):
                    min_val = rule.get("min")
                    max_val = rule.get("max")
                    if min_val is not None and value < min_val:
                        issues.append(_issue("range_min", path, f"Value for '{key}' must be >= {min_val}."))
                    if max_val is not None and value > max_val:
                        issues.append(_issue("range_max", path, f"Value for '{key}' must be <= {max_val}."))

                elif kind in {"regex", "regex_string"} and isinstance(value, str):
                    pattern = rule.get("pattern")
                    if pattern and re.fullmatch(pattern, value) is None:
                        issues.append(_issue("regex_mismatch", path, f"Value for '{key}' does not match required pattern."))

                elif kind == "boolean" and not isinstance(value, bool):
                    issues.append(_issue("invalid_boolean", path, f"Value for '{key}' must be boolean."))

        return issues


BUILTIN_ADAPTERS: dict[str, type[RuleAdapter]] = {
    "builtin.catalog_required_fields": CatalogRequiredFieldsAdapter,
    "builtin.data_type_enforcement": DataTypeEnforcementAdapter,
    "builtin.dependency_constraints": DependencyConstraintsAdapter,
    "builtin.validation_rule_constraints": ValidationRuleConstraintsAdapter,
}
