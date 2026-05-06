from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class IssueCodeService:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._payload: dict[str, Any] = {"registry_version": "1.0.0", "codes": {}}

    def load(self) -> None:
        if not self.config_path.exists():
            return
        self._payload = json.loads(self.config_path.read_text(encoding="utf-8"))

    def get_all(self) -> dict[str, Any]:
        return self._payload

    def get_codes(self) -> dict[str, Any]:
        codes = self._payload.get("codes", {})
        return codes if isinstance(codes, dict) else {}
