from __future__ import annotations

import json
import re
from typing import Any

_DIRECTIVE_START = re.compile(r"^<(?P<name>[@A-Za-z_][\w@-]*)(?:\s+(?P<arg>.*?))?>$")
_DIRECTIVE_END = re.compile(r"^</(?P<name>[@A-Za-z_][\w@-]*)>$")

_SECTION_TO_PIPELINE = {
    "source": "inputs",
    "filter": "filters",
    "match": "outputs",
}

_SPECIAL_CHILDREN = {
    "parse",
    "buffer",
    "format",
    "transport",
    "storage",
    "service_discovery",
    "extract",
    "inject",
    "record",
    "regexp",
    "exclude",
    "secondary",
    "store",
}


def _split_key_value(line: str) -> tuple[str, str]:
    parts = line.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _strip_quotes(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {"'", '"'}:
        return trimmed[1:-1]
    return trimmed


def _parse_scalar(value: str) -> Any:
    raw = _strip_quotes(value)
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        try:
            return int(raw)
        except ValueError:
            return raw
    try:
        if "." in raw and raw.replace(".", "", 1).isdigit():
            return float(raw)
    except ValueError:
        pass
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return raw


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list) or isinstance(value, dict):
        return json.dumps(value, separators=(", ", ": "))
    text = str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or any(ch in text for ch in ['"', "'", "#"]):
        return json.dumps(text)
    return text


