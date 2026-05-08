from __future__ import annotations

from typing import Any


class YamlRenderService:
    """Simple YAML renderer to keep dependencies minimal in first version."""

    def render(
        self,
        *,
        payload: dict[str, Any],
        include_comments: bool = False,
    ) -> str:
        normalized = self._normalize_fluentbit_route_blocks(payload.get("config", {}), path="$")
        config = self._prune_optional_empty_sections(normalized, path="$")
        annotations = payload.get("annotations", {}) if include_comments else {}
        lines: list[str] = []
        self._emit_yaml(config, lines, indent=0, path="$", annotations=annotations)
        return "\n".join(lines) + "\n"

    def _normalize_fluentbit_route_blocks(self, value: Any, *, path: str) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                output_key = key
                if (
                    key == "route"
                    and path.startswith("$.pipeline.inputs[")
                ):
                    output_key = "routes"
                child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                result[output_key] = self._normalize_fluentbit_route_blocks(item, path=child_path)
            return result
        if isinstance(value, list):
            return [
                self._normalize_fluentbit_route_blocks(item, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        return value

    def _prune_optional_empty_sections(self, value: Any, *, path: str) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                if key == "_meta":
                    result[key] = item
                    continue
                child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                pruned = self._prune_optional_empty_sections(item, path=child_path)
                if self._should_skip_empty(path=path, key=key, value=pruned):
                    continue
                result[key] = pruned
            return result
        if isinstance(value, list):
            return [self._prune_optional_empty_sections(item, path=f"{path}[]") for item in value]
        return value

    @staticmethod
    def _should_skip_empty(*, path: str, key: str, value: Any) -> bool:
        if key == "service" and path == "$":
            return isinstance(value, dict) and YamlRenderService._dict_without_meta_is_empty(value)
        if key == "parsers" and path == "$":
            return isinstance(value, list) and len(value) == 0
        if key in {"inputs", "filters", "outputs"} and path == "$.pipeline":
            return isinstance(value, list) and len(value) == 0
        if key == "pipeline" and path == "$":
            return isinstance(value, dict) and YamlRenderService._dict_without_meta_is_empty(value)
        if key in {"labels", "workers", "includes"}:
            if isinstance(value, list) and len(value) == 0:
                return True
        return False

    @staticmethod
    def _dict_without_meta_is_empty(value: dict[str, Any]) -> bool:
        return len([key for key in value.keys() if key != "_meta"]) == 0

    @staticmethod
    def _extract_meta(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        meta = value.get("_meta")
        if isinstance(meta, dict):
            return meta
        return {}

    @staticmethod
    def _comment_lines_from_meta(meta: dict[str, Any]) -> list[str]:
        lines = meta.get("comment_lines")
        if not isinstance(lines, list):
            return []
        return [str(line).rstrip() for line in lines if str(line).strip()]

    @staticmethod
    def _field_comment_lines(meta: dict[str, Any], key: str) -> list[str]:
        field_map = meta.get("field_comment_lines")
        if not isinstance(field_map, dict):
            return []
        lines = field_map.get(key)
        if not isinstance(lines, list):
            return []
        return [str(line).rstrip() for line in lines if str(line).strip()]

    @staticmethod
    def _emit_comment_lines(lines: list[str], output: list[str], *, indent: int) -> None:
        indent_str = " " * indent
        for line in lines:
            output.append(f"{indent_str}# {line}")

    def _emit_yaml(
        self,
        value: Any,
        lines: list[str],
        *,
        indent: int,
        path: str,
        annotations: dict[str, Any],
    ) -> None:
        indent_str = " " * indent

        meta = self._extract_meta(value)
        comment_lines = self._comment_lines_from_meta(meta)
        if comment_lines:
            self._emit_comment_lines(comment_lines, lines, indent=indent)
        else:
            comment = annotations.get(path)
            if isinstance(comment, str) and comment.strip():
                lines.append(f"{indent_str}# {comment.strip()}")

        if isinstance(value, dict):
            keys = [key for key in value.keys() if key != "_meta"]
            if path == "$":
                preferred = ["service", "parsers", "pipeline"]
                ordered = [key for key in preferred if key in value]
                ordered.extend([key for key in keys if key not in ordered])
                keys = ordered
            elif path == "$.pipeline":
                preferred = ["inputs", "filters", "outputs"]
                ordered = [key for key in preferred if key in value]
                ordered.extend([key for key in keys if key not in ordered])
                keys = ordered

            for key in keys:
                item = value[key]
                key_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                field_comment_lines = self._field_comment_lines(meta, key)
                if field_comment_lines:
                    self._emit_comment_lines(field_comment_lines, lines, indent=indent)
                if isinstance(item, (dict, list)):
                    lines.append(f"{indent_str}{key}:")
                    self._emit_yaml(item, lines, indent=indent + 2, path=key_path, annotations=annotations)
                else:
                    lines.append(f"{indent_str}{key}: {self._scalar(item)}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                comment = annotations.get(item_path)
                if isinstance(comment, str) and comment.strip():
                    lines.append(f"{indent_str}# {comment.strip()}")
                if isinstance(item, (dict, list)):
                    lines.append(f"{indent_str}-")
                    self._emit_yaml(item, lines, indent=indent + 2, path=item_path, annotations=annotations)
                else:
                    lines.append(f"{indent_str}- {self._scalar(item)}")
        else:
            lines.append(f"{indent_str}{self._scalar(value)}")

    @staticmethod
    def _scalar(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return "null"
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value)
        if text == "" or any(ch in text for ch in [":", "#", "\n", "\t", " "]):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return text
