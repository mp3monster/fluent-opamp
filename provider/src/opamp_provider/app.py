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

"""Quart OpAMP server skeleton."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import ssl
import tracemalloc
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from google.protobuf import text_format
from quart import Quart, Response, jsonify, redirect, request, websocket
from werkzeug.exceptions import HTTPException

from opamp_provider import auth as provider_auth
from opamp_provider import config as provider_config
from opamp_provider.app_client_filters import (
    client_matches_api_clients_filters,
    coerce_bool_setting,
    normalize_query_text,
    parse_optional_bool,
    serialize_client_record_for_api,
)
from opamp_provider.app_constants import GLOBAL_SETTINGS_HELP, MODEL_DUMP_MODE
from opamp_provider.app_persistence import PersistenceTracker, request_process_shutdown
from opamp_provider.app_routes_settings import register_settings_routes
from opamp_provider.app_routes_ui import register_ui_routes
from opamp_provider.app_ui_assets import load_provider_ui_assets, render_help_html
from opamp_provider.command_queue import (
    QueueCommandRequestError,
    queue_command_from_payload,
)
from opamp_provider.command_record import CommandRecord
from opamp_provider.commands import (
    command_object_factory,
    get_command_metadata,
    get_custom_capabilities_list,
)
from opamp_provider.component_features import (
    UiFeatureMenuItem,
    register_provider_component_entries,
    ui_menu_items_from_component_entries,
)
from opamp_provider.component_version import component_version_text
from opamp_provider.exceptions import ServerToAgentException
from opamp_provider.mcptool import register_mcp_transport, register_tool_routes
from opamp_provider.opamp_protocol import (
    build_error_message as protocol_build_error_message,
)
from opamp_provider.opamp_protocol import (
    build_opamp_http_error_response as protocol_build_opamp_http_error_response,
)
from opamp_provider.opamp_protocol import (
    evaluate_non_opamp_http_auth as protocol_evaluate_non_opamp_http_auth,
)
from opamp_provider.opamp_protocol import (
    evaluate_opamp_transport_auth as protocol_evaluate_opamp_transport_auth,
)
from opamp_provider.opamp_protocol import (
    extract_client_id as protocol_extract_client_id,
)
from opamp_provider.opamp_protocol import (
    header_value as protocol_header_value,
)
from opamp_provider.opamp_protocol import (
    log_blocked_agent_attempt as protocol_log_blocked_agent_attempt,
)
from opamp_provider.opamp_protocol import (
    provider_authorization_mode_to_auth_mode as protocol_provider_authorization_mode_to_auth_mode,
)
from opamp_provider.proto import opamp_pb2
from opamp_provider.remote_config_schema import (
    config_editor_validation_available,
    normalize_remote_config_file_specs,
    normalize_remote_config_selection_specs,
    validate_remote_config_files,
)
from opamp_provider.state import STORE, ClientRecord
from opamp_provider.state_persistence import (
    list_snapshot_files,
    prune_snapshot_files,
    save_state_snapshot,
)
from opamp_provider.transport import decode_message, encode_message
from shared.agent_remote_config import build_agent_remote_config
from shared.opamp_config import (
    OPAMP_HTTP_PATH,
    OPAMP_TRANSPORT_HEADER_NONE,
    PB_FIELD_COMMAND,
    PB_FIELD_CONNECTION_SETTINGS_REQUEST,
    PB_FIELD_CUSTOM_MESSAGE,
    PB_FIELD_PACKAGE_STATUSES,
    UTF8_ENCODING,
    ServerCapabilities,
)

app = Quart("opamp_server")
app.config.setdefault("DIAGNOSTIC_MODE", False)
register_tool_routes(app)
# Expose both SSE and streamable HTTP wiring; /mcp itself is still gated at
# request time by provider.allow-mcp so operators can disable direct streamable
# MCP access while keeping the bridge code loaded.
register_mcp_transport(app, transport="both")
logger = logging.getLogger(__name__)
tracemalloc.start()

_ACTIVE_CONFIG_PATH = provider_config.get_effective_config_path()
_REGISTERED_COMPONENT_ENTRY_POINTS, _CONFIGURED_COMPONENT_ENTRY_POINTS = register_provider_component_entries(
    app=app,
    config_path=_ACTIVE_CONFIG_PATH,
    logger=logger,
)
_UI_FEATURE_MENU_ITEMS: list[UiFeatureMenuItem] = ui_menu_items_from_component_entries(
    _CONFIGURED_COMPONENT_ENTRY_POINTS
)
LANDING_PAGE_REDIRECT_URL = (
    "https://htmlpreview.github.io/?https://raw.githubusercontent.com/"
    "mp3monster/fluent-opamp/main/github-landingpage/index.html"
)

CONTENT_TYPE_PROTO = "application/x-protobuf"  # Content-Type for protobuf payloads.
LOG_HTTP_MSG = "opamp http AgentToServer:\n%s"  # Log format for HTTP messages.
LOG_WS_MSG = "opamp ws AgentToServer:\n%s"  # Log format for WebSocket messages.
ERR_UNSUPPORTED_HEADER = "unsupported transport header"  # Transport header error text.
LOG_REST_COMMAND = "queued command for client %s classifier=%s action=%s at %s"  # Log format for queued REST-originated commands.
LOG_SEND_COMMAND = "sent command to client %s at %s"  # Log format for command dispatch completion.
OPAMP_HEADER_NONE = OPAMP_TRANSPORT_HEADER_NONE  # Expected transport header value.
SERVER_CAPABILITIES_BASE = int(ServerCapabilities.AcceptsStatus)  # Base server capability advertisement.
SERVER_CAPABILITIES_REMOTE_CONFIG = int(
    ServerCapabilities.OffersRemoteConfig
)  # Additional capability bit used when remote-config support is enabled.
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30  # Fallback heartbeat interval for connection settings offers.
CERT_NOT_AFTER_SUFFIX_GMT = " GMT"  # Trailing timezone marker emitted by ssl certificate decoder.
CERT_NOT_AFTER_PARSE_FORMAT = "%b %d %H:%M:%S %Y"  # Datetime parse format for decoded certificate notAfter values.
TLS_EXPIRY_WARNING_DAYS = 30  # Number of days before expiry to highlight certificate warning state.
QUERY_PARAM_SERVICE_INSTANCE_ID = "service_instance_id"  # Query parameter used to filter by service.instance.id.
QUERY_PARAM_CLIENT_VERSION = "client_version"  # Query parameter used to filter by client version.
QUERY_PARAM_HOST_NAME = "host_name"  # Query parameter used to filter by host name.
QUERY_PARAM_HOST_IP = "host_ip"  # Query parameter used to filter by host IP.
QUERY_PARAM_INVERT_FILTER = "invertFilter"  # Query parameter used to invert filter semantics.

COMMAND_RESTART = "restart"  # Standard OpAMP restart command action name.
COMMAND_FORCE_RESYNC = "forceresync"  # Custom action name used to trigger full state resync.
COMMAND_CHATOP = "chatopcommand"  # Custom action name for ChatOps command dispatch.
COMMAND_SHUTDOWN_AGENT = "shutdownagent"  # Custom action name for remote shutdown requests.
COMMAND_NULLCOMMAND = "nullcommand"  # Custom no-op action used for testing command plumbing.
CLASSIFIER_COMMAND = "command"  # Classifier used for standard OpAMP commands.
CLASSIFIER_CUSTOM_COMMAND = "custom_command"  # Classifier used for provider custom command routing.
CLASSIFIER_CUSTOM = "custom"  # Alternate classifier value emitted by some custom command builders.
CHANNEL_HTTP = "HTTP"  # Client channel label for HTTP transport.
CHANNEL_WEBSOCKET = "websocket"  # Client channel label for WebSocket transport.
ACTION_APPLY_CONFIG = "apply_config"  # Next-action token to build remote_config payload.
ACTION_CHANGE_CONNECTIONS = "change_connections"  # Next-action token to build connection settings payload.
ACTION_PACKAGE_AVAILABLE = "package_availabe"  # Next-action token to build packages available payload.
ACTION_COMMAND_AGENT = "command_agent"  # Next-action token to send an OpAMP standard command.
ACTION_CUSTOM_AGENT_COMMAND = "custom_agent_command"  # Next-action token to send a custom capability command.
CLIENT_REMOTE_CONFIG_CAPABILITY = "Accepts Remote Config"  # Human-readable capability required for AgentRemoteConfig offers.
REMOTE_CONFIG_SELECTION_STATUS_ACCEPTED = "accepted"  # Response status for catalog callback selection payloads.
ERR_REMOTE_CONFIG_DISABLED = "remote config is disabled by provider configuration"
# Allowed next-action values accepted by /rest/nextAction.
ACTION_OPTIONS = {
    ACTION_APPLY_CONFIG,
    ACTION_CHANGE_CONNECTIONS,
    ACTION_PACKAGE_AVAILABLE,
    ACTION_COMMAND_AGENT,
    ACTION_CUSTOM_AGENT_COMMAND,
}
_SHUTDOWN_REQUESTED = False  # Guard to prevent duplicate shutdown scheduling.
_LAST_DISCONNECT_PURGE: datetime | None = None  # Timestamp of last disconnected-client purge pass.
_WEBSOCKET_CLIENTS: dict[object, str | None] = {}  # Active websocket -> client_id mapping.
_PERSISTENCE_TRACKER = PersistenceTracker()
ERR_AGENT_PENDING_APPROVAL = "agent pending approval"
ERR_AGENT_BLOCKED = "agent is blocked"
ERR_AGENT_AUTH_FAILED = "agent authentication failed"
ERR_OPAMP_AUTH_CONFIG_INVALID = "invalid opamp-use-authorization configuration"
ERR_UI_AUTH_CONFIG_INVALID = "invalid ui-use-authorization configuration"


@app.errorhandler(HTTPStatus.NOT_FOUND)
async def redirect_unknown_provider_route(_: HTTPException) -> Response:
    """Redirect unknown provider routes to the shared project landing page."""
    logger.info(
        "provider 404 redirect path=%s remote_addr=%s target=%s",
        request.path,
        request.remote_addr,
        LANDING_PAGE_REDIRECT_URL,
    )
    return redirect(LANDING_PAGE_REDIRECT_URL)

def set_state_restore_status(status: str, detail: str = "") -> None:
    """Record persisted-state restore status for diagnostics and logs."""
    _PERSISTENCE_TRACKER.set_state_restore_status(status, detail)


def _record_snapshot_status(
    *,
    status: str,
    path: str | None,
    reason: str,
    at: datetime | None = None,
) -> None:
    """Record latest snapshot save status for diagnostics."""
    _PERSISTENCE_TRACKER.record_snapshot_status(
        status=status,
        path=path,
        reason=reason,
        at=at,
    )


def _is_heartbeat_only_message(agent_msg: opamp_pb2.AgentToServer) -> bool:
    """Return whether AgentToServer payload only contains instance_uid/sequence_num."""
    return _PERSISTENCE_TRACKER.is_heartbeat_only_message(agent_msg)


def _save_state_snapshot(reason: str) -> None:
    """Save one persisted-state snapshot if persistence is enabled."""
    _PERSISTENCE_TRACKER.save_state_snapshot(
        reason=reason,
        store=STORE,
        persistence=provider_config.CONFIG.state_persistence,
        logger=logger,
    )


def _note_non_heartbeat_state_change_and_maybe_autosave() -> None:
    """Track non-heartbeat state change timing and run autosave checks."""
    _PERSISTENCE_TRACKER.note_non_heartbeat_state_change_and_maybe_autosave(
        store=STORE,
        persistence=provider_config.CONFIG.state_persistence,
        logger=logger,
    )


def _state_snapshot_file_count() -> int:
    """Return count of snapshot files currently present for configured prefix."""
    try:
        prefix = provider_config.CONFIG.state_persistence.state_file_prefix
        return len(list_snapshot_files(prefix))
    except Exception as exc:
        logger.warning("failed counting state snapshot files", exc_info=exc)
        return 0


async def _shutdown_after_response() -> None:
    """Delay briefly to flush responses before shutting down."""
    await asyncio.sleep(0.2)
    _request_process_shutdown()


@app.errorhandler(Exception)
async def handle_unexpected_error(error: Exception) -> Response:
    """Return JSON for unexpected errors while preserving HTTPException behavior."""
    if isinstance(error, HTTPException):
        return error
    logger.exception("Unhandled app error", exc_info=error)
    return jsonify({"error": "internal server error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@app.before_request
async def enforce_bearer_auth() -> Response | None:
    """Apply non-OpAMP bearer-token auth using provider.ui-use-authorization."""
    if request.path == OPAMP_HTTP_PATH:
        return None
    decision = _evaluate_non_opamp_http_auth(
        path=request.path,
        method=request.method,
        authorization_header=request.headers.get("Authorization"),
        remote_addr=request.remote_addr,
    )
    if decision.allowed:
        return None
    response = jsonify({"error": decision.error})
    if decision.status_code == HTTPStatus.UNAUTHORIZED:
        response.headers["WWW-Authenticate"] = provider_auth.WWW_AUTHENTICATE_BEARER
    return response, decision.status_code


def _extract_client_id(agent_msg: opamp_pb2.AgentToServer) -> str:
    """Return hex-encoded instance UID when present; otherwise an empty string."""
    return protocol_extract_client_id(agent_msg)


def _request_header_map() -> dict[str, str]:
    """Return request headers as a plain dictionary for audit logging/auth checks."""
    return {str(key): str(value) for key, value in request.headers.items()}


def _websocket_header_map() -> dict[str, str]:
    """Return websocket handshake headers as a plain dictionary."""
    return {str(key): str(value) for key, value in websocket.headers.items()}


def _websocket_remote_addr() -> str | None:
    """Return websocket remote address when available."""
    client_info = getattr(websocket, "client", None)
    if isinstance(client_info, tuple) and client_info:
        return str(client_info[0])
    return None


def _diagnostic_mode_enabled() -> bool:
    """Return whether server diagnostic mode is enabled."""
    return bool(app.config.get("DIAGNOSTIC_MODE", False))


def _client_supports_remote_config(client: ClientRecord) -> bool:
    """Return whether a client has announced remote-config acceptance capability."""
    return CLIENT_REMOTE_CONFIG_CAPABILITY in client.capabilities


def _provider_allows_remote_config() -> bool:
    """Return whether provider configuration enables remote-config UI and queueing support."""
    return provider_config.CONFIG.allow_remote_config is True


def _server_capabilities_mask() -> int:
    """Return the effective server capability bitmask for the current provider config."""
    mask = SERVER_CAPABILITIES_BASE
    if _provider_allows_remote_config():
        mask |= SERVER_CAPABILITIES_REMOTE_CONFIG
    return mask


def _serialize_client_record_for_api(record: ClientRecord) -> dict[str, object]:
    """Return one API-facing client payload enriched with provider UI capability flags."""
    return serialize_client_record_for_api(
        record,
        model_dump_mode=MODEL_DUMP_MODE,
        provider_remote_config_enabled=_provider_allows_remote_config(),
        remote_config_capability_reported=_client_supports_remote_config(record),
    )


def _coerce_bool_setting(value: object, *, key: str) -> bool:
    """Coerce UI/API boolean payload values for settings endpoints."""
    return coerce_bool_setting(value, key=key)


def _normalize_query_text(value: str | None) -> str | None:
    """Return stripped query text or None when empty/unset."""
    return normalize_query_text(value)


def _parse_optional_bool(value: str | bool | None, *, parameter_name: str) -> bool | None:
    """Parse a bool-like query value into `bool | None`."""
    return parse_optional_bool(value, parameter_name=parameter_name)


def _client_matches_api_clients_filters(
    client: ClientRecord,
    *,
    service_instance_id: str | None,
    client_version: str | None,
    host_name: str | None,
    host_ip: str | None,
    invert_filter: bool,
    has_active_filters: bool,
) -> bool:
    """Evaluate whether one client satisfies requested /api/clients filters."""
    return client_matches_api_clients_filters(
        client,
        service_instance_id=service_instance_id,
        client_version=client_version,
        host_name=host_name,
        host_ip=host_ip,
        invert_filter=invert_filter,
        has_active_filters=has_active_filters,
        logger=logger,
    )


def _load_tls_certificate_expiry_utc(cert_file: str) -> datetime | None:
    """Load certificate expiry timestamp in UTC from a PEM certificate file."""
    try:
        cert_data = ssl._ssl._test_decode_cert(cert_file)
    except Exception as exc:
        logger.warning(
            "failed to decode provider tls cert file %s", cert_file, exc_info=exc
        )
        return None
    not_after_raw = cert_data.get("notAfter")
    if not isinstance(not_after_raw, str) or not not_after_raw.strip():
        return None
    normalized_not_after = not_after_raw.strip()
    if normalized_not_after.endswith(CERT_NOT_AFTER_SUFFIX_GMT):
        normalized_not_after = normalized_not_after[: -len(CERT_NOT_AFTER_SUFFIX_GMT)]
    normalized_not_after = " ".join(normalized_not_after.split())
    try:
        parsed = datetime.strptime(normalized_not_after, CERT_NOT_AFTER_PARSE_FORMAT)
    except ValueError:
        logger.warning(
            "failed to parse provider tls cert notAfter value %r",
            not_after_raw,
        )
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _tls_certificate_expiry_metadata(
    *,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Build TLS certificate-expiry metadata for global settings responses."""
    tls_config = provider_config.CONFIG.tls
    if tls_config is None:
        return {
            "tls_enabled": False,
            "https_certificate_expiry_date": None,
            "https_certificate_days_remaining": None,
            "https_certificate_expiring_soon": False,
        }
    expiry_utc = _load_tls_certificate_expiry_utc(tls_config.cert_file)
    if expiry_utc is None:
        return {
            "tls_enabled": True,
            "https_certificate_expiry_date": None,
            "https_certificate_days_remaining": None,
            "https_certificate_expiring_soon": False,
        }
    now = now_utc or datetime.now(timezone.utc)
    days_remaining = (expiry_utc.date() - now.date()).days
    return {
        "tls_enabled": True,
        "https_certificate_expiry_date": expiry_utc.date().isoformat(),
        "https_certificate_days_remaining": days_remaining,
        "https_certificate_expiring_soon": days_remaining <= TLS_EXPIRY_WARNING_DAYS,
    }


