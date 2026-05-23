from __future__ import annotations

import json
import logging
import re
from typing import Any

LOGGER = logging.getLogger(__name__)

DIRECTIVE_NAME_ROOT = "__root__"
DIRECTIVE_INCLUDE = "@include"
DIRECTIVE_SYSTEM = "system"
DIRECTIVE_LABEL = "label"
DIRECTIVE_WORKER = "worker"
DIRECTIVE_FILTER = "filter"
DIRECTIVE_MATCH = "match"
DIRECTIVE_TRANSPORT = "transport"
DIRECTIVE_BUFFER = "buffer"
DIRECTIVE_PARSE = "parse"
DIRECTIVE_FORMAT = "format"
DIRECTIVE_STORAGE = "storage"
DIRECTIVE_SERVICE_DISCOVERY = "service_discovery"
DIRECTIVE_EXTRACT = "extract"
DIRECTIVE_INJECT = "inject"
DIRECTIVE_RECORD = "record"
DIRECTIVE_REGEXP = "regexp"
DIRECTIVE_EXCLUDE = "exclude"
DIRECTIVE_SECONDARY = "secondary"
DIRECTIVE_STORE = "store"

KEY_NAME = "name"
KEY_ARG = "arg"
KEY_PARAMS = "params"
KEY_CHILDREN = "children"
KEY_SERVICE = "service"
KEY_PIPELINE = "pipeline"
KEY_INPUTS = "inputs"
KEY_FILTERS = "filters"
KEY_OUTPUTS = "outputs"
KEY_LABELS = "labels"
KEY_WORKERS = "workers"
KEY_INCLUDES = "includes"
KEY_CONFIG = "config"
KEY_OK = "ok"
KEY_ERRORS = "errors"
KEY_TYPE = "type"
KEY_MATCH = "match"
KEY_DIRECTIVE_ARG = "directive_arg"
KEY_PROTOCOL = "protocol"
KEY_CHUNK_KEYS = "chunk_keys"
KEY_ENTRIES = "entries"
KEY_PATH = "path"
KEY_META = "_meta"
KEY_AT_TYPE = "@type"

SCALAR_TRUE = "true"
SCALAR_FALSE = "false"
EMPTY_JSON_OBJECT = "{}"
EMPTY_JSON_ARRAY = "[]"
EMPTY_STRING_LITERAL = '""'
DEFAULT_MATCH = "**"
INDENT_UNIT = " "
NEWLINE = "\n"
COMMENT_PREFIX = "#"
DQUOTE = '"'
SQUOTE = "'"

DIRECTIVE_START = re.compile(r"^<(?P<name>[@A-Za-z_][\w@-]*)(?:\s+(?P<arg>.*?))?>$")
DIRECTIVE_END = re.compile(r"^</(?P<name>[@A-Za-z_][\w@-]*)>$")

SECTION_TO_PIPELINE = {
    "source": KEY_INPUTS,
    DIRECTIVE_FILTER: KEY_FILTERS,
    DIRECTIVE_MATCH: KEY_OUTPUTS,
}

SPECIAL_CHILDREN = {
    DIRECTIVE_PARSE,
    DIRECTIVE_BUFFER,
    DIRECTIVE_FORMAT,
    DIRECTIVE_TRANSPORT,
    DIRECTIVE_STORAGE,
    DIRECTIVE_SERVICE_DISCOVERY,
    DIRECTIVE_EXTRACT,
    DIRECTIVE_INJECT,
    DIRECTIVE_RECORD,
    DIRECTIVE_REGEXP,
    DIRECTIVE_EXCLUDE,
    DIRECTIVE_SECONDARY,
    DIRECTIVE_STORE,
}

