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
