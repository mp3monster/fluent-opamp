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
            semantic_issues = self._validate_fluentbit_pipeline(config, catalog)
        rule_issues = self.rule_engine_service.evaluate(
            version=version,
            config=config,
            catalog=catalog,
            profile=profile,
        )
        errors = self._normalize_errors(semantic_issues + rule_issues)
        return {"ok": len(errors) == 0, "errors": errors}

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

    def _validate_fluentbit_pipeline(self, config: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
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

        plugins = catalog.get("plugins", {}).get("fluentbit", {})
        processors_def = catalog.get("common", {}).get("processors", {})
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
                )
            )
        return issues

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

        plugin_groups = catalog.get("plugins", {}).get("fluentd", {})
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
            if key in {"name", "directive_arg", "children", "processors"}:
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
                    if key in {"name", "condition"}:
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
