"""Client and admin API route registration for provider app."""

from __future__ import annotations

import asyncio
import base64
import binascii
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from quart import Quart, jsonify, request
from quart.typing import ResponseReturnValue

from opamp_provider.app_client_filters import (
    client_matches_api_clients_filters,
    normalize_query_text,
    parse_optional_bool,
    serialize_client_record_for_api,
)
from opamp_provider.command_queue import (
    QueueCommandRequestError,
    queue_command_from_payload,
)
from opamp_provider.commands import get_command_metadata
from opamp_provider.proto import opamp_pb2
from opamp_provider.remote_config_schema import (
    config_editor_validation_available,
    normalize_remote_config_file_specs,
    normalize_remote_config_selection_specs,
    validate_remote_config_files,
)
from shared.agent_remote_config import build_agent_remote_config

QUERY_PARAM_SERVICE_INSTANCE_ID = "service_instance_id"
QUERY_PARAM_CLIENT_VERSION = "client_version"
QUERY_PARAM_HOST_NAME = "host_name"
QUERY_PARAM_HOST_IP = "host_ip"
QUERY_PARAM_INVERT_FILTER = "invertFilter"
REMOTE_CONFIG_SELECTION_STATUS_ACCEPTED = "accepted"


def register_client_routes(  # noqa: PLR0913
    app: Quart,
    *,
    provider_config: Any,
    store: Any,
    logger: Any,
    model_dump_mode: str,
    command_builders: dict[tuple[str, str], Any],
    action_options: set[str],
    action_apply_config: str,
    action_change_connections: str,
    client_remote_config_capability: str,
    remote_config_disabled_error: str,
    diagnostic_mode_enabled: Any,
    close_websockets: Any,
    shutdown_after_response: Any,
    coerce_bool_setting: Any,
) -> None:
    """Register provider client-management and admin API routes."""

    last_disconnect_purge: datetime | None = None

    def provider_allows_remote_config() -> bool:
        """Return whether remote config support is enabled in provider config."""
        return provider_config.CONFIG.allow_remote_config is True

    def provider_allows_connection_settings() -> bool:
        """Return whether connection-settings offers are enabled in provider config."""
        return provider_config.CONFIG.allow_connection_settings is True

    def client_supports_remote_config(client: Any) -> bool:
        """Return whether a client advertised remote-config support."""
        return client_remote_config_capability in client.capabilities

    def serialize_client(record: Any) -> dict[str, object]:
        """Return one API-facing client payload with provider-specific flags."""
        return serialize_client_record_for_api(
            record,
            model_dump_mode=model_dump_mode,
            provider_remote_config_enabled=provider_allows_remote_config(),
            remote_config_capability_reported=client_supports_remote_config(record),
        )

    def remote_config_history_description(file_count: int) -> str:
        """Return the history message used when remote config files are queued."""
        if file_count == 1:
            return "Queued 1 remote config file."
        return f"Queued {file_count} remote config files."

    def _decode_connection_settings_payload(payload: dict[str, Any]) -> bytes:
        """Decode and validate one base64-encoded ConnectionSettingsOffers payload."""
        payload_base64 = str(payload.get("payload_base64") or "").strip()
        if not payload_base64:
            raise ValueError("payload_base64 is required")
        try:
            payload_bytes = base64.b64decode(payload_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("payload_base64 must be valid base64") from exc
        offers = opamp_pb2.ConnectionSettingsOffers()
        try:
            offers.ParseFromString(payload_bytes)
        except Exception as exc:  # pragma: no cover - protobuf raises implementation-specific exceptions
            raise ValueError("payload_base64 does not contain valid connection settings") from exc
        if not offers.ListFields():
            raise ValueError("payload_base64 does not contain valid connection settings")
        return payload_bytes

    @app.post("/api/client-errors")
    async def client_errors() -> ResponseReturnValue:
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
    async def list_clients() -> ResponseReturnValue:
        """List tracked clients, optionally filtered by metadata query parameters."""
        nonlocal last_disconnect_purge
        now = datetime.now(timezone.utc)
        keep_minutes = max(1, int(provider_config.CONFIG.minutes_keep_disconnected))
        purge_interval = timedelta(minutes=keep_minutes / 2)
        if last_disconnect_purge is None or now - last_disconnect_purge >= purge_interval:
            cutoff = now - timedelta(minutes=keep_minutes)
            removed = store.purge_disconnected(cutoff)
            if removed:
                logger.info("purged %s disconnected clients", len(removed))
            last_disconnect_purge = now

        service_instance_id = normalize_query_text(
            request.args.get(QUERY_PARAM_SERVICE_INSTANCE_ID)
        )
        client_version = normalize_query_text(
            request.args.get(QUERY_PARAM_CLIENT_VERSION)
        )
        host_name = normalize_query_text(request.args.get(QUERY_PARAM_HOST_NAME))
        host_ip = normalize_query_text(request.args.get(QUERY_PARAM_HOST_IP))
        try:
            invert_filter = (
                parse_optional_bool(
                    request.args.get(QUERY_PARAM_INVERT_FILTER),
                    parameter_name=QUERY_PARAM_INVERT_FILTER,
                )
                is True
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

        has_active_filters = any(
            value is not None
            for value in (service_instance_id, client_version, host_name, host_ip)
        )
        clients = [
            serialize_client(client)
            for client in store.list()
            if client_matches_api_clients_filters(
                client,
                service_instance_id=service_instance_id,
                client_version=client_version,
                host_name=host_name,
                host_ip=host_ip,
                invert_filter=invert_filter,
                has_active_filters=has_active_filters,
                logger=logger,
            )
        ]
        return jsonify(
            {
                "clients": clients,
                "total": len(clients),
                "pending_approval_total": store.pending_approval_count(),
            }
        )

    @app.get("/api/approvals/pending")
    async def list_pending_approvals() -> ResponseReturnValue:
        """List agents currently waiting for human approval."""
        pending = [
            client.model_dump(mode=model_dump_mode)
            for client in store.list_pending_approvals()
        ]
        return jsonify({"clients": pending, "total": len(pending)})

    @app.post("/api/approvals/pending")
    async def apply_pending_approval_decisions() -> ResponseReturnValue:
        """Apply approve/block decisions for pending agents."""
        payload = await request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
        decisions_raw = payload.get("decisions")
        if not isinstance(decisions_raw, list) or not decisions_raw:
            return (
                jsonify({"error": "decisions array is required"}),
                HTTPStatus.BAD_REQUEST,
            )

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
                moved = store.approve_pending_approval(client_id)
                if moved is not None:
                    approved += 1
                continue
            if decision == "block":
                store.block_agent(
                    client_id,
                    reason="blocked via pending approval workflow",
                    headers={str(key): str(value) for key, value in request.headers.items()},
                    ip=request.remote_addr,
                )
                blocked += 1

        return jsonify(
            {
                "approved": approved,
                "blocked": blocked,
                "pending_approval_total": store.pending_approval_count(),
            }
        )

    @app.get("/api/commands/custom")
    async def list_custom_commands() -> ResponseReturnValue:
        """Return custom command metadata for UI command selection/configuration."""
        client_id = (request.args.get("client_id") or "").strip()
        reported_capabilities: set[str] = set()
        if client_id:
            record = store.get(client_id)
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
            command["reported_by_client"] = bool(
                fqdn and fqdn in reported_capabilities
            )
        return jsonify({"commands": commands})

    @app.get("/api/clients/<client_id>")
    async def get_client(client_id: str) -> ResponseReturnValue:
        """Get a single client record."""
        record = store.get(client_id)
        if record is None:
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
        return jsonify(serialize_client(record))

    @app.delete("/api/clients/<client_id>")
    async def delete_client(client_id: str) -> ResponseReturnValue:
        """Remove a client from memory."""
        record = store.remove_client(client_id)
        if record is None:
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
        logger.warning(
            "client removed from store client_id=%s last_state=%s",
            client_id,
            record.model_dump(mode=model_dump_mode),
        )
        return jsonify({"status": "removed"})

    @app.post("/api/clients/<client_id>/commands")
    async def queue_command(client_id: str) -> ResponseReturnValue:
        """Queue a structured command intent for a client."""
        payload = await request.get_json(silent=True)
        try:
            cmd = queue_command_from_payload(
                client_id=client_id,
                payload=payload,
                store=store,
                max_events=provider_config.CONFIG.client_event_history_size,
                command_builders=command_builders,
                logger=logger,
            )
        except QueueCommandRequestError as exc:
            return jsonify(exc.payload), int(exc.status_code)
        return jsonify(cmd.model_dump(mode=model_dump_mode)), HTTPStatus.CREATED

    @app.post("/api/clients/<client_id>/actions")
    async def set_client_actions(client_id: str) -> ResponseReturnValue:
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
            record = store.set_next_actions(client_id, None)
            return jsonify(record.model_dump(mode=model_dump_mode))
        invalid = [action for action in actions if action not in action_options]
        if invalid:
            return (
                jsonify(
                    {
                        "error": "invalid actions",
                        "invalid": invalid,
                        "allowed": sorted(action_options),
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )
        record = store.set_next_actions(client_id, actions)
        return jsonify(record.model_dump(mode=model_dump_mode))

    @app.put("/api/clients/<client_id>/heartbeat-frequency")
    async def set_client_heartbeat_frequency(client_id: str) -> ResponseReturnValue:
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
        record = store.set_client_heartbeat_frequency(
            client_id,
            heartbeat_frequency,
            max_events=provider_config.CONFIG.client_event_history_size,
        )
        if record is None:
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
        return jsonify(record.model_dump(mode=model_dump_mode))

    @app.post("/api/clients/<client_id>/identify")
    async def issue_agent_identification(client_id: str) -> ResponseReturnValue:
        """Issue a new instance UID for a client."""
        record = store.get(client_id)
        if record is None:
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
        new_uid = store.generate_unique_instance_uid()
        store.set_agent_identification(client_id, new_uid)
        store.add_event(
            client_id,
            description="Issue New Unique ID",
            max_events=provider_config.CONFIG.client_event_history_size,
        )
        logger.info("issued new instance uid for client %s", client_id)
        return jsonify({"status": "queued", "new_instance_uid": new_uid.hex()})

    @app.post("/api/clients/<client_id>/config")
    async def set_requested_config(client_id: str) -> ResponseReturnValue:
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
        record = store.set_requested_config(
            client_id,
            config_text=config_text,
            version=str(version) if version else None,
            apply_at=apply_at,
        )
        return jsonify(record.model_dump(mode=model_dump_mode))

    @app.post("/api/clients/<client_id>/remote-config-selection")
    async def accept_remote_config_selection(client_id: str) -> ResponseReturnValue:
        """Normalize remote-config catalog selections for one client."""
        if not provider_allows_remote_config():
            logger.warning(
                "remote config selection rejected because provider setting is disabled client_id=%s",
                client_id,
            )
            return (
                jsonify({"error": remote_config_disabled_error}),
                HTTPStatus.FORBIDDEN,
            )

        payload = await request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST

        client = store.get(client_id)
        if client is None:
            logger.warning(
                "remote config selection rejected for unknown client client_id=%s",
                client_id,
            )
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND

        try:
            selection_specs = normalize_remote_config_selection_specs(
                payload.get("files")
            )
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
    async def queue_remote_config_offer(client_id: str) -> ResponseReturnValue:
        """Validate, build, and queue a remote-config offer for a client."""
        if not provider_allows_remote_config():
            logger.warning(
                "remote config request rejected because provider setting is disabled client_id=%s",
                client_id,
            )
            return (
                jsonify({"error": remote_config_disabled_error}),
                HTTPStatus.FORBIDDEN,
            )

        payload = await request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST

        client = store.get(client_id)
        if client is None:
            logger.warning(
                "remote config request rejected for unknown client client_id=%s",
                client_id,
            )
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND
        if not client_supports_remote_config(client):
            logger.warning(
                "remote config request rejected client_id=%s capabilities=%s missing=%s",
                client_id,
                client.capabilities,
                client_remote_config_capability,
            )
            return (
                jsonify(
                    {
                        "error": "client does not accept remote config",
                        "required_capability": client_remote_config_capability,
                        "client_capabilities": client.capabilities,
                    }
                ),
                HTTPStatus.CONFLICT,
            )

        try:
            file_specs = normalize_remote_config_file_specs(payload.get("files"))
            include_hash = coerce_bool_setting(
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
        config_hash_hex = (
            remote_config.config_hash.hex() if remote_config.config_hash else ""
        )
        logger.info(
            "queued remote config offer client_id=%s files=%s payload_size_bytes=%s config_hash=%s",
            client_id,
            len(file_specs),
            len(remote_config_bytes),
            config_hash_hex or "none",
        )

        store.set_pending_remote_config(client_id, remote_config_bytes)
        record = store.enqueue_next_action(client_id, action_apply_config)
        store.add_event(
            client_id,
            description=remote_config_history_description(len(file_specs)),
            max_events=provider_config.CONFIG.client_event_history_size,
        )
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
                    "queued_action": action_apply_config,
                    "next_actions": record.next_actions,
                    "editor_validation_available": config_editor_validation_available(
                        app.extensions
                    ),
                }
            ),
            HTTPStatus.CREATED,
        )

    @app.post("/api/clients/<client_id>/connection-settings")
    async def queue_connection_settings_offer(client_id: str) -> ResponseReturnValue:
        """Validate, store, and queue one connection-settings offer for a client."""
        if not provider_allows_connection_settings():
            logger.warning(
                "connection settings request rejected because provider setting is disabled client_id=%s",
                client_id,
            )
            return (
                jsonify(
                    {
                        "error": (
                            "connection settings are disabled by provider configuration"
                        )
                    }
                ),
                HTTPStatus.FORBIDDEN,
            )

        payload = await request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST

        client = store.get(client_id)
        if client is None:
            logger.warning(
                "connection settings request rejected for unknown client client_id=%s",
                client_id,
            )
            return jsonify({"error": "client not found"}), HTTPStatus.NOT_FOUND

        connection_name = str(payload.get("connection_name") or "").strip()
        if not connection_name:
            return jsonify({"error": "connection_name is required"}), HTTPStatus.BAD_REQUEST

        try:
            connection_settings_bytes = _decode_connection_settings_payload(payload)
        except ValueError as exc:
            logger.warning(
                "connection settings request validation failed client_id=%s error=%s",
                client_id,
                exc,
            )
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

        store.set_pending_connection_settings(client_id, connection_settings_bytes)
        record = store.enqueue_next_action(client_id, action_change_connections)
        store.add_event(
            client_id,
            description=f"Queued connection settings for {connection_name}.",
            max_events=provider_config.CONFIG.client_event_history_size,
        )
        logger.info(
            "queued connection settings offer client_id=%s connection_name=%s payload_size_bytes=%s",
            client_id,
            connection_name,
            len(connection_settings_bytes),
        )
        return (
            jsonify(
                {
                    "client_id": client_id,
                    "connection_name": connection_name,
                    "payload_size_bytes": len(connection_settings_bytes),
                    "queued_action": action_change_connections,
                    "next_actions": record.next_actions,
                }
            ),
            HTTPStatus.CREATED,
        )

    @app.post("/api/test/clients/<client_id>/remote-config")
    async def build_test_remote_config(client_id: str) -> ResponseReturnValue:
        """Construct and queue a test AgentRemoteConfig payload for a client."""
        if not diagnostic_mode_enabled():
            return (
                jsonify({"error": "diagnostic mode is disabled"}),
                HTTPStatus.FORBIDDEN,
            )
        payload = await request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
        try:
            file_specs = normalize_remote_config_file_specs(payload.get("files"))
            include_hash = coerce_bool_setting(
                payload.get("include_hash", True),
                key="include_hash",
            )
            queue_action = coerce_bool_setting(
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
        record = store.set_pending_remote_config(
            client_id,
            remote_config.SerializeToString(),
        )
        if queue_action:
            record = store.enqueue_next_action(client_id, action_apply_config)
            store.add_event(
                client_id,
                description=remote_config_history_description(len(file_specs)),
                max_events=provider_config.CONFIG.client_event_history_size,
            )

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
                    "queued_action": action_apply_config if queue_action else None,
                    "next_actions": record.next_actions,
                }
            ),
            HTTPStatus.CREATED,
        )

    @app.post("/api/shutdown")
    async def shutdown_server() -> ResponseReturnValue:
        """Shutdown the server if explicitly confirmed."""
        payload = await request.get_json(silent=True) or {}
        confirm = payload.get("confirm") is True
        if not confirm:
            return jsonify({"error": "confirm is required"}), HTTPStatus.BAD_REQUEST
        logger.warning("shutdown requested via API")
        await close_websockets()
        asyncio.create_task(shutdown_after_response())
        return jsonify({"status": "shutting down"})
