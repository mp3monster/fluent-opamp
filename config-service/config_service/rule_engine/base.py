from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class RuleContext:
    version: str
    config: dict[str, Any]
    catalog: dict[str, Any]
    params: dict[str, Any]


class RuleAdapter(ABC):
    @abstractmethod
    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Return a list of normalized validation issues."""
