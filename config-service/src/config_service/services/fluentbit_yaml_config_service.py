from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

_PIPELINE_SECTIONS = ("inputs", "filters", "outputs")


class _FluentBitYamlLoader(yaml.SafeLoader):
    """YAML loader that keeps Fluent Bit string-ish scalars as strings.

    Fluent Bit YAML examples commonly use unquoted values like:
    - name: null
    - daemon: on
    - http_server: off

    In generic YAML these can be coerced into null/booleans, but for
    Fluent Bit they are often intended as literal strings.
    """


for _first_char, _resolver_mappings in list(_FluentBitYamlLoader.yaml_implicit_resolvers.items()):
    _FluentBitYamlLoader.yaml_implicit_resolvers[_first_char] = [
        (tag, regexp)
        for tag, regexp in _resolver_mappings
        if tag not in {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:null"}
    ]


def _issue(
    order: int,
    code: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    source: str = "parser",
) -> dict[str, Any]:
    return {
        "order": order,
        "code": code,
        "path": path,
        "message": message,
        "severity": severity,
        "source": source,
    }


class FluentBitYamlConfigService:
    """Parse Fluent Bit YAML config into the internal document model."""

    def parse(self, text: str) -> dict[str, Any]:
        if not str(text or "").strip():
            raise ValueError("The Fluent Bit YAML file is empty.")

        try:
            loaded = yaml.load(text, Loader=_FluentBitYamlLoader)
        except yaml.YAMLError as exc:
            raise ValueError(f"Fluent Bit YAML could not be parsed: {exc}") from exc

        if loaded is None:
            raise ValueError("The Fluent Bit YAML file is empty.")
        if not isinstance(loaded, dict):
            raise ValueError("The Fluent Bit YAML root must be a mapping/object.")

        config: dict[str, Any] = {
            "service": {},
            "pipeline": {"inputs": [], "filters": [], "outputs": []},
            "labels": [],
            "workers": [],
            "includes": [],
        }
        errors: list[dict[str, Any]] = []
        order = 1

        for key, value in loaded.items():
            if key == "service":
                if isinstance(value, dict):
                    config["service"] = deepcopy(value)
                else:
                    errors.append(
                        _issue(
                            order,
                            "fluentbit_yaml_invalid_section",
                            "$.service",
                            "Ignored service section because it is not a mapping/object.",
                        )
                    )
                    order += 1
                continue

            if key == "pipeline":
                pipeline_payload, pipeline_errors = self._parse_pipeline(value, order)
                config["pipeline"] = pipeline_payload
                errors.extend(pipeline_errors)
                order += len(pipeline_errors)
                continue

            errors.append(
                _issue(
                    order,
                    "fluentbit_yaml_ignored_section",
                    f"$.{key}",
                    f"Ignored unsupported Fluent Bit YAML section '{key}'.",
                )
            )
            order += 1

        return {
            "config": config,
            "errors": errors,
            "ok": len(errors) == 0,
        }

    def _parse_pipeline(self, payload: Any, start_order: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        pipeline = {"inputs": [], "filters": [], "outputs": []}
        errors: list[dict[str, Any]] = []
        order = start_order

        if not isinstance(payload, dict):
            errors.append(
                _issue(
                    order,
                    "fluentbit_yaml_invalid_section",
                    "$.pipeline",
                    "Ignored pipeline section because it is not a mapping/object.",
                )
            )
            return pipeline, errors

        for section_name, section_value in payload.items():
            if section_name not in _PIPELINE_SECTIONS:
                errors.append(
                    _issue(
                        order,
                        "fluentbit_yaml_ignored_section",
                        f"$.pipeline.{section_name}",
                        f"Ignored unsupported pipeline section '{section_name}'.",
                    )
                )
                order += 1
                continue

            if not isinstance(section_value, list):
                errors.append(
                    _issue(
                        order,
                        "fluentbit_yaml_invalid_section",
                        f"$.pipeline.{section_name}",
                        f"Ignored pipeline section '{section_name}' because it is not a list.",
                    )
                )
                order += 1
                continue

            for index, item in enumerate(section_value):
                item_path = f"$.pipeline.{section_name}[{index}]"
                if not isinstance(item, dict):
                    errors.append(
                        _issue(
                            order,
                            "fluentbit_yaml_invalid_plugin",
                            item_path,
                            f"Ignored {section_name[:-1]} entry at index {index} because it is not an object.",
                        )
                    )
                    order += 1
                    continue
                if not str(item.get("name") or "").strip():
                    errors.append(
                        _issue(
                            order,
                            "missing_plugin_name",
                            item_path,
                            f"Ignored {section_name[:-1]} entry at index {index} because it does not define a plugin name.",
                        )
                    )
                    order += 1
                    continue
                pipeline[section_name].append(deepcopy(item))

        return pipeline, errors
