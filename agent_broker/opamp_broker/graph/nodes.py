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

"""Node implementations for normalization, intent classification, and execution.

The graph keeps each stage as a focused function so intermediate state is easy
to inspect and behavior can be extended without rewriting the full pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Final

try:
    import pandas as pd
except Exception:  # pragma: no cover - fallback for minimal runtime environments.
    pd = None  # type: ignore[assignment]

from opamp_broker.graph.state import (
    STATE_KEY_API_COMMAND_MODE,
    STATE_KEY_COMMAND,
    STATE_KEY_CONVERSATION_HISTORY,
    STATE_KEY_INTENT,
    STATE_KEY_NORMALIZED_TEXT,
    STATE_KEY_REQUIRES_CONFIRMATION,
    STATE_KEY_RESPONSE_TEXT,
    STATE_KEY_TARGET,
    STATE_KEY_TEXT,
    STATE_KEY_TOOL_ARGS,
    STATE_KEY_TOOL_NAME,
    STATE_KEY_TOOL_RESULT,
    STATE_KEY_TOOLS_AVAILABLE,
    BrokerState,
)
from opamp_broker.graph.slash_commands import apply_slash_command_overrides
from opamp_broker.graph.table_rendering import render_fixed_width_table
from opamp_broker.mcp.tools import MCPToolRegistry
from opamp_broker.mcp.client import MCPServerUnavailableError
from opamp_broker.planner.engine import (
    Planner,
    RESPONSE_TEXT_KEY,
    TOOL_ARGS_KEY,
    TOOL_NAME_KEY,
)
from opamp_broker.planner.rule_first_planner import RuleFirstPlanner

DEFAULT_MCP_SERVER_OFFLINE_MESSAGE = (
    "The OpAMP server is currently offline. Please try again shortly."
)

# Tool response payload keys.
PAYLOAD_KEY_ACTION: Final[str] = "action"
PAYLOAD_KEY_AGENT_ID: Final[str] = "agent_id"
PAYLOAD_KEY_AGENTS: Final[str] = "agents"
PAYLOAD_KEY_CLASSIFIER: Final[str] = "classifier"
PAYLOAD_KEY_CLIENT_ID: Final[str] = "client_id"
PAYLOAD_KEY_COMMANDS: Final[str] = "commands"
PAYLOAD_KEY_CONTENT: Final[str] = "content"
PAYLOAD_KEY_DISPLAY_NAME: Final[str] = "displayname"
PAYLOAD_KEY_ERROR: Final[str] = "error"
PAYLOAD_KEY_ID: Final[str] = "id"
PAYLOAD_KEY_INSTANCE_ID: Final[str] = "instance_id"
PAYLOAD_KEY_NAME: Final[str] = "name"
PAYLOAD_KEY_OPERATION: Final[str] = "operation"
PAYLOAD_KEY_OPENAPI_SPEC: Final[str] = "openapi_spec"
PAYLOAD_KEY_PATHS: Final[str] = "paths"
PAYLOAD_KEY_STATUS: Final[str] = "status"
PAYLOAD_KEY_TEXT: Final[str] = "text"
PAYLOAD_KEY_TOTAL: Final[str] = "total"

PAYLOAD_STATUS_QUEUED: Final[str] = "queued"
UNKNOWN_CLIENT_LABEL: Final[str] = "unknown-client"
RESPONSE_PREVIEW_ITEM_LIMIT: Final[int] = 10
AGENT_TABLE_MAX_ROWS: Final[int] = RESPONSE_PREVIEW_ITEM_LIMIT
AGENT_LONG_DETAILS_MAX_ITEMS: Final[int] = AGENT_TABLE_MAX_ROWS
AGENT_DESCRIPTION_KEY_PREFIX: Final[str] = "key:"
AGENT_DESCRIPTION_STRING_VALUE_PREFIX: Final[str] = "string_value:"
AGENT_DESCRIPTION_BOOL_VALUE_PREFIX: Final[str] = "bool_value:"
AGENT_DESCRIPTION_INT_VALUE_PREFIX: Final[str] = "int_value:"
AGENT_DESCRIPTION_DOUBLE_VALUE_PREFIX: Final[str] = "double_value:"
AGENT_DESCRIPTION_BYTES_VALUE_PREFIX: Final[str] = "bytes_value:"
AGENT_FALLBACK_IP_KEY: Final[str] = "ip"
AGENT_FALLBACK_HOSTNAME_KEY: Final[str] = "hostname"
AGENT_FALLBACK_MAC_KEY: Final[str] = "mac_address"
AGENT_SOURCE_REMOTE_ADDR_KEY: Final[str] = "remote_addr"
AGENT_SOURCE_CLIENT_ID_KEY: Final[str] = "client_id"
AGENT_SOURCE_AGENT_DESCRIPTION_KEY: Final[str] = "agent_description"
OPENAPI_COMPONENTS_KEY: Final[str] = "components"
OPENAPI_SCHEMAS_KEY: Final[str] = "schemas"
OPENAPI_PROPERTIES_KEY: Final[str] = "properties"
OPENAPI_DESCRIPTION_KEY: Final[str] = "description"
OPENAPI_OTEL_AGENT_SCHEMA_KEY: Final[str] = "OtelAgent"
OPENAPI_PATHS_KEY: Final[str] = "paths"
OPENAPI_TOOL_OTEL_AGENTS_PATH_KEY: Final[str] = "/tool/otelAgents"
OPENAPI_GET_KEY: Final[str] = "get"
OPENAPI_RESPONSES_KEY: Final[str] = "responses"
OPENAPI_RESPONSE_200_KEY: Final[str] = "200"
OPENAPI_CONTENT_KEY: Final[str] = "content"
OPENAPI_APPLICATION_JSON_KEY: Final[str] = "application/json"
OPENAPI_SCHEMA_KEY: Final[str] = "schema"
OPENAPI_SCHEMA_REF_KEY: Final[str] = "$ref"
OPENAPI_REF_PREFIX: Final[str] = "#/components/schemas/"
MARKDOWN_BULLET: Final[str] = "- "
COMPONENT_HEALTH_NORMALIZED_KEY: Final[str] = "componenthealth"
AGENT_TABLE_ATTRIBUTE_HEADER: Final[str] = "attribute"
AGENT_TABLE_MISSING_VALUE: Final[str] = "-"
AGENT_TABLE_MAX_ATTRIBUTE_COLUMN_WIDTH: Final[int] = 24
AGENT_TABLE_MAX_AGENT_COLUMN_WIDTH: Final[int] = 36
AGENT_TABLE_FALLBACK_LABEL_PREFIX: Final[str] = "agent-"
AGENT_LABEL_KEYS: Final[tuple[str, ...]] = (
    PAYLOAD_KEY_ID,
    PAYLOAD_KEY_NAME,
    PAYLOAD_KEY_AGENT_ID,
    PAYLOAD_KEY_INSTANCE_ID,
)
AGENT_TABLE_PRIORITY_COLUMNS: Final[tuple[str, ...]] = (
    PAYLOAD_KEY_ID,
    PAYLOAD_KEY_NAME,
    PAYLOAD_KEY_AGENT_ID,
    PAYLOAD_KEY_INSTANCE_ID,
    PAYLOAD_KEY_STATUS,
)
AGENT_SHORT_RICH_TEXT_FIELDS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("service.name", ("service.name",)),
    ("service.type", ("service.type",)),
    ("service.instance.id", ("service.instance.id",)),
    ("service.version", ("service.version",)),
    ("os_type", ("os.type", "os_type")),
    ("os_version", ("os.version", "os_version")),
    ("hostname", ("host.name", AGENT_FALLBACK_HOSTNAME_KEY)),
    ("ip", ("host.ip", "ip", "ip_address", AGENT_SOURCE_REMOTE_ADDR_KEY)),
    ("mac_address", ("host.mac", "host.mac_address", AGENT_FALLBACK_MAC_KEY)),
)
AGENT_FIELD_DESCRIPTION_DEFAULTS: Final[dict[str, str]] = {
    "service.name": "Service name reported by the OpenTelemetry agent.",
    "service.type": "Service type/category for the running workload.",
    "service.instance.id": "Stable instance identifier for the running service.",
    "service.version": "Service version reported in agent identifying attributes.",
    "os.type": "Operating system family/type for the host environment.",
    "os.version": "Operating system version for the host environment.",
    "host.name": "Hostname reported by the agent.",
    "host.ip": "Primary host IP address reported by the agent.",
    "host.mac": "Primary host MAC address reported by the agent.",
    AGENT_SOURCE_CLIENT_ID_KEY: "Unique client identifier tracked by the provider.",
    AGENT_SOURCE_REMOTE_ADDR_KEY: "Last known source IP address observed by the provider.",
}
AGENT_CORE_DETAIL_FIELDS: Final[tuple[str, ...]] = (
    AGENT_SOURCE_CLIENT_ID_KEY,
    "service.name",
    "service.type",
    "service.instance.id",
    "service.version",
    "os.type",
    "os.version",
    "host.name",
    "host.ip",
    "host.mac",
    AGENT_SOURCE_REMOTE_ADDR_KEY,
)
PLANNER_MAX_EXECUTION_STEPS_DEFAULT: Final[int] = 4
PLANNER_MAX_EXECUTION_STEPS_HARD_LIMIT: Final[int] = 8
PLANNER_FOLLOW_UP_SUMMARY_MAX_CHARS: Final[int] = 1200
PLANNER_FOLLOW_UP_ARGS_MAX_CHARS: Final[int] = 400

logger = logging.getLogger(__name__)

ToolResponseFormatter = Callable[
    [str, str, dict[str, Any], dict[str, Any], str],
    Awaitable[str | None],
]


def _normalize_tool_args(raw_tool_args: Any) -> dict[str, Any]:
    """Return normalized tool args as a dictionary.

    Why this helper exists:
    planner output can contain malformed types; execution paths should always
    handle arguments as a dict to keep tool calls predictable.
    """
    if isinstance(raw_tool_args, dict):
        return raw_tool_args
    return {}


def _normalize_planner_step_limit(max_planning_steps: int) -> int:
    """Clamp configured planner step count to a safe bounded range."""
    try:
        normalized = int(max_planning_steps)
    except (TypeError, ValueError):
        return PLANNER_MAX_EXECUTION_STEPS_DEFAULT
    if normalized <= 0:
        return 1
    if normalized > PLANNER_MAX_EXECUTION_STEPS_HARD_LIMIT:
        return PLANNER_MAX_EXECUTION_STEPS_HARD_LIMIT
    return normalized


def _build_follow_up_planner_text(
    *,
    user_text: str,
    tool_name: str,
    tool_args: dict[str, Any],
    tool_summary: str,
) -> str:
    """Build follow-up planner prompt text after one tool execution.

    Why this helper exists:
    multi-step planning needs explicit context from the latest tool execution so
    the LLM can decide whether to stop or select the next tool call.
    """
    try:
        rendered_args = json.dumps(tool_args, ensure_ascii=False, default=str)
    except TypeError:
        rendered_args = str(tool_args)
    if len(rendered_args) > PLANNER_FOLLOW_UP_ARGS_MAX_CHARS:
        rendered_args = rendered_args[:PLANNER_FOLLOW_UP_ARGS_MAX_CHARS] + "..."

    summary = str(tool_summary).strip()
    if len(summary) > PLANNER_FOLLOW_UP_SUMMARY_MAX_CHARS:
        omitted = len(summary) - PLANNER_FOLLOW_UP_SUMMARY_MAX_CHARS
        summary = (
            summary[:PLANNER_FOLLOW_UP_SUMMARY_MAX_CHARS]
            + f"... [truncated {omitted} chars]"
        )

    return (
        "Continue this request if needed.\n"
        f"Original user request: {user_text}\n"
        f"Latest executed tool: {tool_name}\n"
        f"Latest tool args: {rendered_args}\n"
        f"Latest tool result summary: {summary}\n"
        "If the request is complete, set tool_name to null and provide final response_text. "
        "If another tool call is required, choose exactly one next tool."
    )


def _strip_bot_mention(text: str) -> str:
    """Remove Slack bot mention tokens from inbound text.

    Why this approach:
    mention tokens are transport noise that can degrade intent matching if not
    removed before normalization.

    Args:
        text: Raw message text from Slack events or slash commands.

    Returns:
        str: Text with ``<@...>`` mention fragments removed and stripped.
    """
    return re.sub(r"<@[^>]+>", "", text).strip()


def _format_tool_response(tool_name: str, result: dict[str, Any]) -> str:
    """Convert MCP tool output into a concise user-facing explanation."""
    content = result.get(PAYLOAD_KEY_CONTENT)
    parsed_content = _parse_content_payload(content)

    if isinstance(parsed_content, dict):
        error = parsed_content.get(PAYLOAD_KEY_ERROR)
        if isinstance(error, str) and error.strip():
            return f"The tool `{tool_name}` returned an error: {error.strip()}"

        if PAYLOAD_KEY_AGENTS in parsed_content and isinstance(parsed_content[PAYLOAD_KEY_AGENTS], list):
            return _summarize_agents_payload(parsed_content)

        if PAYLOAD_KEY_COMMANDS in parsed_content and isinstance(parsed_content[PAYLOAD_KEY_COMMANDS], list):
            return _summarize_commands_payload(parsed_content)

        if PAYLOAD_KEY_PATHS in parsed_content and isinstance(parsed_content[PAYLOAD_KEY_PATHS], dict):
            return _summarize_openapi_payload(parsed_content)

        if str(parsed_content.get(PAYLOAD_KEY_STATUS, "")).strip().lower() == PAYLOAD_STATUS_QUEUED:
            return _summarize_queue_result(parsed_content)

        return _summarize_mapping(parsed_content)

    if isinstance(parsed_content, list):
        if not parsed_content:
            return "The tool returned an empty result."
        preview = ", ".join(
            str(item) for item in parsed_content[:RESPONSE_PREVIEW_ITEM_LIMIT]
        )
        suffix = (
            ""
            if len(parsed_content) <= RESPONSE_PREVIEW_ITEM_LIMIT
            else ", ..."
        )
        return f"The tool returned {len(parsed_content)} item(s): {preview}{suffix}"

    text = str(parsed_content).strip()
    if text:
        return text
    return "The tool completed, but did not return any output."


def _parse_content_payload(content: Any) -> Any:
    """Normalize MCP content payload without attempting JSON auto-parsing."""
    if isinstance(content, list):
        text_chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and PAYLOAD_KEY_TEXT in item:
                text_chunks.append(str(item.get(PAYLOAD_KEY_TEXT, "")))
            else:
                text_chunks.append(str(item))
        return " ".join(chunk for chunk in text_chunks if chunk.strip()).strip()
    if isinstance(content, str):
        return content
    if content is None:
        return {}
    return content


def _extract_agent_labels(agents: list[Any]) -> list[str]:
    """Extract stable human-readable labels from agent payload entries.

    Why this helper exists:
    summary responses need deterministic labels even when payloads vary across
    provider versions and tool implementations.
    """
    labels: list[str] = []
    for agent in agents:
        if isinstance(agent, dict):
            for key in AGENT_LABEL_KEYS:
                value = agent.get(key)
                if value is not None and str(value).strip():
                    labels.append(str(value).strip())
                    break
        elif str(agent).strip():
            labels.append(str(agent).strip())
    return labels


def _summarize_agents_payload(payload: dict[str, Any]) -> str:
    """Build a concise natural-language summary for an agents tool payload.

    Why this helper exists:
    agent list results can be large; we provide a compact summary/table preview
    for Slack-friendly responses.
    """
    agents_raw = payload.get(PAYLOAD_KEY_AGENTS, [])
    if not isinstance(agents_raw, list):
        return "I checked the agents list, but the payload was invalid."
    total_raw = payload.get(PAYLOAD_KEY_TOTAL)
    try:
        total = int(total_raw) if total_raw is not None else len(agents_raw)
    except (TypeError, ValueError):
        total = len(agents_raw)

    if total <= 0:
        return "I checked and found no OpenTelemetry agents."

    summary_table = _render_agents_summary_table(agents_raw)
    if summary_table:
        shown = min(len(agents_raw), AGENT_TABLE_MAX_ROWS)
        suffix = (
            f"\nShowing first {shown} agent(s)."
            if total > shown or len(agents_raw) > shown
            else ""
        )
        return (
            f"I found {total} OpenTelemetry agent(s).{suffix}\n\n"
            "Summary view (attributes x agents):\n"
            f"```\n{summary_table}\n```"
        )

    labels = _extract_agent_labels(agents_raw)
    if labels:
        preview = ", ".join(labels[:AGENT_TABLE_MAX_ROWS])
        extra = "" if len(labels) <= AGENT_TABLE_MAX_ROWS else ", ..."
        return f"I found {total} OpenTelemetry agent(s): {preview}{extra}"
    return f"I found {total} OpenTelemetry agent(s)."


def _render_agents_short_rich_text(agents: list[Any]) -> str:
    """Render a short bullet list view of agents and key identifying fields."""
    rendered: list[str] = []
    for agent in agents[:AGENT_TABLE_MAX_ROWS]:
        if not isinstance(agent, dict):
            continue
        line = _render_agent_short_rich_text(agent)
        if line:
            rendered.append(f"{MARKDOWN_BULLET}{line}")
    return "\n".join(rendered)


def _render_agents_summary_table(agents: list[Any]) -> str | None:
    """Render a fixed-width attribute-vs-agent summary table.

    Why this helper exists:
    tabular output makes cross-agent comparisons easier than paragraph text.
    """
    table_agents = [agent for agent in agents[:AGENT_TABLE_MAX_ROWS] if isinstance(agent, dict)]
    if not table_agents:
        return None

    headers = [AGENT_TABLE_ATTRIBUTE_HEADER]
    agent_values: list[dict[str, str]] = []
    for index, agent in enumerate(table_agents):
        labels = _extract_agent_labels([agent])
        fallback_label = f"{AGENT_TABLE_FALLBACK_LABEL_PREFIX}{index + 1}"
        headers.append(labels[0] if labels else fallback_label)
        agent_values.append(_extract_agent_attribute_values(agent))

    rows: list[list[str]] = []
    for label, candidates in AGENT_SHORT_RICH_TEXT_FIELDS:
        row = [label]
        for values in agent_values:
            row.append(
                _first_non_empty_attribute(values, candidates)
                or AGENT_TABLE_MISSING_VALUE
            )
        rows.append(row)
    return render_fixed_width_table(
        headers,
        rows,
        first_column_max_width=AGENT_TABLE_MAX_ATTRIBUTE_COLUMN_WIDTH,
        data_column_max_width=AGENT_TABLE_MAX_AGENT_COLUMN_WIDTH,
    )


def _render_agent_short_rich_text(agent: dict[str, Any]) -> str:
    """Render one agent as compact `key=value` text for quick previews."""
    values = _extract_agent_attribute_values(agent)
    parts: list[str] = []
    for label, candidates in AGENT_SHORT_RICH_TEXT_FIELDS:
        value = _first_non_empty_attribute(values, candidates)
        if value:
            parts.append(f"{label}={value}")
    if parts:
        return "; ".join(parts)
    fallback_label = _extract_agent_labels([agent])
    if fallback_label:
        return str(fallback_label[0])
    return ""


def _render_agent_short_rich_txt(agent: dict[str, Any]) -> str:
    """Compatibility alias using `rich_txt` naming for short agent rendering."""
    return _render_agent_short_rich_text(agent)


def _render_agents_detailed_rich_text(
    agents: list[Any],
    *,
    field_descriptions: dict[str, str],
) -> str:
    """Render detailed markdown bullets for multiple agents.

    Why this helper exists:
    detailed views are useful for diagnostics while still enforcing response
    size limits for chat surfaces.
    """
    rendered: list[str] = []
    count = 0
    for agent in agents:
        if count >= AGENT_LONG_DETAILS_MAX_ITEMS:
            break
        if not isinstance(agent, dict):
            continue
        count += 1
        rendered.append(f"Agent {count}:")
        details = _render_agent_long_rich_text(
            agent,
            field_descriptions=field_descriptions,
        )
        if details:
            rendered.append(details)
    return "\n".join(rendered).strip()


def _render_agent_long_rich_text(
    agent: dict[str, Any],
    *,
    field_descriptions: dict[str, str],
) -> str:
    """Render one agent with ordered attributes and optional field descriptions."""
    values = _extract_agent_attribute_values(agent)
    if not values:
        return f"{MARKDOWN_BULLET}No attributes reported."
    ordered_keys = _order_agent_attribute_keys(values)
    lines: list[str] = []
    for key in ordered_keys:
        raw_value = values.get(key)
        if raw_value is None:
            continue
        value = str(raw_value).strip()
        if not value:
            continue
        description = field_descriptions.get(key, "").strip()
        if description:
            lines.append(f"{MARKDOWN_BULLET}`{key}`: `{value}` ({description})")
        else:
            lines.append(f"{MARKDOWN_BULLET}`{key}`: `{value}`")
    return "\n".join(lines)


def _render_agent_long_rich_txt(
    agent: dict[str, Any],
    *,
    field_descriptions: dict[str, str],
) -> str:
    """Compatibility alias using `rich_txt` naming for detailed rendering."""
    return _render_agent_long_rich_text(
        agent,
        field_descriptions=field_descriptions,
    )


def _order_agent_attribute_keys(values: dict[str, str]) -> list[str]:
    """Order attributes with core diagnostic keys first, then alphabetical extras."""
    core_keys = [key for key in AGENT_CORE_DETAIL_FIELDS if key in values]
    remaining = sorted(
        key for key in values if key not in set(AGENT_CORE_DETAIL_FIELDS)
    )
    return core_keys + remaining


def _extract_agent_attribute_values(agent: dict[str, Any]) -> dict[str, str]:
    """Normalize a raw agent object into flattened, display-ready string attributes."""
    values: dict[str, str] = {}
    for key, value in agent.items():
        if str(key) == AGENT_SOURCE_AGENT_DESCRIPTION_KEY:
            continue
        if isinstance(value, (dict, list)):
            continue
        rendered = str(value).strip() if value is not None else ""
        if rendered:
            values[str(key)] = rendered

    description_attributes = _parse_agent_description_attributes(
        str(agent.get(AGENT_SOURCE_AGENT_DESCRIPTION_KEY, ""))
    )
    values.update(description_attributes)

    if AGENT_SOURCE_REMOTE_ADDR_KEY in values and AGENT_FALLBACK_IP_KEY not in values:
        values[AGENT_FALLBACK_IP_KEY] = values[AGENT_SOURCE_REMOTE_ADDR_KEY]
    if "host.name" in values and AGENT_FALLBACK_HOSTNAME_KEY not in values:
        values[AGENT_FALLBACK_HOSTNAME_KEY] = values["host.name"]
    if "host.mac" in values and AGENT_FALLBACK_MAC_KEY not in values:
        values[AGENT_FALLBACK_MAC_KEY] = values["host.mac"]
    return values


def _parse_agent_description_attributes(agent_description: str) -> dict[str, str]:
    """Extract key/value attributes from proto-like `agent_description` text blocks."""
    attributes: dict[str, str] = {}
    if not agent_description.strip():
        return attributes

    current_key: str | None = None
    for raw_line in agent_description.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key_match = re.search(r'key:\s*"([^"]+)"', line)
        if key_match:
            current_key = key_match.group(1).strip()
            inline_value = _extract_inline_proto_value(line)
            if current_key and inline_value:
                attributes[current_key] = inline_value
                current_key = None
            continue
        if not current_key:
            continue
        inline_value = _extract_inline_proto_value(line)
        if inline_value:
            attributes[current_key] = inline_value
            current_key = None
    return attributes


def _parse_proto_scalar(line: str) -> str:
    """Parse a simple proto scalar line into a cleaned string value."""
    _, _, raw = line.partition(":")
    candidate = raw.strip()
    if candidate.startswith('"') and candidate.endswith('"') and len(candidate) >= 2:
        return candidate[1:-1]
    return candidate


def _extract_inline_proto_value(line: str) -> str:
    """Extract inline proto `*_value` tokens from a single text line."""
    for prefix in (
        AGENT_DESCRIPTION_STRING_VALUE_PREFIX,
        AGENT_DESCRIPTION_BOOL_VALUE_PREFIX,
        AGENT_DESCRIPTION_INT_VALUE_PREFIX,
        AGENT_DESCRIPTION_DOUBLE_VALUE_PREFIX,
        AGENT_DESCRIPTION_BYTES_VALUE_PREFIX,
    ):
        marker_index = line.find(prefix)
        if marker_index < 0:
            continue
        candidate = line[marker_index + len(prefix):].strip()
        if not candidate:
            continue
        candidate = candidate.split("}", 1)[0].strip()
        candidate = candidate.split("{", 1)[0].strip()
        if candidate.startswith('"') and candidate.endswith('"') and len(candidate) >= 2:
            candidate = candidate[1:-1]
        if candidate:
            return candidate
    return ""


def _first_non_empty_attribute(
    values: dict[str, str],
    keys: tuple[str, ...],
) -> str | None:
    """Return the first non-empty value for a prioritized set of attribute keys."""
    for key in keys:
        value = values.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _resolve_agent_field_descriptions(openapi_spec: Any) -> dict[str, str]:
    """Merge default field descriptions with OpenAPI-derived schema descriptions."""
    descriptions: dict[str, str] = dict(AGENT_FIELD_DESCRIPTION_DEFAULTS)
    schema_descriptions = _extract_agent_field_descriptions_from_spec(openapi_spec)
    descriptions.update(schema_descriptions)
    return descriptions


def _extract_agent_field_descriptions_from_spec(openapi_spec: Any) -> dict[str, str]:
    """Extract attribute descriptions for `OtelAgent` fields from OpenAPI spec."""
    if not isinstance(openapi_spec, dict):
        return {}

    schema = _resolve_otel_agent_schema_from_spec(openapi_spec)
    if not isinstance(schema, dict):
        return {}
    properties = schema.get(OPENAPI_PROPERTIES_KEY)
    if not isinstance(properties, dict):
        return {}

    descriptions: dict[str, str] = {}
    for key, property_spec in properties.items():
        if not isinstance(property_spec, dict):
            continue
        description = str(property_spec.get(OPENAPI_DESCRIPTION_KEY, "")).strip()
        if description:
            descriptions[str(key)] = description
    return descriptions


def _resolve_otel_agent_schema_from_spec(openapi_spec: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve the effective `OtelAgent` schema from components or response refs."""
    components = openapi_spec.get(OPENAPI_COMPONENTS_KEY)
    if not isinstance(components, dict):
        return None
    schemas = components.get(OPENAPI_SCHEMAS_KEY)
    if not isinstance(schemas, dict):
        return None

    direct_schema = schemas.get(OPENAPI_OTEL_AGENT_SCHEMA_KEY)
    if isinstance(direct_schema, dict):
        return direct_schema

    paths = openapi_spec.get(OPENAPI_PATHS_KEY)
    if not isinstance(paths, dict):
        return None
    otel_agents_path = paths.get(OPENAPI_TOOL_OTEL_AGENTS_PATH_KEY)
    if not isinstance(otel_agents_path, dict):
        return None
    get_operation = otel_agents_path.get(OPENAPI_GET_KEY)
    if not isinstance(get_operation, dict):
        return None
    responses = get_operation.get(OPENAPI_RESPONSES_KEY)
    if not isinstance(responses, dict):
        return None
    ok_response = responses.get(OPENAPI_RESPONSE_200_KEY)
    if not isinstance(ok_response, dict):
        return None
    content = ok_response.get(OPENAPI_CONTENT_KEY)
    if not isinstance(content, dict):
        return None
    app_json = content.get(OPENAPI_APPLICATION_JSON_KEY)
    if not isinstance(app_json, dict):
        return None
    schema = app_json.get(OPENAPI_SCHEMA_KEY)
    if not isinstance(schema, dict):
        return None
    schema_ref = str(schema.get(OPENAPI_SCHEMA_REF_KEY, "")).strip()
    if not schema_ref.startswith(OPENAPI_REF_PREFIX):
        return None
    schema_name = schema_ref[len(OPENAPI_REF_PREFIX):]
    response_schema = schemas.get(schema_name)
    if not isinstance(response_schema, dict):
        return None
    response_properties = response_schema.get(OPENAPI_PROPERTIES_KEY)
    if not isinstance(response_properties, dict):
        return None
    agents_property = response_properties.get(PAYLOAD_KEY_AGENTS)
    if not isinstance(agents_property, dict):
        return None
    items = agents_property.get("items")
    if not isinstance(items, dict):
        return None
    item_ref = str(items.get(OPENAPI_SCHEMA_REF_KEY, "")).strip()
    if not item_ref.startswith(OPENAPI_REF_PREFIX):
        return None
    item_schema_name = item_ref[len(OPENAPI_REF_PREFIX):]
    item_schema = schemas.get(item_schema_name)
    if isinstance(item_schema, dict):
        return item_schema
    return None