def _header_value(
    *,
    headers: dict[str, str],
    name: str,
) -> str | None:
    """Return a case-insensitive header value from a plain header dictionary."""
    return protocol_header_value(headers=headers, name=name)


def _provider_authorization_mode_to_auth_mode(
    provider_mode: str,
) -> str | None:
    """Map provider config authorization values to auth module mode."""
    return protocol_provider_authorization_mode_to_auth_mode(provider_mode)


def _evaluate_opamp_transport_auth(
    *,
    headers: dict[str, str],
    remote_addr: str | None,
    channel: str,
) -> provider_auth.AuthDecision:
    """Authorize OpAMP transport requests using provider config mode."""
    return protocol_evaluate_opamp_transport_auth(
        headers=headers,
        remote_addr=remote_addr,
        channel=channel,
        opamp_http_path=OPAMP_HTTP_PATH,
        invalid_config_error=ERR_OPAMP_AUTH_CONFIG_INVALID,
    )


def _evaluate_non_opamp_http_auth(
    *,
    path: str,
    method: str,
    authorization_header: str | None,
    remote_addr: str | None,
) -> provider_auth.AuthDecision:
    """Authorize non-OpAMP HTTP requests using provider.ui-use-authorization."""
    return protocol_evaluate_non_opamp_http_auth(
        path=path,
        method=method,
        authorization_header=authorization_header,
        remote_addr=remote_addr,
        invalid_config_error=ERR_UI_AUTH_CONFIG_INVALID,
    )


