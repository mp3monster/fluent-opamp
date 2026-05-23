from __future__ import annotations

from typing import Any

KEY_TYPE = "type"
KEY_PROPERTIES = "properties"
KEY_COMMENT_LINES = "comment_lines"
KEY_FIELD_COMMENT_LINES = "field_comment_lines"
KEY_ITEMS = "items"
KEY_ADDITIONAL_PROPERTIES = "additionalProperties"
KEY_ENGINE = "engine"
KEY_DATA_TYPE = "data_type"
KEY_DESCRIPTION = "description"
KEY_REFERENCE = "reference"
KEY_REQUIRED = "required"
KEY_X_DOC_REFERENCE = "x-doc-reference"
KEY_X_DOC_REQUIRED = "x-doc-required"
KEY_X_CONFIG_DATA_TYPE = "x-config-data-type"
KEY_X_REFERENCES_PARSER = "x-references-parser"
KEY_REFERENCES_PARSER = "references_parser"
KEY_CALLED_ENUM_OPTIONS = "called_enum_options"
KEY_DEFAULT = "default"
KEY_NAME = "name"
KEY_DIRECTIVE_ARGUMENT = "directive_argument"
KEY_FIELDS = "fields"
KEY_ALLOWED_CHILDREN = "allowed_children"
KEY_SECTION = "section"
KEY_INCLUDES = "includes"
KEY_CHILDREN = "children"
KEY_PROCESSORS = "processors"
KEY_ROUTE = "route"
KEY_TITLE = "title"
KEY_ALL_OF = "allOf"
KEY_FLUENT_BIT_VERSION = "fluent_bit_version"
KEY_CONST = "const"
KEY_ENUM = "enum"
KEY_ONE_OF = "oneOf"
KEY_CONFIG = "config"
KEY_PARSER_FORMATS = "parser_formats"
KEY_DOC_URL = "doc_url"
KEY_SIGNALS = "signals"
KEY_CONDITION = "condition"
KEY_RULES = "rules"
KEY_LABELS = "labels"
KEY_WORKERS = "workers"
KEY_PIPELINE = "pipeline"
KEY_PLUGINS = "plugins"
KEY_COMMON = "common"
KEY_NESTED_SECTIONS = "nested_sections"
KEY_ROOT_SECTIONS = "root_sections"
KEY_PLUGIN_BACKED = "plugin_backed"
KEY_VARIANTS = "variants"
KEY_REUSES_OUTPUT_PLUGINS = "reuses_output_plugins"
KEY_OUTPUTS = "outputs"
KEY_INPUTS = "inputs"
KEY_FILTERS = "filters"
KEY_IMPLEMENTED = "implemented"
KEY_ALLOW_FILTERS_AS_PROCESSORS = "allow_filters_as_processors"
KEY_SUPPORTS_CONDITION = "supports_condition"
KEY_TOP_LEVEL_FIELDS = "top_level_fields"
KEY_ROUTE_FIELDS = "route_fields"
KEY_CONDITION_FIELDS = "condition_fields"
KEY_RULE_FIELDS = "rule_fields"
KEY_VALUE = "value"
KEY_TO = "to"
KEY_ANY_OF = "anyOf"
KEY_OP = "op"
KEY_META = "_meta"
DIRECTIVE_ARGUMENT_ALIAS = "directive_arg"
ENGINE_FLUENTBIT = "fluentbit"
ENGINE_FLUENTD = "fluentd"

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
        KEY_ENUM: "string",
    }
    FLUENTBIT_UPSTREAM_DOC_PATH = (
        "/administration/configuring-fluent-bit/yaml/upstream-servers-section"
    )

    @staticmethod
    def _meta_schema() -> dict[str, Any]:
        return {
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_COMMENT_LINES: {
                    KEY_TYPE: "array",
                    KEY_ITEMS: {KEY_TYPE: "string"},
                },
                KEY_FIELD_COMMENT_LINES: {
                    KEY_TYPE: "object",
                    KEY_ADDITIONAL_PROPERTIES: {
                        KEY_TYPE: "array",
                        KEY_ITEMS: {KEY_TYPE: "string"},
                    },
                },
            },
            KEY_ADDITIONAL_PROPERTIES: False,
        }

    def _with_object_meta(self, schema: dict[str, Any]) -> dict[str, Any]:
        if schema.get(KEY_TYPE) != "object":
            return schema
        props = dict(schema.get(KEY_PROPERTIES, {}))
        props[KEY_META] = self._meta_schema()
        schema[KEY_PROPERTIES] = props
        return schema

    def compile_schema(
        self,
        catalog: dict[str, Any],
        strict_mode: bool = True,
        parser_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        engine = str(catalog.get(KEY_ENGINE) or ENGINE_FLUENTBIT).lower()
        if engine == ENGINE_FLUENTD:
            return self._compile_fluentd_schema(catalog, strict_mode=strict_mode)
        return self._compile_fluentbit_schema(
            catalog,
            strict_mode=strict_mode,
            parser_definition=parser_definition,
        )

    def _field_schema(self, field: dict[str, Any]) -> dict[str, Any]:
        catalog_data_type = str(field.get(KEY_DATA_TYPE, "string")).lower()
        json_type = self.TYPE_MAP.get(catalog_data_type, "string")
        payload: dict[str, Any] = {
            KEY_TYPE: json_type,
            KEY_DESCRIPTION: field.get(KEY_DESCRIPTION, ""),
            KEY_X_DOC_REFERENCE: field.get(KEY_REFERENCE, ""),
            KEY_X_DOC_REQUIRED: bool(field.get(KEY_REQUIRED, False)),
            KEY_X_CONFIG_DATA_TYPE: catalog_data_type,
            KEY_X_REFERENCES_PARSER: bool(field.get(KEY_REFERENCES_PARSER, False)),
        }
        enum_options = field.get(KEY_CALLED_ENUM_OPTIONS)
        if isinstance(enum_options, list) and enum_options:
            payload[KEY_ENUM] = list(enum_options)
        if KEY_DEFAULT in field:
            payload[KEY_DEFAULT] = field[KEY_DEFAULT]
        return payload

    @staticmethod
    def _directive_argument_names(directive_argument: dict[str, Any]) -> tuple[str, str | None]:
        configured_name = str(directive_argument.get(KEY_NAME) or "").strip()
        if not configured_name or configured_name == DIRECTIVE_ARGUMENT_ALIAS:
            return DIRECTIVE_ARGUMENT_ALIAS, None
        return configured_name, DIRECTIVE_ARGUMENT_ALIAS

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
        fluentbit_route: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        props: dict[str, Any] = {
            KEY_NAME: {KEY_TYPE: "string", KEY_CONST: plugin_name, KEY_TITLE: "Plugin"}
        }
        required = [KEY_NAME]
        all_of: list[dict[str, Any]] = []

        directive_arg = plugin_def.get(KEY_DIRECTIVE_ARGUMENT)
        if allow_directive_arg and isinstance(directive_arg, dict):
            canonical_name, alias_name = self._directive_argument_names(directive_arg)
            field_schema = self._field_schema(directive_arg)
            props[canonical_name] = field_schema
            if alias_name:
                props[alias_name] = dict(field_schema)
            if directive_arg.get(KEY_REQUIRED) is True:
                if alias_name:
                    all_of.append(
                        {
                            KEY_ANY_OF: [
                                {KEY_REQUIRED: [canonical_name]},
                                {KEY_REQUIRED: [alias_name]},
                            ]
                        }
                    )
                else:
                    required.append(canonical_name)

        for field in plugin_def.get(KEY_FIELDS, []):
            field_name = field[KEY_NAME]
            props[field_name] = self._field_schema(field)
            if field.get(KEY_REQUIRED) is True:
                required.append(field_name)

        if nested_sections and isinstance(plugin_def.get(KEY_ALLOWED_CHILDREN), list):
            child_props: dict[str, Any] = {}
            for child_meta in plugin_def[KEY_ALLOWED_CHILDREN]:
                section_name = child_meta.get(KEY_SECTION)
                if not isinstance(section_name, str) or section_name not in nested_sections:
                    continue
                child_schema = self._nested_section_items_schema(
                    section_name,
                    nested_sections[section_name],
                    strict_mode=strict_mode,
                    nested_sections=nested_sections,
                )
                child_props[section_name] = {KEY_TYPE: "array", KEY_ITEMS: child_schema}
            if child_props:
                child_props[KEY_INCLUDES] = {
                    KEY_TYPE: "array",
                    KEY_ITEMS: self._with_object_meta({
                        KEY_TYPE: "object",
                        KEY_PROPERTIES: {"path": {KEY_TYPE: "string"}},
                        KEY_REQUIRED: ["path"],
                        KEY_ADDITIONAL_PROPERTIES: False,
                    }),
                }
                props[KEY_CHILDREN] = self._with_object_meta({
                    KEY_TYPE: "object",
                    KEY_PROPERTIES: child_props,
                    KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                })

        if fluentbit_processors and fluentbit_section in {KEY_INPUTS, KEY_OUTPUTS}:
            processors_schema = self._fluentbit_processors_schema(
                fluentbit_processors,
                strict_mode=strict_mode,
                filter_plugins=fluentbit_filter_plugins,
            )
            props[KEY_PROCESSORS] = processors_schema
        if fluentbit_route and fluentbit_section == KEY_INPUTS:
            props[KEY_ROUTE] = self._fluentbit_route_schema(
                fluentbit_route,
                strict_mode=strict_mode,
            )

        schema = {
            KEY_TYPE: "object",
            KEY_TITLE: plugin_def.get(KEY_TITLE, plugin_name),
            KEY_PROPERTIES: props,
            KEY_REQUIRED: required,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        }
        if all_of:
            schema[KEY_ALL_OF] = all_of
        return self._with_object_meta(schema)

    @staticmethod
    def _fluentbit_doc_series_from_catalog(catalog: dict[str, Any]) -> str:
        """Return `<major>.<minor>` series used by versioned Fluent Bit doc URLs."""
        version = str(catalog.get(KEY_FLUENT_BIT_VERSION) or "")
        parts = version.split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}.{parts[1]}"
        return "5.0"

    def _fluentbit_upstream_doc_url(self, catalog: dict[str, Any]) -> str:
        """Build version-aware documentation URL for `upstream_servers`."""
        return (
            "https://docs.fluentbit.io/manual/"
            f"{self._fluentbit_doc_series_from_catalog(catalog)}"
            f"{self.FLUENTBIT_UPSTREAM_DOC_PATH}"
        )

    def _fluentbit_upstream_servers_schema(self, *, strict_mode: bool, catalog: dict[str, Any]) -> dict[str, Any]:
        """Schema for YAML `upstream_servers` root section supported in Fluent Bit v3.2+."""
        doc_url = self._fluentbit_upstream_doc_url(catalog)
        node_schema = self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_NAME: {
                    KEY_TYPE: "string",
                    KEY_DESCRIPTION: "Node identifier.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
                "host": {
                    KEY_TYPE: "string",
                    KEY_DESCRIPTION: "Host/IP address for the upstream node.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
                "port": {
                    KEY_TYPE: "integer",
                    KEY_DESCRIPTION: "TCP port for the upstream node endpoint.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
                "tls": {
                    KEY_TYPE: "boolean",
                    KEY_DESCRIPTION: "Enable TLS for this node connection.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
                "tls_verify": {
                    KEY_TYPE: "boolean",
                    KEY_DESCRIPTION: "Verify TLS peer certificate when TLS is enabled.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
                "shared_key": {
                    KEY_TYPE: "string",
                    KEY_DESCRIPTION: "Shared key for secured upstream communication.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
            },
            KEY_REQUIRED: [KEY_NAME, "host", "port"],
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })
        group_schema = self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_NAME: {
                    KEY_TYPE: "string",
                    KEY_DESCRIPTION: "Upstream group identifier.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
                "nodes": {
                    KEY_TYPE: "array",
                    KEY_ITEMS: node_schema,
                    KEY_DESCRIPTION: "List of upstream nodes used for round-robin routing.",
                    KEY_X_DOC_REFERENCE: doc_url,
                },
            },
            KEY_REQUIRED: [KEY_NAME, "nodes"],
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })
        return {
            KEY_TYPE: "array",
            KEY_ITEMS: group_schema,
            KEY_DESCRIPTION: "Root-level upstream server groups for output plugin load-balancing.",
            KEY_X_DOC_REFERENCE: doc_url,
        }

    def _compile_fluentbit_schema(
        self,
        catalog: dict[str, Any],
        *,
        strict_mode: bool,
        parser_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plugin_groups = catalog.get(KEY_PLUGINS, {})
        processors_def = catalog.get(KEY_COMMON, {}).get(KEY_PROCESSORS, {})
        route_def = catalog.get(KEY_COMMON, {}).get(KEY_ROUTE, {})

        def section_item_schema(section: str) -> dict[str, Any]:
            plugin_schemas = [
                self._plugin_schema(
                    plugin_name,
                    plugin_def,
                    strict_mode=strict_mode,
                    allow_directive_arg=False,
                    fluentbit_processors=processors_def,
                    fluentbit_section=section,
                    fluentbit_filter_plugins=plugin_groups.get(KEY_FILTERS, {}),
                    fluentbit_route=route_def,
                )
                for plugin_name, plugin_def in plugin_groups.get(section, {}).items()
            ]
            return {KEY_ONE_OF: plugin_schemas} if plugin_schemas else {KEY_TYPE: "object"}

        return self._with_object_meta({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_CONFIG: self._with_object_meta({
                    KEY_TYPE: "object",
                    KEY_PROPERTIES: {
                        "service": self._with_object_meta({
                            KEY_TYPE: "object",
                            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                        }),
                        "parsers": self._parser_list_schema(
                            parser_definition,
                            strict_mode=strict_mode,
                        ),
                        "upstream_servers": self._fluentbit_upstream_servers_schema(
                            strict_mode=strict_mode,
                            catalog=catalog,
                        ),
                        KEY_PIPELINE: self._with_object_meta({
                            KEY_TYPE: "object",
                            KEY_PROPERTIES: {
                                KEY_INPUTS: {KEY_TYPE: "array", KEY_ITEMS: section_item_schema(KEY_INPUTS)},
                                KEY_FILTERS: {KEY_TYPE: "array", KEY_ITEMS: section_item_schema(KEY_FILTERS)},
                                KEY_OUTPUTS: {KEY_TYPE: "array", KEY_ITEMS: section_item_schema(KEY_OUTPUTS)},
                            },
                            KEY_REQUIRED: [KEY_INPUTS, KEY_OUTPUTS],
                            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                        })
                    },
                    KEY_REQUIRED: [KEY_PIPELINE],
                    KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                }),
                "annotations": {
                    KEY_TYPE: "object",
                    KEY_ADDITIONAL_PROPERTIES: {KEY_TYPE: "string", "maxLength": 500},
                },
            },
            KEY_REQUIRED: [KEY_CONFIG],
            KEY_ADDITIONAL_PROPERTIES: False,
        })

    def _parser_list_schema(
        self,
        parser_definition: dict[str, Any] | None,
        *,
        strict_mode: bool,
    ) -> dict[str, Any]:
        if not parser_definition:
            return {KEY_TYPE: "array", KEY_ITEMS: {KEY_TYPE: "object"}}
        parser_formats = parser_definition.get(KEY_PARSER_FORMATS, {})
        if not isinstance(parser_formats, dict) or not parser_formats:
            return {KEY_TYPE: "array", KEY_ITEMS: {KEY_TYPE: "object"}}

        variants: list[dict[str, Any]] = []
        for format_name, format_payload in parser_formats.items():
            if not isinstance(format_payload, dict):
                continue
            props: dict[str, Any] = {
                KEY_NAME: {
                    KEY_TYPE: "string",
                    KEY_DESCRIPTION: "Sets the name of your parser.",
                },
                "format": {
                    KEY_TYPE: "string",
                    KEY_CONST: str(format_name),
                    KEY_DESCRIPTION: str(format_payload.get(KEY_DESCRIPTION) or ""),
                    KEY_X_DOC_REFERENCE: str(format_payload.get(KEY_DOC_URL) or ""),
                },
            }
            required = [KEY_NAME, "format"]
            for field in format_payload.get(KEY_FIELDS, []):
                props[field[KEY_NAME]] = self._field_schema(field)
                if field.get(KEY_REQUIRED) is True:
                    required.append(field[KEY_NAME])
            variants.append(
                self._with_object_meta({
                    KEY_TYPE: "object",
                    KEY_TITLE: str(format_payload.get(KEY_TITLE) or format_name),
                    KEY_PROPERTIES: props,
                    KEY_REQUIRED: required,
                    KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                })
            )
        return {
            KEY_TYPE: "array",
            KEY_ITEMS: {KEY_ONE_OF: variants} if variants else {KEY_TYPE: "object"},
        }

    def _fluentbit_processors_schema(
        self,
        processors_def: dict[str, Any],
        *,
        strict_mode: bool,
        filter_plugins: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        signal_props: dict[str, Any] = {}
        signals = processors_def.get(KEY_SIGNALS, {})
        for signal_name, signal_def in signals.items():
            variants = signal_def.get(KEY_PROCESSORS, {})
            item_schemas = [
                self._processor_variant_schema(name, variant, strict_mode=strict_mode, include_condition=bool(processors_def.get(KEY_CONDITION) and variant.get(KEY_SUPPORTS_CONDITION)))
                for name, variant in variants.items()
            ]
            if signal_name == "logs" and signal_def.get(KEY_ALLOW_FILTERS_AS_PROCESSORS) and filter_plugins:
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
                KEY_TYPE: "array",
                KEY_ITEMS: {KEY_ONE_OF: item_schemas} if item_schemas else {KEY_TYPE: "object"},
            }
        return self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: signal_props,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })

    def _fluentbit_route_schema(
        self,
        route_def: dict[str, Any],
        *,
        strict_mode: bool,
    ) -> dict[str, Any]:
        props: dict[str, Any] = {}
        for field in route_def.get(KEY_TOP_LEVEL_FIELDS, []):
            props[field[KEY_NAME]] = self._field_schema(field)

        route_entry_schema = self._fluentbit_route_entry_schema(
            route_def,
            strict_mode=strict_mode,
        )
        for signal in route_def.get(KEY_SIGNALS, []):
            signal_name = str(signal.get(KEY_NAME) or "").strip()
            if not signal_name:
                continue
            props[signal_name] = {
                KEY_TYPE: "array",
                KEY_ITEMS: route_entry_schema,
                KEY_DESCRIPTION: str(signal.get(KEY_DESCRIPTION) or ""),
            }
        return self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: props,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })

    def _fluentbit_route_entry_schema(
        self,
        route_def: dict[str, Any],
        *,
        strict_mode: bool,
    ) -> dict[str, Any]:
        route_props: dict[str, Any] = {}
        required: list[str] = []
        for field in route_def.get(KEY_ROUTE_FIELDS, []):
            route_props[field[KEY_NAME]] = self._field_schema(field)
            if field.get(KEY_REQUIRED) is True:
                required.append(field[KEY_NAME])

        condition_props: dict[str, Any] = {}
        for field in route_def.get(KEY_CONDITION_FIELDS, []):
            condition_props[field[KEY_NAME]] = self._field_schema(field)

        rule_props: dict[str, Any] = {}
        for field in route_def.get(KEY_RULE_FIELDS, []):
            if field[KEY_NAME] == KEY_VALUE:
                rule_props[KEY_VALUE] = {
                    KEY_DESCRIPTION: str(field.get(KEY_DESCRIPTION) or ""),
                    KEY_X_DOC_REFERENCE: str(field.get(KEY_REFERENCE) or ""),
                    KEY_X_DOC_REQUIRED: bool(field.get(KEY_REQUIRED, False)),
                    KEY_X_CONFIG_DATA_TYPE: str(field.get(KEY_DATA_TYPE) or "any"),
                    KEY_ANY_OF: [
                        {KEY_TYPE: "string"},
                        {KEY_TYPE: "number"},
                        {KEY_TYPE: "integer"},
                        {KEY_TYPE: "boolean"},
                        {KEY_TYPE: "array"},
                        {KEY_TYPE: "object"},
                        {KEY_TYPE: "null"},
                    ],
                }
            else:
                rule_props[field[KEY_NAME]] = self._field_schema(field)

        condition_props[KEY_RULES] = {
            KEY_TYPE: "array",
            KEY_ITEMS: self._with_object_meta({
                KEY_TYPE: "object",
                KEY_PROPERTIES: rule_props,
                KEY_REQUIRED: [
                    field[KEY_NAME]
                    for field in route_def.get(KEY_RULE_FIELDS, [])
                    if field.get(KEY_REQUIRED) is True
                ],
                KEY_ADDITIONAL_PROPERTIES: not strict_mode,
            }),
            KEY_DESCRIPTION: "Routing rules to evaluate for this route.",
        }

        route_props[KEY_CONDITION] = self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: condition_props,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })
        route_props[KEY_TO] = self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_OUTPUTS: {
                    KEY_TYPE: "array",
                    KEY_ITEMS: {KEY_TYPE: "string"},
                }
            },
            KEY_REQUIRED: [KEY_OUTPUTS],
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })
        required.extend([KEY_CONDITION, KEY_TO])

        return self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: route_props,
            KEY_REQUIRED: required,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
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
            KEY_NAME: {KEY_TYPE: "string", KEY_CONST: processor_name},
        }
        required = [KEY_NAME]
        for field in variant.get(KEY_FIELDS, []):
            props[field[KEY_NAME]] = self._field_schema(field)
            if field.get(KEY_REQUIRED) is True:
                required.append(field[KEY_NAME])
        if include_condition:
            props[KEY_CONDITION] = self._with_object_meta({
                KEY_TYPE: "object",
                KEY_PROPERTIES: {
                    KEY_OP: {
                        KEY_TYPE: "string",
                        KEY_ENUM: ["and", "or"],
                    },
                    KEY_RULES: {
                        KEY_TYPE: "array",
                        KEY_ITEMS: {KEY_TYPE: "object"},
                    },
                },
                KEY_REQUIRED: [KEY_OP, KEY_RULES],
                KEY_ADDITIONAL_PROPERTIES: not strict_mode,
            })
        return self._with_object_meta({
            KEY_TYPE: "object",
            KEY_TITLE: variant.get(KEY_TITLE, processor_name),
            KEY_PROPERTIES: props,
            KEY_REQUIRED: required,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })

    def _compile_fluentd_schema(self, catalog: dict[str, Any], strict_mode: bool) -> dict[str, Any]:
        plugin_groups = catalog.get(KEY_PLUGINS, {})
        nested_sections = catalog.get(KEY_NESTED_SECTIONS, {})
        root_sections = catalog.get(KEY_ROOT_SECTIONS, {})

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
            return {KEY_ONE_OF: plugin_schemas} if plugin_schemas else {KEY_TYPE: "object"}

        label_schema = self._root_container_schema(
            root_sections.get(KEY_LABELS, {}),
            strict_mode=strict_mode,
            include_labels=False,
            include_workers=False,
            plugin_groups=plugin_groups,
            nested_sections=nested_sections,
        )
        worker_schema = self._root_container_schema(
            root_sections.get(KEY_WORKERS, {}),
            strict_mode=strict_mode,
            include_labels=True,
            include_workers=False,
            plugin_groups=plugin_groups,
            nested_sections=nested_sections,
        )

        return self._with_object_meta({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_CONFIG: self._with_object_meta({
                    KEY_TYPE: "object",
                    KEY_PROPERTIES: {
                        "service": self._with_object_meta({
                            KEY_TYPE: "object",
                            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                        }),
                        KEY_INCLUDES: {
                            KEY_TYPE: "array",
                            KEY_ITEMS: {KEY_TYPE: "string"},
                        },
                        KEY_PIPELINE: self._with_object_meta({
                            KEY_TYPE: "object",
                            KEY_PROPERTIES: {
                                KEY_INPUTS: {KEY_TYPE: "array", KEY_ITEMS: main_section_schema(KEY_INPUTS)},
                                KEY_FILTERS: {KEY_TYPE: "array", KEY_ITEMS: main_section_schema(KEY_FILTERS)},
                                KEY_OUTPUTS: {KEY_TYPE: "array", KEY_ITEMS: main_section_schema(KEY_OUTPUTS)},
                            },
                            KEY_REQUIRED: [KEY_INPUTS, KEY_FILTERS, KEY_OUTPUTS],
                            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                        }),
                        KEY_LABELS: {KEY_TYPE: "array", KEY_ITEMS: label_schema},
                        KEY_WORKERS: {KEY_TYPE: "array", KEY_ITEMS: worker_schema},
                    },
                    KEY_REQUIRED: [KEY_PIPELINE],
                    KEY_ADDITIONAL_PROPERTIES: not strict_mode,
                }),
                "annotations": {
                    KEY_TYPE: "object",
                    KEY_ADDITIONAL_PROPERTIES: {KEY_TYPE: "string", "maxLength": 500},
                },
            },
            KEY_REQUIRED: [KEY_CONFIG],
            KEY_ADDITIONAL_PROPERTIES: False,
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
        for field in root_def.get(KEY_FIELDS, []):
            props[field[KEY_NAME]] = self._field_schema(field)
            if field.get(KEY_REQUIRED) is True:
                required.append(field[KEY_NAME])
        props[KEY_PIPELINE] = self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: {
                KEY_INPUTS: {
                    KEY_TYPE: "array",
                    KEY_ITEMS: {
                        KEY_ONE_OF: [
                            self._plugin_schema(
                                plugin_name,
                                plugin_def,
                                strict_mode=strict_mode,
                                nested_sections=nested_sections,
                            )
                            for plugin_name, plugin_def in plugin_groups.get(KEY_INPUTS, {}).items()
                        ]
                    },
                },
                KEY_FILTERS: {
                    KEY_TYPE: "array",
                    KEY_ITEMS: {
                        KEY_ONE_OF: [
                            self._plugin_schema(
                                plugin_name,
                                plugin_def,
                                strict_mode=strict_mode,
                                nested_sections=nested_sections,
                            )
                            for plugin_name, plugin_def in plugin_groups.get(KEY_FILTERS, {}).items()
                        ]
                    },
                },
                KEY_OUTPUTS: {
                    KEY_TYPE: "array",
                    KEY_ITEMS: {
                        KEY_ONE_OF: [
                            self._plugin_schema(
                                plugin_name,
                                plugin_def,
                                strict_mode=strict_mode,
                                nested_sections=nested_sections,
                            )
                            for plugin_name, plugin_def in plugin_groups.get(KEY_OUTPUTS, {}).items()
                        ]
                    },
                },
            },
            KEY_REQUIRED: [KEY_INPUTS, KEY_FILTERS, KEY_OUTPUTS],
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })
        props[KEY_INCLUDES] = {KEY_TYPE: "array", KEY_ITEMS: {KEY_TYPE: "string"}}
        if include_labels:
            props[KEY_LABELS] = {
                KEY_TYPE: "array",
                KEY_ITEMS: self._root_container_schema(
                    {KEY_FIELDS: [{KEY_NAME: KEY_NAME, KEY_REQUIRED: True, KEY_DESCRIPTION: "Label name", KEY_REFERENCE: "", KEY_DATA_TYPE: "string"}]},
                    strict_mode=strict_mode,
                    include_labels=False,
                    include_workers=False,
                    plugin_groups=plugin_groups,
                    nested_sections=nested_sections,
                ),
            }
        if include_workers:
            props[KEY_WORKERS] = {KEY_TYPE: "array", KEY_ITEMS: {KEY_TYPE: "object"}}
        return self._with_object_meta({
            KEY_TYPE: "object",
            KEY_PROPERTIES: props,
            KEY_REQUIRED: required,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        })

    def _nested_section_items_schema(
        self,
        section_name: str,
        nested_def: dict[str, Any],
        *,
        strict_mode: bool,
        nested_sections: dict[str, Any],
    ) -> dict[str, Any]:
        if nested_def.get(KEY_REUSES_OUTPUT_PLUGINS) is True:
            return self._with_object_meta({
                KEY_TYPE: "object",
                KEY_PROPERTIES: {
                    KEY_NAME: {KEY_TYPE: "string"},
                },
                KEY_REQUIRED: [KEY_NAME],
                KEY_ADDITIONAL_PROPERTIES: True,
            })
        if nested_def.get(KEY_PLUGIN_BACKED) is True:
            variants = nested_def.get(KEY_VARIANTS, {})
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
            return {KEY_ONE_OF: schemas} if schemas else {KEY_TYPE: "object"}

        props: dict[str, Any] = {}
        required: list[str] = []
        all_of: list[dict[str, Any]] = []
        directive_arg = nested_def.get(KEY_DIRECTIVE_ARGUMENT)
        if isinstance(directive_arg, dict):
            canonical_name, alias_name = self._directive_argument_names(directive_arg)
            field_schema = self._field_schema(directive_arg)
            props[canonical_name] = field_schema
            if alias_name:
                props[alias_name] = dict(field_schema)
            if directive_arg.get(KEY_REQUIRED) is True:
                if alias_name:
                    all_of.append(
                        {
                            KEY_ANY_OF: [
                                {KEY_REQUIRED: [canonical_name]},
                                {KEY_REQUIRED: [alias_name]},
                            ]
                        }
                    )
                else:
                    required.append(canonical_name)
        for field in nested_def.get(KEY_FIELDS, []):
            props[field[KEY_NAME]] = self._field_schema(field)
            if field.get(KEY_REQUIRED) is True:
                required.append(field[KEY_NAME])
        schema = {
            KEY_TYPE: "object",
            KEY_PROPERTIES: props,
            KEY_REQUIRED: required,
            KEY_ADDITIONAL_PROPERTIES: not strict_mode,
        }
        if all_of:
            schema[KEY_ALL_OF] = all_of
        return self._with_object_meta(schema)