def _render_agents_table(agents: list[Any]) -> str | None:
    """Render a pandas-based normalized agent table when pandas is available.

    Why this helper exists:
    this path provides a broad dynamic table view for debugging environments,
    while fixed-width summary rendering is used for regular user responses.
    """
    if pd is None:
        return None

    rows: list[dict[str, Any]] = []
    for agent in agents[:AGENT_TABLE_MAX_ROWS]:
        if isinstance(agent, dict):
            row = {
                str(key): _stringify_table_value(value)
                for key, value in agent.items()
            }
            if row:
                rows.append(row)
            continue
        label = str(agent).strip()
        if label:
            rows.append({PAYLOAD_KEY_NAME: label})

    if not rows:
        return None

    try:
        frame = pd.json_normalize(rows, sep=".").fillna("")
    except Exception:
        return None

    if frame.empty:
        return None
    ordered_columns = _ordered_agent_columns(list(frame.columns))
    return frame[ordered_columns].to_string(index=False)


def _ordered_agent_columns(columns: list[str]) -> list[str]:
    """Order table columns with priority identifiers first, then alphabetical."""
    preferred = [col for col in AGENT_TABLE_PRIORITY_COLUMNS if col in columns]
    remaining = sorted(col for col in columns if col not in preferred)
    return preferred + remaining


