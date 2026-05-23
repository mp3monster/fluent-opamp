from __future__ import annotations

from typing import Any

KEY_CONFIG = "config"
KEY_ANNOTATIONS = "annotations"
KEY_META = "_meta"
KEY_COMMENT_LINES = "comment_lines"
KEY_FIELD_COMMENT_LINES = "field_comment_lines"
KEY_ROUTE = "route"
KEY_ROUTES = "routes"
KEY_ENV = "env"
KEY_SERVICE = "service"
KEY_PARSERS = "parsers"
KEY_UPSTREAM_SERVERS = "upstream_servers"
KEY_PIPELINE = "pipeline"
KEY_INPUTS = "inputs"
KEY_FILTERS = "filters"
KEY_OUTPUTS = "outputs"
KEY_PROCESSORS = "processors"
KEY_LABELS = "labels"
KEY_WORKERS = "workers"
KEY_INCLUDES = "includes"

PATH_ROOT = "$"
PATH_PIPELINE = "$.pipeline"
PATH_PIPELINE_INPUTS_PREFIX = "$.pipeline.inputs["

SCALAR_TRUE = "true"
SCALAR_FALSE = "false"
SCALAR_NULL = "null"
YAML_SPECIAL_CHARS = [":", "#", "\n", "\t", " "]
PREFERRED_ROOT_KEYS = [KEY_ENV, KEY_SERVICE, KEY_PARSERS, KEY_UPSTREAM_SERVERS, KEY_PIPELINE]
PREFERRED_PIPELINE_KEYS = [KEY_INPUTS, KEY_FILTERS, KEY_OUTPUTS]
SKIPPABLE_LIST_KEYS = {KEY_LABELS, KEY_WORKERS, KEY_INCLUDES}
PIPELINE_LIST_KEYS = {KEY_INPUTS, KEY_FILTERS, KEY_OUTPUTS}


