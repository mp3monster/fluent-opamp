"""Target handlers for the OpAMP MCP configuration utility."""

from opamp_mcp_config.targets.base import ApplyResult, ClientTarget
from opamp_mcp_config.targets.claude import ClaudeTarget
from opamp_mcp_config.targets.codex import CodexTarget
from opamp_mcp_config.targets.gemini import GeminiTarget
from opamp_mcp_config.targets.librechat import LibreChatTarget
from opamp_mcp_config.targets.vscode import VSCodeTarget

__all__ = [
    "ApplyResult",
    "ClientTarget",
    "ClaudeTarget",
    "CodexTarget",
    "GeminiTarget",
    "LibreChatTarget",
    "VSCodeTarget",
]
