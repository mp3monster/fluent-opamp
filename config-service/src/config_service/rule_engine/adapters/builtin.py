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

import logging
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
KEY_KIND = "kind"
KEY_MIN = "min"
KEY_MAX = "max"
KEY_PATTERN = "pattern"
KEY_ALLOW_FILTERS_AS_PROCESSORS = "allow_filters_as_processors"

ISSUE_KEY_CODE = "code"
ISSUE_KEY_PATH = "path"
ISSUE_KEY_MESSAGE = "message"
ISSUE_KEY_SEVERITY = "severity"
ISSUE_KEY_SOURCE = "source"
ISSUE_SEVERITY_ERROR = "error"
ISSUE_SOURCE_RULES = "rules"

RULE_KIND_RANGE = "range"
RULE_KIND_REGEX = "regex"
RULE_KIND_REGEX_STRING = "regex_string"
RULE_KIND_BOOLEAN = "boolean"
DATA_TYPE_STRING = "string"
DATA_TYPE_TIME = "time"
DATA_TYPE_INTEGER = "integer"
DATA_TYPE_BOOLEAN = "boolean"
DATA_TYPE_FLOAT = "float"
DATA_TYPE_NUMBER = "number"
DATA_TYPE_DURATION = "duration"
DATA_TYPE_SIZE = "size"
DATA_TYPE_ARRAY = "array"
DATA_TYPE_LIST = "list"
DATA_TYPE_OBJECT = "object"
DATA_TYPE_MAP = "map"
SIGNAL_LOGS = "logs"

LOGGER = logging.getLogger(__name__)


def _iter_pipeline_plugins(config: dict[str, Any]):
    """Yield concrete plugin objects from the main pipeline for rule checks."""
    pipeline = config.get(KEY_PIPELINE, {})
    if not isinstance(pipeline, dict):
        LOGGER.warning("rule adapter pipeline payload is not a dict; skipping plugin traversal")
        return
    for section in (KEY_INPUTS, KEY_FILTERS, KEY_OUTPUTS):
        items = pipeline.get(section, [])
        if not isinstance(items, list):
            LOGGER.warning(
                "rule adapter pipeline section is not a list; skipping section=%s type=%s",
                section,
                type(items).__name__,
            )
            continue
        for idx, item in enumerate(items):
            if isinstance(item, dict):
                yield section, idx, item
            else:
                LOGGER.warning(
                    "rule adapter plugin entry is not a dict; skipping section=%s index=%s type=%s",
                    section,
                    idx,
                    type(item).__name__,
                )


def _catalog_plugin(catalog: dict[str, Any], section: str, name: str) -> dict[str, Any] | None:
    """Look up a plugin definition in the loaded catalog."""
    plugin = catalog.get(KEY_PLUGINS, {}).get(section, {}).get(name)
    if plugin is None:
        LOGGER.debug("catalog plugin definition not found section=%s name=%s", section, name)
    return plugin


def _issue(
    code: str,
    path: str,
    message: str,
    severity: str = ISSUE_SEVERITY_ERROR,
    source: str = ISSUE_SOURCE_RULES,
) -> dict[str, Any]:
    """Create a consistently-shaped rule-engine issue payload."""
    return {
        ISSUE_KEY_CODE: code,
        ISSUE_KEY_PATH: path,
        ISSUE_KEY_MESSAGE: message,
        ISSUE_KEY_SEVERITY: severity,
        ISSUE_KEY_SOURCE: source,
    }


