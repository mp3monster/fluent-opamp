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

"""Slack event and command handlers that drive broker conversation flow.

This module adapts Slack payloads into graph state, updates session snapshots,
and emits thread responses with a consistent output contract.
"""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import re
import shlex
from typing import Any

from slack_bolt.async_app import AsyncApp

from opamp_broker.graph.state import (
    STATE_KEY_AI_ENABLED,
    STATE_KEY_API_COMMAND_MODE,
    STATE_KEY_CHANNEL_ID,
    STATE_KEY_CONVERSATION_HISTORY,
    STATE_KEY_DIRECT_TOOL_ARGS,
    STATE_KEY_DIRECT_TOOL_NAME,
    STATE_KEY_INTENT,
    STATE_KEY_TARGET,
    STATE_KEY_TEAM_ID,
    STATE_KEY_TEXT,
    STATE_KEY_THREAD_TS,
    STATE_KEY_USER_ID,
)
from opamp_broker.session.manager import SessionManager

logger = logging.getLogger(__name__)
CONFIG_KEY_MESSAGES = "messages"
CONFIG_KEY_SLACK = "slack"
CONFIG_KEY_COMMAND_NAME = "command_name"
MESSAGE_KEY_HELP = "help"
MESSAGE_KEY_SLACK_ERROR_REPLY = "slack_error_reply"
SLACK_KEY_EVENT = "event"
SLACK_KEY_TEAM_ID = "team_id"
SLACK_KEY_TEAM = "team"
SLACK_KEY_ID = "id"
SLACK_KEY_AUTHORIZATIONS = "authorizations"
SLACK_KEY_CHANNEL = "channel"
SLACK_KEY_CHANNEL_ID = "channel_id"
SLACK_KEY_THREAD_TS = "thread_ts"
SLACK_KEY_TS = "ts"
SLACK_KEY_TRIGGER_ID = "trigger_id"
SLACK_KEY_USER = "user"
SLACK_KEY_USER_ID = "user_id"
SLACK_KEY_TEXT = "text"
SLACK_KEY_CHANNEL_TYPE = "channel_type"
SLACK_KEY_RESPONSE_TEXT = "response_text"
SLACK_KEY_ENVIRONMENT = "environment"
SLACK_KEY_UNKNOWN = "unknown"
SLACK_KEY_NO_THREAD = "no-thread"
SLACK_KEY_IN_CHANNEL = "in_channel"
SLACK_CHANNEL_TYPE_IM = "im"
AI_MODE_ENABLED_TEXT = "on"
AI_MODE_OFF_EXACT_COMMAND = "ai off"
AI_MODE_ON_EXACT_COMMAND = "ai on"
AI_MODE_OFF_ACK_TEXT = "Affirmative, Dave. I read you."
AI_MODE_PREFIX_PATTERN = re.compile(r"^\s*ai\s+(on|off)\b[:\s,-]*(.*)$", re.IGNORECASE)
SLASH_PREFIX = "/"
API_ROOT_OPAMP = "/opamp"
API_ROOT_SHORT = "/api"
API_LEGACY_NAMESPACE = "api"
API_VERB_HELP = "help"
API_VERB_TOOLS = "tools"
API_VERB_CALL = "call"
LOG_KEY_EVENT = "event"
LOG_KEY_CONTEXT = "context"
LOG_KEY_COMMAND = "command"
LOG_KEY_ROUTE = "route"
CONVERSATION_HISTORY_MAX_MESSAGES = 12
HISTORY_ROLE_USER = "user"
HISTORY_ROLE_ASSISTANT = "assistant"
HISTORY_ROLE_SYSTEM = "system"


def _build_non_thread_session_scope(user_id: str | None) -> str:
    """Build a deterministic session scope for non-thread channel exchanges."""
    normalized_user_id = str(user_id or "").strip() or SLACK_KEY_UNKNOWN
    return f"{SLACK_KEY_NO_THREAD}:{normalized_user_id}"


def _derive_session_thread_ts(
    *,
    reply_thread_ts: str | None,
    user_id: str | None,
) -> str:
    """Return session scope id, preserving real thread ts when present."""
    normalized_thread_ts = str(reply_thread_ts or "").strip()
    if normalized_thread_ts:
        return normalized_thread_ts
    return _build_non_thread_session_scope(user_id)


