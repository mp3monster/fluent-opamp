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

import re
from typing import Any

from config_service.rule_engine.base import RuleAdapter, RuleContext

try:
    from luaparser import ast as lua_ast
except ImportError:  # pragma: no cover - exercised via runtime fallback
    lua_ast = None


def _issue(code: str, path: str, message: str, severity: str = "error", source: str = "rules") -> dict[str, Any]:
    """Create a consistently-shaped rule-engine issue payload."""
    return {
        "code": code,
        "path": path,
        "message": message,
        "severity": severity,
        "source": source,
    }


class LuaCodeSyntaxAdapter(RuleAdapter):
    """Validate inline Lua snippets declared in catalog fields of type `code`."""

    _LINE_COL_RE = re.compile(r"line\\s+(?P<line>\\d+):(?P<column>\\d+):\\s*(?P<detail>.+)$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Scan pipeline plugins and validate only Lua-targeted `code` fields."""
        issues: list[dict[str, Any]] = []
        pipeline = context.config.get("pipeline", {})
        if not isinstance(pipeline, dict):
            return issues

        plugin_groups = context.catalog.get("plugins", {})
        for section in ("inputs", "filters", "outputs"):
            items = pipeline.get(section, [])
            if not isinstance(items, list):
                continue
            section_defs = plugin_groups.get(section, {})
            for idx, plugin_instance in enumerate(items):
                if not isinstance(plugin_instance, dict):
                    continue
                plugin_name = plugin_instance.get("name")
                if not isinstance(plugin_name, str) or not plugin_name:
                    continue
                plugin_def = section_defs.get(plugin_name)
                if not isinstance(plugin_def, dict):
                    continue
                issues.extend(
                    self._validate_plugin_code_fields(
                        plugin_instance=plugin_instance,
                        plugin_def=plugin_def,
                        path_prefix=f"$.config.pipeline.{section}[{idx}]",
                    )
                )
        return issues

    def _validate_plugin_code_fields(
        self,
        *,
        plugin_instance: dict[str, Any],
        plugin_def: dict[str, Any],
        path_prefix: str,
    ) -> list[dict[str, Any]]:
        """Find Lua code fields on a plugin instance and validate their source."""
        issues: list[dict[str, Any]] = []
        for field in plugin_def.get("fields", []):
            if not isinstance(field, dict):
                continue
            if str(field.get("data_type", "")).lower() != "code":
                continue
            validation_rule = field.get("validation_rule")
            if not isinstance(validation_rule, dict):
                continue
            if str(validation_rule.get("kind", "")).lower() != "code_syntax":
                continue
            if str(validation_rule.get("language", "")).lower() != "lua":
                continue

            field_name = str(field.get("name", ""))
            if not field_name:
                continue
            code_value = plugin_instance.get(field_name)
            if code_value is None:
                continue
            if not isinstance(code_value, str):
                continue
            if not code_value.strip():
                continue

            issues.extend(
                self._validate_lua_source(
                    source=code_value,
                    path=f"{path_prefix}.{field_name}",
                )
            )
        return issues

    def _validate_lua_source(self, *, source: str, path: str) -> list[dict[str, Any]]:
        """Run luaparser and normalize syntax failures into UI-friendly issues."""
        if lua_ast is None:
            return [
                _issue(
                    "lua_parser_unavailable",
                    path,
                    "Lua validation is unavailable because the 'luaparser' dependency is not installed.",
                )
            ]

        try:
            lua_ast.parse(source)
        except Exception as exc:  # luaparser raises SyntaxException with formatted text
            message = str(exc).strip() or "Lua syntax validation failed."
            match = self._LINE_COL_RE.search(message)
            if match:
                line = match.group("line")
                column = match.group("column")
                detail = match.group("detail").strip()
                message = f"Lua syntax error at line {line}, column {column}: {detail}"
            elif message.lower() in {"none", "syntax errors: none", "syntax errors"}:
                message = "Lua syntax error: the source is incomplete or invalid."
            elif not message.lower().startswith("lua syntax error"):
                message = f"Lua syntax error: {message}"
            return [_issue("lua_syntax_error", path, message)]
        return []


CUSTOM_ADAPTERS: dict[str, type[RuleAdapter]] = {
    "custom.lua_code_syntax": LuaCodeSyntaxAdapter,
}
