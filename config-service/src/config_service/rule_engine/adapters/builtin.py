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

KEY_PIPELINE = "pipeline"
KEY_INPUTS = "inputs"
KEY_FILTERS = "filters"
KEY_OUTPUTS = "outputs"
KEY_NAME = "name"
KEY_PLUGINS = "plugins"
KEY_FIELDS = "fields"
KEY_REQUIRED = "required"
KEY_COMMON = "common"
KEY_PROCESSORS = "processors"
KEY_SIGNALS = "signals"
KEY_CONDITION = "condition"
KEY_VALIDATION_RULE = "validation_rule"
KEY_DATA_TYPE = "data_type"


def _iter_pipeline_plugins(config: dict[str, Any]):
    """Yield concrete plugin objects from the main pipeline for rule checks."""
    pipeline = config.get(KEY_PIPELINE, {})
    for section in (KEY_INPUTS, KEY_FILTERS, KEY_OUTPUTS):
        items = pipeline.get(section, [])
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if isinstance(item, dict):
                    yield section, idx, item


def _catalog_plugin(catalog: dict[str, Any], section: str, name: str) -> dict[str, Any] | None:
    """Look up a plugin definition in the loaded catalog."""
    return catalog.get(KEY_PLUGINS, {}).get(section, {}).get(name)


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

    _ENV_VAR_PATTERN = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}$")
    _TIME_VALUE_PATTERN = re.compile(r"^\d+[smhdSMHD]?$")

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

    @classmethod
    def _is_numeric_env_var(cls, value: Any) -> bool:
        """Return true when value is a Fluent Bit-style env placeholder like ${MY_VAR}."""
        return isinstance(value, str) and bool(cls._ENV_VAR_PATTERN.fullmatch(value))

    @classmethod
    def _is_valid_time_value(cls, value: Any) -> bool:
        """Return true for integer values or strings like 10, 10s, 10m, 10h, 10d."""
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return value >= 0
        if isinstance(value, str):
            return bool(cls._TIME_VALUE_PATTERN.fullmatch(value))
        return False

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Reject values whose in-memory types drift from the catalog contract."""
        issues: list[dict[str, Any]] = []
        common_processors = context.catalog.get(KEY_COMMON, {}).get(KEY_PROCESSORS, {})
        processor_signals = common_processors.get(KEY_SIGNALS, {})
        filter_plugins = context.catalog.get(KEY_PLUGINS, {}).get(KEY_FILTERS, {})
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get(KEY_NAME, ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue
            issues.extend(
                self._validate_payload_types(
                    payload=plugin_instance,
                    field_defs=plugin_def.get(KEY_FIELDS, []),
                    path_prefix=f"$.pipeline.{section}[{idx}]",
                )
            )
            if section in {KEY_INPUTS, KEY_OUTPUTS}:
                issues.extend(
                    self._validate_processor_types(
                        plugin_instance=plugin_instance,
                        path_prefix=f"$.pipeline.{section}[{idx}]",
                        processor_signals=processor_signals,
                        filter_plugins=filter_plugins,
                    )
                )
        return issues

    def _validate_payload_types(
        self,
        *,
        payload: dict[str, Any],
        field_defs: list[dict[str, Any]],
        path_prefix: str,
    ) -> list[dict[str, Any]]:
        """Validate one payload object's field values against catalog data types.

        High-complexity flow notes:
        - Skip unknown keys early to avoid duplicate unknown-field handling elsewhere.
        - Special-case `time` and numeric env placeholders before generic type checks.
        - Keep bool-vs-number guard explicit because `bool` is a Python `int` subtype.
        """
        issues: list[dict[str, Any]] = []
        fields_by_name = {field[KEY_NAME]: field for field in field_defs if isinstance(field, dict)}
        # Walk payload keys once and evaluate expected type per catalog field metadata.
        for key, value in payload.items():
            if key == KEY_NAME or key not in fields_by_name:
                continue
            data_type = str(fields_by_name[key].get(KEY_DATA_TYPE, "string")).lower()
            # Time fields intentionally support integer values and compact duration strings.
            if data_type == "time":
                if not self._is_valid_time_value(value):
                    issues.append(
                        _issue(
                            "invalid_type",
                            f"{path_prefix}.{key}",
                            f"Field '{key}' expects a non-negative integer or a string with optional s/m/h/d suffix.",
                        )
                    )
                continue
            expected = self.TYPE_MAP.get(data_type)
            if expected is None:
                continue
            # Numeric fields may safely defer value resolution to runtime env expansion.
            if data_type in {"integer", "float", "number"} and self._is_numeric_env_var(value):
                continue
            if data_type in {"integer", "float", "number"} and isinstance(value, bool):
                issues.append(
                    _issue(
                        "invalid_type",
                        f"{path_prefix}.{key}",
                        f"Field '{key}' expects {data_type}, got boolean.",
                    )
                )
                continue
            if not isinstance(value, expected):
                issues.append(
                    _issue(
                        "invalid_type",
                        f"{path_prefix}.{key}",
                        f"Field '{key}' expects {data_type}.",
                    )
                )
        return issues

    def _validate_processor_types(
        self,
        *,
        plugin_instance: dict[str, Any],
        path_prefix: str,
        processor_signals: dict[str, Any],
        filter_plugins: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate nested processor field types for inputs/outputs plugin payloads.

        High-complexity flow notes:
        - Validate processor container shape before deep traversal.
        - Build per-signal processor allow-list, optionally merging filter plugins
          when Fluent Bit allows filters to run as processors for logs.
        - Delegate each processor payload to `_validate_payload_types`.
        """
        issues: list[dict[str, Any]] = []
        processors = plugin_instance.get(KEY_PROCESSORS)
        if not isinstance(processors, dict):
            return issues
        # Traverse signal -> processor-entry hierarchy and validate known processors only.
        for signal_name, processor_items in processors.items():
            if not isinstance(processor_items, list):
                continue
            signal_def = processor_signals.get(signal_name, {})
            available_processors = dict(signal_def.get(KEY_PROCESSORS, {}))
            if signal_name == "logs" and signal_def.get("allow_filters_as_processors"):
                available_processors.update(filter_plugins)
            for idx, processor_payload in enumerate(processor_items):
                if not isinstance(processor_payload, dict):
                    continue
                processor_name = processor_payload.get(KEY_NAME)
                if not isinstance(processor_name, str) or not processor_name:
                    continue
                processor_def = available_processors.get(processor_name)
                if not isinstance(processor_def, dict):
                    continue
                issues.extend(
                    self._validate_payload_types(
                        payload=processor_payload,
                        field_defs=processor_def.get(KEY_FIELDS, []),
                        path_prefix=f"{path_prefix}.{KEY_PROCESSORS}.{signal_name}[{idx}]",
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
        """Apply rule-level constraints declared in catalog field metadata.

        High-complexity flow notes:
        - Iterate only known plugin fields so unknown keys are handled elsewhere.
        - Dispatch by `validation_rule.kind` to targeted validation branches.
        - Each branch emits normalized, path-aware rule issues.
        """
        issues: list[dict[str, Any]] = []
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get(KEY_NAME, ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue

            fields_by_name = {f[KEY_NAME]: f for f in plugin_def.get(KEY_FIELDS, [])}
            # Evaluate constraints only for declared fields present in payload.
            for key, value in plugin_instance.items():
                if key == KEY_NAME or key not in fields_by_name:
                    continue
                rule = fields_by_name[key].get(KEY_VALIDATION_RULE)
                if not isinstance(rule, dict):
                    continue
                kind = rule.get("kind")
                path = f"$.pipeline.{section}[{idx}].{key}"

                # Numeric bounds check branch.
                if kind == "range" and isinstance(value, (int, float)) and not isinstance(value, bool):
                    min_val = rule.get("min")
                    max_val = rule.get("max")
                    if min_val is not None and value < min_val:
                        issues.append(_issue("range_min", path, f"Value for '{key}' must be >= {min_val}."))
                    if max_val is not None and value > max_val:
                        issues.append(_issue("range_max", path, f"Value for '{key}' must be <= {max_val}."))

                # Regex pattern compliance branch.
                elif kind in {"regex", "regex_string"} and isinstance(value, str):
                    pattern = rule.get("pattern")
                    if pattern and re.fullmatch(pattern, value) is None:
                        issues.append(_issue("regex_mismatch", path, f"Value for '{key}' does not match required pattern."))

                # Explicit boolean-only branch.
                elif kind == "boolean" and not isinstance(value, bool):
                    issues.append(_issue("invalid_boolean", path, f"Value for '{key}' must be boolean."))

        return issues


BUILTIN_ADAPTERS: dict[str, type[RuleAdapter]] = {
    "builtin.catalog_required_fields": CatalogRequiredFieldsAdapter,
    "builtin.data_type_enforcement": DataTypeEnforcementAdapter,
    "builtin.dependency_constraints": DependencyConstraintsAdapter,
    "builtin.validation_rule_constraints": ValidationRuleConstraintsAdapter,
}
