from __future__ import annotations

from typing import Any


class SchemaService:
    """Compiles runtime JSON schema from catalog metadata."""

    TYPE_MAP = {
        "string": "string",
        "code": "string",
        "duration": "string",
        "time": "string",
        "size": "string",
        "integer": "integer",
        "number": "number",
        "float": "number",
        "boolean": "boolean",
        "array": "array",
        "list": "array",
        "object": "object",
        "map": "object",
        "hash": "object",
        "enum": "string",
    }

    @staticmethod
    def _meta_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "comment_lines": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "field_comment_lines": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "additionalProperties": False,
        }

    def _with_object_meta(self, schema: dict[str, Any]) -> dict[str, Any]:
        if schema.get("type") != "object":
            return schema
        props = dict(schema.get("properties", {}))
        props["_meta"] = self._meta_schema()
        schema["properties"] = props
        return schema

    def compile_schema(self, catalog: dict[str, Any], strict_mode: bool = True) -> dict[str, Any]:
        engine = str(catalog.get("engine") or "fluentbit").lower()
        if engine == "fluentd":
            return self._compile_fluentd_schema(catalog, strict_mode=strict_mode)
        return self._compile_fluentbit_schema(catalog, strict_mode=strict_mode)

    def _field_schema(self, field: dict[str, Any]) -> dict[str, Any]:
        catalog_data_type = str(field.get("data_type", "string")).lower()
        json_type = self.TYPE_MAP.get(catalog_data_type, "string")
        payload: dict[str, Any] = {
            "type": json_type,
            "description": field.get("description", ""),
            "x-doc-reference": field.get("reference", ""),
            "x-doc-required": bool(field.get("required", False)),
            "x-config-data-type": catalog_data_type,
        }
        enum_options = field.get("called_enum_options")
        if isinstance(enum_options, list) and enum_options:
            payload["enum"] = list(enum_options)
        if "default" in field:
            payload["default"] = field["default"]
        return payload

    def _plugin_schema(
        self,
        plugin_name: str,
        plugin_def: dict[str, Any],
        *,
        strict_mode: bool,
        nested_sections: dict[str, Any] | None = None,
        allow_directive_arg: bool = True,
        fluentbit_processors: dict[str, Any] | None = None,
        fluentbit_section: str | None = None,
        fluentbit_filter_plugins: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        props: dict[str, Any] = {
            "name": {"type": "string", "const": plugin_name, "title": "Plugin"}
        }
        required = ["name"]

        directive_arg = plugin_def.get("directive_argument")
        if allow_directive_arg and isinstance(directive_arg, dict):
            props["directive_arg"] = self._field_schema(directive_arg)
            if directive_arg.get("required") is True:
                required.append("directive_arg")

        for field in plugin_def.get("fields", []):
            field_name = field["name"]
            props[field_name] = self._field_schema(field)
            if field.get("required") is True:
                required.append(field_name)

        if nested_sections and isinstance(plugin_def.get("allowed_children"), list):
            child_props: dict[str, Any] = {}
            for child_meta in plugin_def["allowed_children"]:
                section_name = child_meta.get("section")
                if not isinstance(section_name, str) or section_name not in nested_sections:
                    continue
                child_schema = self._nested_section_items_schema(
                    section_name,
                    nested_sections[section_name],
                    strict_mode=strict_mode,
                    nested_sections=nested_sections,
                )
                child_props[section_name] = {"type": "array", "items": child_schema}
            if child_props:
                child_props["includes"] = {
                    "type": "array",
                    "items": self._with_object_meta({
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                        "additionalProperties": False,
                    }),
                }
                props["children"] = self._with_object_meta({
                    "type": "object",
                    "properties": child_props,
                    "additionalProperties": not strict_mode,
                })

        if fluentbit_processors and fluentbit_section in {"inputs", "outputs"}:
            processors_schema = self._fluentbit_processors_schema(
                fluentbit_processors,
                strict_mode=strict_mode,
                filter_plugins=fluentbit_filter_plugins,
            )
            props["processors"] = processors_schema

        return self._with_object_meta({
            "type": "object",
            "title": plugin_def.get("title", plugin_name),
            "properties": props,
            "required": required,
            "additionalProperties": not strict_mode,
        })

    def _compile_fluentbit_schema(self, catalog: dict[str, Any], strict_mode: bool) -> dict[str, Any]:
        plugin_groups = catalog.get("plugins", {})
        processors_def = catalog.get("common", {}).get("processors", {})

        def section_item_schema(section: str) -> dict[str, Any]:
            plugin_schemas = [
                self._plugin_schema(
                    plugin_name,
                    plugin_def,
                    strict_mode=strict_mode,
                    allow_directive_arg=False,
                    fluentbit_processors=processors_def,
                    fluentbit_section=section,
                    fluentbit_filter_plugins=plugin_groups.get("filters", {}),
                )
                for plugin_name, plugin_def in plugin_groups.get(section, {}).items()
            ]
            return {"oneOf": plugin_schemas} if plugin_schemas else {"type": "object"}

        return self._with_object_meta({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "config": self._with_object_meta({
                    "type": "object",
                    "properties": {
                        "pipeline": self._with_object_meta({
                            "type": "object",
                            "properties": {
                                "inputs": {"type": "array", "items": section_item_schema("inputs")},
                                "filters": {"type": "array", "items": section_item_schema("filters")},
                                "outputs": {"type": "array", "items": section_item_schema("outputs")},
                            },
                            "required": ["inputs", "outputs"],
                            "additionalProperties": not strict_mode,
                        })
                    },
                    "required": ["pipeline"],
                    "additionalProperties": not strict_mode,
                }),
                "annotations": {
                    "type": "object",
                    "additionalProperties": {"type": "string", "maxLength": 500},
                },
            },
            "required": ["config"],
            "additionalProperties": False,
        })

    def _fluentbit_processors_schema(
        self,
        processors_def: dict[str, Any],
        *,
        strict_mode: bool,
        filter_plugins: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        signal_props: dict[str, Any] = {}
        signals = processors_def.get("signals", {})
        for signal_name, signal_def in signals.items():
            variants = signal_def.get("processors", {})
            item_schemas = [
                self._processor_variant_schema(name, variant, strict_mode=strict_mode, include_condition=bool(processors_def.get("condition") and variant.get("supports_condition")))
                for name, variant in variants.items()
            ]
            if signal_name == "logs" and signal_def.get("allow_filters_as_processors") and filter_plugins:
                item_schemas.extend(
                    [
                        self._processor_variant_schema(
                            filter_name,
                            filter_def,
                            strict_mode=strict_mode,
                            include_condition=False,
                        )
                        for filter_name, filter_def in filter_plugins.items()
                    ]
                )
            signal_props[signal_name] = {
                "type": "array",
                "items": {"oneOf": item_schemas} if item_schemas else {"type": "object"},
            }
        return self._with_object_meta({
            "type": "object",
            "properties": signal_props,
            "additionalProperties": not strict_mode,
        })

    def _processor_variant_schema(
        self,
        processor_name: str,
        variant: dict[str, Any],
        *,
        strict_mode: bool,
        include_condition: bool,
    ) -> dict[str, Any]:
        props: dict[str, Any] = {
            "name": {"type": "string", "const": processor_name},
        }
        required = ["name"]
        for field in variant.get("fields", []):
            props[field["name"]] = self._field_schema(field)
            if field.get("required") is True:
                required.append(field["name"])
        if include_condition:
            props["condition"] = self._with_object_meta({
                "type": "object",
                "properties": {
                    "op": {
                        "type": "string",
                        "enum": ["and", "or"],
                    },
                    "rules": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
                "required": ["op", "rules"],
                "additionalProperties": not strict_mode,
            })
        return self._with_object_meta({
            "type": "object",
            "title": variant.get("title", processor_name),
            "properties": props,
            "required": required,
            "additionalProperties": not strict_mode,
        })

    def _compile_fluentd_schema(self, catalog: dict[str, Any], strict_mode: bool) -> dict[str, Any]:
        plugin_groups = catalog.get("plugins", {})
        nested_sections = catalog.get("nested_sections", {})
        root_sections = catalog.get("root_sections", {})

        def main_section_schema(section: str) -> dict[str, Any]:
            plugin_schemas = [
                self._plugin_schema(
                    plugin_name,
                    plugin_def,
                    strict_mode=strict_mode,
                    nested_sections=nested_sections,
                )
                for plugin_name, plugin_def in plugin_groups.get(section, {}).items()
            ]
            return {"oneOf": plugin_schemas} if plugin_schemas else {"type": "object"}

        label_schema = self._root_container_schema(
            root_sections.get("labels", {}),
            strict_mode=strict_mode,
            include_labels=False,
            include_workers=False,
            plugin_groups=plugin_groups,
            nested_sections=nested_sections,
        )
        worker_schema = self._root_container_schema(
            root_sections.get("workers", {}),
            strict_mode=strict_mode,
            include_labels=True,
            include_workers=False,
            plugin_groups=plugin_groups,
            nested_sections=nested_sections,
        )

        return self._with_object_meta({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "config": self._with_object_meta({
                    "type": "object",
                    "properties": {
                        "service": self._with_object_meta({
                            "type": "object",
                            "additionalProperties": not strict_mode,
                        }),
                        "includes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "pipeline": self._with_object_meta({
                            "type": "object",
                            "properties": {
                                "inputs": {"type": "array", "items": main_section_schema("inputs")},
                                "filters": {"type": "array", "items": main_section_schema("filters")},
                                "outputs": {"type": "array", "items": main_section_schema("outputs")},
                            },
                            "required": ["inputs", "filters", "outputs"],
                            "additionalProperties": not strict_mode,
                        }),
                        "labels": {"type": "array", "items": label_schema},
                        "workers": {"type": "array", "items": worker_schema},
                    },
                    "required": ["pipeline"],
                    "additionalProperties": not strict_mode,
                }),
                "annotations": {
                    "type": "object",
                    "additionalProperties": {"type": "string", "maxLength": 500},
                },
            },
            "required": ["config"],
            "additionalProperties": False,
        })

    def _root_container_schema(
        self,
        root_def: dict[str, Any],
        *,
        strict_mode: bool,
        include_labels: bool,
        include_workers: bool,
        plugin_groups: dict[str, Any],
        nested_sections: dict[str, Any],
    ) -> dict[str, Any]:
        props: dict[str, Any] = {}
        required: list[str] = []
        for field in root_def.get("fields", []):
            props[field["name"]] = self._field_schema(field)
            if field.get("required") is True:
                required.append(field["name"])
        props["pipeline"] = self._with_object_meta({
            "type": "object",
            "properties": {
                "inputs": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            self._plugin_schema(
                                plugin_name,
                                plugin_def,
                                strict_mode=strict_mode,
                                nested_sections=nested_sections,
                            )
                            for plugin_name, plugin_def in plugin_groups.get("inputs", {}).items()
                        ]
                    },
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            self._plugin_schema(
                                plugin_name,
                                plugin_def,
                                strict_mode=strict_mode,
                                nested_sections=nested_sections,
                            )
                            for plugin_name, plugin_def in plugin_groups.get("filters", {}).items()
                        ]
                    },
                },
                "outputs": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            self._plugin_schema(
                                plugin_name,
                                plugin_def,
                                strict_mode=strict_mode,
                                nested_sections=nested_sections,
                            )
                            for plugin_name, plugin_def in plugin_groups.get("outputs", {}).items()
                        ]
                    },
                },
            },
            "required": ["inputs", "filters", "outputs"],
            "additionalProperties": not strict_mode,
        })
        props["includes"] = {"type": "array", "items": {"type": "string"}}
        if include_labels:
            props["labels"] = {
                "type": "array",
                "items": self._root_container_schema(
                    {"fields": [{"name": "name", "required": True, "description": "Label name", "reference": "", "data_type": "string"}]},
                    strict_mode=strict_mode,
                    include_labels=False,
                    include_workers=False,
                    plugin_groups=plugin_groups,
                    nested_sections=nested_sections,
                ),
            }
        if include_workers:
            props["workers"] = {"type": "array", "items": {"type": "object"}}
        return self._with_object_meta({
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": not strict_mode,
        })

    def _nested_section_items_schema(
        self,
        section_name: str,
        nested_def: dict[str, Any],
        *,
        strict_mode: bool,
        nested_sections: dict[str, Any],
    ) -> dict[str, Any]:
        if nested_def.get("reuses_output_plugins") is True:
            return self._with_object_meta({
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": True,
            })
        if nested_def.get("plugin_backed") is True:
            variants = nested_def.get("variants", {})
            schemas = [
                self._plugin_schema(
                    variant_name,
                    variant_def,
                    strict_mode=strict_mode,
                    nested_sections=nested_sections,
                    allow_directive_arg=section_name not in {"buffer"},
                )
                for variant_name, variant_def in variants.items()
            ]
            return {"oneOf": schemas} if schemas else {"type": "object"}

        props: dict[str, Any] = {}
        required: list[str] = []
        directive_arg = nested_def.get("directive_argument")
        if isinstance(directive_arg, dict):
            props["directive_arg"] = self._field_schema(directive_arg)
            if directive_arg.get("required") is True:
                required.append("directive_arg")
        for field in nested_def.get("fields", []):
            props[field["name"]] = self._field_schema(field)
            if field.get("required") is True:
                required.append(field["name"])
        return self._with_object_meta({
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": not strict_mode,
        })
