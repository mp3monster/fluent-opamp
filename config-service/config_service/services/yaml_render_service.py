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
        config = payload.get("config", {})
        annotations = payload.get("annotations", {}) if include_comments else {}
        lines: list[str] = []
        self._emit_yaml(config, lines, indent=0, path="$", annotations=annotations)
        return "\n".join(lines) + "\n"

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

        comment = annotations.get(path)
        if isinstance(comment, str) and comment.strip():
            lines.append(f"{indent_str}# {comment.strip()}")

        if isinstance(value, dict):
            keys = list(value.keys())
            if path == "$":
                preferred = ["service", "pipeline"]
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