def _stringify_table_value(value: Any) -> Any:
    """Convert nested values into compact JSON strings for tabular rendering."""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, sort_keys=True)
        except TypeError:
            return str(value)
    return value


def _summarize_commands_payload(payload: dict[str, Any]) -> str:
    """Summarize command-catalog payloads into concise user-facing text."""
    commands_raw = payload.get(PAYLOAD_KEY_COMMANDS, [])
    if not isinstance(commands_raw, list):
        return "I checked the command catalog, but the payload was invalid."
    total_raw = payload.get(PAYLOAD_KEY_TOTAL)
    try:
        total = int(total_raw) if total_raw is not None else len(commands_raw)
    except (TypeError, ValueError):
        total = len(commands_raw)

    if total <= 0:
        return "I checked and found no available commands."

    labels = _extract_command_labels(commands_raw)
    if labels:
        preview = ", ".join(labels[:RESPONSE_PREVIEW_ITEM_LIMIT])
        suffix = "" if len(labels) <= RESPONSE_PREVIEW_ITEM_LIMIT else ", ..."
        return f"I found {total} available command(s): {preview}{suffix}."
    return f"I found {total} available command(s)."


def _extract_command_labels(commands: list[Any]) -> list[str]:
    """Extract display labels for command definitions with graceful fallbacks."""
    labels: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            raw = str(command).strip()
            if raw:
                labels.append(raw)
            continue
        display_name = str(command.get(PAYLOAD_KEY_DISPLAY_NAME, "")).strip()
        operation = str(command.get(PAYLOAD_KEY_OPERATION, "")).strip()
        classifier = str(command.get(PAYLOAD_KEY_CLASSIFIER, "")).strip()
        if display_name:
            labels.append(display_name)
        elif classifier and operation:
            labels.append(f"{classifier}/{operation}")
        elif operation:
            labels.append(operation)
    return labels


