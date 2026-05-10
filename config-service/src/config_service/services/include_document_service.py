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

from copy import deepcopy
from pathlib import Path
from typing import Any


class IncludeDocumentService:
    """Resolve, merge, and render include graphs without mutating source payloads."""

    def __init__(self, *, fluentbit_yaml_config_service: Any, fluentd_config_service: Any) -> None:
        self._fluentbit_yaml_config_service = fluentbit_yaml_config_service
        self._fluentd_config_service = fluentd_config_service

    def resolve_include_documents(
        self,
        *,
        config_type: str,
        source_path: str,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        root_path = Path(source_path).expanduser()
        base_dir = root_path.parent if root_path.name else root_path
        return self._resolve_include_list(
            config_type=str(config_type or "fluentbit").lower(),
            base_dir=base_dir,
            include_items=config.get("includes"),
            seen_stack=[root_path.resolve(strict=False)],
        )

    def merge_for_validation(
        self,
        *,
        config: dict[str, Any],
        included_documents: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        merged = self._empty_like(config)
        for document in included_documents or []:
            child_config = self._merged_config_from_document(document)
            if child_config is not None:
                merged = self._merge_configs(merged, child_config)
        merged = self._merge_configs(merged, deepcopy(config))
        return merged

    def render_included_documents(
        self,
        *,
        config_type: str,
        included_documents: list[dict[str, Any]] | None,
        include_comments: bool,
        yaml_render_service: Any,
        fluentd_config_service: Any,
    ) -> list[dict[str, Any]]:
        rendered: list[dict[str, Any]] = []
        for document in included_documents or []:
            child_config = document.get("config")
            node: dict[str, Any] = {
                "include_path": document.get("include_path", ""),
                "resolved_path": document.get("resolved_path", ""),
                "ok": bool(document.get("ok", False)),
                "errors": deepcopy(document.get("errors", [])),
            }
            if isinstance(child_config, dict):
                if str(config_type or "fluentbit").lower() == "fluentd":
                    node["text"] = fluentd_config_service.render(deepcopy(child_config))
                else:
                    node["yaml"] = yaml_render_service.render(
                        payload={"config": deepcopy(child_config)},
                        include_comments=include_comments,
                    )
            child_includes = document.get("included_documents")
            if isinstance(child_includes, list):
                node["included_documents"] = self.render_included_documents(
                    config_type=config_type,
                    included_documents=child_includes,
                    include_comments=include_comments,
                    yaml_render_service=yaml_render_service,
                    fluentd_config_service=fluentd_config_service,
                )
            else:
                node["included_documents"] = []
            rendered.append(node)
        return rendered

    def _resolve_include_list(
        self,
        *,
        config_type: str,
        base_dir: Path,
        include_items: Any,
        seen_stack: list[Path],
    ) -> list[dict[str, Any]]:
        if not isinstance(include_items, list):
            return []

        resolved: list[dict[str, Any]] = []
        for item in include_items:
            if not isinstance(item, str) or not item.strip():
                continue
            include_path = item.strip()
            candidates = self._expand_include_candidates(base_dir=base_dir, include_path=include_path)
            if not candidates:
                resolved.append(
                    self._error_node(
                        include_path=include_path,
                        resolved_path=str((base_dir / include_path).resolve(strict=False)),
                        code="include_file_not_found",
                        message=f"Included file '{include_path}' could not be found.",
                    )
                )
                continue

            for candidate in candidates:
                candidate_resolved = candidate.resolve(strict=False)
                if candidate_resolved in seen_stack:
                    resolved.append(
                        self._error_node(
                            include_path=include_path,
                            resolved_path=str(candidate_resolved),
                            code="include_cycle_detected",
                            message=f"Include cycle detected for '{candidate_resolved}'.",
                        )
                    )
                    continue

                try:
                    text = candidate.read_text(encoding="utf-8")
                except OSError as exc:
                    resolved.append(
                        self._error_node(
                            include_path=include_path,
                            resolved_path=str(candidate_resolved),
                            code="include_file_not_readable",
                            message=f"Included file '{candidate_resolved}' could not be read: {exc}",
                        )
                    )
                    continue

                try:
                    parsed = self._parse_child_text(config_type=config_type, text=text)
                except ValueError as exc:
                    resolved.append(
                        self._error_node(
                            include_path=include_path,
                            resolved_path=str(candidate_resolved),
                            code="include_parse_error",
                            message=str(exc),
                        )
                    )
                    continue

                child_config = parsed.get("config")
                if not isinstance(child_config, dict):
                    resolved.append(
                        self._error_node(
                            include_path=include_path,
                            resolved_path=str(candidate_resolved),
                            code="include_parse_error",
                            message=f"Included file '{candidate_resolved}' did not produce a valid config object.",
                        )
                    )
                    continue

                resolved.append(
                    {
                        "include_path": include_path,
                        "resolved_path": str(candidate_resolved),
                        "ok": bool(parsed.get("ok", True)),
                        "errors": deepcopy(parsed.get("errors", [])),
                        "config": deepcopy(child_config),
                        "included_documents": self._resolve_include_list(
                            config_type=config_type,
                            base_dir=candidate.parent,
                            include_items=child_config.get("includes"),
                            seen_stack=seen_stack + [candidate_resolved],
                        ),
                    }
                )
        return resolved

    @staticmethod
    def _error_node(*, include_path: str, resolved_path: str, code: str, message: str) -> dict[str, Any]:
        return {
            "include_path": include_path,
            "resolved_path": resolved_path,
            "ok": False,
            "errors": [
                {
                    "order": 1,
                    "code": code,
                    "path": "$.includes",
                    "message": message,
                    "severity": "warning",
                    "source": "include-loader",
                }
            ],
            "included_documents": [],
        }

    @staticmethod
    def _expand_include_candidates(*, base_dir: Path, include_path: str) -> list[Path]:
        candidate = Path(include_path).expanduser()
        if not candidate.is_absolute():
            candidate = (base_dir / candidate).resolve(strict=False)
        if any(token in include_path for token in ("*", "?", "[")):
            return sorted(Path(path) for path in candidate.parent.glob(candidate.name))
        if candidate.exists():
            return [candidate]
        return []

    def _parse_child_text(self, *, config_type: str, text: str) -> dict[str, Any]:
        if str(config_type or "fluentbit").lower() == "fluentd":
            config = self._fluentd_config_service.parse(text)
            return {"ok": True, "config": config, "errors": []}
        return self._fluentbit_yaml_config_service.parse(text)

    def _merged_config_from_document(self, document: dict[str, Any]) -> dict[str, Any] | None:
        config = document.get("config")
        if not isinstance(config, dict):
            return None
        return self.merge_for_validation(
            config=deepcopy(config),
            included_documents=document.get("included_documents", []),
        )

    @staticmethod
    def _empty_like(config: dict[str, Any]) -> dict[str, Any]:
        empty: dict[str, Any] = {}
        for key, value in config.items():
            if isinstance(value, dict):
                empty[key] = {}
            elif isinstance(value, list):
                empty[key] = []
            else:
                empty[key] = deepcopy(value)
        return empty

    def _merge_configs(self, base: Any, extra: Any) -> Any:
        if isinstance(base, dict) and isinstance(extra, dict):
            merged = deepcopy(base)
            for key, value in extra.items():
                if key == "_meta":
                    if isinstance(value, dict):
                        merged[key] = deepcopy(value)
                    continue
                if key not in merged:
                    merged[key] = deepcopy(value)
                    continue
                merged[key] = self._merge_configs(merged[key], value)
            return merged
        if isinstance(base, list) and isinstance(extra, list):
            return deepcopy(base) + deepcopy(extra)
        return deepcopy(base if base not in (None, "") else extra)
