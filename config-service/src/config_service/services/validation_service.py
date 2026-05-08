from __future__ import annotations

from typing import Any

from config_service.services.rule_engine_service import RuleEngineService


class ValidationService:
    def __init__(self, rule_engine_service: RuleEngineService) -> None:
        self.rule_engine_service = rule_engine_service

    def validate(
        self,
        *,
        version: str,
        payload: dict[str, Any],
        catalog: dict[str, Any],
        profile: str | None,
        parser_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = payload.get("config")
        if not isinstance(config, dict):
            return {
                "ok": False,
                "errors": self._normalize_errors(
                    [
                        {
                            "code": "invalid_payload",
                            "path": "$.config",
                            "message": "Payload must include object 'config'.",
                            "severity": "error",
                            "source": "schema",
                        }
                    ]
                ),
            }

        engine = str(catalog.get("engine") or "fluentbit").lower()
        if engine == "fluentd":
            semantic_issues = self._validate_fluentd_config(config, catalog)
        else:
            semantic_issues = self._validate_fluentbit_pipeline(
                config,
                catalog,
                parser_definition=parser_definition,
            )
        rule_issues = self.rule_engine_service.evaluate(
            version=version,
            config=config,
            catalog=catalog,
            profile=profile,
        )
        errors = self._normalize_errors(semantic_issues + rule_issues)
        has_error = any(str(item.get("severity") or "error").lower() == "error" for item in errors)
        return {"ok": not has_error, "errors": errors}

    def _normalize_errors(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, issue in enumerate(issues, start=1):
            item = dict(issue)
            item["order"] = index
            item["code"] = str(item.get("code") or "unknown_issue")
            item["message"] = str(item.get("message") or "Validation issue")
            item["path"] = str(item.get("path") or "$")
            item["severity"] = str(item.get("severity") or "error")
            item["source"] = str(item.get("source") or "validation")
            normalized.append(item)
        return normalized

    def _validate_fluentbit_pipeline(
        self,
        config: dict[str, Any],
        catalog: dict[str, Any],
        *,
        parser_definition: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        parser_issues, custom_parser_names, builtin_parser_names = self._validate_fluentbit_parsers(
            config.get("parsers"),
            parser_definition,
        )
        issues.extend(parser_issues)
        pipeline = config.get("pipeline")
        if not isinstance(pipeline, dict):
            issues.append(
                {
                    "code": "missing_pipeline",
                    "path": "$.config.pipeline",
                    "message": "config.pipeline must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            )
            return issues

        plugins = catalog.get("plugins", {})
        processors_def = catalog.get("common", {}).get("processors", {})
        route_def = catalog.get("common", {}).get("route", {})
        for section in ("inputs", "filters", "outputs"):
            issues.extend(
                self._validate_plugin_list(
                    section_items=pipeline.get(section),
                    path_prefix=f"$.config.pipeline.{section}",
                    section=section,
                    plugins=plugins,
                    nested_sections={},
                    allow_children=False,
                    fluentbit_processors=processors_def,
                    fluentbit_filter_plugins=plugins.get("filters", {}),
                    known_parser_names=custom_parser_names | builtin_parser_names,
                    fluentbit_route=route_def,
                    pipeline=pipeline,
                )
            )
        return issues

    def _validate_fluentbit_parsers(
        self,
        parsers_payload: Any,
        parser_definition: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], set[str], set[str]]:
        issues: list[dict[str, Any]] = []
        custom_parser_names: set[str] = set()
        builtin_parser_names = (
            set(parser_definition.get("builtin_parser_names", []))
            if parser_definition
            else set()
        )
        if parsers_payload is None:
            return issues, custom_parser_names, builtin_parser_names
        if not isinstance(parsers_payload, list):
            return [
                {
                    "code": "invalid_section_type",
                    "path": "$.config.parsers",
                    "message": "parsers must be an array.",
                    "severity": "warning",
                    "source": "schema",
                }
            ], custom_parser_names, builtin_parser_names

        parser_formats = (
            parser_definition.get("parser_formats", {})
            if isinstance(parser_definition, dict)
            else {}
        )
        for idx, parser_instance in enumerate(parsers_payload):
            path = f"$.config.parsers[{idx}]"
            if not isinstance(parser_instance, dict):
                issues.append(
                    {
                        "code": "invalid_plugin_item",
                        "path": path,
                        "message": "Parser definition must be an object.",
                        "severity": "warning",
                        "source": "schema",
                    }
                )
                continue

            parser_name = parser_instance.get("name")
            if not isinstance(parser_name, str) or not parser_name:
                issues.append(
                    {
                        "code": "missing_required_field",
                        "path": f"{path}.name",
                        "message": "Parser definition requires a non-empty name.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
            elif parser_name in custom_parser_names:
                issues.append(
                    {
                        "code": "duplicate_parser_name",
                        "path": f"{path}.name",
                        "message": f"Parser name '{parser_name}' is defined more than once.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
            else:
                custom_parser_names.add(parser_name)

            parser_format = parser_instance.get("format")
            if not isinstance(parser_format, str) or not parser_format:
                issues.append(
                    {
                        "code": "missing_required_field",
                        "path": f"{path}.format",
                        "message": "Parser definition requires a non-empty format.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
                continue
            format_def = parser_formats.get(parser_format)
            if not isinstance(format_def, dict):
                issues.append(
                    {
                        "code": "unknown_parser_format",
                        "path": f"{path}.format",
                        "message": f"Unknown parser format '{parser_format}'.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
                continue
            fields = {field["name"]: field for field in format_def.get("fields", [])}
            for required in [
                name
                for name, field in fields.items()
                if field.get("required") is True
            ]:
                value = parser_instance.get(required)
                if value is None or (isinstance(value, str) and not value):
                    issues.append(
                        {
                            "code": "missing_required_field",
                            "path": f"{path}.{required}",
                            "message": f"Required field '{required}' is missing.",
                            "severity": "warning",
                            "source": "semantic",
                        }
                    )
            for key in parser_instance:
                if key in {"name", "format", "_meta"}:
                    continue
                if key not in fields:
                    issues.append(
                        {
                            "code": "unknown_field",
                            "path": f"{path}.{key}",
                            "message": f"Unknown field '{key}' for parser format '{parser_format}'.",
                            "severity": "warning",
                            "source": "semantic",
                        }
                    )
        return issues, custom_parser_names, builtin_parser_names

    def _validate_fluentd_config(self, config: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        pipeline = config.get("pipeline")
        if not isinstance(pipeline, dict):
            return [
                {
                    "code": "missing_pipeline",
                    "path": "$.config.pipeline",
                    "message": "config.pipeline must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            ]

        plugin_groups = catalog.get("plugins", {})
        nested_sections = catalog.get("nested_sections", {})
        for section in ("inputs", "filters", "outputs"):
            issues.extend(
                self._validate_plugin_list(
                    section_items=pipeline.get(section),
                    path_prefix=f"$.config.pipeline.{section}",
                    section=section,
                    plugins=plugin_groups,
                    nested_sections=nested_sections,
                    allow_children=True,
                    fluentbit_processors=None,
                    fluentbit_filter_plugins=None,
                    known_parser_names=set(),
                    fluentbit_route=None,
                    pipeline=pipeline,
                )
            )

        labels = config.get("labels", [])
        if labels is not None and not isinstance(labels, list):
            issues.append(
                {
                    "code": "invalid_section_type",
                    "path": "$.config.labels",
                    "message": "labels must be an array.",
                    "severity": "error",
                    "source": "schema",
                }
            )
        elif isinstance(labels, list):
            for idx, label in enumerate(labels):
                issues.extend(
                    self._validate_label_like(
                        label,
                        path_prefix=f"$.config.labels[{idx}]",
                        plugin_groups=plugin_groups,
                        nested_sections=nested_sections,
                    )
                )

        workers = config.get("workers", [])
        if workers is not None and not isinstance(workers, list):
            issues.append(
                {
                    "code": "invalid_section_type",
                    "path": "$.config.workers",
                    "message": "workers must be an array.",
                    "severity": "error",
                    "source": "schema",
                }
            )
        elif isinstance(workers, list):
            for idx, worker in enumerate(workers):
                issues.extend(
                    self._validate_worker(
                        worker,
                        path_prefix=f"$.config.workers[{idx}]",
                        plugin_groups=plugin_groups,
                        nested_sections=nested_sections,
                    )
                )
        return issues

    def _validate_label_like(
        self,
        payload: Any,
        *,
        path_prefix: str,
        plugin_groups: dict[str, Any],
        nested_sections: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not isinstance(payload, dict):
            return [
                {
                    "code": "invalid_plugin_item",
                    "path": path_prefix,
                    "message": "Label definition must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            ]
        if not isinstance(payload.get("name"), str) or not payload.get("name"):
            issues.append(
                {
                    "code": "missing_required_field",
                    "path": f"{path_prefix}.name",
                    "message": "Label definition requires a non-empty name.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
        pipeline = payload.get("pipeline", {})
        if not isinstance(pipeline, dict):
            issues.append(
                {
                    "code": "missing_pipeline",
                    "path": f"{path_prefix}.pipeline",
                    "message": "Label definition requires a pipeline object.",
                    "severity": "error",
                    "source": "schema",
                }
            )
            return issues
        for section in ("inputs", "filters", "outputs"):
            issues.extend(
                self._validate_plugin_list(
                    section_items=pipeline.get(section),
                    path_prefix=f"{path_prefix}.pipeline.{section}",
                    section=section,
                    plugins=plugin_groups,
                    nested_sections=nested_sections,
                    allow_children=True,
                    fluentbit_processors=None,
                    fluentbit_filter_plugins=None,
                    known_parser_names=set(),
                    fluentbit_route=None,
                    pipeline=pipeline,
                )
            )
        return issues

    def _validate_worker(
        self,
        payload: Any,
        *,
        path_prefix: str,
        plugin_groups: dict[str, Any],
        nested_sections: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues = self._validate_label_like(
            payload,
            path_prefix=path_prefix,
            plugin_groups=plugin_groups,
            nested_sections=nested_sections,
        )
        if isinstance(payload, dict):
            labels = payload.get("labels", [])
            if labels is not None and not isinstance(labels, list):
                issues.append(
                    {
                        "code": "invalid_section_type",
                        "path": f"{path_prefix}.labels",
                        "message": "Worker labels must be an array.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
            elif isinstance(labels, list):
                for idx, label in enumerate(labels):
                    issues.extend(
                        self._validate_label_like(
                            label,
                            path_prefix=f"{path_prefix}.labels[{idx}]",
                            plugin_groups=plugin_groups,
                            nested_sections=nested_sections,
                        )
                    )
        return issues

    def _validate_plugin_list(
        self,
        *,
        section_items: Any,
        path_prefix: str,
        section: str,
        plugins: dict[str, Any],
        nested_sections: dict[str, Any],
        allow_children: bool,
        fluentbit_processors: dict[str, Any] | None,
        fluentbit_filter_plugins: dict[str, Any] | None,
        known_parser_names: set[str],
        fluentbit_route: dict[str, Any] | None,
        pipeline: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if section_items is None:
            return issues
        if not isinstance(section_items, list):
            return [
                {
                    "code": "invalid_section_type",
                    "path": path_prefix,
                    "message": f"{section} must be an array.",
                    "severity": "error",
                    "source": "schema",
                }
            ]
        for idx, plugin_instance in enumerate(section_items):
            path = f"{path_prefix}[{idx}]"
            if not isinstance(plugin_instance, dict):
                issues.append(
                    {
                        "code": "invalid_plugin_item",
                        "path": path,
                        "message": "Plugin instance must be an object.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
                continue
            plugin_name = plugin_instance.get("name")
            if not isinstance(plugin_name, str) or not plugin_name:
                issues.append(
                    {
                        "code": "missing_plugin_name",
                        "path": f"{path}.name",
                        "message": "Plugin instance requires a non-empty 'name'.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
                continue
            plugin_def = plugins.get(section, {}).get(plugin_name)
            if plugin_def is None:
                issues.append(
                    {
                        "code": "unknown_plugin",
                        "path": f"{path}.name",
                        "message": f"Unknown plugin '{plugin_name}' in section '{section}'.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
                continue
            issues.extend(
                self._validate_plugin_instance(
                    path,
                    plugin_instance,
                    plugin_def,
                    nested_sections,
                    allow_children,
                    fluentbit_processors=fluentbit_processors,
                    fluentbit_filter_plugins=fluentbit_filter_plugins,
                    section=section,
                    known_parser_names=known_parser_names,
                    fluentbit_route=fluentbit_route,
                    pipeline=pipeline,
                )
            )
        return issues

    def _validate_plugin_instance(
        self,
        path: str,
        plugin_instance: dict[str, Any],
        plugin_def: dict[str, Any],
        nested_sections: dict[str, Any],
        allow_children: bool,
        fluentbit_processors: dict[str, Any] | None,
        fluentbit_filter_plugins: dict[str, Any] | None,
        section: str,
        known_parser_names: set[str],
        fluentbit_route: dict[str, Any] | None,
        pipeline: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        fields = {field["name"]: field for field in plugin_def.get("fields", [])}
        directive_arg = plugin_def.get("directive_argument")
        if isinstance(directive_arg, dict) and directive_arg.get("required") is True and "directive_arg" not in plugin_instance:
            issues.append(
                {
                    "code": "missing_required_field",
                    "path": f"{path}.directive_arg",
                    "message": "Required directive argument is missing.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
        for required in [name for name, field in fields.items() if field.get("required") is True]:
            if required not in plugin_instance:
                issues.append(
                    {
                        "code": "missing_required_field",
                        "path": f"{path}.{required}",
                        "message": f"Required field '{required}' is missing.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
        for key in plugin_instance:
            if key in {"name", "directive_arg", "children", "processors", "route", "_meta"}:
                continue
            if key not in fields:
                issues.append(
                    {
                        "code": "unknown_field",
                        "path": f"{path}.{key}",
                        "message": f"Unknown field '{key}' for plugin '{plugin_instance.get('name')}'.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
        issues.extend(
            self._validate_parser_references(
                path=path,
                plugin_instance=plugin_instance,
                fields=fields,
                known_parser_names=known_parser_names,
            )
        )
        if allow_children:
            issues.extend(self._validate_children(path, plugin_instance, plugin_def, nested_sections))
        if fluentbit_processors and section in {"inputs", "outputs"}:
            issues.extend(
                self._validate_fluentbit_processors(
                    path=path,
                    plugin_instance=plugin_instance,
                    processors_def=fluentbit_processors,
                    filter_plugins=fluentbit_filter_plugins or {},
                )
            )
        if fluentbit_route and section == "inputs":
            issues.extend(
                self._validate_fluentbit_route(
                    path=path,
                    plugin_instance=plugin_instance,
                    route_def=fluentbit_route,
                    outputs=pipeline.get("outputs") if isinstance(pipeline, dict) else [],
                )
            )
        return issues

    def _validate_parser_references(
        self,
        *,
        path: str,
        plugin_instance: dict[str, Any],
        fields: dict[str, dict[str, Any]],
        known_parser_names: set[str],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not known_parser_names:
            return issues
        for field_name, field_def in fields.items():
            if field_def.get("references_parser") is not True:
                continue
            value = plugin_instance.get(field_name)
            if not isinstance(value, str) or not value:
                continue
            if value not in known_parser_names:
                issues.append(
                    {
                        "code": "unknown_parser_reference",
                        "path": f"{path}.{field_name}",
                        "message": f"Parser '{value}' was not found in the defined parsers or known built-in parser names.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
        return issues

    def _validate_fluentbit_processors(
        self,
        *,
        path: str,
        plugin_instance: dict[str, Any],
        processors_def: dict[str, Any],
        filter_plugins: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        processors = plugin_instance.get("processors")
        if processors is None:
            return issues
        if not isinstance(processors, dict):
            return [
                {
                    "code": "invalid_section_type",
                    "path": f"{path}.processors",
                    "message": "processors must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            ]
        signals = processors_def.get("signals", {})
        for signal_name, items in processors.items():
            signal_path = f"{path}.processors.{signal_name}"
            signal_def = signals.get(signal_name)
            if signal_def is None:
                issues.append(
                    {
                        "code": "unknown_nested_section",
                        "path": signal_path,
                        "message": f"Unknown processors signal '{signal_name}'.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
                continue
            if not isinstance(items, list):
                issues.append(
                    {
                        "code": "invalid_section_type",
                        "path": signal_path,
                        "message": "Signal processors must be an array.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
                continue
            available = dict(signal_def.get("processors", {}))
            if signal_name == "logs" and signal_def.get("allow_filters_as_processors"):
                available.update(filter_plugins)
            for idx, processor in enumerate(items):
                proc_path = f"{signal_path}[{idx}]"
                if not isinstance(processor, dict):
                    issues.append(
                        {
                            "code": "invalid_plugin_item",
                            "path": proc_path,
                            "message": "Processor entry must be an object.",
                            "severity": "error",
                            "source": "schema",
                        }
                    )
                    continue
                proc_name = processor.get("name")
                if not isinstance(proc_name, str) or not proc_name:
                    issues.append(
                        {
                            "code": "missing_plugin_name",
                            "path": f"{proc_path}.name",
                            "message": "Processor requires a non-empty 'name'.",
                            "severity": "error",
                            "source": "schema",
                        }
                    )
                    continue
                proc_def = available.get(proc_name)
                if proc_def is None:
                    issues.append(
                        {
                            "code": "unknown_plugin",
                            "path": f"{proc_path}.name",
                            "message": f"Unknown processor '{proc_name}' for signal '{signal_name}'.",
                            "severity": "error",
                            "source": "semantic",
                        }
                    )
                    continue
                fields = {field["name"]: field for field in proc_def.get("fields", [])}
                for required in [name for name, field in fields.items() if field.get("required") is True]:
                    if required not in processor:
                        issues.append(
                            {
                                "code": "missing_required_field",
                                "path": f"{proc_path}.{required}",
                                "message": f"Required field '{required}' is missing.",
                                "severity": "error",
                                "source": "semantic",
                            }
                        )
                for key in processor:
                    if key in {"name", "condition", "_meta"}:
                        continue
                    if key not in fields:
                        issues.append(
                            {
                                "code": "unknown_field",
                                "path": f"{proc_path}.{key}",
                                "message": f"Unknown field '{key}' for processor '{proc_name}'.",
                                "severity": "warning",
                                "source": "semantic",
                            }
                        )
                if "condition" in processor:
                    if not proc_def.get("supports_condition"):
                        issues.append(
                            {
                                "code": "unknown_field",
                                "path": f"{proc_path}.condition",
                                "message": f"Processor '{proc_name}' does not support conditional processing.",
                                "severity": "warning",
                                "source": "semantic",
                            }
                        )
                    elif not isinstance(processor["condition"], dict):
                        issues.append(
                            {
                                "code": "invalid_section_type",
                                "path": f"{proc_path}.condition",
                                "message": "condition must be an object.",
                                "severity": "error",
                                "source": "schema",
                            }
                        )
        return issues

    def _validate_fluentbit_route(
        self,
        *,
        path: str,
        plugin_instance: dict[str, Any],
        route_def: dict[str, Any],
        outputs: Any,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        route_payload = plugin_instance.get("route")
        if route_payload is None:
            return issues
        if not isinstance(route_payload, dict):
            return [
                {
                    "code": "invalid_section_type",
                    "path": f"{path}.route",
                    "message": "route must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            ]

        top_level_fields = {
            field["name"]: field
            for field in route_def.get("top_level_fields", [])
            if isinstance(field, dict) and isinstance(field.get("name"), str)
        }
        allowed_signals = {
            str(signal.get("name")): signal
            for signal in route_def.get("signals", [])
            if isinstance(signal, dict) and isinstance(signal.get("name"), str)
        }
        seen_route_names: set[str] = set()
        available_output_refs = self._route_output_reference_names(outputs)
        has_any_routes = False

        for key, value in route_payload.items():
            if key == "_meta":
                continue
            if key in top_level_fields:
                if key == "per_record_routing" and not isinstance(value, bool):
                    issues.append(
                        {
                            "code": "invalid_route_field_type",
                            "path": f"{path}.route.per_record_routing",
                            "message": "per_record_routing must be true or false.",
                            "severity": "error",
                            "source": "schema",
                        }
                    )
                continue

            signal_meta = allowed_signals.get(key)
            if signal_meta is None:
                issues.append(
                    {
                        "code": "unknown_route_signal",
                        "path": f"{path}.route.{key}",
                        "message": f"Unknown route signal '{key}'.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )
                continue

            if not isinstance(value, list):
                issues.append(
                    {
                        "code": "invalid_section_type",
                        "path": f"{path}.route.{key}",
                        "message": f"Route signal '{key}' must be an array.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
                continue

            if value:
                has_any_routes = True
            if signal_meta.get("implemented") is False:
                issues.append(
                    {
                        "code": "route_signal_not_fully_supported",
                        "path": f"{path}.route.{key}",
                        "message": f"Signal '{key}' is parsed by Fluent Bit but is not fully evaluated yet.",
                        "severity": "warning",
                        "source": "semantic",
                    }
                )

            for idx, route_item in enumerate(value):
                issues.extend(
                    self._validate_route_item(
                        route_item,
                        path_prefix=f"{path}.route.{key}[{idx}]",
                        seen_route_names=seen_route_names,
                        available_output_refs=available_output_refs,
                    )
                )

        if has_any_routes and route_payload.get("per_record_routing") is not True:
            issues.append(
                {
                    "code": "route_not_enabled",
                    "path": f"{path}.route.per_record_routing",
                    "message": "Conditional routing rules are defined but per_record_routing is not enabled.",
                    "severity": "warning",
                    "source": "semantic",
                }
            )
        return issues

    def _validate_route_item(
        self,
        route_item: Any,
        *,
        path_prefix: str,
        seen_route_names: set[str],
        available_output_refs: set[str],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not isinstance(route_item, dict):
            return [
                {
                    "code": "invalid_plugin_item",
                    "path": path_prefix,
                    "message": "Route entry must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            ]

        route_name = route_item.get("name")
        if not isinstance(route_name, str) or not route_name:
            issues.append(
                {
                    "code": "missing_required_field",
                    "path": f"{path_prefix}.name",
                    "message": "Route entry requires a non-empty name.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
        elif route_name in seen_route_names:
            issues.append(
                {
                    "code": "duplicate_route_name",
                    "path": f"{path_prefix}.name",
                    "message": f"Route name '{route_name}' is defined more than once.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
        else:
            seen_route_names.add(route_name)

        condition = route_item.get("condition")
        if not isinstance(condition, dict):
            issues.append(
                {
                    "code": "missing_required_field",
                    "path": f"{path_prefix}.condition",
                    "message": "Route entry requires a condition object.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
        else:
            issues.extend(
                self._validate_route_condition(
                    condition,
                    path_prefix=f"{path_prefix}.condition",
                )
            )

        destination = route_item.get("to")
        if not isinstance(destination, dict):
            issues.append(
                {
                    "code": "missing_required_field",
                    "path": f"{path_prefix}.to",
                    "message": "Route entry requires a to object.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
        else:
            route_outputs = destination.get("outputs")
            if not isinstance(route_outputs, list) or not route_outputs:
                issues.append(
                    {
                        "code": "missing_required_field",
                        "path": f"{path_prefix}.to.outputs",
                        "message": "Route entry requires at least one output destination.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
            else:
                for idx, output_name in enumerate(route_outputs):
                    output_path = f"{path_prefix}.to.outputs[{idx}]"
                    if not isinstance(output_name, str) or not output_name:
                        issues.append(
                            {
                                "code": "invalid_route_output_reference",
                                "path": output_path,
                                "message": "Route output reference must be a non-empty string.",
                                "severity": "error",
                                "source": "schema",
                            }
                        )
                        continue
                    if available_output_refs and output_name not in available_output_refs:
                        issues.append(
                            {
                                "code": "unknown_route_output_reference",
                                "path": output_path,
                                "message": f"Route output '{output_name}' was not found in the configured outputs by name or alias.",
                                "severity": "warning",
                                "source": "semantic",
                            }
                        )
        return issues

    def _validate_route_condition(
        self,
        condition: dict[str, Any],
        *,
        path_prefix: str,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if condition.get("default") is True:
            return issues

        op = condition.get("op")
        if op not in {"and", "or"}:
            issues.append(
                {
                    "code": "invalid_route_condition_operator",
                    "path": f"{path_prefix}.op",
                    "message": "Route condition operator must be 'and' or 'or'.",
                    "severity": "error",
                    "source": "semantic",
                }
            )

        rules = condition.get("rules")
        if not isinstance(rules, list) or not rules:
            issues.append(
                {
                    "code": "missing_required_field",
                    "path": f"{path_prefix}.rules",
                    "message": "Route condition requires at least one rule unless it is marked as default.",
                    "severity": "error",
                    "source": "semantic",
                }
            )
            return issues

        valid_contexts = {
            "body",
            "group_attributes",
            "group_metadata",
            "metadata",
            "otel_resource_attributes",
            "otel_scope_attributes",
            "otel_scope_metadata",
        }
        valid_ops = {
            "eq",
            "gt",
            "gte",
            "in",
            "lt",
            "lte",
            "neq",
            "not_in",
            "not_regex",
            "regex",
        }
        for idx, rule in enumerate(rules):
            rule_path = f"{path_prefix}.rules[{idx}]"
            if not isinstance(rule, dict):
                issues.append(
                    {
                        "code": "invalid_plugin_item",
                        "path": rule_path,
                        "message": "Route condition rule must be an object.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
                continue
            if "context" in rule and rule.get("context") not in valid_contexts:
                issues.append(
                    {
                        "code": "invalid_route_context",
                        "path": f"{rule_path}.context",
                        "message": f"Unknown route rule context '{rule.get('context')}'.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
            if not isinstance(rule.get("field"), str) or not rule.get("field"):
                issues.append(
                    {
                        "code": "missing_required_field",
                        "path": f"{rule_path}.field",
                        "message": "Route rule requires a non-empty field.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
            if rule.get("op") not in valid_ops:
                issues.append(
                    {
                        "code": "invalid_route_rule_operator",
                        "path": f"{rule_path}.op",
                        "message": f"Unknown route rule operator '{rule.get('op')}'.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
            if "value" not in rule:
                issues.append(
                    {
                        "code": "missing_required_field",
                        "path": f"{rule_path}.value",
                        "message": "Route rule requires a comparison value.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
        return issues

    def _route_output_reference_names(self, outputs: Any) -> set[str]:
        names: set[str] = set()
        if not isinstance(outputs, list):
            return names
        counters: dict[str, int] = {}
        for output in outputs:
            if not isinstance(output, dict):
                continue
            plugin_name = output.get("name")
            if isinstance(plugin_name, str) and plugin_name:
                names.add(plugin_name)
                sequence = counters.get(plugin_name, 0)
                names.add(f"{plugin_name}.{sequence}")
                counters[plugin_name] = sequence + 1
            alias = output.get("alias")
            if isinstance(alias, str) and alias:
                names.add(alias)
        return names

    def _validate_children(
        self,
        path: str,
        plugin_instance: dict[str, Any],
        plugin_def: dict[str, Any],
        nested_sections: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        children = plugin_instance.get("children")
        if children is None:
            return issues
        if not isinstance(children, dict):
            return [
                {
                    "code": "invalid_section_type",
                    "path": f"{path}.children",
                    "message": "children must be an object.",
                    "severity": "error",
                    "source": "schema",
                }
            ]
        allowed = {
            item["section"]: item
            for item in plugin_def.get("allowed_children", [])
            if isinstance(item, dict) and isinstance(item.get("section"), str)
        }
        for child_name, child_items in children.items():
            if child_name == "includes":
                continue
            if child_name not in allowed:
                issues.append(
                    {
                        "code": "unknown_nested_section",
                        "path": f"{path}.children.{child_name}",
                        "message": f"Nested section '{child_name}' is not allowed for plugin '{plugin_instance.get('name')}'.",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
                continue
            if not isinstance(child_items, list):
                issues.append(
                    {
                        "code": "invalid_section_type",
                        "path": f"{path}.children.{child_name}",
                        "message": f"Nested section '{child_name}' must be an array.",
                        "severity": "error",
                        "source": "schema",
                    }
                )
                continue
            nested_def = nested_sections.get(child_name, {})
            card = allowed[child_name].get("cardinality", {})
            maximum = card.get("maximum")
            if isinstance(maximum, int) and len(child_items) > maximum:
                issues.append(
                    {
                        "code": "nested_cardinality_exceeded",
                        "path": f"{path}.children.{child_name}",
                        "message": f"Nested section '{child_name}' allows at most {maximum} item(s).",
                        "severity": "error",
                        "source": "semantic",
                    }
                )
            if nested_def.get("reuses_output_plugins") is True:
                continue
            fields = {
                field["name"]: field
                for field in nested_def.get("fields", [])
                if isinstance(field, dict)
            }
            variants = nested_def.get("variants", {})
            for idx, child_item in enumerate(child_items):
                if not isinstance(child_item, dict):
                    issues.append(
                        {
                            "code": "invalid_plugin_item",
                            "path": f"{path}.children.{child_name}[{idx}]",
                            "message": "Nested section item must be an object.",
                            "severity": "error",
                            "source": "schema",
                        }
                    )
                    continue
                if nested_def.get("plugin_backed") is True and variants and "name" not in child_item:
                    issues.append(
                        {
                            "code": "missing_plugin_name",
                            "path": f"{path}.children.{child_name}[{idx}].name",
                            "message": "Nested plugin section requires a non-empty 'name'.",
                            "severity": "error",
                            "source": "semantic",
                        }
                    )
                    continue
                if nested_def.get("plugin_backed") is True and variants:
                    variant = variants.get(child_item.get("name"))
                    if variant is None:
                        issues.append(
                            {
                                "code": "unknown_plugin",
                                "path": f"{path}.children.{child_name}[{idx}].name",
                                "message": f"Unknown nested plugin '{child_item.get('name')}' in section '{child_name}'.",
                                "severity": "error",
                                "source": "semantic",
                            }
                        )
                        continue
                    required_fields = [f["name"] for f in variant.get("fields", []) if f.get("required") is True]
                else:
                    required_fields = [name for name, field in fields.items() if field.get("required") is True]
                for required in required_fields:
                    if required not in child_item:
                        issues.append(
                            {
                                "code": "missing_required_field",
                                "path": f"{path}.children.{child_name}[{idx}].{required}",
                                "message": f"Required field '{required}' is missing.",
                                "severity": "error",
                                "source": "semantic",
                            }
                        )
        return issues