def _normalize_conversation_history(
    history_raw: Any,
) -> list[dict[str, str]]:
    if not isinstance(history_raw, list):
        return []

    history: list[dict[str, str]] = []
    for message in history_raw:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).strip().lower()
        if role not in {HISTORY_ROLE_USER, HISTORY_ROLE_ASSISTANT, HISTORY_ROLE_SYSTEM}:
            continue
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        history.append({"role": role, "content": content})
    if len(history) > CONVERSATION_HISTORY_MAX_MESSAGES:
        return history[-CONVERSATION_HISTORY_MAX_MESSAGES:]
    return history


def _build_planner_history(session: Any) -> list[dict[str, str]]:
    return _normalize_conversation_history(
        getattr(session, "conversation_history", []),
    )


def _append_conversation_turn(
    history: list[dict[str, str]],
    *,
    user_text: str,
    assistant_text: str,
) -> list[dict[str, str]]:
    updated = list(history)
    normalized_user_text = str(user_text).strip()
    normalized_assistant_text = str(assistant_text).strip()
    if normalized_user_text:
        updated.append({"role": HISTORY_ROLE_USER, "content": normalized_user_text})
    if normalized_assistant_text:
        updated.append(
            {"role": HISTORY_ROLE_ASSISTANT, "content": normalized_assistant_text}
        )
    if len(updated) > CONVERSATION_HISTORY_MAX_MESSAGES:
        return updated[-CONVERSATION_HISTORY_MAX_MESSAGES:]
    return updated


def _log_selected_route(
    *,
    route: str,
    team_id: str,
    channel_id: str,
    thread_ts: str,
    user_id: str | None,
) -> None:
    """Log the selected Slack handling route for traceability."""
    logger.info(
        "==== Slack route selected: %s ====",
        route,
        extra={
            LOG_KEY_EVENT: "slack.handlers.route_selected",
            LOG_KEY_CONTEXT: {
                SLACK_KEY_TEAM_ID: team_id,
                SLACK_KEY_CHANNEL_ID: channel_id,
                SLACK_KEY_THREAD_TS: thread_ts,
                SLACK_KEY_USER_ID: user_id or SLACK_KEY_UNKNOWN,
                LOG_KEY_ROUTE: route,
            },
        },
    )


def _extract_ai_mode_directive(text: str) -> tuple[bool | None, str]:
    """Parse optional `AI On`/`AI Off` prefix and return remaining text."""
    candidate = str(text).strip()
    if not candidate:
        return None, ""
    match = AI_MODE_PREFIX_PATTERN.match(candidate)
    if match is None:
        return None, candidate
    toggle = str(match.group(1)).strip().lower() == AI_MODE_ENABLED_TEXT
    remainder = str(match.group(2)).strip()
    return toggle, remainder


def _normalize_mode_command_text(text: str) -> str:
    candidate = re.sub(r"<@[^>]+>", "", str(text or ""))
    return " ".join(candidate.split()).strip().lower()


def _build_ai_mode_changed_text(ai_enabled: bool) -> str:
    if ai_enabled:
        return (
            "AI mode is now ON for this client. "
            "Subsequent messages will use the LLM path."
        )
    return (
        "AI mode is now OFF for this client. "
        "Subsequent messages will use the non-AI path."
    )


def _api_usage_text() -> str:
    return (
        "Usage:\n"
        "`/opamp help [syntax|tools|call|<tool_name>]`\n"
        "`/opamp tools [filter_text]`\n"
        "`/opamp call <tool_name> [key=value ...]`\n"
        "`/opamp call <tool_name> --json '{\"key\":\"value\"}'`"
    )


def _build_api_help_text(topic: str | None = None) -> str:
    topic_normalized = str(topic or "").strip().lower()
    if topic_normalized in {"syntax", ""}:
        return (
            "Strict API command mode for OpAMP.\n"
            f"{_api_usage_text()}\n"
            "Tip: run `/opamp tools` to discover callable tool names."
        )
    if topic_normalized == API_VERB_TOOLS:
        return (
            "`/opamp tools [filter_text]`\n"
            "Lists discovered tools. Optional filter narrows output."
        )
    if topic_normalized == API_VERB_CALL:
        return (
            "`/opamp call <tool_name> [key=value ...]`\n"
            "`/opamp call <tool_name> --json '{\"key\":\"value\"}'`\n"
            "Use either key/value tokens or --json, not both."
        )
    return (
        f"Help for `{topic_normalized}`: run `/opamp tools {topic_normalized}` "
        "to locate the tool, then call it using `/opamp call ...`.\n"
        f"{_api_usage_text()}"
    )


