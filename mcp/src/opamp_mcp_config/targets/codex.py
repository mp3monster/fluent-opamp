"""Codex target handler for the MCP config utility."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from opamp_mcp_config.targets.base import ApplyResult


class CodexTarget:
    """Apply OpAMP MCP settings by invoking the Codex CLI."""

    key = "codex"

    def __init__(
        self,
        *,
        build_stdio_server_entry: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._build_stdio_server_entry = build_stdio_server_entry

    def apply(self, settings: dict[str, Any], *, dry_run: bool) -> ApplyResult:
        cfg = dict(settings["clients"][self.key])
        name = str(cfg.get("name") or "opamp-server")
        entry = self._build_stdio_server_entry(settings)
        command = ["codex", "mcp", "add", name]
        for env_key, env_value in entry.get("env", {}).items():
            command.extend(["--env", f"{env_key}={env_value}"])
        command.append("--")
        command.append(str(entry["command"]))
        command.extend(str(item) for item in entry.get("args", []))
        if not dry_run:
            if shutil.which("codex") is None:
                raise RuntimeError("codex CLI is not available on PATH")
            subprocess.run(["codex", "mcp", "remove", name], check=False)
            subprocess.run(command, check=True)
        return ApplyResult(self.key, " ".join(command), not dry_run)