def _build_error_message(
    *,
    instance_uid: bytes | None,
    error_message: str,
    error_type: opamp_pb2.ServerErrorResponseType = (
        opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest
    ),
) -> opamp_pb2.ServerToAgent:
    """Build a ServerToAgent error payload without requiring prior response state."""
    return protocol_build_error_message(
        instance_uid=instance_uid,
        error_message=error_message,
        error_type=error_type,
    )


def _build_opamp_http_error_response(
    *,
    instance_uid: bytes | None,
    status_code: int,
    error_message: str,
    headers: dict[str, str] | None = None,
    error_type: opamp_pb2.ServerErrorResponseType = (
        opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest
    ),
) -> Response:
    """Build a protobuf HTTP response carrying a ServerToAgent error payload."""
    return protocol_build_opamp_http_error_response(
        instance_uid=instance_uid,
        status_code=status_code,
        error_message=error_message,
        headers=headers,
        error_type=error_type,
    )


def _log_blocked_agent_attempt(
    *,
    client_id: str,
    channel: str,
    headers: dict[str, str],
    remote_addr: str | None,
) -> None:
    """Log one blocked-agent request with headers for audit visibility."""
    protocol_log_blocked_agent_attempt(
        client_id=client_id,
        channel=channel,
        headers=headers,
        remote_addr=remote_addr,
        logger=logger,
    )


def _build_apply_config(
    response: opamp_pb2.ServerToAgent,
    client: ClientRecord | None = None,
) -> opamp_pb2.ServerToAgent:
    """Attach a remote_config action to the ServerToAgent response."""
    logger.info("building next action payload: %s", ACTION_APPLY_CONFIG)
    if client is not None:
        pending_remote_config = STORE.pop_pending_remote_config(client.client_id)
        if pending_remote_config:
            response.remote_config.ParseFromString(pending_remote_config)
            return response
    response.remote_config.SetInParent()
    return response


def _build_change_connections(
    response: opamp_pb2.ServerToAgent,
    client: ClientRecord | None = None,
) -> opamp_pb2.ServerToAgent:
    """Build connection settings update payload for the client heartbeat interval."""
    logger.info("building next action payload: %s", ACTION_CHANGE_CONNECTIONS)
    raw_interval = (
        getattr(client, "heartbeat_frequency", DEFAULT_HEARTBEAT_INTERVAL_SECONDS)
        if client is not None
        else DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    )
    try:
        interval_seconds = max(1, int(raw_interval))
    except (TypeError, ValueError):
        interval_seconds = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    response.connection_settings.opamp.heartbeat_interval_seconds = interval_seconds
    logger.info(
        "set connection_settings.opamp.heartbeat_interval_seconds=%s for client_id=%s",
        interval_seconds,
        client.client_id if client is not None else "unknown",
    )
    return response


def _build_package_available(
    response: opamp_pb2.ServerToAgent,
) -> opamp_pb2.ServerToAgent:
    """Return a not-available error for package availability action."""
    logger.info("building next action payload: %s", ACTION_PACKAGE_AVAILABLE)
    # response.packages_available.SetInParent()
    response = _build_error(
        msg=response, error_message="Package Availability feature not available"
    )
    return response


def _build_agent_remote_config(
    response: opamp_pb2.ServerToAgent, request_msg: opamp_pb2.AgentToServer
) -> opamp_pb2.ServerToAgent:
    """Placeholder builder for AgentRemoteConfig server offers."""
    logger.info("remote config TBD")
    return response


def _build_connection_settings_offers(
    response: opamp_pb2.ServerToAgent, request_msg: opamp_pb2.AgentToServer
) -> opamp_pb2.ServerToAgent:
    """Placeholder builder for ConnectionSettingsOffers server offers."""
    logger.info("connection settings TBD")
    return response


def _build_packages_available(
    response: opamp_pb2.ServerToAgent, request_msg: opamp_pb2.AgentToServer
) -> opamp_pb2.ServerToAgent:
    """Placeholder builder for PackagesAvailable server offers."""
    logger.info("packages available: TBD")
    return response


def _build_offer_payloads(
    response: opamp_pb2.ServerToAgent, request_msg: opamp_pb2.AgentToServer
) -> opamp_pb2.ServerToAgent:
    """Apply placeholder offer builders for request-driven server payloads."""
    response = _build_agent_remote_config(response, request_msg)
    response = _build_connection_settings_offers(response, request_msg)
    response = _build_packages_available(response, request_msg)
    return response