class CatalogRequiredFieldsAdapter(RuleAdapter):
    """Mirror catalog-required plugin fields into rule-engine validation."""

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Report plugin instances that are missing catalog-mandated fields."""
        LOGGER.info("starting catalog required fields evaluation version=%s", context.version)
        issues: list[dict[str, Any]] = []
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get(KEY_NAME, ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue
            required_fields = [
                field[KEY_NAME]
                for field in plugin_def.get(KEY_FIELDS, [])
                if isinstance(field, dict) and field.get(KEY_REQUIRED) is True and KEY_NAME in field
            ]
            for field_name in required_fields:
                if field_name not in plugin_instance:
                    LOGGER.warning(
                        "required field missing section=%s index=%s plugin=%s field=%s",
                        section,
                        idx,
                        plugin_name,
                        field_name,
                    )
                    issues.append(
                        _issue(
                            "missing_required_field",
                            f"$.pipeline.{section}[{idx}].{field_name}",
                            f"Required field '{field_name}' is missing for plugin '{plugin_name}'.",
                        )
                    )
        LOGGER.info(
            "completed catalog required fields evaluation version=%s issue_count=%s",
            context.version,
            len(issues),
        )
        return issues


class DataTypeEnforcementAdapter(RuleAdapter):
    """Enforce simple runtime Python types derived from catalog field metadata."""

    _ENV_VAR_PATTERN = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}$")
    _TIME_VALUE_PATTERN = re.compile(r"^\d+[smhdSMHD]?$")

    TYPE_MAP = {
        DATA_TYPE_STRING: str,
        "code": str,
        DATA_TYPE_INTEGER: int,
        DATA_TYPE_BOOLEAN: bool,
        DATA_TYPE_FLOAT: (int, float),
        DATA_TYPE_NUMBER: (int, float),
        DATA_TYPE_DURATION: str,
        DATA_TYPE_SIZE: str,
        DATA_TYPE_ARRAY: list,
        DATA_TYPE_LIST: list,
        DATA_TYPE_OBJECT: dict,
        DATA_TYPE_MAP: dict,
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
        LOGGER.info("starting data type enforcement evaluation version=%s", context.version)
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
        LOGGER.info(
            "completed data type enforcement evaluation version=%s issue_count=%s",
            context.version,
            len(issues),
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
            data_type = str(fields_by_name[key].get(KEY_DATA_TYPE, DATA_TYPE_STRING)).lower()
            # Time fields intentionally support integer values and compact duration strings.
            if data_type == DATA_TYPE_TIME:
                if not self._is_valid_time_value(value):
                    LOGGER.warning(
                        "time field failed validation path=%s key=%s value_type=%s",
                        path_prefix,
                        key,
                        type(value).__name__,
                    )
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
                LOGGER.debug("skipping unknown catalog data type key=%s data_type=%s", key, data_type)
                continue
            # Numeric fields may safely defer value resolution to runtime env expansion.
            if data_type in {DATA_TYPE_INTEGER, DATA_TYPE_FLOAT, DATA_TYPE_NUMBER} and self._is_numeric_env_var(value):
                continue
            if data_type in {DATA_TYPE_INTEGER, DATA_TYPE_FLOAT, DATA_TYPE_NUMBER} and isinstance(value, bool):
                LOGGER.warning(
                    "numeric field received boolean path=%s key=%s",
                    path_prefix,
                    key,
                )
                issues.append(
                    _issue(
                        "invalid_type",
                        f"{path_prefix}.{key}",
                        f"Field '{key}' expects {data_type}, got boolean.",
                    )
                )
                continue
            if not isinstance(value, expected):
                LOGGER.warning(
                    "field type mismatch path=%s key=%s expected=%s actual_type=%s",
                    path_prefix,
                    key,
                    data_type,
                    type(value).__name__,
                )
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
            if processors is not None:
                LOGGER.warning(
                    "processor payload is not a dict path=%s type=%s",
                    path_prefix,
                    type(processors).__name__,
                )
            return issues
        # Traverse signal -> processor-entry hierarchy and validate known processors only.
        for signal_name, processor_items in processors.items():
            if not isinstance(processor_items, list):
                LOGGER.warning(
                    "processor signal entry is not a list path=%s signal=%s type=%s",
                    path_prefix,
                    signal_name,
                    type(processor_items).__name__,
                )
                continue
            signal_def = processor_signals.get(signal_name, {})
            available_processors = dict(signal_def.get(KEY_PROCESSORS, {}))
            if signal_name == SIGNAL_LOGS and signal_def.get(KEY_ALLOW_FILTERS_AS_PROCESSORS):
                available_processors.update(filter_plugins)
            for idx, processor_payload in enumerate(processor_items):
                if not isinstance(processor_payload, dict):
                    LOGGER.warning(
                        "processor entry is not a dict path=%s signal=%s index=%s type=%s",
                        path_prefix,
                        signal_name,
                        idx,
                        type(processor_payload).__name__,
                    )
                    continue
                processor_name = processor_payload.get(KEY_NAME)
                if not isinstance(processor_name, str) or not processor_name:
                    LOGGER.warning(
                        "processor entry missing name path=%s signal=%s index=%s",
                        path_prefix,
                        signal_name,
                        idx,
                    )
                    continue
                processor_def = available_processors.get(processor_name)
                if not isinstance(processor_def, dict):
                    LOGGER.debug(
                        "processor definition not found path=%s signal=%s processor=%s",
                        path_prefix,
                        signal_name,
                        processor_name,
                    )
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
        LOGGER.info("dependency constraints evaluation not yet implemented version=%s", context.version)
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
        LOGGER.info("starting validation rule constraints evaluation version=%s", context.version)
        issues: list[dict[str, Any]] = []
        for section, idx, plugin_instance in _iter_pipeline_plugins(context.config):
            plugin_name = str(plugin_instance.get(KEY_NAME, ""))
            plugin_def = _catalog_plugin(context.catalog, section, plugin_name)
            if not plugin_def:
                continue

            fields_by_name = {
                field[KEY_NAME]: field
                for field in plugin_def.get(KEY_FIELDS, [])
                if isinstance(field, dict) and KEY_NAME in field
            }
            # Evaluate constraints only for declared fields present in payload.
            for key, value in plugin_instance.items():
                if key == KEY_NAME or key not in fields_by_name:
                    continue
                rule = fields_by_name[key].get(KEY_VALIDATION_RULE)
                if not isinstance(rule, dict):
                    continue
                kind = rule.get(KEY_KIND)
                path = f"$.pipeline.{section}[{idx}].{key}"

                # Numeric bounds check branch.
                if kind == RULE_KIND_RANGE and isinstance(value, (int, float)) and not isinstance(value, bool):
                    min_val = rule.get(KEY_MIN)
                    max_val = rule.get(KEY_MAX)
                    if min_val is not None and value < min_val:
                        LOGGER.warning("range minimum violation path=%s min=%s value=%s", path, min_val, value)
                        issues.append(_issue("range_min", path, f"Value for '{key}' must be >= {min_val}."))
                    if max_val is not None and value > max_val:
                        LOGGER.warning("range maximum violation path=%s max=%s value=%s", path, max_val, value)
                        issues.append(_issue("range_max", path, f"Value for '{key}' must be <= {max_val}."))

                # Regex pattern compliance branch.
                elif kind in {RULE_KIND_REGEX, RULE_KIND_REGEX_STRING} and isinstance(value, str):
                    pattern = rule.get(KEY_PATTERN)
                    if pattern and re.fullmatch(pattern, value) is None:
                        LOGGER.warning("regex mismatch path=%s pattern=%s", path, pattern)
                        issues.append(_issue("regex_mismatch", path, f"Value for '{key}' does not match required pattern."))

                # Explicit boolean-only branch.
                elif kind == RULE_KIND_BOOLEAN and not isinstance(value, bool):
                    LOGGER.warning("boolean constraint violation path=%s actual_type=%s", path, type(value).__name__)
                    issues.append(_issue("invalid_boolean", path, f"Value for '{key}' must be boolean."))

        LOGGER.info(
            "completed validation rule constraints evaluation version=%s issue_count=%s",
            context.version,
            len(issues),
        )
        return issues


BUILTIN_ADAPTERS: dict[str, type[RuleAdapter]] = {
    "builtin.catalog_required_fields": CatalogRequiredFieldsAdapter,
    "builtin.data_type_enforcement": DataTypeEnforcementAdapter,
    "builtin.dependency_constraints": DependencyConstraintsAdapter,
    "builtin.validation_rule_constraints": ValidationRuleConstraintsAdapter,
}
