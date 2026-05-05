from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ServiceDefinitionService:
    """Loads versioned service-section option definitions for UI/runtime usage."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self._registry: dict[str, Any] = {}
        self._definitions_by_type: dict[str, dict[str, dict[str, Any]]] = {}
        self._load_registry()

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def _resolve_path(self, ref: str) -> Path:
        candidate = Path(ref)
        if candidate.is_absolute():
            return candidate
        return self._repo_root() / ref

    def _load_registry(self) -> None:
        self._registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        grouped = self._registry_definitions_by_type()
        if not grouped:
            raise ValueError("service-registry.json must include non-empty service definitions")

    def _registry_definitions_by_type(self) -> dict[str, dict[str, str]]:
        grouped = self._registry.get("service_definitions_by_type")
        if isinstance(grouped, dict) and grouped:
            normalized: dict[str, dict[str, str]] = {}
            for config_type, versions in grouped.items():
                if isinstance(versions, dict) and versions:
                    normalized[str(config_type)] = {str(version): str(path) for version, path in versions.items()}
            return normalized
        mapping = self._registry.get("service_definitions", {})
        if isinstance(mapping, dict) and mapping:
            return {"fluentbit": {str(version): str(path) for version, path in mapping.items()}}
        return {}

    def load_all(self) -> None:
        loaded: dict[str, dict[str, dict[str, Any]]] = {}
        for config_type, version_map in self._registry_definitions_by_type().items():
            loaded[config_type] = {}
            for version, ref in version_map.items():
                path = self._resolve_path(str(ref))
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.validate_definition(version, payload, source=str(path))
                loaded[config_type][version] = payload
        self._definitions_by_type = loaded

    def validate_definition(self, version: str, payload: dict[str, Any], source: str = "<in-memory>") -> None:
        engine = str(payload.get("engine") or "fluentbit").lower()
        required_top = {"section", "cardinality", "options"}
        if engine == "fluentbit":
            required_top.add("fluent_bit_version")
        elif engine == "fluentd":
            required_top.add("fluentd_version")
        missing = [k for k in required_top if k not in payload]
        if missing:
            raise ValueError(f"Service definition {version} missing keys {missing} ({source})")

        if payload.get("section") != "service":
            raise ValueError(f"Service definition {version} section must be 'service' ({source})")

        cardinality = payload.get("cardinality", {})
        if not isinstance(cardinality, dict):
            raise ValueError(f"Service definition {version} cardinality must be object ({source})")
        if cardinality.get("maximum") != 1:
            raise ValueError(f"Service definition {version} cardinality.maximum must be 1 ({source})")

        options = payload.get("options")
        if not isinstance(options, list):
            raise ValueError(f"Service definition {version} options must be array ({source})")

        for idx, item in enumerate(options):
            if not isinstance(item, dict):
                raise ValueError(f"Service definition {version} option[{idx}] must be object ({source})")
            for req in ("name", "required", "description", "reference", "data_type"):
                if req not in item:
                    raise ValueError(
                        f"Service definition {version} option[{idx}] missing {req} ({source})"
                    )

    def get_definition(self, version: str, config_type: str | None = None) -> dict[str, Any]:
        if config_type:
            mapping = self._definitions_by_type.get(str(config_type), {})
            if version not in mapping:
                raise KeyError(f"Unsupported service-definition version for {config_type}: {version}")
            return mapping[version]
        matches = [
            payload
            for version_map in self._definitions_by_type.values()
            for candidate_version, payload in version_map.items()
            if candidate_version == version
        ]
        if not matches:
            raise KeyError(f"Unsupported service-definition version: {version}")
        if len(matches) > 1:
            raise KeyError(f"Ambiguous service-definition version without config type: {version}")
        return matches[0]