NESTED_OUTPUT_DIRECTIVES = {DIRECTIVE_STORE, DIRECTIVE_SECONDARY}
DIRECTIVE_ARG_SECTIONS = {DIRECTIVE_FILTER, DIRECTIVE_MATCH}
ARG_RENDER_SECTIONS = {DIRECTIVE_FILTER, DIRECTIVE_MATCH}
RECORD_STYLE_CHILDREN = {DIRECTIVE_RECORD, DIRECTIVE_REGEXP, DIRECTIVE_EXCLUDE}
NESTED_PLUGIN_CHILDREN = {
    DIRECTIVE_PARSE,
    DIRECTIVE_BUFFER,
    DIRECTIVE_FORMAT,
    DIRECTIVE_STORAGE,
    DIRECTIVE_SERVICE_DISCOVERY,
}
DIRECTIVE_ARG_CHILDREN = {DIRECTIVE_TRANSPORT, DIRECTIVE_EXTRACT, DIRECTIVE_INJECT}
SKIP_PLUGIN_RENDER_KEYS = {KEY_NAME, KEY_MATCH, KEY_DIRECTIVE_ARG, KEY_CHILDREN, KEY_META}
SKIP_NESTED_PLUGIN_RENDER_KEYS = {
    KEY_NAME,
    KEY_DIRECTIVE_ARG,
    KEY_CHILDREN,
    KEY_CHUNK_KEYS,
    KEY_META,
}
SKIP_NESTED_OUTPUT_RENDER_KEYS = {KEY_NAME, KEY_DIRECTIVE_ARG, KEY_CHILDREN, KEY_META}
SKIP_TRANSPORT_RENDER_KEYS = {KEY_DIRECTIVE_ARG, KEY_META}


def _split_key_value(line: str) -> tuple[str, str]:
    """Split one Fluentd key/value line into the key token and remaining value text."""
    parts = line.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _strip_quotes(value: str) -> str:
    """Strip matching surrounding quotes from one scalar string value."""
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {SQUOTE, DQUOTE}:
        return trimmed[1:-1]
    return trimmed


def _parse_scalar(value: str) -> Any:
    """Parse one Fluentd scalar string into a Python value when safely possible."""
    raw = _strip_quotes(value)
    lowered = raw.lower()
    if lowered == SCALAR_TRUE:
        return True
    if lowered == SCALAR_FALSE:
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
            LOGGER.warning("failed to parse structured Fluentd scalar; keeping raw value")
            return raw
    return raw


def _format_scalar(value: Any) -> str:
    """Format one Python value as a Fluentd scalar string."""
    if isinstance(value, bool):
        return SCALAR_TRUE if value else SCALAR_FALSE
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list) or isinstance(value, dict):
        return json.dumps(value, separators=(", ", ": "))
    text = str(value)
    if not text:
        return EMPTY_STRING_LITERAL
    if any(ch.isspace() for ch in text) or any(ch in text for ch in [DQUOTE, SQUOTE, COMMENT_PREFIX]):
        return json.dumps(text)
    return text