def _build_restart_command(
    response: opamp_pb2.ServerToAgent, pending_command: CommandRecord
) -> opamp_pb2.ServerToAgent:
    """Build a restart ServerToAgentCommand payload."""
    logger.info(
        "building command payload classifier=%s action=%s",
        pending_command.classifier,
        pending_command.action,
    )
    response.command.type = opamp_pb2.CommandType.CommandType_Restart
    logger.debug(
        "created ServerToAgent.command payload: %s",
        text_format.MessageToString(response.command).strip(),
    )
    return response


def _build_force_resync_command(
    response: opamp_pb2.ServerToAgent, pending_command: CommandRecord
) -> opamp_pb2.ServerToAgent:
    """Build a report-full-state ServerToAgent flags payload."""
    logger.info(
        "building command payload classifier=%s action=%s",
        pending_command.classifier,
        pending_command.action,
    )
    response.flags = response.flags | int(
        opamp_pb2.ServerToAgentFlags.ServerToAgentFlags_ReportFullState
    )
    logger.debug("created ServerToAgent.flags payload: %s", response.flags)
    return response


def _kv_lookup(pairs: list[dict[str, str]], key: str) -> str:
    """Fetch a string value from a list of key/value dictionaries."""
    for pair in pairs:
        if pair.get("key", "").strip().lower() == key.lower():
            return str(pair.get("value", "")).strip()
    return ""


def _build_custom_command_payload(
    response: opamp_pb2.ServerToAgent, pending_command: CommandRecord
) -> opamp_pb2.ServerToAgent:
    """Build a ServerToAgent custom message payload from queued key/value pairs."""
    logger.info(
        "building custom command payload classifier=%s action=%s",
        pending_command.classifier,
        pending_command.action,
    )
    classifier = (pending_command.classifier or "").strip().lower()
    action = (pending_command.action or "").strip().lower()
    if classifier == CLASSIFIER_CUSTOM:
        try:
            command_obj = command_object_factory(
                classifier=classifier,
                key_values={
                    pair["key"]: pair["value"]
                    for pair in pending_command.key_value_pairs
                },
            )
            if hasattr(command_obj, "to_custom_message"):
                response.custom_message.CopyFrom(command_obj.to_custom_message())
                logger.debug(
                    "created ServerToAgent.custom_message payload from custom command object: %s",
                    text_format.MessageToString(response.custom_message).strip(),
                )
                return response
        except ValueError:
            logger.debug(
                "no concrete custom command object for action=%s; using generic payload builder",
                action,
            )

    capability = _kv_lookup(pending_command.key_value_pairs, "capability")
    custom_type = _kv_lookup(pending_command.key_value_pairs, "type")
    data_value = _kv_lookup(pending_command.key_value_pairs, "data")

    response.custom_message.capability = capability or "custom_command"
    response.custom_message.type = custom_type or pending_command.action
    if data_value:
        response.custom_message.data = data_value.encode(UTF8_ENCODING)
    else:
        response.custom_message.data = b""
    logger.debug(
        "created ServerToAgent.custom_message payload: %s",
        text_format.MessageToString(response.custom_message).strip(),
    )
    return response


COMMAND_BUILDERS: dict[
    tuple[str, str],
    Callable[[opamp_pb2.ServerToAgent, CommandRecord], opamp_pb2.ServerToAgent],
] = {
    (CLASSIFIER_COMMAND, COMMAND_RESTART): _build_restart_command,
    (CLASSIFIER_COMMAND, COMMAND_FORCE_RESYNC): _build_force_resync_command,
    # Design intent: wildcard custom routing avoids per-command app.py edits.
    # Validation still happens in queue_command via command_object_factory.
    (CLASSIFIER_CUSTOM, "*"): _build_custom_command_payload,
    (CLASSIFIER_CUSTOM_COMMAND, "*"): _build_custom_command_payload,
}


def _apply_command_intent(
    response: opamp_pb2.ServerToAgent, pending_command: CommandRecord | None
) -> opamp_pb2.ServerToAgent:
    """Map classifier/action to a payload builder and apply it to the response."""
    if pending_command is None:
        return response
    classifier = pending_command.classifier.strip().lower()
    action = pending_command.action.strip().lower()
    builder = COMMAND_BUILDERS.get((classifier, action))
    if builder is None:
        builder = COMMAND_BUILDERS.get((classifier, "*"))
    if builder is None:
        logger.warning(
            "No command builder for classifier=%s action=%s",
            classifier,
            action,
        )
        return response
    updated_response = builder(response, pending_command)
    logger.debug(
        "created command intent payload summary client classifier=%s action=%s has_command=%s has_custom_message=%s",
        classifier,
        action,
        updated_response.HasField(PB_FIELD_COMMAND),
        updated_response.HasField(PB_FIELD_CUSTOM_MESSAGE),
    )
    return updated_response


def _apply_next_action(
    response: opamp_pb2.ServerToAgent,
    *,
    action: str,
    pending_command: CommandRecord | None,
    client: ClientRecord | None = None,
) -> opamp_pb2.ServerToAgent:
    """Dispatch the next action string to the correct builder."""
    if action == ACTION_APPLY_CONFIG:
        return _build_apply_config(response, client)
    if action == ACTION_CHANGE_CONNECTIONS:
        return _build_change_connections(response, client)
    if action == ACTION_PACKAGE_AVAILABLE:
        return _build_package_available(response)
    if action == ACTION_COMMAND_AGENT:
        return _apply_command_intent(response, pending_command)
    if action == ACTION_CUSTOM_AGENT_COMMAND:
        return _apply_command_intent(response, pending_command)
    logger.warning("unknown next action: %s", action)
    return response


def _build_response(
    request_msg: opamp_pb2.AgentToServer,
    pending_command: CommandRecord | None,
    client: ClientRecord | None = None,
    channel: str | None = None,
) -> opamp_pb2.ServerToAgent:
    """Build a minimal ServerToAgent response for a request."""
    response = opamp_pb2.ServerToAgent()
    if request_msg.instance_uid:
        response.instance_uid = request_msg.instance_uid
        logger.info("set response to: %s", response.instance_uid)
    else:
        logger.warning("Cant set response instance_uid")

    # Server capability advertisement is driven by provider feature toggles.
    response.capabilities = _server_capabilities_mask()
    custom_capabilities = get_custom_capabilities_list()
    if custom_capabilities:
        response.custom_capabilities.capabilities.extend(custom_capabilities)
    if client:
        pending_identification = STORE.pop_agent_identification(client.client_id)
        if pending_identification:
            response.agent_identification.new_instance_uid = pending_identification
    response = _build_offer_payloads(response, request_msg)
    if channel == CHANNEL_HTTP and client:
        next_action = STORE.pop_next_action(client.client_id)
        if next_action:
            response = _apply_next_action(
                response,
                action=next_action,
                pending_command=pending_command,
                client=client,
            )
    response = _apply_command_intent(response, pending_command)
    return response


def _has_dispatched_command_payload(response_msg: opamp_pb2.ServerToAgent) -> bool:
    """Return whether a queued command was encoded in this response message."""
    return (
        response_msg.HasField(PB_FIELD_COMMAND)
        or response_msg.HasField(PB_FIELD_CUSTOM_MESSAGE)
        or bool(response_msg.flags)
    )


def _build_error(
    msg: opamp_pb2.ServerToAgent,
    error_type: opamp_pb2.ServerErrorResponseType = (
        opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest
    ),
    error_message: str = "Bad Request",
) -> opamp_pb2.ServerToAgent:
    """Build an error response and append error details to the message."""
    response = msg
    if not response.instance_uid:
        raise ServerToAgentException("no instance UID set")

    if not response.error_response:
        response.error_response = opamp_pb2.ErrorResponseType

    response.error_response.type = error_type

    if not response.error_response.error_message:
        response.error_response.error_message = error_message
    else:
        response.error_response.error_message = (
            response.error_response.error_message + "\n" + error_message
        )

    if (
        error_type
        == opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_Unavailable
    ):
        retry_ns = int(provider_config.CONFIG.retry_after_seconds) * 1_000_000_000
        response.error_response.retry_info.retry_after_nanoseconds = retry_ns

    logging.getLogger(__name__).info(
        "Constructed an error response to transmit: %s",
        response.error_response,
    )
    return response


