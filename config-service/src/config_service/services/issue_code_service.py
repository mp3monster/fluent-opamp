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
# 
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