def _summarize_openapi_payload(payload: dict[str, Any]) -> str:
    """Summarize OpenAPI path metadata with bounded preview output."""
    paths_raw = payload.get(PAYLOAD_KEY_PATHS)
    if not isinstance(paths_raw, dict):
        return "I checked the OpenAPI spec, but no paths were available."
    routes = sorted(str(path).strip() for path in paths_raw if str(path).strip())
    total = len(routes)
    if total <= 0:
        return "I checked the OpenAPI spec, but it contains no routes."
    preview = ", ".join(routes[:RESPONSE_PREVIEW_ITEM_LIMIT])
    suffix = "" if len(routes) <= RESPONSE_PREVIEW_ITEM_LIMIT else ", ..."
    return f"I found {total} API route(s) in the OpenAPI spec: {preview}{suffix}."


def _summarize_queue_result(payload: dict[str, Any]) -> str:
    """Summarize queued-operation acknowledgements for command dispatch tools."""
    client_id = str(payload.get(PAYLOAD_KEY_CLIENT_ID, "")).strip() or UNKNOWN_CLIENT_LABEL
    classifier = str(payload.get(PAYLOAD_KEY_CLASSIFIER, "")).strip()
    action = str(payload.get(PAYLOAD_KEY_ACTION, "")).strip()
    if classifier and action:
        return (
            f"Queued command `{classifier}/{action}` for client `{client_id}`."
        )
    return f"Queued command for client `{client_id}`."


