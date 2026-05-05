from __future__ import annotations

from typing import Any

from config_service.rule_engine.adapters.builtin import BUILTIN_ADAPTERS
from config_service.rule_engine.adapters.lua_code import CUSTOM_ADAPTERS
from config_service.rule_engine.adapters.sql_code import CUSTOM_ADAPTERS as SQL_CUSTOM_ADAPTERS
from config_service.rule_engine.base import RuleAdapter


class RuleAdapterRegistry:
    def __init__(self) -> None:
        self._adapters = dict(BUILTIN_ADAPTERS)
        self._adapters.update(CUSTOM_ADAPTERS)
        self._adapters.update(SQL_CUSTOM_ADAPTERS)

    def resolve(self, adapter_name: str) -> type[RuleAdapter]:
        adapter_cls = self._adapters.get(adapter_name)
        if adapter_cls is None:
            raise ValueError(f"Unsupported rule adapter: {adapter_name}")
        return adapter_cls

    def validate_ruleset(self, name: str, ruleset: dict[str, Any]) -> None:
        if "adapter" not in ruleset:
            raise ValueError(f"Ruleset '{name}' must define adapter")
        self.resolve(str(ruleset["adapter"]))
