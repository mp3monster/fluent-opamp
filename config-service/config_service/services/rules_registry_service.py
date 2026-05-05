from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_service.rule_engine.registry import RuleAdapterRegistry


class RulesRegistryService:
    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self._registry: dict[str, Any] = {}
        self._adapter_registry = RuleAdapterRegistry()
        self._load()

    def _load(self) -> None:
        self._registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.validate_registry()

    def validate_registry(self) -> None:
        if "profiles" not in self._registry or "rulesets" not in self._registry:
            raise ValueError("validation-rules-registry.json must include 'profiles' and 'rulesets'")

        rulesets = self._registry["rulesets"]
        if not isinstance(rulesets, dict) or not rulesets:
            raise ValueError("rulesets must be a non-empty object")

        for name, ruleset in rulesets.items():
            if not isinstance(ruleset, dict):
                raise ValueError(f"ruleset '{name}' must be an object")
            self._adapter_registry.validate_ruleset(name, ruleset)

        profiles = self._registry["profiles"]
        for profile_name, profile in profiles.items():
            if not isinstance(profile, dict):
                raise ValueError(f"profile '{profile_name}' must be an object")
            for ruleset_name in profile.get("rulesets", []):
                if ruleset_name not in rulesets:
                    raise ValueError(
                        f"profile '{profile_name}' references unknown ruleset '{ruleset_name}'"
                    )

    def get_registry(self) -> dict[str, Any]:
        return self._registry

    def get_default_profile(self) -> str:
        default = self._registry.get("default_profile")
        if not default:
            raise ValueError("default_profile missing from validation rules registry")
        return str(default)

    def get_profile_rulesets(self, profile: str, version: str) -> list[str]:
        profiles = self._registry.get("profiles", {})
        if profile not in profiles:
            raise KeyError(f"Unknown validation profile: {profile}")

        selected = list(profiles[profile].get("rulesets", []))
        version_overrides = self._registry.get("version_overrides", {})
        for extra in version_overrides.get(version, {}).get("additional_rulesets", []):
            if extra not in selected:
                selected.append(extra)
        return selected

    def get_ruleset(self, ruleset_name: str) -> dict[str, Any]:
        return self._registry["rulesets"][ruleset_name]

    @property
    def adapter_registry(self) -> RuleAdapterRegistry:
        return self._adapter_registry