class FluentdConfigService:
    """Parse and render standard Fluentd `.conf` text."""

    @staticmethod
    def _has_substantive_keys(payload: Any) -> bool:
        """Return whether a payload dict has keys other than metadata placeholders."""
        return isinstance(payload, dict) and any(key != KEY_META for key in payload.keys())

    def parse(self, text: str) -> dict[str, Any]:
        """Parse Fluentd text into the normalized config-service payload shape."""
        LOGGER.info("parsing Fluentd config text")
        root = self._parse_ast(text)
        model = self._ast_to_model(root)
        LOGGER.info("parsed Fluentd config text")
        return model

    def render(self, config: dict[str, Any]) -> str:
        """Render a normalized Fluentd payload back into Fluentd `.conf` text."""
        LOGGER.info("rendering Fluentd config payload")
        lines: list[str] = []
        service = config.get(KEY_SERVICE)
        if self._has_substantive_keys(service):
            lines.extend(self._render_key_value_block(DIRECTIVE_SYSTEM, service, indent=0))
            lines.append("")

        includes = config.get(KEY_INCLUDES)
        if isinstance(includes, list):
            for item in includes:
                if isinstance(item, str) and item:
                    lines.append(f"{DIRECTIVE_INCLUDE} {item}")
            if includes:
                lines.append("")

        pipeline = config.get(KEY_PIPELINE, {})
        if isinstance(pipeline, dict):
            lines.extend(self._render_pipeline(pipeline, indent=0))

        labels = config.get(KEY_LABELS)
        if isinstance(labels, list):
            for label in labels:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_label(label, indent=0))

        workers = config.get(KEY_WORKERS)
        if isinstance(workers, list):
            for worker in workers:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_worker(worker, indent=0))

        LOGGER.info("rendered Fluentd config payload")
        return NEWLINE.join(line for line in lines if line is not None).rstrip() + NEWLINE

    def _parse_ast(self, text: str) -> dict[str, Any]:
        """Parse Fluentd text into a directive tree that preserves nested structure."""
        root = {KEY_NAME: DIRECTIVE_NAME_ROOT, KEY_ARG: None, KEY_PARAMS: [], KEY_CHILDREN: []}
        stack = [root]
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(COMMENT_PREFIX):
                continue
            if stripped.startswith(f"{DIRECTIVE_INCLUDE} "):
                stack[-1][KEY_CHILDREN].append(
                    {
                        KEY_NAME: DIRECTIVE_INCLUDE,
                        KEY_ARG: stripped[len(f"{DIRECTIVE_INCLUDE} ") :].strip(),
                        KEY_PARAMS: [],
                        KEY_CHILDREN: [],
                    }
                )
                continue
            end_match = DIRECTIVE_END.match(stripped)
            if end_match:
                name = end_match.group(KEY_NAME)
                if len(stack) == 1 or stack[-1][KEY_NAME] != name:
                    raise ValueError(f"Unexpected closing directive </{name}> on line {line_number}")
                stack.pop()
                continue
            start_match = DIRECTIVE_START.match(stripped)
            if start_match:
                node = {
                    KEY_NAME: start_match.group(KEY_NAME),
                    KEY_ARG: (start_match.group(KEY_ARG) or "").strip() or None,
                    KEY_PARAMS: [],
                    KEY_CHILDREN: [],
                }
                stack[-1][KEY_CHILDREN].append(node)
                stack.append(node)
                continue
            key, value = _split_key_value(stripped)
            stack[-1][KEY_PARAMS].append((key, _parse_scalar(value)))
        if len(stack) != 1:
            open_names = " > ".join(node[KEY_NAME] for node in stack[1:])
            raise ValueError(f"Unclosed Fluentd directives: {open_names}")
        return root

    def _ast_to_model(self, root: dict[str, Any]) -> dict[str, Any]:
        """Convert a parsed directive tree into the normalized config payload."""
        config: dict[str, Any] = {
            KEY_SERVICE: {},
            KEY_PIPELINE: {KEY_INPUTS: [], KEY_FILTERS: [], KEY_OUTPUTS: []},
            KEY_LABELS: [],
            KEY_WORKERS: [],
            KEY_INCLUDES: [],
        }
        for child in root[KEY_CHILDREN]:
            self._consume_root_child(config, child)
        return config

    def _consume_root_child(self, config: dict[str, Any], node: dict[str, Any]) -> None:
        """Merge one top-level Fluentd AST child into the normalized config payload."""
        name = node[KEY_NAME]
        if name == DIRECTIVE_INCLUDE:
            config.setdefault(KEY_INCLUDES, []).append(node[KEY_ARG])
            return
        if name == DIRECTIVE_SYSTEM:
            config[KEY_SERVICE].update(self._params_dict(node))
            return
        if name == DIRECTIVE_LABEL:
            config.setdefault(KEY_LABELS, []).append(self._label_from_node(node))
            return
        if name == DIRECTIVE_WORKER:
            config.setdefault(KEY_WORKERS, []).append(self._worker_from_node(node))
            return
        if name in SECTION_TO_PIPELINE:
            config[KEY_PIPELINE][SECTION_TO_PIPELINE[name]].append(self._plugin_from_node(name, node))
            return

    def _label_from_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert one `<label>` node into the normalized label payload."""
        payload = {
            KEY_NAME: node.get(KEY_ARG) or "",
            KEY_PIPELINE: {KEY_INPUTS: [], KEY_FILTERS: [], KEY_OUTPUTS: []},
        }
        includes: list[str] = []
        for child in node[KEY_CHILDREN]:
            if child[KEY_NAME] == DIRECTIVE_INCLUDE:
                includes.append(child[KEY_ARG])
                continue
            if child[KEY_NAME] in SECTION_TO_PIPELINE:
                payload[KEY_PIPELINE][SECTION_TO_PIPELINE[child[KEY_NAME]]].append(
                    self._plugin_from_node(child[KEY_NAME], child)
                )
        if includes:
            payload[KEY_INCLUDES] = includes
        return payload

    def _worker_from_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert one `<worker>` node into the normalized worker payload."""
        payload = {
            KEY_NAME: node.get(KEY_ARG) or "",
            KEY_PIPELINE: {KEY_INPUTS: [], KEY_FILTERS: [], KEY_OUTPUTS: []},
            KEY_LABELS: [],
        }
        includes: list[str] = []
        for child in node[KEY_CHILDREN]:
            if child[KEY_NAME] == DIRECTIVE_INCLUDE:
                includes.append(child[KEY_ARG])
                continue
            if child[KEY_NAME] == DIRECTIVE_LABEL:
                payload[KEY_LABELS].append(self._label_from_node(child))
                continue
            if child[KEY_NAME] in SECTION_TO_PIPELINE:
                payload[KEY_PIPELINE][SECTION_TO_PIPELINE[child[KEY_NAME]]].append(
                    self._plugin_from_node(child[KEY_NAME], child)
                )
        if includes:
            payload[KEY_INCLUDES] = includes
        return payload

    def _plugin_from_node(
        self,
        section_name: str,
        node: dict[str, Any],
        *,
        nested_output: bool = False,
    ) -> dict[str, Any]:
        """Convert one directive node into the normalized plugin payload."""
        params = self._params_dict(node)
        name_value = params.pop(KEY_AT_TYPE, params.pop(KEY_TYPE, None))
        plugin: dict[str, Any] = {KEY_NAME: name_value or node[KEY_NAME]}
        if node.get(KEY_ARG) and section_name in DIRECTIVE_ARG_SECTIONS and not nested_output:
            plugin[KEY_MATCH] = node[KEY_ARG]
            plugin[KEY_DIRECTIVE_ARG] = node[KEY_ARG]
        if section_name == DIRECTIVE_TRANSPORT and node.get(KEY_ARG):
            plugin[KEY_PROTOCOL] = node[KEY_ARG]
            plugin[KEY_DIRECTIVE_ARG] = node[KEY_ARG]
        if section_name == DIRECTIVE_BUFFER and node.get(KEY_ARG):
            plugin[KEY_CHUNK_KEYS] = [part.strip() for part in node[KEY_ARG].split(",") if part.strip()]
        plugin.update(params)
        children = self._children_from_node(node)
        if children:
            plugin[KEY_CHILDREN] = children
        return plugin

    def _children_from_node(self, node: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Convert nested Fluentd child directives into the normalized children payload."""
        children: dict[str, list[dict[str, Any]]] = {}
        includes: list[str] = []
        for child in node[KEY_CHILDREN]:
            child_name = child[KEY_NAME]
            if child_name == DIRECTIVE_INCLUDE:
                includes.append(child[KEY_ARG])
                continue
            if child_name not in SPECIAL_CHILDREN:
                continue
            item = self._child_item_from_node(child)
            children.setdefault(child_name, []).append(item)
        if includes:
            children[KEY_INCLUDES] = [{KEY_PATH: path} for path in includes]
        return children

    def _child_item_from_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert one nested Fluentd child directive into the normalized child payload."""
        name = node[KEY_NAME]
        if name in NESTED_OUTPUT_DIRECTIVES:
            return self._plugin_from_node(DIRECTIVE_MATCH, node, nested_output=True)
        if name in RECORD_STYLE_CHILDREN:
            payload = self._params_dict(node)
            if name == DIRECTIVE_RECORD:
                return {KEY_ENTRIES: payload}
            return payload
        if name in NESTED_PLUGIN_CHILDREN:
            return self._plugin_from_node(name, node)
        if name in DIRECTIVE_ARG_CHILDREN:
            payload = self._params_dict(node)
            if node.get(KEY_ARG):
                if name == DIRECTIVE_TRANSPORT:
                    payload[KEY_PROTOCOL] = node[KEY_ARG]
                payload[KEY_DIRECTIVE_ARG] = node[KEY_ARG]
            return payload
        return self._params_dict(node)

    def _params_dict(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert one node parameter list into a dictionary payload."""
        payload: dict[str, Any] = {}
        for key, value in node.get(KEY_PARAMS, []):
            payload[key] = value
        return payload

    def _render_pipeline(self, pipeline: dict[str, Any], *, indent: int) -> list[str]:
        """Render the normalized Fluentd pipeline sections back into directive blocks."""
        lines: list[str] = []
        for section_key, directive_name in (
            (KEY_INPUTS, "source"),
            (KEY_FILTERS, DIRECTIVE_FILTER),
            (KEY_OUTPUTS, DIRECTIVE_MATCH),
        ):
            items = pipeline.get(section_key)
            if not isinstance(items, list):
                continue
            for item in items:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_plugin(item, directive_name, indent=indent))
        return lines

    def _render_label(self, label: dict[str, Any], *, indent: int) -> list[str]:
        """Render one normalized label payload into Fluentd label directives."""
        name = str(label.get(KEY_NAME) or "").strip()
        lines = [self._indent(indent) + f"<{DIRECTIVE_LABEL} {name}>"]
        includes = label.get(KEY_INCLUDES)
        if isinstance(includes, list):
            for item in includes:
                if isinstance(item, str) and item:
                    lines.append(self._indent(indent + 2) + f"{DIRECTIVE_INCLUDE} {item}")
        pipeline = label.get(KEY_PIPELINE, {})
        lines.extend(self._render_pipeline(pipeline, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{DIRECTIVE_LABEL}>")
        return lines

    def _render_worker(self, worker: dict[str, Any], *, indent: int) -> list[str]:
        """Render one normalized worker payload into Fluentd worker directives."""
        name = str(worker.get(KEY_NAME) or "").strip()
        lines = [self._indent(indent) + f"<{DIRECTIVE_WORKER} {name}>"]
        includes = worker.get(KEY_INCLUDES)
        if isinstance(includes, list):
            for item in includes:
                if isinstance(item, str) and item:
                    lines.append(self._indent(indent + 2) + f"{DIRECTIVE_INCLUDE} {item}")
        pipeline = worker.get(KEY_PIPELINE, {})
        lines.extend(self._render_pipeline(pipeline, indent=indent + 2))
        labels = worker.get(KEY_LABELS)
        if isinstance(labels, list):
            for label in labels:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.extend(self._render_label(label, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{DIRECTIVE_WORKER}>")
        return lines

    def _render_plugin(self, plugin: dict[str, Any], directive_name: str, *, indent: int) -> list[str]:
        """Render one normalized plugin payload into a Fluentd directive block."""
        arg = ""
        if directive_name in ARG_RENDER_SECTIONS:
            arg_value = plugin.get(KEY_MATCH, plugin.get(KEY_DIRECTIVE_ARG))
            arg = " " + str(arg_value or DEFAULT_MATCH)
        lines = [self._indent(indent) + f"<{directive_name}{arg}>"]
        lines.extend(self._render_plugin_body(plugin, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{directive_name}>")
        return lines

    def _render_plugin_body(self, plugin: dict[str, Any], *, indent: int) -> list[str]:
        """Render the body lines for one normalized plugin payload."""
        lines = [self._indent(indent) + f"{KEY_AT_TYPE} {_format_scalar(plugin.get(KEY_NAME, ''))}"]
        for key, value in plugin.items():
            if key in SKIP_PLUGIN_RENDER_KEYS:
                continue
            if key == KEY_CHUNK_KEYS:
                continue
            lines.append(self._indent(indent) + f"{key} {_format_scalar(value)}")
        children = plugin.get(KEY_CHILDREN)
        if isinstance(children, dict):
            for child_name, child_items in children.items():
                if child_name == KEY_INCLUDES:
                    for include in child_items:
                        path = include.get(KEY_PATH)
                        if path:
                            lines.append(self._indent(indent) + f"{DIRECTIVE_INCLUDE} {path}")
                    continue
                if not isinstance(child_items, list):
                    continue
                for child_item in child_items:
                    lines.extend(self._render_child(child_name, child_item, indent=indent))
        return lines

    def _render_child(self, section_name: str, item: dict[str, Any], *, indent: int) -> list[str]:
        """Render one normalized nested child payload into Fluentd child directives."""
        if section_name in NESTED_OUTPUT_DIRECTIVES:
            return self._render_nested_output(section_name, item, indent=indent)
        if section_name == DIRECTIVE_RECORD:
            lines = [self._indent(indent) + f"<{DIRECTIVE_RECORD}>"]
            entries = item.get(KEY_ENTRIES, {})
            if isinstance(entries, dict):
                for key, value in entries.items():
                    lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
            lines.append(self._indent(indent) + f"</{DIRECTIVE_RECORD}>")
            return lines
        if section_name in {DIRECTIVE_REGEXP, DIRECTIVE_EXCLUDE}:
            lines = [self._indent(indent) + f"<{section_name}>"]
            for key, value in item.items():
                if key == KEY_META:
                    continue
                lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
            lines.append(self._indent(indent) + f"</{section_name}>")
            return lines
        if section_name in NESTED_PLUGIN_CHILDREN:
            return self._render_nested_plugin(section_name, item, indent=indent)
        if section_name in DIRECTIVE_ARG_CHILDREN:
            arg = ""
            if section_name == DIRECTIVE_TRANSPORT:
                protocol = item.get(KEY_PROTOCOL, item.get(KEY_DIRECTIVE_ARG))
                if protocol is not None:
                    arg = " " + str(protocol or "")
            elif KEY_DIRECTIVE_ARG in item:
                arg = " " + str(item.get(KEY_DIRECTIVE_ARG) or "")
            lines = [self._indent(indent) + f"<{section_name}{arg}>"]
            for key, value in item.items():
                if key in SKIP_TRANSPORT_RENDER_KEYS or (
                    section_name == DIRECTIVE_TRANSPORT and key == KEY_PROTOCOL
                ):
                    continue
                lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
            lines.append(self._indent(indent) + f"</{section_name}>")
            return lines
        return []

    def _render_nested_plugin(self, section_name: str, item: dict[str, Any], *, indent: int) -> list[str]:
        """Render one nested plugin payload such as `<buffer>` or `<parse>`."""
        arg = ""
        if section_name == DIRECTIVE_BUFFER:
            chunk_keys = item.get(KEY_CHUNK_KEYS)
            if isinstance(chunk_keys, list) and chunk_keys:
                arg = " " + ",".join(str(part) for part in chunk_keys)
        lines = [self._indent(indent) + f"<{section_name}{arg}>"]
        lines.append(self._indent(indent + 2) + f"{KEY_AT_TYPE} {_format_scalar(item.get(KEY_NAME, ''))}")
        for key, value in item.items():
            if key in SKIP_NESTED_PLUGIN_RENDER_KEYS:
                continue
            lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
        children = item.get(KEY_CHILDREN)
        if isinstance(children, dict):
            for child_name, child_items in children.items():
                if not isinstance(child_items, list):
                    continue
                for child_item in child_items:
                    lines.extend(self._render_child(child_name, child_item, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{section_name}>")
        return lines

    def _render_nested_output(self, section_name: str, item: dict[str, Any], *, indent: int) -> list[str]:
        """Render one nested output payload such as `<store>` or `<secondary>`."""
        lines = [self._indent(indent) + f"<{section_name}>"]
        lines.append(self._indent(indent + 2) + f"{KEY_AT_TYPE} {_format_scalar(item.get(KEY_NAME, ''))}")
        for key, value in item.items():
            if key in SKIP_NESTED_OUTPUT_RENDER_KEYS:
                continue
            lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
        children = item.get(KEY_CHILDREN)
        if isinstance(children, dict):
            for child_name, child_items in children.items():
                if not isinstance(child_items, list):
                    continue
                for child_item in child_items:
                    lines.extend(self._render_child(child_name, child_item, indent=indent + 2))
        lines.append(self._indent(indent) + f"</{section_name}>")
        return lines

    def _render_key_value_block(self, directive_name: str, params: dict[str, Any], *, indent: int) -> list[str]:
        """Render one simple directive block that contains only key/value pairs."""
        lines = [self._indent(indent) + f"<{directive_name}>"]
        for key, value in params.items():
            if key == KEY_META:
                continue
            lines.append(self._indent(indent + 2) + f"{key} {_format_scalar(value)}")
        lines.append(self._indent(indent) + f"</{directive_name}>")
        return lines

    @staticmethod
    def _indent(size: int) -> str:
        """Return the left-padding string for one render indentation depth."""
        return INDENT_UNIT * size
