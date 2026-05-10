#!/usr/bin/env python3
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

    def _resolve_path(self, ref: str) -> Path:
        candidate = Path(ref)
        if candidate.is_absolute():
            return candidate
        return self.registry_path.parent.parent / ref

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
        return {}

    @staticmethod
    def _normalize_config_type(config_type: str) -> str:
        normalized = str(config_type or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        if normalized == "fluentbit":
            return "fluentbit"
        if normalized == "fluentd":
            return "fluentd"
        return str(config_type or "").strip()

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
        required_top = {"engine", "section", "cardinality", "options"}
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
            normalized_type = self._normalize_config_type(str(config_type))
            mapping = self._definitions_by_type.get(normalized_type, {})
            if version in mapping:
                return mapping[version]
            # Fall back to a unique match across config types when alias/typing mismatches happen.
            matches = [
                payload
                for version_map in self._definitions_by_type.values()
                for candidate_version, payload in version_map.items()
                if candidate_version == version
            ]
            if len(matches) == 1:
                return matches[0]
            raise KeyError(f"Unsupported service-definition version for {config_type}: {version}")
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