def _summarize_mapping(payload: dict[str, Any]) -> str:
    """Summarize generic mapping payloads while skipping component health noise."""
    if not payload:
        return "The tool returned an empty result."
    pairs: list[str] = []
    for key, value in payload.items():
        key_name = str(key).strip() or "value"
        if _is_component_health_field_name(key_name):
            continue
        if _is_null_like_scalar(value):
            continue
        if isinstance(value, list):
            if not value:
                pairs.append(f"{key_name} is empty")
                continue
            if all(not isinstance(item, (dict, list)) for item in value):
                preview = ", ".join(str(item) for item in value[:5])
                suffix = "" if len(value) <= 5 else ", ..."
                pairs.append(
                    f"{key_name} has {len(value)} item(s): {preview}{suffix}"
                )
            else:
                pairs.append(f"{key_name} contains {len(value)} structured item(s)")
            continue
        if isinstance(value, dict):
            nested_keys = [
                str(nested).strip()
                for nested in value.keys()
                if not _is_component_health_field_name(str(nested).strip())
            ]
            preview = ", ".join(item for item in nested_keys[:5] if item)
            suffix = "" if len(nested_keys) <= 5 else ", ..."
            if preview:
                pairs.append(
                    f"{key_name} includes {len(nested_keys)} field(s): {preview}{suffix}"
                )
            else:
                pairs.append(f"{key_name} contains structured data")
            continue
        pairs.append(f"{key_name} is {value}")
    if not pairs:
        return "The tool returned details, but no reportable status fields."
    return "Tool result: " + "; ".join(pairs) + "."