def _unsupported_agent_fields(agent_msg: opamp_pb2.AgentToServer) -> list[str]:
    """Return unsupported top-level AgentToServer fields currently rejected by server."""
    unsupported: list[str] = []
    if agent_msg.HasField(PB_FIELD_PACKAGE_STATUSES):
        unsupported.append(PB_FIELD_PACKAGE_STATUSES)
    if agent_msg.HasField(PB_FIELD_CONNECTION_SETTINGS_REQUEST):
        unsupported.append(PB_FIELD_CONNECTION_SETTINGS_REQUEST)
    return unsupported


def _build_http_auth_error_response(
    *,
    agent_msg: opamp_pb2.AgentToServer,
    auth_decision: provider_auth.AuthDecision,
) -> Response:
    """Build an OpAMP HTTP auth error response with expected headers and type."""
    response_headers: dict[str, str] = {}
    if auth_decision.status_code == HTTPStatus.UNAUTHORIZED:
        response_headers["WWW-Authenticate"] = (
            provider_auth.WWW_AUTHENTICATE_BEARER
        )
    error_type = (
        opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_Unavailable
        if auth_decision.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        else opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest
    )
    return _build_opamp_http_error_response(
        instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
        status_code=auth_decision.status_code,
        error_message=auth_decision.error or ERR_AGENT_AUTH_FAILED,
        headers=response_headers,
        error_type=error_type,
    )


def _build_http_unsupported_fields_response(
    *,
    agent_msg: opamp_pb2.AgentToServer,
    unsupported_fields: list[str],
) -> Response:
    """Build a protobuf HTTP bad-request response for unsupported AgentToServer fields."""
    response_msg = opamp_pb2.ServerToAgent()
    response_msg.instance_uid = agent_msg.instance_uid
    response_msg = _build_error(
        error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
        error_message=(f"unsupported fields: {', '.join(unsupported_fields)}"),
        msg=response_msg,
    )
    return Response(
        response_msg.SerializeToString(),
        content_type=CONTENT_TYPE_PROTO,
        status=HTTPStatus.BAD_REQUEST,
    )


def _http_human_in_loop_gate_response(
    *,
    agent_msg: opamp_pb2.AgentToServer,
    client_id: str | None,
    known_client: ClientRecord | None,
    request_headers: dict[str, str],
    remote_addr: str | None,
) -> Response | None:
    """Return an approval-gate response when the agent is not yet approved."""
    if not provider_config.CONFIG.human_in_loop_approval:
        return None
    if not client_id:
        return _build_opamp_http_error_response(
            instance_uid=None,
            status_code=HTTPStatus.BAD_REQUEST,
            error_message="instance_uid is required when human_in_loop_approval is enabled",
        )
    if known_client is not None:
        return None
    if STORE.get_pending_approval(client_id) is None:
        try:
            STORE.add_pending_approval_from_agent_msg(
                agent_msg,
                channel=CHANNEL_HTTP,
                remote_addr=remote_addr,
            )
            logger.info(
                "agent moved to pending approval client_id=%s remote_addr=%s",
                client_id,
                remote_addr or "unknown",
            )
        except Exception as approval_error:
            STORE.block_agent(
                client_id,
                reason=f"failed pending approval payload transformation: {approval_error}",
                headers=request_headers,
                ip=remote_addr,
            )
            logger.exception(
                "failed to transform pending approval payload; client blocked client_id=%s",
                client_id,
                exc_info=approval_error,
            )
            return _build_opamp_http_error_response(
                instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
                status_code=HTTPStatus.FORBIDDEN,
                error_message=ERR_AGENT_BLOCKED,
                error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
            )
    return _build_opamp_http_error_response(
        instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
        status_code=HTTPStatus.FORBIDDEN,
        error_message=ERR_AGENT_PENDING_APPROVAL,
        error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
    )


def _build_http_success_response(
    *,
    agent_msg: opamp_pb2.AgentToServer,
    remote_addr: str | None,
) -> Response:
    """Persist one HTTP agent message, build response, and mark commands sent."""
    client = STORE.upsert_from_agent_msg(
        agent_msg,
        channel=CHANNEL_HTTP,
        remote_addr=remote_addr,
    )
    if not _is_heartbeat_only_message(agent_msg):
        _note_non_heartbeat_state_change_and_maybe_autosave()
    pending_command = STORE.next_pending_command(client.client_id)
    response_msg = _build_response(
        agent_msg,
        pending_command,
        client=client,
        channel=CHANNEL_HTTP,
    )
    if pending_command is not None and _has_dispatched_command_payload(
        response_msg
    ):
        STORE.mark_command_sent(client.client_id, pending_command)
        logger.info(LOG_SEND_COMMAND, client.client_id, datetime.now(timezone.utc))
    return Response(response_msg.SerializeToString(), content_type=CONTENT_TYPE_PROTO)


def _build_websocket_auth_error_message(
    auth_decision: provider_auth.AuthDecision,
) -> opamp_pb2.ServerToAgent:
    """Build an auth error ServerToAgent message for websocket handshakes."""
    error_type = (
        opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_Unavailable
        if auth_decision.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        else opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest
    )
    return _build_error_message(
        instance_uid=None,
        error_type=error_type,
        error_message=auth_decision.error or ERR_AGENT_AUTH_FAILED,
    )


async def _send_websocket_error_and_close(
    response_msg: opamp_pb2.ServerToAgent,
) -> None:
    """Send one websocket error response and close with policy-violation code."""
    await websocket.send(encode_message(response_msg.SerializeToString()))
    await websocket.close(code=1008)


def _websocket_human_in_loop_gate(
    *,
    agent_msg: opamp_pb2.AgentToServer,
    client_id: str | None,
    known_client: ClientRecord | None,
    ws_headers: dict[str, str],
    remote_addr: str | None,
) -> tuple[opamp_pb2.ServerToAgent | None, bool]:
    """Evaluate websocket approval gate and return response + close flag when blocked."""
    if not provider_config.CONFIG.human_in_loop_approval:
        return None, False
    if not client_id:
        return (
            _build_error_message(
                instance_uid=None,
                error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
                error_message="instance_uid is required when human_in_loop_approval is enabled",
            ),
            True,
        )
    if known_client is not None:
        return None, False
    if STORE.get_pending_approval(client_id) is None:
        try:
            STORE.add_pending_approval_from_agent_msg(
                agent_msg,
                channel=CHANNEL_WEBSOCKET,
                remote_addr=remote_addr,
            )
            logger.info(
                "agent moved to pending approval client_id=%s remote_addr=%s",
                client_id,
                remote_addr or "unknown",
            )
        except Exception as approval_error:
            STORE.block_agent(
                client_id,
                reason=(
                    "failed pending approval payload "
                    f"transformation: {approval_error}"
                ),
                headers=ws_headers,
                ip=remote_addr,
            )
            logger.exception(
                (
                    "failed to transform pending approval payload; "
                    "client blocked client_id=%s"
                ),
                client_id,
                exc_info=approval_error,
            )
            return (
                _build_error_message(
                    instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
                    error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
                    error_message=ERR_AGENT_BLOCKED,
                ),
                True,
            )
    return (
        _build_error_message(
            instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
            error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
            error_message=ERR_AGENT_PENDING_APPROVAL,
        ),
        True,
    )


def _process_websocket_agent_message(
    *,
    agent_msg: opamp_pb2.AgentToServer,
    ws_headers: dict[str, str],
    remote_addr: str | None,
) -> tuple[opamp_pb2.ServerToAgent, CommandRecord | None, ClientRecord | None, bool]:
    """Process one decoded websocket AgentToServer message and return response context."""
    pending_command = None
    client = None
    close_after_send = False
    client_id = _extract_client_id(agent_msg)

    if client_id and STORE.is_blocked_agent(client_id):
        _log_blocked_agent_attempt(
            client_id=client_id,
            channel=CHANNEL_WEBSOCKET,
            headers=ws_headers,
            remote_addr=remote_addr,
        )
        return (
            _build_error_message(
                instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
                error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
                error_message=ERR_AGENT_BLOCKED,
            ),
            pending_command,
            client,
            True,
        )

    known_client = STORE.get(client_id) if client_id else None
    approval_response, close_after_send = _websocket_human_in_loop_gate(
        agent_msg=agent_msg,
        client_id=client_id,
        known_client=known_client,
        ws_headers=ws_headers,
        remote_addr=remote_addr,
    )
    if approval_response is not None:
        return approval_response, pending_command, client, close_after_send

    client = STORE.upsert_from_agent_msg(
        agent_msg,
        channel=CHANNEL_WEBSOCKET,
        remote_addr=remote_addr,
    )
    if not _is_heartbeat_only_message(agent_msg):
        _note_non_heartbeat_state_change_and_maybe_autosave()
    _WEBSOCKET_CLIENTS[websocket] = client.client_id
    pending_command = STORE.next_pending_command(client.client_id)
    response_msg = _build_response(
        agent_msg,
        pending_command,
        client=client,
        channel=CHANNEL_WEBSOCKET,
    )
    return response_msg, pending_command, client, False