class FluentdConfigService:
    """Parse and render standard Fluentd .conf text."""

    @staticmethod
    def _has_substantive_keys(payload: Any) -> bool:
        return isinstance(payload, dict) and any(key != "_meta" for key in payload.keys())

    def parse(self, text: str) -> dict[str, Any]:
        root = self._parse_ast(text)
        return self._ast_to_model(root)

    def render(self, config: dict[str, Any]) -> str:
        lines: list[str] = []
        service = config.get("service")
        if self._has_substantive_keys(service):
            lines.extend(self._render_key_value_block("system", service, indent=0))
            lines.append("")

        includes = config.get("includes")
        if isinstance(includes, list):
            for item in includes:
                if isinstance(item, str) and item:
                    lines.append(f"@include {item}")
            if includes:
                lines.append("")

        pipeline = config.get("pipeline", {})
        if isinstance(pipeline, dict):
            lines.extend(self._render_pipeline(pipeline, indent=0))

        labels = config.get("labels")
        if isinstance(labels, list):
            for label in labels:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_label(label, indent=0))

        workers = config.get("workers")
        if isinstance(workers, list):
            for worker in workers:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_worker(worker, indent=0))

        return "\n".join(line for line in lines if line is not None).rstrip() + "\n"

    def _parse_ast(self, text: str) -> dict[str, Any]:
        root = {"name": "__root__", "arg": None, "params": [], "children": []}
        stack = [root]
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("@include "):
                stack[-1]["children"].append(
                    {"name": "@include", "arg": stripped[len("@include ") :].strip(), "params": [], "children": []}
                )
                continue
            end_match = _DIRECTIVE_END.match(stripped)
            if end_match:
                name = end_match.group("name")
                if len(stack) == 1 or stack[-1]["name"] != name:
                    raise ValueError(f"Unexpected closing directive </{name}> on line {line_number}")
                stack.pop()
                continue
            start_match = _DIRECTIVE_START.match(stripped)
            if start_match:
                node = {
                    "name": start_match.group("name"),
                    "arg": (start_match.group("arg") or "").strip() or None,
                    "params": [],
                    "children": [],
                }
                stack[-1]["children"].append(node)
                stack.append(node)
                continue
            key, value = _split_key_value(stripped)
            stack[-1]["params"].append((key, _parse_scalar(value)))
        if len(stack) != 1:
            open_names = " > ".join(node["name"] for node in stack[1:])
            raise ValueError(f"Unclosed Fluentd directives: {open_names}")
        return root

    def _ast_to_model(self, root: dict[str, Any]) -> dict[str, Any]:
        config: dict[str, Any] = {
            "service": {},
            "pipeline": {"inputs": [], "filters": [], "outputs": []},
            "labels": [],
            "workers": [],
            "includes": [],
        }
        for child in root["children"]:
            self._consume_root_child(config, child)
        return config

    def _consume_root_child(self, config: dict[str, Any], node: dict[str, Any]) -> None:
        name = node["name"]
        if name == "@include":
            config.setdefault("includes", []).append(node["arg"])
            return
        if name == "system":
            config["service"].update(self._params_dict(node))
            return
        if name == "label":
            config.setdefault("labels", []).append(self._label_from_node(node))
            return
        if name == "worker":
            config.setdefault("workers", []).append(self._worker_from_node(node))
            return
        if name in _SECTION_TO_PIPELINE:
            config["pipeline"][_SECTION_TO_PIPELINE[name]].append(self._plugin_from_node(name, node))
            return

    def _label_from_node(self, node: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "name": node.get("arg") or "",
            "pipeline": {"inputs": [], "filters": [], "outputs": []},
        }
        includes: list[str] = []
        for child in node["children"]:
            if child["name"] == "@include":
                includes.append(child["arg"])
                continue
            if child["name"] in _SECTION_TO_PIPELINE:
                payload["pipeline"][_SECTION_TO_PIPELINE[child["name"]]].append(
                    self._plugin_from_node(child["name"], child)
                )
        if includes:
            payload["includes"] = includes
        return payload

    def _worker_from_node(self, node: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "name": node.get("arg") or "",
            "pipeline": {"inputs": [], "filters": [], "outputs": []},
            "labels": [],
        }
        includes: list[str] = []
        for child in node["children"]:
            if child["name"] == "@include":
                includes.append(child["arg"])
                continue
            if child["name"] == "label":
                payload["labels"].append(self._label_from_node(child))
                continue
            if child["name"] in _SECTION_TO_PIPELINE:
                payload["pipeline"][_SECTION_TO_PIPELINE[child["name"]]].append(
                    self._plugin_from_node(child["name"], child)
                )
        if includes:
            payload["includes"] = includes
        return payload

    def _plugin_from_node(
        self,
        section_name: str,
        node: dict[str, Any],
        *,
        nested_output: bool = False,
    ) -> dict[str, Any]:
        params = self._params_dict(node)
        name_value = params.pop("@type", params.pop("type", None))
        plugin: dict[str, Any] = {"name": name_value or node["name"]}
        if node.get("arg") and section_name in {"filter", "match"} and not nested_output:
            plugin["directive_arg"] = node["arg"]
        if section_name == "transport" and node.get("arg"):
            plugin["directive_arg"] = node["arg"]
        if section_name == "buffer" and node.get("arg"):
            plugin["chunk_keys"] = [part.strip() for part in node["arg"].split(",") if part.strip()]
        plugin.update(params)
        children = self._children_from_node(node)
        if children:
            plugin["children"] = children
        return plugin

    def _children_from_node(self, node: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        children: dict[str, list[dict[str, Any]]] = {}
        includes: list[str] = []
        for child in node["children"]:
            child_name = child["name"]
            if child_name == "@include":
                includes.append(child["arg"])
                continue
            if child_name not in _SPECIAL_CHILDREN:
                continue
            item = self._child_item_from_node(child)
            children.setdefault(child_name, []).append(item)
        if includes:
            children["includes"] = [{"path": path} for path in includes]
        return children

    def _child_item_from_node(self, node: dict[str, Any]) -> dict[str, Any]:
        name = node["name"]
        if name in {"store", "secondary"}:
            return self._plugin_from_node("match", node, nested_output=True)
        if name in {"record", "regexp", "exclude"}:
            payload = self._params_dict(node)
            if name == "record":
                return {"entries": payload}
            return payload
        if name in {"parse", "buffer", "format", "storage", "service_discovery"}:
            return self._plugin_from_node(name, node)
        if name in {"transport", "extract", "inject"}:
            payload = self._params_dict(node)
            if node.get("arg"):
                payload["directive_arg"] = node["arg"]
            return payload
        return self._params_dict(node)

    def _params_dict(self, node: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in node.get("params", []):
            payload[key] = value
        return payload

    def _render_pipeline(self, pipeline: dict[str, Any], *, indent: int) -> list[str]:
        lines: list[str] = []
        for section_key, directive_name in (("inputs", "source"), ("filters", "filter"), ("outputs", "match")):
            items = pipeline.get(section_key)
            if not isinstance(items, list):
                continue
            for item in items:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_plugin(item, directive_name, indent=indent))
        return lines

    def _render_label(self, label: dict[str, Any], *, indent: int) -> list[str]:
        name = str(label.get("name") or "").strip()
        lines = [self._indent(indent) + f"<label {name}>"]
        includes = label.get("includes")
        if isinstance(includes, list):
            for item in includes:
                if isinstance(item, str) and item:
                    lines.append(self._indent(indent + 2) + f"@include {item}")
        pipeline = label.get("pipeline", {})
        lines.extend(self._render_pipeline(pipeline, indent=indent + 2))
        lines.append(self._indent(indent) + "</label>")
        return lines

    def _render_worker(self, worker: dict[str, Any], *, indent: int) -> list[str]:
        name = str(worker.get("name") or "").strip()
        lines = [self._indent(indent) + f"<worker {name}>"]
        includes = worker.get("includes")
        if isinstance(includes, list):
            for item in includes:
                if isinstance(item, str) and item:
                    lines.append(self._indent(indent + 2) + f"@include {item}")
        pipeline = worker.get("pipeline", {})
        lines.extend(self._render_pipeline(pipeline, indent=indent + 2))
        labels = worker.get("labels")
        if isinstance(labels, list):
            for label in labels:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_label(label, indent=indent + 2))
        lines.append(self._indent(indent) + "</worker>")
        return lines

    def _render_plugin(self, plugin: dict[str, Any], directive_name: str, *, indent: int) -> list[str]:
        arg = ""
        if directive_name in {"filter", "match"}:
            arg = " " + str(plugin.get("directive_arg") or "**")
        lines = [self._indent(indent) + f"<{directive_name}{arg}>"]
        lines.extend(self._render_plugin_body(plugin, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{directive_name}>")
        return lines

    def _render_plugin_body(self, plugin: dict[str, Any], *, indent: int) -> list[str]:
        lines = [self._indent(indent) + f"@type {_format_scalar(plugin.get('name', ''))}"]
        for key, value in plugin.items():
            if key in {"name", "directive_arg", "children", "_meta"}:
                continue
            if key == "chunk_keys":
                continue
            lines.append(self._indent(indent) + f"{key} {_format_scalar(value)}")
        children = plugin.get("children")
        if isinstance(children, dict):
            for child_name, child_items in children.items():
                if child_name == "includes":
                    for include in child_items:
                        path = include.get("path")
                        if path:
                            lines.append(self._indent(indent) + f"@include {path}")
                    continue
                if not isinstance(child_items, list):
                    continue
                for child_item in child_items:
                    lines.extend(self._render_child(child_name, child_item, indent=indent))
        return lines

    def _render_child(self, section_name: str, item: dict[str, Any], *, indent: int) -> list[str]:
        if section_name in {"store", "secondary"}:
            return self._render_nested_output(section_name, item, indent=indent)
        if section_name == "record":
            lines = [self._indent(indent) + "<record>"]
            entries = item.get("entries", {})
            if isinstance(entries, dict):
                for key, value in entries.items():
                    lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
            lines.append(self._indent(indent) + "</record>")
            return lines
        if section_name in {"regexp", "exclude"}:
            lines = [self._indent(indent) + f"<{section_name}>"]
            for key, value in item.items():
                if key == "_meta":
                    continue
                lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
            lines.append(self._indent(indent) + f"</{section_name}>")
            return lines
        if section_name in {"parse", "buffer", "format", "storage", "service_discovery"}:
            return self._render_nested_plugin(section_name, item, indent=indent)
        if section_name in {"transport", "extract", "inject"}:
            arg = ""
            if "directive_arg" in item:
                arg = " " + str(item.get("directive_arg") or "")
            lines = [self._indent(indent) + f"<{section_name}{arg}>"]
            for key, value in item.items():
                if key in {"directive_arg", "_meta"}:
                    continue
                lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
            lines.append(self._indent(indent) + f"</{section_name}>")
            return lines
        return []

    def _render_nested_plugin(self, section_name: str, item: dict[str, Any], *, indent: int) -> list[str]:
        arg = ""
        if section_name == "buffer":
            chunk_keys = item.get("chunk_keys")
            if isinstance(chunk_keys, list) and chunk_keys:
                arg = " " + ",".join(str(part) for part in chunk_keys)
        lines = [self._indent(indent) + f"<{section_name}{arg}>"]
        lines.append(self._indent(indent + 2) + f"@type {_format_scalar(item.get('name', ''))}")
        for key, value in item.items():
            if key in {"name", "directive_arg", "children", "chunk_keys", "_meta"}:
                continue
            lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
        children = item.get("children")
        if isinstance(children, dict):
            for child_name, child_items in children.items():
                if not isinstance(child_items, list):
                    continue
                for child_item in child_items:
                    lines.extend(self._render_child(child_name, child_item, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{section_name}>")
        return lines

    def _render_nested_output(self, section_name: str, item: dict[str, Any], *, indent: int) -> list[str]:
        lines = [self._indent(indent) + f"<{section_name}>"]
        lines.append(self._indent(indent + 2) + f"@type {_format_scalar(item.get('name', ''))}")
        for key, value in item.items():
            if key in {"name", "directive_arg", "children", "_meta"}:
                continue
            lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
        children = item.get("children")
        if isinstance(children, dict):
            for child_name, child_items in children.items():
                if not isinstance(child_items, list):
                    continue
                for child_item in child_items:
                    lines.extend(self._render_child(child_name, child_item, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{section_name}>")
        return lines

    def _render_key_value_block(self, directive_name: str, params: dict[str, Any], *, indent: int) -> list[str]:
        lines = [self._indent(indent) + f"<{directive_name}>"]
        for key, value in params.items():
            if key == "_meta":
                continue
            lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
        lines.append(self._indent(indent) + f"</{directive_name}>")
        return lines

    @staticmethod
    def _indent(size: int) -> str:
        return " " * size
