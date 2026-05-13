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

import platform
import shlex
from abc import ABC, abstractmethod
from pathlib import Path
from string import Template
from typing import Any

from config_service.agent_validation.exceptions import AgentCommandBuildError
from config_service.agent_validation.models import ValidationAgentEntry


class AgentValidationAdapter(ABC):
    """Adapter abstraction for different agent-specific command/result behaviors."""

    @abstractmethod
    def create_command(
        self,
        *,
        config_text: str | None,
        config_path: Path | None,
        entry: ValidationAgentEntry,
    ) -> str:
        """
        Build an executable command string from config input and entry metadata.

        Implementations should raise AgentCommandBuildError for unsupported inputs.
        """

    @abstractmethod
    def interpret_result(self, result_text: str) -> dict[str, Any]:
        """Convert raw process text output into a JSON-serializable structure."""


class TemplateCommandAdapter(AgentValidationAdapter):
    """
    Default adapter for command-line validators.

    Supports placeholders in command args:
    - `{config_path}`: absolute path to rendered temporary or explicit config file
    - `{config_text}`: full config content (quoted for shell safety)
    """

    def _quote(self, value: str) -> str:
        if platform.system().lower() == "windows":
            # Keep quoting behavior consistent with subprocess on Windows shells.
            return '"' + str(value).replace('"', '\\"') + '"'
        return shlex.quote(str(value))

    def _expand_argument(self, arg: str, *, config_text: str | None, config_path: Path | None) -> str:
        if "{config_path}" in arg and config_path is None:
            raise AgentCommandBuildError(
                "Command entry requires {config_path}, but no file path was provided."
            )
        if "{config_text}" in arg and config_text is None:
            raise AgentCommandBuildError(
                "Command entry requires {config_text}, but no config text was provided."
            )
        replacements = {
            "config_path": str(config_path) if config_path is not None else "",
            "config_text": str(config_text or ""),
        }
        return Template(arg.replace("{", "${")).safe_substitute(replacements)

    def create_command(
        self,
        *,
        config_text: str | None,
        config_path: Path | None,
        entry: ValidationAgentEntry,
    ) -> str:
        command_path = str(entry.command_path or "").strip()
        if not command_path:
            raise AgentCommandBuildError("Validation agent command_path is empty.")

        parts: list[str] = [self._quote(command_path)]
        for arg in entry.command_args:
            expanded = self._expand_argument(
                str(arg),
                config_text=config_text,
                config_path=config_path,
            )
            parts.append(self._quote(expanded))
        return " ".join(parts)

    def interpret_result(self, result_text: str) -> dict[str, Any]:
        messages = [
            line.strip()
            for line in str(result_text or "").replace("\r\n", "\n").split("\n")
            if line.strip()
        ]
        return {
            "messages": messages,
        }