class YamlRenderService:
    """Simple YAML renderer to keep dependencies minimal in first version."""

    def render(
        self,
        *,
        payload: dict[str, Any],
        include_comments: bool = False,
    ) -> str:
        """Render one config payload back into YAML text."""
        normalized = self._normalize_fluentbit_route_blocks(payload.get(KEY_CONFIG, {}), path=PATH_ROOT)
        config = self._prune_optional_empty_sections(normalized, path=PATH_ROOT)
        annotations = payload.get(KEY_ANNOTATIONS, {}) if include_comments else {}
        lines: list[str] = []
        self._emit_yaml(config, lines, indent=0, path=PATH_ROOT, annotations=annotations)
        return "\n".join(lines) + "\n"

    def _normalize_fluentbit_route_blocks(self, value: Any, *, path: str) -> Any:
        """Rename Fluent Bit input-level `route` blocks to YAML `routes` output."""
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                output_key = key
                if key == KEY_ROUTE and path.startswith(PATH_PIPELINE_INPUTS_PREFIX):
                    output_key = KEY_ROUTES
                child_path = f"{path}.{key}" if path != PATH_ROOT else f"$.{key}"
                result[output_key] = self._normalize_fluentbit_route_blocks(item, path=child_path)
            return result
        if isinstance(value, list):
            return [
                self._normalize_fluentbit_route_blocks(item, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        return value

    def _prune_optional_empty_sections(self, value: Any, *, path: str) -> Any:
        """Remove known optional empty sections from the rendered YAML tree."""
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                if key == KEY_META:
                    result[key] = item
                    continue
                child_path = f"{path}.{key}" if path != PATH_ROOT else f"$.{key}"
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
        """Return true when an empty section should be omitted from YAML output."""
        if key == KEY_SERVICE and path == PATH_ROOT:
            return isinstance(value, dict) and YamlRenderService._dict_without_meta_is_empty(value)
        if key == KEY_ENV and path == PATH_ROOT:
            return isinstance(value, dict) and YamlRenderService._dict_without_meta_is_empty(value)
        if key == KEY_UPSTREAM_SERVERS and path == PATH_ROOT:
            return isinstance(value, list) and len(value) == 0
        if key == KEY_PARSERS and path == PATH_ROOT:
            return isinstance(value, list) and len(value) == 0
        if key in PIPELINE_LIST_KEYS and path == PATH_PIPELINE:
            return isinstance(value, list) and len(value) == 0
        if key == KEY_PIPELINE and path == PATH_ROOT:
            return isinstance(value, dict) and YamlRenderService._dict_without_meta_is_empty(value)
        if key == KEY_PROCESSORS:
            return isinstance(value, dict) and YamlRenderService._processors_without_meta_is_empty(value)
        if key in SKIPPABLE_LIST_KEYS and isinstance(value, list) and len(value) == 0:
            return True
        return False

    @staticmethod
    def _dict_without_meta_is_empty(value: dict[str, Any]) -> bool:
        """Return true when a mapping has no non-meta keys."""
        return len([key for key in value.keys() if key != KEY_META]) == 0

    @staticmethod
    def _processors_without_meta_is_empty(value: dict[str, Any]) -> bool:
        """Return true when processor groups contain no meaningful entries."""
        for key, item in value.items():
            if key == KEY_META:
                continue
            if isinstance(item, list):
                if len(item) > 0:
                    return False
                continue
            if isinstance(item, dict):
                if not YamlRenderService._dict_without_meta_is_empty(item):
                    return False
                continue
            if item not in (None, ""):
                return False
        return True

    @staticmethod
    def _extract_meta(value: Any) -> dict[str, Any]:
        """Extract renderer metadata attached to a mapping node."""
        if not isinstance(value, dict):
            return {}
        meta = value.get(KEY_META)
        if isinstance(meta, dict):
            return meta
        return {}

    @staticmethod
    def _comment_lines_from_meta(meta: dict[str, Any]) -> list[str]:
        """Return node-level comment lines from a metadata payload."""
        lines = meta.get(KEY_COMMENT_LINES)
        if not isinstance(lines, list):
            return []
        return [str(line).rstrip() for line in lines if str(line).strip()]

    @staticmethod
    def _field_comment_lines(meta: dict[str, Any], key: str) -> list[str]:
        """Return field-specific comment lines from a metadata payload."""
        field_map = meta.get(KEY_FIELD_COMMENT_LINES)
        if not isinstance(field_map, dict):
            return []
        lines = field_map.get(key)
        if not isinstance(lines, list):
            return []
        return [str(line).rstrip() for line in lines if str(line).strip()]

    @staticmethod
    def _emit_comment_lines(lines: list[str], output: list[str], *, indent: int) -> None:
        """Append comment lines to the emitted YAML buffer."""
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
        """Recursively emit YAML lines from the normalized config tree."""
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
            keys = [key for key in value.keys() if key != KEY_META]
            if path == PATH_ROOT:
                ordered = [key for key in PREFERRED_ROOT_KEYS if key in value]
                ordered.extend([key for key in keys if key not in ordered])
                keys = ordered
            elif path == PATH_PIPELINE:
                ordered = [key for key in PREFERRED_PIPELINE_KEYS if key in value]
                ordered.extend([key for key in keys if key not in ordered])
                keys = ordered

            for index, key in enumerate(keys):
                if path == PATH_ROOT and index > 0:
                    lines.extend(["", ""])
                item = value[key]
                key_path = f"{path}.{key}" if path != PATH_ROOT else f"$.{key}"
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
        """Convert one scalar Python value into YAML-safe text."""
        if value is True:
            return SCALAR_TRUE
        if value is False:
            return SCALAR_FALSE
        if value is None:
            return SCALAR_NULL
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value)
        if text == "" or any(ch in text for ch in YAML_SPECIAL_CHARS):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return text