def _is_component_health_field_name(field_name: str) -> bool:
    """Identify component-health fields across naming variations."""
    normalized = re.sub(r"[^a-z0-9]", "", str(field_name).strip().lower())
    return normalized == COMPONENT_HEALTH_NORMALIZED_KEY


def _is_null_like_scalar(value: Any) -> bool:
    """Return True when scalar payload values should be omitted from summaries."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
        return True
    return False


def normalize_input(state: BrokerState) -> BrokerState:
    """Normalize user text into a canonical state field.

    Why this approach:
    collapsing whitespace and stripping mentions gives downstream nodes a stable
    representation for keyword matching.

    Args:
        state: Mutable broker state carrying inbound message text.

    Returns:
        BrokerState: Updated state containing normalized text.
    """
    text = _strip_bot_mention(state.get(STATE_KEY_TEXT, ""))
    normalized = " ".join(text.split()).strip()
    state[STATE_KEY_NORMALIZED_TEXT] = normalized
    return state


def classify_intent(state: BrokerState) -> BrokerState:
    """Classify message intent and whether explicit confirmation is required.

    Why this approach:
    lightweight intent labels remain useful for diagnostics and session context
    without imposing execution control decisions at this stage.

    Args:
        state: Mutable broker state containing normalized user text.

    Returns:
        BrokerState: Updated state with command, intent, and confirmation flags.
    """
    text = state.get(STATE_KEY_NORMALIZED_TEXT, "").lower()
    parts = text.split()
    state[STATE_KEY_REQUIRES_CONFIRMATION] = False
    state[STATE_KEY_COMMAND] = parts[0] if parts else "help"

    if not text:
        state[STATE_KEY_INTENT] = "help"
    elif any(word in text for word in ["restart", "delete"]):
        state[STATE_KEY_INTENT] = "action"
    elif any(word in text for word in ["status", "health", "config", "tools", "help", "diff"]):
        state[STATE_KEY_INTENT] = "query"
    else:
        state[STATE_KEY_INTENT] = "diagnostic"
    return state


async def plan_action(
    state: BrokerState,
    tool_registry: MCPToolRegistry,
    planner: Planner,
    offline_message: str = DEFAULT_MCP_SERVER_OFFLINE_MESSAGE,
) -> BrokerState:
    """Use the runtime planner to map user text to a tool-constrained plan.

    Why this approach:
    planning is delegated to the LLM planner, but tool selection is validated
    against discovered MCP tools so execution remains strictly constrained.

    Args:
        state: Mutable broker state holding normalized user text.
        tool_registry: MCP registry providing discovered tool metadata.
        planner: Planner implementation (LLM or deterministic fallback).

    Returns:
        BrokerState: Updated state with response text and/or planned tool call.
    """
    text = state.get(STATE_KEY_NORMALIZED_TEXT, "")
    tool_names = tool_registry.list_names()
    if not tool_names:
        try:
            await tool_registry.refresh()
        except MCPServerUnavailableError as exc:
            logger.error(
                "MCP server unavailable during tool discovery: %s",
                exc,
                exc_info=True,
            )
            state[STATE_KEY_TOOLS_AVAILABLE] = []
            state[STATE_KEY_TOOL_NAME] = None
            state[STATE_KEY_TOOL_ARGS] = {}
            state[STATE_KEY_RESPONSE_TEXT] = offline_message
            return state
        except Exception:
            logger.exception("Unexpected error during MCP tool discovery refresh.")
        tool_names = tool_registry.list_names()

    tools = [
        tool_registry.get(name) or {PAYLOAD_KEY_NAME: name}
        for name in tool_names
    ]

    state[STATE_KEY_TOOLS_AVAILABLE] = tool_names
    state[STATE_KEY_TOOL_NAME] = None
    state[STATE_KEY_TOOL_ARGS] = {}
    if apply_slash_command_overrides(state, tool_names):
        return state

    conversation_history_raw = state.get(STATE_KEY_CONVERSATION_HISTORY, [])
    conversation_history = (
        conversation_history_raw
        if isinstance(conversation_history_raw, list)
        else []
    )

    try:
        plan = await planner.plan(
            text=text,
            tools=tools,
            conversation_history=conversation_history,
        )
    except Exception as exc:
        logger.exception(
            "Planner failed; falling back to rule-first planning. error=%s",
            exc,
        )
        try:
            plan = await RuleFirstPlanner().plan(
                text=text,
                tools=tools,
                conversation_history=conversation_history,
            )
        except Exception:
            logger.exception("Fallback planner failed unexpectedly.")
            state[STATE_KEY_TOOL_NAME] = None
            state[STATE_KEY_TOOL_ARGS] = {}
            state[STATE_KEY_RESPONSE_TEXT] = (
                "I hit an internal planning issue. Please try again in a moment."
            )
            return state

    chosen_tool = plan.get(TOOL_NAME_KEY)
    if chosen_tool and chosen_tool not in tool_names:
        chosen_tool = None

    chosen_args = plan.get(TOOL_ARGS_KEY, {})
    if not isinstance(chosen_args, dict):
        chosen_args = {}
    if not chosen_tool:
        chosen_args = {}

    state[STATE_KEY_TOOL_NAME] = chosen_tool
    state[STATE_KEY_TOOL_ARGS] = chosen_args
    state[STATE_KEY_REQUIRES_CONFIRMATION] = False

    response_text = plan.get(RESPONSE_TEXT_KEY, "")
    if isinstance(response_text, str) and response_text.strip():
        state[STATE_KEY_RESPONSE_TEXT] = response_text.strip()
    elif not chosen_tool:
        state[STATE_KEY_RESPONSE_TEXT] = (
            "I couldn't map that to a known MCP tool yet. "
            "Ask for `tools` to see what I discovered."
        )

    target = chosen_args.get(STATE_KEY_TARGET)
    if target is None:
        parts = text.split()
        target = parts[-1] if len(parts) > 1 else None
    state[STATE_KEY_TARGET] = str(target) if target is not None else None
    return state


async def execute_or_summarize(
    state: BrokerState,
    tool_registry: MCPToolRegistry,
    offline_message: str = DEFAULT_MCP_SERVER_OFFLINE_MESSAGE,
    tool_response_formatter: ToolResponseFormatter | None = None,
    planner: Planner | None = None,
    max_planning_steps: int = PLANNER_MAX_EXECUTION_STEPS_DEFAULT,
) -> BrokerState:
    """Execute the selected tool call or produce a user-facing fallback message.

    Why this approach:
    this node centralizes final response rendering so all branches return a
    consistent ``response_text`` contract for Slack handlers.

    Args:
        state: Mutable broker state with planning outputs.
        tool_registry: MCP registry used to execute the selected tool.

    Returns:
        BrokerState: Updated state containing tool results and response text.
    """
    current_tool_name_raw = state.get(STATE_KEY_TOOL_NAME)
    current_tool_name = (
        str(current_tool_name_raw).strip()
        if isinstance(current_tool_name_raw, str)
        else ""
    )
    if not current_tool_name:
        if STATE_KEY_RESPONSE_TEXT not in state:
            state[STATE_KEY_RESPONSE_TEXT] = (
                "I couldn't map that to a known MCP tool yet. "
                "Ask for `tools` to see what I discovered."
            )
        return state

    current_tool_args = _normalize_tool_args(state.get(STATE_KEY_TOOL_ARGS, {}))
    state[STATE_KEY_TOOL_ARGS] = current_tool_args

    normalized_user_text = str(state.get(STATE_KEY_NORMALIZED_TEXT, "")).strip()
    replanning_enabled = (
        planner is not None
        and not bool(state.get(STATE_KEY_API_COMMAND_MODE, False))
    )
    known_tool_names: set[str] = set()
    if replanning_enabled:
        available_tool_names = state.get(STATE_KEY_TOOLS_AVAILABLE, [])
        if not isinstance(available_tool_names, list):
            available_tool_names = []
        known_tool_names = {
            str(name).strip()
            for name in available_tool_names
            if str(name).strip()
        }
        if not known_tool_names and hasattr(tool_registry, "list_names"):
            try:
                known_tool_names = {
                    str(name).strip()
                    for name in tool_registry.list_names()
                    if str(name).strip()
                }
            except Exception:
                logger.exception("Failed listing tools for follow-up planning.")
        if not known_tool_names:
            known_tool_names = {current_tool_name}

    max_steps = _normalize_planner_step_limit(max_planning_steps)
    step_count = 0
    final_result: dict[str, Any] = {}
    final_default_response_text = ""
    while True:
        step_count += 1
        try:
            result = await tool_registry.call_tool(
                current_tool_name,
                current_tool_args,
            )
        except MCPServerUnavailableError as exc:
            logger.error(
                "MCP server unavailable while calling tool %s: %s",
                current_tool_name,
                exc,
                exc_info=True,
            )
            state[STATE_KEY_TOOL_RESULT] = {PAYLOAD_KEY_ERROR: str(exc)}
            state[STATE_KEY_RESPONSE_TEXT] = offline_message
            return state

        final_result = result
        final_default_response_text = _format_tool_response(
            current_tool_name,
            result,
        )

        state[STATE_KEY_TOOL_NAME] = current_tool_name
        state[STATE_KEY_TOOL_ARGS] = current_tool_args
        state[STATE_KEY_TOOL_RESULT] = result
        state[STATE_KEY_RESPONSE_TEXT] = final_default_response_text

        if not replanning_enabled or step_count >= max_steps:
            break

        tools_for_replanning = [
            tool_registry.get(name) or {PAYLOAD_KEY_NAME: name}
            for name in sorted(known_tool_names)
        ]
        follow_up_text = _build_follow_up_planner_text(
            user_text=normalized_user_text,
            tool_name=current_tool_name,
            tool_args=current_tool_args,
            tool_summary=final_default_response_text,
        )
        conversation_history_raw = state.get(STATE_KEY_CONVERSATION_HISTORY, [])
        conversation_history = (
            conversation_history_raw
            if isinstance(conversation_history_raw, list)
            else []
        )
        try:
            follow_up_plan = await planner.plan(
                text=follow_up_text,
                tools=tools_for_replanning,
                conversation_history=conversation_history,
            )
        except Exception:
            logger.exception(
                "Planner follow-up step failed after tool execution; "
                "returning latest tool response."
            )
            break

        next_tool_name_raw = follow_up_plan.get(TOOL_NAME_KEY)
        next_tool_name = (
            str(next_tool_name_raw).strip()
            if isinstance(next_tool_name_raw, str)
            else ""
        )
        next_response_text_raw = follow_up_plan.get(RESPONSE_TEXT_KEY, "")
        next_response_text = (
            str(next_response_text_raw).strip()
            if isinstance(next_response_text_raw, str)
            else str(next_response_text_raw).strip()
        )
        if not next_tool_name:
            if next_response_text:
                state[STATE_KEY_RESPONSE_TEXT] = next_response_text
            break

        if next_tool_name not in known_tool_names:
            if next_response_text:
                state[STATE_KEY_RESPONSE_TEXT] = next_response_text
            else:
                state[STATE_KEY_RESPONSE_TEXT] = (
                    f"I couldn't execute follow-up tool `{next_tool_name}` because "
                    "it is not currently available."
                )
            break

        next_tool_args = _normalize_tool_args(
            follow_up_plan.get(TOOL_ARGS_KEY, {}),
        )
        if (
            next_tool_name == current_tool_name
            and next_tool_args == current_tool_args
        ):
            if next_response_text:
                state[STATE_KEY_RESPONSE_TEXT] = next_response_text
            break

        current_tool_name = next_tool_name
        current_tool_args = next_tool_args
        next_target = current_tool_args.get(STATE_KEY_TARGET)
        if next_target is not None:
            state[STATE_KEY_TARGET] = str(next_target)

    if tool_response_formatter is not None and final_result:
        try:
            formatted_response = await tool_response_formatter(
                user_text=normalized_user_text,
                tool_name=current_tool_name,
                tool_args=current_tool_args,
                tool_result=final_result,
                default_response_text=final_default_response_text,
            )
            if isinstance(formatted_response, str) and formatted_response.strip():
                state[STATE_KEY_RESPONSE_TEXT] = formatted_response.strip()
        except Exception:
            logger.exception(
                "AI formatter failed; returning default tool response text."
            )
    return state