def _filter_tools_response(response_text: str, filter_text: str) -> str:
    query = str(filter_text).strip().lower()
    if not query:
        return response_text
    lines = [line for line in response_text.splitlines() if line.strip()]
    tool_lines = [line for line in lines if line.strip().startswith("- `")]
    if not tool_lines:
        return response_text
    matched = [line for line in tool_lines if query in line.lower()]
    if not matched:
        return (
            f"No tools matched filter `{filter_text}`.\n"
            "Tip: run `/opamp tools` to see all tools."
        )
    return "Available MCP tools (filtered):\n" + "\n".join(matched)


def _parse_api_call_args(raw_tokens: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    if not raw_tokens:
        return {}, None

    if "--json" in raw_tokens:
        json_index = raw_tokens.index("--json")
        if len(raw_tokens) != 2 or json_index != 0:
            return None, "Use either key=value arguments or `--json`, not both."
        try:
            payload = json.loads(raw_tokens[1])
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON for `--json`: {exc.msg}."
        if not isinstance(payload, dict):
            return None, "`--json` payload must decode to a JSON object."
        return payload, None

    parsed: dict[str, Any] = {}
    for token in raw_tokens:
        if "=" not in token:
            return None, f"Invalid argument `{token}`. Expected `key=value`."
        key, value = token.split("=", 1)
        key_name = key.strip()
        if not key_name:
            return None, f"Invalid argument `{token}`. Key cannot be empty."
        parsed[key_name] = value
    return parsed, None


def _parse_api_command(text: str) -> dict[str, Any] | None:
    """Parse strict slash command-mode operations.

    Primary syntax is `/opamp <verb> ...`; legacy `/opamp api <verb> ...` is
    still accepted for compatibility.
    """
    normalized = str(text or "").strip()
    if not normalized or not normalized.startswith(SLASH_PREFIX):
        return None

    try:
        tokens = shlex.split(normalized)
    except ValueError as exc:
        return {
            "api_mode": True,
            "error": f"Invalid command quoting: {exc}.",
        }
    if not tokens:
        return {
            "api_mode": True,
            "error": _api_usage_text(),
        }

    first = tokens[0].strip().lower()
    index = 1
    if first == API_ROOT_OPAMP:
        if len(tokens) > 1 and tokens[1].strip().lower() == API_LEGACY_NAMESPACE:
            index = 2
    elif first == API_ROOT_SHORT:
        index = 1
    else:
        return {
            "api_mode": True,
            "error": "Unsupported slash syntax. Use `/opamp <help|tools|call> ...`.",
        }

    if len(tokens) <= index:
        return {
            "api_mode": True,
            "immediate_response": _build_api_help_text(),
        }

    verb = tokens[index].strip().lower()
    tail = tokens[index + 1 :]
    if verb == API_VERB_HELP:
        topic = tail[0] if tail else ""
        return {
            "api_mode": True,
            "immediate_response": _build_api_help_text(topic),
        }
    if verb == API_VERB_TOOLS:
        return {
            "api_mode": True,
            "verb": API_VERB_TOOLS,
            "planner_text": "tools",
            "tools_filter": " ".join(tail).strip(),
        }
    if verb == API_VERB_CALL:
        if not tail:
            return {
                "api_mode": True,
                "error": "Missing tool name.\n" + _api_usage_text(),
            }
        tool_name = str(tail[0]).strip()
        if not tool_name:
            return {
                "api_mode": True,
                "error": "Missing tool name.\n" + _api_usage_text(),
            }
        tool_args, parse_error = _parse_api_call_args(tail[1:])
        if parse_error:
            return {
                "api_mode": True,
                "error": f"{parse_error}\n{_api_usage_text()}",
            }
        return {
            "api_mode": True,
            "verb": API_VERB_CALL,
            "planner_text": tool_name,
            "direct_tool_name": tool_name,
            "direct_tool_args": tool_args or {},
        }
    return {
        "api_mode": True,
        "error": f"Unsupported verb `{verb}`.\n{_api_usage_text()}",
    }


def register_handlers(
    app: AsyncApp,
    session_manager: SessionManager,
    compiled_graph: Any,
    config: dict[str, Any],
) -> None:
    """Register slash-command, mention, and DM handlers on the Slack app.

    Why this approach:
    colocating registration keeps shared helpers (session updates and graph
    invocation) close to the handlers that use them.

    Args:
        app: Slack Bolt async application receiving events.
        session_manager: Session storage used to persist thread context.
        compiled_graph: LangGraph runnable used to process user requests.
        config: Runtime broker configuration including message templates.

    Returns:
        None: Handlers are registered by side effect on ``app``.
    """
    message_config = (
        config.get(CONFIG_KEY_MESSAGES, {})
        if isinstance(config, dict)
        else {}
    )
    help_text = str(
        message_config.get(
            MESSAGE_KEY_HELP,
            "Try `/opamp status collector-a`, `/opamp health collector-a`, "
            "or mention me with a question.",
        )
    )
    slack_error_reply = str(
        message_config.get(
            MESSAGE_KEY_SLACK_ERROR_REPLY,
            "sorry a bit dizzy at the moment",
        )
    ).strip() or "sorry a bit dizzy at the moment"

    async def _invoke_graph_and_update_session(
        *,
        team_id: str,
        channel_id: str,
        thread_ts: str,
        user_id: str | None,
        user_text: str,
    ) -> str:
        """Invoke the graph and persist the resulting session state."""
        session = await session_manager.upsert(team_id, channel_id, thread_ts, user_id)
        simple_mode_command = _normalize_mode_command_text(user_text)
        if simple_mode_command in {AI_MODE_OFF_EXACT_COMMAND, AI_MODE_ON_EXACT_COMMAND}:
            _log_selected_route(
                route="control.ai_mode_exact_command",
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
            )
            ai_enabled = simple_mode_command == AI_MODE_ON_EXACT_COMMAND
            await session_manager.update(
                session.key,
                ai_enabled=ai_enabled,
            )
            session = await session_manager.upsert(team_id, channel_id, thread_ts, user_id)
            response_text = (
                AI_MODE_OFF_ACK_TEXT
                if not ai_enabled
                else _build_ai_mode_changed_text(ai_enabled)
            )
            session_history = _normalize_conversation_history(session.conversation_history)
            updated_history = _append_conversation_turn(
                session_history,
                user_text=user_text,
                assistant_text=response_text,
            )
            await session_manager.update(
                session.key,
                current_target=None,
                environment=None,
                intent="control",
                last_summary=response_text,
                conversation_history=updated_history,
            )
            return response_text

        api_request = _parse_api_command(user_text)
        if api_request is not None:
            _log_selected_route(
                route="api.slash_command_mode",
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
            )
            session_history = _normalize_conversation_history(session.conversation_history)
            if isinstance(api_request.get("error"), str) and api_request.get("error"):
                response_text = str(api_request["error"]).strip()
            elif isinstance(
                api_request.get("immediate_response"),
                str,
            ) and api_request.get("immediate_response"):
                response_text = str(api_request["immediate_response"]).strip()
            else:
                planner_history = _build_planner_history(session)
                result = await compiled_graph.ainvoke(
                    {
                        STATE_KEY_TEAM_ID: team_id,
                        STATE_KEY_CHANNEL_ID: channel_id,
                        STATE_KEY_THREAD_TS: thread_ts,
                        STATE_KEY_USER_ID: user_id or "",
                        STATE_KEY_TEXT: str(api_request.get("planner_text", "")).strip(),
                        STATE_KEY_CONVERSATION_HISTORY: planner_history,
                        STATE_KEY_AI_ENABLED: False,
                        STATE_KEY_API_COMMAND_MODE: True,
                        STATE_KEY_DIRECT_TOOL_NAME: api_request.get("direct_tool_name"),
                        STATE_KEY_DIRECT_TOOL_ARGS: api_request.get("direct_tool_args", {}),
                    }
                )
                response_text = str(result.get(SLACK_KEY_RESPONSE_TEXT, help_text))
                if str(api_request.get("verb", "")).strip().lower() == API_VERB_TOOLS:
                    response_text = _filter_tools_response(
                        response_text,
                        str(api_request.get("tools_filter", "")).strip(),
                    )

            updated_history = _append_conversation_turn(
                session_history,
                user_text=user_text,
                assistant_text=response_text,
            )
            await session_manager.update(
                session.key,
                current_target=None,
                environment=None,
                intent="api",
                last_summary=response_text,
                conversation_history=updated_history,
            )
            return response_text

        ai_mode_override, planner_text = _extract_ai_mode_directive(user_text)
        ai_enabled = bool(session.ai_enabled)
        if ai_mode_override is not None:
            ai_enabled = bool(ai_mode_override)
            await session_manager.update(
                session.key,
                ai_enabled=ai_enabled,
            )
            session = await session_manager.upsert(team_id, channel_id, thread_ts, user_id)
        if not planner_text and ai_mode_override is not None:
            _log_selected_route(
                route="control.ai_mode_directive_only",
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
            )
            response_text = _build_ai_mode_changed_text(ai_enabled)
            session_history = _normalize_conversation_history(session.conversation_history)
            updated_history = _append_conversation_turn(
                session_history,
                user_text=user_text,
                assistant_text=response_text,
            )
            await session_manager.update(
                session.key,
                current_target=None,
                environment=None,
                intent="control",
                last_summary=response_text,
                conversation_history=updated_history,
            )
            return response_text

        session_history = _normalize_conversation_history(session.conversation_history)
        planner_history = _build_planner_history(session)
        _log_selected_route(
            route=(
                "graph.standard_ai_enabled"
                if ai_enabled
                else "graph.standard_ai_disabled"
            ),
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            user_id=user_id,
        )
        result = await compiled_graph.ainvoke(
            {
                STATE_KEY_TEAM_ID: team_id,
                STATE_KEY_CHANNEL_ID: channel_id,
                STATE_KEY_THREAD_TS: thread_ts,
                STATE_KEY_USER_ID: user_id or "",
                STATE_KEY_TEXT: planner_text,
                STATE_KEY_CONVERSATION_HISTORY: planner_history,
                STATE_KEY_AI_ENABLED: ai_enabled,
            }
        )
        response_text = str(result.get(SLACK_KEY_RESPONSE_TEXT, help_text))
        updated_history = _append_conversation_turn(
            session_history,
            user_text=user_text,
            assistant_text=response_text,
        )
        await session_manager.update(
            session.key,
            current_target=result.get(STATE_KEY_TARGET),
            environment=result.get(SLACK_KEY_ENVIRONMENT),
            intent=result.get(STATE_KEY_INTENT),
            last_summary=response_text,
            conversation_history=updated_history,
        )
        return response_text

    async def _reply(
        responder: Any,
        *,
        response_text: str,
        thread_ts: str | None = None,
        response_type: str | None = None,
    ) -> None:
        """Send a Slack response."""
        payload: dict[str, Any] = {SLACK_KEY_TEXT: response_text}
        if thread_ts:
            payload[SLACK_KEY_THREAD_TS] = thread_ts
        if response_type:
            payload["response_type"] = response_type
        await responder(**payload)

    async def _process_message(body: dict[str, Any], text: str, say: Any) -> None:
        """Process a conversational message event and post graph output."""
        event = body.get(SLACK_KEY_EVENT, {})
        team_id = body.get(SLACK_KEY_TEAM_ID) or body.get(
            SLACK_KEY_AUTHORIZATIONS,
            [{}],
        )[0].get(SLACK_KEY_TEAM_ID, SLACK_KEY_UNKNOWN)
        channel_id = event.get(SLACK_KEY_CHANNEL) or body.get(SLACK_KEY_CHANNEL_ID)
        reply_thread_ts = (
            str(event.get(SLACK_KEY_THREAD_TS, "")).strip()
            or None
        )
        session_thread_ts = _derive_session_thread_ts(
            reply_thread_ts=reply_thread_ts,
            user_id=event.get(SLACK_KEY_USER) or body.get(SLACK_KEY_USER_ID),
        )
        user_id = event.get(SLACK_KEY_USER) or body.get(SLACK_KEY_USER_ID)
        try:
            response_text = await _invoke_graph_and_update_session(
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=session_thread_ts,
                user_id=user_id,
                user_text=text,
            )
            await _reply(
                say,
                response_text=response_text,
                thread_ts=reply_thread_ts,
            )
        except Exception:
            logger.exception(
                "failed processing Slack message event",
                extra={
                    LOG_KEY_EVENT: "slack.handlers.message_processing_failed",
                    LOG_KEY_CONTEXT: {
                        SLACK_KEY_TEAM_ID: team_id,
                        SLACK_KEY_CHANNEL_ID: channel_id,
                        SLACK_KEY_THREAD_TS: session_thread_ts,
                    },
                },
            )
            with suppress(Exception):
                if reply_thread_ts:
                    await say(text=slack_error_reply, thread_ts=reply_thread_ts)
                else:
                    await say(text=slack_error_reply)

    @app.command(config[CONFIG_KEY_SLACK][CONFIG_KEY_COMMAND_NAME])
    async def handle_command(ack: Any, body: dict[str, Any], respond: Any) -> None:
        """Handle `/opamp` commands and return a channel-visible response.

        Why this flow:
        slash commands should acknowledge quickly and reply in-channel so the
        exchange remains visible to collaborators.

        Args:
            ack: Slack acknowledgment callable for command receipt.
            body: Slash command payload from Slack.
            respond: Slack response callable for command replies.

        Returns:
            None: Acknowledges, updates session state, and sends a response.
        """
        await ack()
        text = body.get(SLACK_KEY_TEXT, "").strip()
        if not text:
            await respond(help_text)
            return

        team_id = body.get(SLACK_KEY_TEAM_ID, SLACK_KEY_UNKNOWN)
        channel_id = body.get(SLACK_KEY_CHANNEL_ID, SLACK_KEY_UNKNOWN)
        raw_thread_ts = str(body.get(SLACK_KEY_THREAD_TS, "")).strip() or None
        user_id = body.get(SLACK_KEY_USER_ID)
        session_thread_ts = _derive_session_thread_ts(
            reply_thread_ts=raw_thread_ts,
            user_id=user_id,
        )
        try:
            response_text = await _invoke_graph_and_update_session(
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=session_thread_ts,
                user_id=user_id,
                user_text=text,
            )
            await _reply(
                respond,
                response_text=response_text,
                response_type=SLACK_KEY_IN_CHANNEL,
            )
        except Exception:
            logger.exception(
                "failed handling Slack slash command",
                extra={
                    LOG_KEY_EVENT: "slack.handlers.command_failed",
                    LOG_KEY_CONTEXT: {
                        SLACK_KEY_TEAM_ID: team_id,
                        SLACK_KEY_CHANNEL_ID: channel_id,
                        SLACK_KEY_THREAD_TS: session_thread_ts,
                        LOG_KEY_COMMAND: config[CONFIG_KEY_SLACK][CONFIG_KEY_COMMAND_NAME],
                    },
                },
            )
            with suppress(Exception):
                await respond(text=slack_error_reply, response_type=SLACK_KEY_IN_CHANNEL)

    @app.event("app_mention")
    async def handle_mention(body: dict[str, Any], say: Any) -> None:
        """Handle app mentions in channels by delegating to message processing.

        Args:
            body: Slack event envelope for the mention.
            say: Slack Bolt responder bound to the source channel/thread.

        Returns:
            None: Posts graph output back to the mention thread.
        """
        text = body.get(SLACK_KEY_EVENT, {}).get(SLACK_KEY_TEXT, "")
        await _process_message(body, text, say)

    @app.event("message")
    async def handle_message(
        body: dict[str, Any], say: Any, event: dict[str, Any]
    ) -> None:
        """Handle direct-message events while ignoring non-DM traffic.

        Why this guard:
        channel message events are noisy; restricting this path to DM traffic
        prevents duplicate responses when app mentions already handle channels.

        Args:
            body: Slack event envelope.
            say: Slack Bolt responder bound to the event context.
            event: Flattened event payload supplied by Bolt.

        Returns:
            None: Processes DM text through the conversation graph when eligible.
        """
        channel_type = event.get(SLACK_KEY_CHANNEL_TYPE)
        if channel_type != SLACK_CHANNEL_TYPE_IM:
            return
        text = event.get(SLACK_KEY_TEXT, "")
        await _process_message(body, text, say)
