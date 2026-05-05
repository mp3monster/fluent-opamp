from __future__ import annotations

from typing import Any

from config_service.rule_engine.base import RuleContext
from config_service.services.rules_registry_service import RulesRegistryService


class RuleEngineService:
    def __init__(self, rules_registry_service: RulesRegistryService) -> None:
        self.rules_registry_service = rules_registry_service

    def evaluate(
        self,
        *,
        version: str,
        config: dict[str, Any],
        catalog: dict[str, Any],
        profile: str | None,
    ) -> list[dict[str, Any]]:
        selected_profile = profile or self.rules_registry_service.get_default_profile()
        ruleset_names = self.rules_registry_service.get_profile_rulesets(selected_profile, version)

        issues: list[dict[str, Any]] = []
        for ruleset_name in ruleset_names:
            ruleset = self.rules_registry_service.get_ruleset(ruleset_name)
            if not ruleset.get("enabled", True):
                continue
            adapter_name = str(ruleset["adapter"])
            adapter_cls = self.rules_registry_service.adapter_registry.resolve(adapter_name)
            adapter = adapter_cls()
            context = RuleContext(
                version=version,
                config=config,
                catalog=catalog,
                params=dict(ruleset.get("params", {})),
            )
            issues.extend(adapter.evaluate(context))
        return issues