@app.post(OPAMP_HTTP_PATH)
async def opamp_http() -> Response:
    """Handle OpAMP HTTP POST requests."""
    try:
        data = await request.get_data()
        agent_msg = opamp_pb2.AgentToServer()
        if data:
            agent_msg.ParseFromString(data)

        logger.info(LOG_HTTP_MSG, text_format.MessageToString(agent_msg))
        client_id = _extract_client_id(agent_msg)
        request_headers = _request_header_map()
        remote_addr = request.remote_addr

        if client_id and STORE.is_blocked_agent(client_id):
            _log_blocked_agent_attempt(
                client_id=client_id,
                channel=CHANNEL_HTTP,
                headers=request_headers,
                remote_addr=remote_addr,
            )
            return _build_opamp_http_error_response(
                instance_uid=agent_msg.instance_uid if agent_msg.instance_uid else None,
                status_code=HTTPStatus.FORBIDDEN,
                error_message=ERR_AGENT_BLOCKED,
                error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
            )

        opamp_auth_decision = _evaluate_opamp_transport_auth(
            headers=request_headers,
            remote_addr=remote_addr,
            channel=CHANNEL_HTTP,
        )
        if not opamp_auth_decision.allowed:
            return _build_http_auth_error_response(
                agent_msg=agent_msg,
                auth_decision=opamp_auth_decision,
            )

        known_client = STORE.get(client_id) if client_id else None
        approval_response = _http_human_in_loop_gate_response(
            agent_msg=agent_msg,
            client_id=client_id,
            known_client=known_client,
            request_headers=request_headers,
            remote_addr=remote_addr,
        )
        if approval_response is not None:
            return approval_response

        unsupported = _unsupported_agent_fields(agent_msg)
        if unsupported:
            return _build_http_unsupported_fields_response(
                agent_msg=agent_msg,
                unsupported_fields=unsupported,
            )
        return _build_http_success_response(
            agent_msg=agent_msg,
            remote_addr=remote_addr,
        )
    except Exception as exc:
        logger.exception("Unhandled HTTP error - %s", exc_info=exc)
        response_msg = _build_error_message(
            instance_uid=None,
            error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_Unavailable,
            error_message="internal server error",
        )
        payload = response_msg.SerializeToString()
        return Response(
            payload,
            content_type=CONTENT_TYPE_PROTO,
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@app.websocket(OPAMP_HTTP_PATH)
async def opamp_websocket() -> None:
    """Handle OpAMP WebSocket connections."""
    _WEBSOCKET_CLIENTS[websocket] = None
    ws_headers = _websocket_header_map()
    remote_addr = _websocket_remote_addr()
    try:
        opamp_auth_decision = _evaluate_opamp_transport_auth(
            headers=ws_headers,
            remote_addr=remote_addr,
            channel=CHANNEL_WEBSOCKET,
        )
        if not opamp_auth_decision.allowed:
            await _send_websocket_error_and_close(
                _build_websocket_auth_error_message(opamp_auth_decision)
            )
            return

        while True:
            pending_command = None
            client = None
            close_after_send = False
            agent_msg = opamp_pb2.AgentToServer()
            data = await websocket.receive()
            if isinstance(data, str):
                data = data.encode(UTF8_ENCODING)
            try:
                header, payload = decode_message(data)
                if header != OPAMP_HEADER_NONE:
                    response_msg = _build_error_message(
                        instance_uid=None,
                        error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
                        error_message=ERR_UNSUPPORTED_HEADER,
                    )
                else:
                    if payload:
                        agent_msg.ParseFromString(payload)
                    logger.info(LOG_WS_MSG, text_format.MessageToString(agent_msg))
                    (
                        response_msg,
                        pending_command,
                        client,
                        close_after_send,
                    ) = _process_websocket_agent_message(
                        agent_msg=agent_msg,
                        ws_headers=ws_headers,
                        remote_addr=remote_addr,
                    )
            except ValueError as exc:
                logger.warning("OpAMP websocket value error: %s", exc)
                response_msg = _build_error_message(
                    instance_uid=(
                        agent_msg.instance_uid if agent_msg.instance_uid else None
                    ),
                    error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_BadRequest,
                    error_message=str(exc),
                )
            except Exception as exc:
                logger.exception("Unhandled websocket error", exc_info=exc)
                response_msg = _build_error_message(
                    instance_uid=(
                        agent_msg.instance_uid if agent_msg.instance_uid else None
                    ),
                    error_type=opamp_pb2.ServerErrorResponseType.ServerErrorResponseType_Unavailable,
                    error_message="internal server error",
                )

            out_payload = response_msg.SerializeToString()
            await websocket.send(encode_message(out_payload))
            if pending_command is not None and _has_dispatched_command_payload(
                response_msg
            ):
                if client is not None:
                    STORE.mark_command_sent(client.client_id, pending_command)
                    logger.info(
                        LOG_SEND_COMMAND, client.client_id, datetime.now(timezone.utc)
                    )
            if close_after_send:
                await websocket.close(code=1008)
                break
    finally:
        _WEBSOCKET_CLIENTS.pop(websocket, None)


async def _close_websockets() -> None:
    """Close all active WebSocket connections."""
    if not _WEBSOCKET_CLIENTS:
        return

    async def _close_one(web_socket: object, client_id: str | None) -> None:
        try:
            await web_socket.close(code=1001)
            if client_id:
                logger.info("closed websocket for client %s", client_id)
            else:
                logger.info("closed websocket for unknown client")
        except Exception as err:
            logger.warning(
                "failed to close websocket for client %s - %s", client_id, err
            )

    await asyncio.gather(
        *[
            _close_one(web_socket, client_id)
            for web_socket, client_id in list(_WEBSOCKET_CLIENTS.items())
            if web_socket is not None
        ],
        return_exceptions=True,
    )


@app.after_serving
async def _finalize_server() -> None:
    """Finalizer to cleanly close WebSocket connections on shutdown."""
    await _close_websockets()
    _save_state_snapshot("graceful_shutdown")


@app.post("/api/client-errors")
async def client_errors() -> Response:
    """Record one client-side UI error reported by browser JavaScript."""
    body = await request.get_json(silent=True) or {}
    message = str(body.get("message") or "Unknown UI error").strip()
    kind = str(body.get("kind") or "runtime_error").strip()
    source = str(body.get("source") or "browser").strip()
    path = str(body.get("path") or request.headers.get("Referer") or "").strip()
    stack = str(body.get("stack") or "").strip()
    line = body.get("line")
    column = body.get("column")
    user_agent = request.headers.get("User-Agent", "")

    log_message = (
        f"UI ERROR | kind={kind} | source={source} | path={path or '-'} | "
        f"line={line if line is not None else '-'} | column={column if column is not None else '-'} | "
        f"message={message}"
    )
    if user_agent:
        log_message += f" | user_agent={user_agent}"
    if stack:
        log_message += f"\n{stack}"
    logger.error(log_message)
    return jsonify({"ok": True}), HTTPStatus.OK


@app.get("/api/clients")
async def list_clients() -> Response:
    """List all tracked clients."""
    global _LAST_DISCONNECT_PURGE
    now = datetime.now(timezone.utc)
    keep_minutes = max(1, int(provider_config.CONFIG.minutes_keep_disconnected))
    purge_interval = timedelta(minutes=keep_minutes / 2)
    if _LAST_DISCONNECT_PURGE is None or now - _LAST_DISCONNECT_PURGE >= purge_interval:
        cutoff = now - timedelta(minutes=keep_minutes)
        removed = STORE.purge_disconnected(cutoff)
        if removed:
            logger.info("purged %s disconnected clients", len(removed))
        _LAST_DISCONNECT_PURGE = now
    service_instance_id = _normalize_query_text(
        request.args.get(QUERY_PARAM_SERVICE_INSTANCE_ID)
    )
    client_version = _normalize_query_text(request.args.get(QUERY_PARAM_CLIENT_VERSION))
    host_name = _normalize_query_text(request.args.get(QUERY_PARAM_HOST_NAME))
    host_ip = _normalize_query_text(request.args.get(QUERY_PARAM_HOST_IP))
    try:
        invert_filter = (
            _parse_optional_bool(
                request.args.get(QUERY_PARAM_INVERT_FILTER),
                parameter_name=QUERY_PARAM_INVERT_FILTER,
            )
            is True
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    has_active_filters = any(
        value is not None for value in (service_instance_id, client_version, host_name, host_ip)
    )
    clients = [
        _serialize_client_record_for_api(client)
        for client in STORE.list()
        if _client_matches_api_clients_filters(
            client,
            service_instance_id=service_instance_id,
            client_version=client_version,
            host_name=host_name,
            host_ip=host_ip,
            invert_filter=invert_filter,
            has_active_filters=has_active_filters,
        )
    ]
    return jsonify(
        {
            "clients": clients,
            "total": len(clients),
            "pending_approval_total": STORE.pending_approval_count(),
        }
    )


@app.get("/api/approvals/pending")
async def list_pending_approvals() -> Response:
    """List agents currently waiting for human approval."""
    pending = [
        client.model_dump(mode=MODEL_DUMP_MODE)
        for client in STORE.list_pending_approvals()
    ]
    return jsonify({"clients": pending, "total": len(pending)})


@app.post("/api/approvals/pending")
async def apply_pending_approval_decisions() -> Response:
    """Apply approve/block decisions for pending agents."""
    payload = await request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
    decisions_raw = payload.get("decisions")
    if not isinstance(decisions_raw, list) or not decisions_raw:
        return jsonify({"error": "decisions array is required"}), HTTPStatus.BAD_REQUEST

    approved = 0
    blocked = 0
    for item in decisions_raw:
        if not isinstance(item, dict):
            continue
        client_id = str(item.get("client_id", "")).strip()
        decision = str(item.get("decision", "")).strip().lower()
        if not client_id:
            continue
        if decision == "approve":
            moved = STORE.approve_pending_approval(client_id)
            if moved is not None:
                approved += 1
            continue
        if decision == "block":
            STORE.block_agent(
                client_id,
                reason="blocked via pending approval workflow",
                headers=_request_header_map(),
                ip=request.remote_addr,
            )
            blocked += 1

    return jsonify(
        {
            "approved": approved,
            "blocked": blocked,
            "pending_approval_total": STORE.pending_approval_count(),
        }
    )


@app.get("/api/commands/custom")
async def list_custom_commands() -> Response:
    """Return custom command metadata for UI command selection/configuration."""
    client_id = (request.args.get("client_id") or "").strip()
    reported_capabilities: set[str] = set()
    if client_id:
        record = STORE.get(client_id)
        if record is not None:
            reported_capabilities = {
                str(capability).strip()
                for capability in record.custom_capabilities_reported
                if str(capability).strip()
            }
    commands = get_command_metadata(
        parameter_exclude_opamp_standard=True,
        custom_only=True,
    )
    for command in commands:
        fqdn = str(command.get("fqdn", "") or "").strip()
        command["reported_by_client"] = bool(fqdn and fqdn in reported_capabilities)
    return jsonify({"commands": commands})


@app.get("/api/clients/<client_id>")
async def get_client(client_id: str) -> Response:
    """Get a single client record."""
    record = STORE.get(client_id)
    if record is None:
        return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
    return jsonify(_serialize_client_record_for_api(record))


@app.delete("/api/clients/<client_id>")
async def delete_client(client_id: str) -> Response:
    """Remove a client from memory."""
    record = STORE.remove_client(client_id)
    if record is None:
        return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
    logger.warning(
        "client removed from store client_id=%s last_state=%s",
        client_id,
        record.model_dump(mode=MODEL_DUMP_MODE),
    )
    return jsonify({"status": "removed"})


@app.post("/api/clients/<client_id>/commands")
async def queue_command(client_id: str) -> Response:
    """Queue a structured command intent for a client."""
    payload = await request.get_json(silent=True)
    try:
        cmd = queue_command_from_payload(
            client_id=client_id,
            payload=payload,
            store=STORE,
            max_events=provider_config.CONFIG.client_event_history_size,
            command_builders=COMMAND_BUILDERS,
            logger=logger,
        )
    except QueueCommandRequestError as exc:
        return jsonify(exc.payload), int(exc.status_code)
    return jsonify(cmd.model_dump(mode=MODEL_DUMP_MODE)), HTTPStatus.CREATED


@app.post("/api/clients/<client_id>/actions")
async def set_client_actions(client_id: str) -> Response:
    """Set next actions for a client."""
    payload = await request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
    raw_actions = payload.get("actions")
    if raw_actions is None:
        return jsonify({"error": "actions is required"}), HTTPStatus.BAD_REQUEST
    if isinstance(raw_actions, str):
        actions = [raw_actions]
    elif isinstance(raw_actions, list):
        actions = raw_actions
    else:
        return (
            jsonify({"error": "actions must be a list or string"}),
            HTTPStatus.BAD_REQUEST,
        )
    actions = [str(action).strip() for action in actions if str(action).strip()]
    if not actions:
        record = STORE.set_next_actions(client_id, None)
        return jsonify(record.model_dump(mode=MODEL_DUMP_MODE))
    invalid = [action for action in actions if action not in ACTION_OPTIONS]
    if invalid:
        return (
            jsonify(
                {
                    "error": "invalid actions",
                    "invalid": invalid,
                    "allowed": sorted(ACTION_OPTIONS),
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )
    record = STORE.set_next_actions(client_id, actions)
    return jsonify(record.model_dump(mode=MODEL_DUMP_MODE))


@app.put("/api/clients/<client_id>/heartbeat-frequency")
async def set_client_heartbeat_frequency(client_id: str) -> Response:
    """Set heartbeat frequency for a single client and append an event."""
    payload = await request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
    try:
        heartbeat_frequency = int(payload.get("heartbeat_frequency"))
    except (TypeError, ValueError):
        return (
            jsonify({"error": "heartbeat_frequency must be an integer"}),
            HTTPStatus.BAD_REQUEST,
        )
    if heartbeat_frequency <= 0:
        return (
            jsonify({"error": "heartbeat_frequency must be positive"}),
            HTTPStatus.BAD_REQUEST,
        )
    record = STORE.set_client_heartbeat_frequency(
        client_id,
        heartbeat_frequency,
        max_events=provider_config.CONFIG.client_event_history_size,
    )
    if record is None:
        return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
    return jsonify(record.model_dump(mode=MODEL_DUMP_MODE))


@app.post("/api/clients/<client_id>/identify")
async def issue_agent_identification(client_id: str) -> Response:
    """Issue a new instance UID for a client."""
    record = STORE.get(client_id)
    if record is None:
        return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
    new_uid = STORE.generate_unique_instance_uid()
    STORE.set_agent_identification(client_id, new_uid)
    STORE.add_event(
        client_id,
        description="Issue New Unique ID",
        max_events=provider_config.CONFIG.client_event_history_size,
    )
    logger.info("issued new instance uid for client %s", client_id)
    return jsonify({"status": "queued", "new_instance_uid": new_uid.hex()})


@app.post("/api/clients/<client_id>/config")
async def set_requested_config(client_id: str) -> Response:
    """Set requested configuration for a client."""
    payload = await request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
    config_text = str(payload.get("config", "")).strip()
    if not config_text:
        return jsonify({"error": "config is required"}), HTTPStatus.BAD_REQUEST
    version = payload.get("version")
    apply_at_raw = payload.get("apply_at")
    apply_at = None
    if apply_at_raw:
        try:
            apply_at = datetime.fromisoformat(str(apply_at_raw))
        except ValueError:
            return (
                jsonify({"error": "apply_at must be ISO 8601"}),
                HTTPStatus.BAD_REQUEST,
            )
    record = STORE.set_requested_config(
        client_id,
        config_text=config_text,
        version=str(version) if version else None,
        apply_at=apply_at,
    )
    return jsonify(record.model_dump(mode=MODEL_DUMP_MODE))


@app.post("/api/clients/<client_id>/remote-config-selection")
async def accept_remote_config_selection(client_id: str) -> Response:
    """Normalize ordered catalog selections for one client without mutating server-side client state."""
    if not _provider_allows_remote_config():
        logger.warning(
            "remote config selection rejected because provider setting is disabled client_id=%s",
            client_id,
        )
        return jsonify({"error": ERR_REMOTE_CONFIG_DISABLED}), HTTPStatus.FORBIDDEN

    payload = await request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST

    client = STORE.get(client_id)
    if client is None:
        logger.warning(
            "remote config selection rejected for unknown client client_id=%s",
            client_id,
        )
        return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND

    try:
        selection_specs = normalize_remote_config_selection_specs(payload.get("files"))
    except ValueError as exc:
        logger.warning(
            "remote config selection validation failed client_id=%s error=%s",
            client_id,
            exc,
        )
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    return jsonify(
        {
            "status": REMOTE_CONFIG_SELECTION_STATUS_ACCEPTED,
            "client_id": client_id,
            "files": [
                {
                    "source_path": str(selection_spec.source_path),
                    "target_name": selection_spec.target_name,
                    "filename": selection_spec.filename,
                }
                for selection_spec in selection_specs
            ],
        }
    )


@app.post("/api/clients/<client_id>/remote-config")
async def queue_remote_config_offer(client_id: str) -> Response:
    """Validate, build, and queue a remote-config offer for a client."""
    if not _provider_allows_remote_config():
        logger.warning(
            "remote config request rejected because provider setting is disabled client_id=%s",
            client_id,
        )
        return jsonify({"error": ERR_REMOTE_CONFIG_DISABLED}), HTTPStatus.FORBIDDEN

    payload = await request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST

    client = STORE.get(client_id)
    if client is None:
        logger.warning(
            "remote config request rejected for unknown client client_id=%s",
            client_id,
        )
        return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
    if not _client_supports_remote_config(client):
        logger.warning(
            "remote config request rejected client_id=%s capabilities=%s missing=%s",
            client_id,
            client.capabilities,
            CLIENT_REMOTE_CONFIG_CAPABILITY,
        )
        return (
            jsonify(
                {
                    "error": "client does not accept remote config",
                    "required_capability": CLIENT_REMOTE_CONFIG_CAPABILITY,
                    "client_capabilities": client.capabilities,
                }
            ),
            HTTPStatus.CONFLICT,
        )

    try:
        file_specs = normalize_remote_config_file_specs(payload.get("files"))
        include_hash = _coerce_bool_setting(
            payload.get("include_hash", True),
            key="include_hash",
        )
        validation_results = validate_remote_config_files(
            file_specs,
            app_extensions=app.extensions,
            validation_payload=payload.get("validation"),
        )
    except ValueError as exc:
        logger.warning(
            "remote config request validation failed client_id=%s error=%s",
            client_id,
            exc,
        )
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    remote_config = build_agent_remote_config(
        opamp_pb2.AgentRemoteConfig(),
        [file_spec.to_agent_config_map_entry() for file_spec in file_specs],
        include_hash=include_hash,
    )
    remote_config_bytes = remote_config.SerializeToString()
    config_hash_hex = remote_config.config_hash.hex() if remote_config.config_hash else ""
    logger.info(
        "queued remote config offer client_id=%s files=%s payload_size_bytes=%s config_hash=%s",
        client_id,
        len(file_specs),
        len(remote_config_bytes),
        config_hash_hex or "none",
    )

    STORE.set_pending_remote_config(client_id, remote_config_bytes)
    record = STORE.enqueue_next_action(client_id, ACTION_APPLY_CONFIG)
    return (
        jsonify(
            {
                "client_id": client_id,
                "files": [
                    {
                        "source_path": str(file_spec.source_path),
                        "target_name": file_spec.target_name,
                        "content_type": file_spec.content_type,
                        "size_bytes": file_spec.size_bytes,
                    }
                    for file_spec in file_specs
                ],
                "validation": validation_results,
                "config_hash": config_hash_hex,
                "payload_size_bytes": len(remote_config_bytes),
                "queued_action": ACTION_APPLY_CONFIG,
                "next_actions": record.next_actions,
                "editor_validation_available": config_editor_validation_available(
                    app.extensions
                ),
            }
        ),
        HTTPStatus.CREATED,
    )


@app.post("/api/test/clients/<client_id>/remote-config")
async def build_test_remote_config(client_id: str) -> Response:
    """Construct and queue a test AgentRemoteConfig payload for a client."""
    if not _diagnostic_mode_enabled():
        return (
            jsonify({"error": "diagnostic mode is disabled"}),
            HTTPStatus.FORBIDDEN,
        )
    payload = await request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
    try:
        file_specs = normalize_remote_config_file_specs(payload.get("files"))
        include_hash = _coerce_bool_setting(
            payload.get("include_hash", True),
            key="include_hash",
        )
        queue_action = _coerce_bool_setting(
            payload.get("queue_action", True),
            key="queue_action",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    remote_config = build_agent_remote_config(
        opamp_pb2.AgentRemoteConfig(),
        [file_spec.to_agent_config_map_entry() for file_spec in file_specs],
        include_hash=include_hash,
    )
    record = STORE.set_pending_remote_config(
        client_id,
        remote_config.SerializeToString(),
    )
    if queue_action:
        record = STORE.enqueue_next_action(client_id, ACTION_APPLY_CONFIG)

    return (
        jsonify(
            {
                "client_id": client_id,
                "diagnostic_enabled": True,
                "files": [
                    {
                        "source_path": str(file_spec.source_path),
                        "target_name": file_spec.target_name,
                        "content_type": file_spec.content_type,
                        "size_bytes": file_spec.size_bytes,
                    }
                    for file_spec in file_specs
                ],
                "include_hash": include_hash,
                "config_hash": remote_config.config_hash.hex()
                if remote_config.config_hash
                else "",
                "queued_action": ACTION_APPLY_CONFIG if queue_action else None,
                "next_actions": record.next_actions,
            }
        ),
        HTTPStatus.CREATED,
    )


@app.post("/api/shutdown")
async def shutdown_server() -> Response:
    """Shutdown the server if explicitly confirmed."""
    payload = await request.get_json(silent=True) or {}
    confirm = payload.get("confirm") is True
    if not confirm:
        return jsonify({"error": "confirm is required"}), HTTPStatus.BAD_REQUEST
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    logger.warning("shutdown requested via API")
    await _close_websockets()
    asyncio.create_task(_shutdown_after_response())
    return jsonify({"status": "shutting down"})

_UI_ASSETS = load_provider_ui_assets(logger=logger)
register_ui_routes(
    app,
    ui_assets=_UI_ASSETS,
    provider_config=provider_config,
    global_settings_help=GLOBAL_SETTINGS_HELP,
    render_help_html=render_help_html,
    component_version_text=component_version_text,
    ui_feature_menu_items=_UI_FEATURE_MENU_ITEMS,
    registered_component_entry_points=_REGISTERED_COMPONENT_ENTRY_POINTS,
)
register_settings_routes(
    app,
    provider_config=provider_config,
    store=STORE,
    logger=logger,
    persistence_tracker=_PERSISTENCE_TRACKER,
    diagnostic_mode_enabled=_diagnostic_mode_enabled,
    state_snapshot_file_count=_state_snapshot_file_count,
    tls_certificate_expiry_metadata=_tls_certificate_expiry_metadata,
    record_snapshot_status=_record_snapshot_status,
    coerce_bool_setting=_coerce_bool_setting,
    save_state_snapshot_func=lambda **kwargs: save_state_snapshot(**kwargs),
    prune_snapshot_files_func=lambda **kwargs: prune_snapshot_files(**kwargs),
)
