from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CatalogService:
    """Loads and validates versioned plugin catalogs by configuration type."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self._registry: dict[str, Any] = {}
        self._catalogs_by_type: dict[str, dict[str, dict[str, Any]]] = {}
        self._load_registry()

    @staticmethod
    def _repo_root() -> Path:
        # config-service/config_service/services -> repo root is 3 parents up.
        return Path(__file__).resolve().parents[3]

    def _resolve_catalog_path(self, catalog_ref: str) -> Path:
        candidate = Path(catalog_ref)
        if candidate.is_absolute():
            return candidate
        return self._repo_root() / catalog_ref

    def _load_registry(self) -> None:
        self._registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        catalogs_by_type = self._registry_catalogs_by_type()
        if not catalogs_by_type:
            raise ValueError("catalog-registry.json must define at least one catalog group")

    def _registry_catalogs_by_type(self) -> dict[str, dict[str, str]]:
        grouped = self._registry.get("catalogs_by_type")
        if isinstance(grouped, dict) and grouped:
            normalized: dict[str, dict[str, str]] = {}
            for config_type, catalogs in grouped.items():
                if isinstance(catalogs, dict) and catalogs:
                    normalized[str(config_type)] = {str(version): str(path) for version, path in catalogs.items()}
            return normalized

        catalogs = self._registry.get("catalogs", {})
        if isinstance(catalogs, dict) and catalogs:
            return {"fluentbit": {str(version): str(path) for version, path in catalogs.items()}}
        return {}

    def load_all_catalogs(self) -> None:
        loaded: dict[str, dict[str, dict[str, Any]]] = {}
        for config_type, version_map in self._registry_catalogs_by_type().items():
            loaded[config_type] = {}
            for version, catalog_ref in version_map.items():
                path = self._resolve_catalog_path(catalog_ref)
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.validate_catalog_payload(version, payload, source=str(path))
                loaded[config_type][version] = payload
        self._catalogs_by_type = loaded

    def validate_catalog_payload(self, version: str, payload: dict[str, Any], source: str = "<in-memory>") -> None:
        engine = str(payload.get("engine") or "fluentbit").lower()
        top_required = {"plugins", "custom_plugins"}
        if engine == "fluentbit":
            top_required.add("fluent_bit_version")
        elif engine == "fluentd":
            top_required.update({"fluentd_version", "nested_sections", "root_sections"})
        missing = [key for key in top_required if key not in payload]
        if missing:
            raise ValueError(f"Catalog {version} missing required keys {missing} ({source})")

        plugins = payload.get("plugins")
        expected_group = "fluentbit" if engine == "fluentbit" else "fluentd"
        if not isinstance(plugins, dict) or expected_group not in plugins:
            raise ValueError(f"Catalog {version} must include plugins.{expected_group} ({source})")

        engine_plugins = plugins[expected_group]
        for section in ("inputs", "filters", "outputs"):
            section_map = engine_plugins.get(section)
            if not isinstance(section_map, dict):
                raise ValueError(f"Catalog {version} section {section} must be an object ({source})")
            for plugin_name, plugin_def in section_map.items():
                if "fields" not in plugin_def or not isinstance(plugin_def["fields"], list):
                    raise ValueError(
                        f"Catalog {version} plugin {section}.{plugin_name} must define list 'fields' ({source})"
                    )
                for idx, field in enumerate(plugin_def["fields"]):
                    for req in ("name", "required", "description", "reference", "data_type"):
                        if req not in field:
                            raise ValueError(
                                f"Catalog {version} plugin {section}.{plugin_name} field[{idx}] missing {req} ({source})"
                            )
                directive_argument = plugin_def.get("directive_argument")
                if directive_argument is not None:
                    self._validate_field_like(
                        version=version,
                        field=directive_argument,
                        source=source,
                        context=f"plugin {section}.{plugin_name} directive_argument",
                    )

        if engine == "fluentd":
            nested_sections = payload.get("nested_sections")
            if not isinstance(nested_sections, dict):
                raise ValueError(f"Catalog {version} nested_sections must be an object ({source})")
            for nested_name, nested_def in nested_sections.items():
                if not isinstance(nested_def, dict):
                    raise ValueError(
                        f"Catalog {version} nested section {nested_name} must be an object ({source})"
                    )
                if nested_def.get("plugin_backed") is True:
                    variants = nested_def.get("variants")
                    if nested_def.get("reuses_output_plugins") is True:
                        continue
                    if not isinstance(variants, dict) or not variants:
                        raise ValueError(
                            f"Catalog {version} nested section {nested_name} must define variants ({source})"
                        )
                    for variant_name, variant_def in variants.items():
                        if not isinstance(variant_def, dict) or not isinstance(
                            variant_def.get("fields"), list
                        ):
                            raise ValueError(
                                f"Catalog {version} nested section {nested_name}.{variant_name} "
                                f"must define list 'fields' ({source})"
                            )
                        for idx, field in enumerate(variant_def["fields"]):
                            self._validate_field_like(
                                version=version,
                                field=field,
                                source=source,
                                context=f"nested section {nested_name}.{variant_name} field[{idx}]",
                            )
                else:
                    fields = nested_def.get("fields")
                    if not isinstance(fields, list):
                        raise ValueError(
                            f"Catalog {version} nested section {nested_name} must define list 'fields' ({source})"
                        )
                    for idx, field in enumerate(fields):
                        self._validate_field_like(
                            version=version,
                            field=field,
                            source=source,
                            context=f"nested section {nested_name} field[{idx}]",
                        )

    def _validate_field_like(
        self,
        *,
        version: str,
        field: dict[str, Any],
        source: str,
        context: str,
    ) -> None:
        for req in ("name", "required", "description", "reference", "data_type"):
            if req not in field:
                raise ValueError(
                    f"Catalog {version} {context} missing {req} ({source})"
                )

    def get_supported_config_types(self) -> list[str]:
        return list(self._catalogs_by_type.keys())

    def get_versions(self, config_type: str | None = None) -> list[str]:
        resolved_type = str(config_type or "fluentbit")
        return list(self._catalogs_by_type.get(resolved_type, {}).keys())

    def get_default_version(self, config_type: str | None = None) -> str:
        defaults = self._registry.get("default_versions")
        resolved_type = str(config_type or "fluentbit")
        if isinstance(defaults, dict) and defaults.get(resolved_type):
            return str(defaults[resolved_type])
        if resolved_type == "fluentbit":
            default = self._registry.get("default_fluent_bit_version")
            if default:
                return str(default)
        versions = self.get_versions(resolved_type)
        if versions:
            return str(versions[0])
        raise ValueError(f"No default version configured for {resolved_type}")

    def get_catalog(self, version: str, config_type: str | None = None) -> dict[str, Any]:
        if config_type:
            version_map = self._catalogs_by_type.get(str(config_type), {})
            if version not in version_map:
                raise KeyError(f"Unsupported version for {config_type}: {version}")
            return version_map[version]

        matches = [
            payload
            for version_map in self._catalogs_by_type.values()
            for candidate_version, payload in version_map.items()
            if candidate_version == version
        ]
        if not matches:
            raise KeyError(f"Unsupported version: {version}")
        if len(matches) > 1:
            raise KeyError(f"Ambiguous version without config type: {version}")
        return matches[0]

    def validate_catalog_for_version(self, version: str) -> dict[str, Any]:
        payload = self.get_catalog(version)
        self.validate_catalog_payload(version, payload)
        return {"ok": True, "version": version}
