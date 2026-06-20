"""Settings route registration for provider app."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from quart import Quart, Response, jsonify, request

from shared.opamp_config import UTF8_ENCODING


def register_settings_routes(  # noqa: PLR0913
    app: Quart,
    *,
    provider_config: Any,
    store: Any,
    logger: Any,
    persistence_tracker: Any,
    diagnostic_mode_enabled: Any,
    state_snapshot_file_count: Any,
    tls_certificate_expiry_metadata: Any,
    record_snapshot_status: Any,
    coerce_bool_setting: Any,
    save_state_snapshot_func: Any,
    prune_snapshot_files_func: Any,
) -> None:
    """Register provider settings-related routes."""

    @app.get("/api/settings/comms")
    async def get_comms_settings() -> Response:
        """Get communication threshold settings."""
        state_prefix = pathlib.Path(provider_config.CONFIG.state_persistence.state_file_prefix)
        payload = {
            "delayed_comms_seconds": provider_config.CONFIG.delayed_comms_seconds,
            "significant_comms_seconds": provider_config.CONFIG.significant_comms_seconds,
            "minutes_keep_disconnected": provider_config.CONFIG.minutes_keep_disconnected,
            "client_event_history_size": provider_config.CONFIG.client_event_history_size,
            "human_in_loop_approval": provider_config.CONFIG.human_in_loop_approval,
            "state_persistence_enabled": (
                provider_config.CONFIG.state_persistence.enabled is True
            ),
            "opamp_use_authorization": provider_config.CONFIG.opamp_use_authorization,
            "state_save_folder": str(state_prefix.parent),
            "retention_count": int(
                provider_config.CONFIG.state_persistence.retention_count
            ),
            "state_snapshot_file_count": state_snapshot_file_count(),
            "autosave_interval_seconds_since_change": int(
                provider_config.CONFIG.state_persistence.autosave_interval_seconds_since_change
            ),
        }
        payload.update(tls_certificate_expiry_metadata())
        return jsonify(payload)

    @app.get("/api/settings/diagnostic")
    async def get_diagnostic_settings() -> Response:
        """Return diagnostic-mode status used by UI feature gating."""
        return jsonify(
            {
                "diagnostic_enabled": diagnostic_mode_enabled(),
                "state_persistence_enabled": provider_config.CONFIG.state_persistence.enabled
                is True,
                "state_persistence": persistence_tracker.status,
            }
        )

    @app.post("/api/settings/state/save")
    async def save_state_snapshot_now() -> Response:
        """Force an immediate persisted-state snapshot save."""
        persistence = provider_config.CONFIG.state_persistence
        if persistence.enabled is not True:
            record_snapshot_status(
                status="skipped",
                path=None,
                reason="manual_ui_trigger_disabled",
            )
            return (
                jsonify({"error": "state persistence is disabled"}),
                HTTPStatus.BAD_REQUEST,
            )
        now = datetime.now(timezone.utc)
        try:
            path = save_state_snapshot_func(
                store=store,
                persistence=persistence,
                reason="manual_ui_trigger",
                logger=logger,
                now=now,
            )
            snapshot_path = str(path) if path is not None else None
            record_snapshot_status(
                status="saved",
                path=snapshot_path,
                reason="manual_ui_trigger",
                at=now,
            )
            return jsonify(
                {
                    "status": "saved",
                    "snapshot_path": snapshot_path,
                    "saved_at_utc": now.replace(microsecond=0).isoformat(),
                }
            )
        except Exception as exc:
            logger.exception(
                "manual state snapshot save failed",
                exc_info=exc,
            )
            record_snapshot_status(
                status="failed",
                path=None,
                reason="manual_ui_trigger",
                at=now,
            )
            return (
                jsonify({"error": "failed to save provider state snapshot"}),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    @app.get("/api/settings/server-opamp-config")
    async def get_server_opamp_config() -> Response:
        """Return provider config file content for diagnostic UI view."""
        if not diagnostic_mode_enabled():
            return (
                jsonify({"error": "diagnostic mode is disabled"}),
                HTTPStatus.FORBIDDEN,
            )

        config_path = provider_config.get_effective_config_path().resolve()
        if not config_path.exists() or not config_path.is_file():
            return (
                jsonify({"error": "provider config file not found"}),
                HTTPStatus.NOT_FOUND,
            )
        if config_path.suffix.lower() != ".json":
            return (
                jsonify({"error": "provider config path must be a JSON file"}),
                HTTPStatus.BAD_REQUEST,
            )

        try:
            config_raw = config_path.read_text(encoding=UTF8_ENCODING)
            config_json = json.loads(config_raw)
        except Exception as exc:
            logger.exception("failed to read provider config file", exc_info=exc)
            return (
                jsonify({"error": "failed to read provider config file"}),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return jsonify(
            {
                "diagnostic_enabled": True,
                "config_path": str(config_path),
                "config_text": json.dumps(config_json, indent=2),
            }
        )

    @app.put("/api/settings/comms")
    async def update_comms_settings() -> Response:
        """Update communication threshold settings."""
        payload = await request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
        try:
            delayed = int(
                payload.get(
                    "delayed_comms_seconds", provider_config.CONFIG.delayed_comms_seconds
                )
            )
            significant = int(
                payload.get(
                    "significant_comms_seconds",
                    provider_config.CONFIG.significant_comms_seconds,
                )
            )
            minutes_keep_disconnected = int(
                payload.get(
                    "minutes_keep_disconnected",
                    provider_config.CONFIG.minutes_keep_disconnected,
                )
            )
            client_event_history_size = int(
                payload.get(
                    "client_event_history_size",
                    provider_config.CONFIG.client_event_history_size,
                )
            )
            human_in_loop_approval = coerce_bool_setting(
                payload.get(
                    "human_in_loop_approval",
                    provider_config.CONFIG.human_in_loop_approval,
                ),
                key="human_in_loop_approval",
            )
            state_persistence_enabled = coerce_bool_setting(
                payload.get(
                    "state_persistence_enabled",
                    provider_config.CONFIG.state_persistence.enabled,
                ),
                key="state_persistence_enabled",
            )
            state_save_folder = str(
                payload.get(
                    "state_save_folder",
                    str(
                        pathlib.Path(
                            provider_config.CONFIG.state_persistence.state_file_prefix
                        ).parent
                    ),
                )
            ).strip()
            autosave_interval_seconds_since_change = int(
                payload.get(
                    "autosave_interval_seconds_since_change",
                    provider_config.CONFIG.state_persistence.autosave_interval_seconds_since_change,
                )
            )
            retention_count = int(
                payload.get(
                    "retention_count",
                    provider_config.CONFIG.state_persistence.retention_count,
                )
            )
        except (TypeError, ValueError):
            return (
                jsonify(
                    {
                        "error": (
                            "thresholds must be integers, "
                            "human_in_loop_approval/state_persistence_enabled must be boolean, and "
                            "autosave_interval_seconds_since_change/retention_count must be integer"
                        )
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )
        if (
            delayed <= 0
            or significant <= 0
            or minutes_keep_disconnected <= 0
            or client_event_history_size <= 0
        ):
            return jsonify({"error": "thresholds must be positive"}), HTTPStatus.BAD_REQUEST
        if autosave_interval_seconds_since_change <= 0:
            return (
                jsonify(
                    {
                        "error": (
                            "autosave_interval_seconds_since_change must be a positive integer"
                        )
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )
        if retention_count <= 0:
            return (
                jsonify({"error": "retention_count must be a positive integer"}),
                HTTPStatus.BAD_REQUEST,
            )
        if not state_save_folder:
            return (
                jsonify({"error": "state_save_folder must be a non-empty string"}),
                HTTPStatus.BAD_REQUEST,
            )
        if delayed >= significant:
            return (
                jsonify({"error": "significant must be greater than delayed"}),
                HTTPStatus.BAD_REQUEST,
            )
        try:
            config = provider_config.update_comms_thresholds(
                delayed=delayed,
                significant=significant,
                minutes_keep_disconnected=minutes_keep_disconnected,
                client_event_history_size=client_event_history_size,
                human_in_loop_approval=human_in_loop_approval,
                state_persistence_enabled=state_persistence_enabled,
                state_save_folder=state_save_folder,
                retention_count=retention_count,
                autosave_interval_seconds_since_change=(
                    autosave_interval_seconds_since_change
                ),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
        try:
            if retention_count < state_snapshot_file_count():
                prune_snapshot_files_func(
                    state_file_prefix=config.state_persistence.state_file_prefix,
                    retention_count=config.state_persistence.retention_count,
                    logger=logger,
                )
        except Exception as exc:
            logger.warning(
                "failed pruning snapshots after retention update",
                exc_info=exc,
            )
        try:
            provider_config.persist_provider_config(config)
        except Exception as exc:
            logger.exception("failed to persist provider settings", exc_info=exc)
            return (
                jsonify({"error": "failed to persist provider settings to opamp.json"}),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        return jsonify(
            {
                "delayed_comms_seconds": config.delayed_comms_seconds,
                "significant_comms_seconds": config.significant_comms_seconds,
                "minutes_keep_disconnected": config.minutes_keep_disconnected,
                "client_event_history_size": config.client_event_history_size,
                "human_in_loop_approval": config.human_in_loop_approval,
                "state_persistence_enabled": config.state_persistence.enabled is True,
                "opamp_use_authorization": config.opamp_use_authorization,
                "state_save_folder": str(
                    pathlib.Path(config.state_persistence.state_file_prefix).parent
                ),
                "retention_count": int(config.state_persistence.retention_count),
                "state_snapshot_file_count": state_snapshot_file_count(),
                "autosave_interval_seconds_since_change": int(
                    config.state_persistence.autosave_interval_seconds_since_change
                ),
            }
        )

    @app.get("/api/settings/client")
    async def get_client_settings() -> Response:
        """Get client global settings."""
        return jsonify(
            {
                "default_heartbeat_frequency": store.get_default_heartbeat_frequency(),
            }
        )

    @app.put("/api/settings/client")
    async def update_client_settings() -> Response:
        """Update client global settings and apply to all known clients."""
        payload = await request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "payload is required"}), HTTPStatus.BAD_REQUEST
        try:
            default_heartbeat_frequency = int(
                payload.get(
                    "default_heartbeat_frequency",
                    store.get_default_heartbeat_frequency(),
                )
            )
        except (TypeError, ValueError):
            return (
                jsonify({"error": "default_heartbeat_frequency must be an integer"}),
                HTTPStatus.BAD_REQUEST,
            )
        if default_heartbeat_frequency <= 0:
            return (
                jsonify({"error": "default_heartbeat_frequency must be positive"}),
                HTTPStatus.BAD_REQUEST,
            )
        config = provider_config.update_default_heartbeat_frequency(
            default_heartbeat_frequency=default_heartbeat_frequency
        )
        try:
            provider_config.persist_provider_config(config)
        except Exception as exc:
            logger.exception("failed to persist provider settings", exc_info=exc)
            return (
                jsonify({"error": "failed to persist provider settings to opamp.json"}),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        updated_clients = store.set_default_heartbeat_frequency(
            default_heartbeat_frequency,
            max_events=provider_config.CONFIG.client_event_history_size,
        )
        return jsonify(
            {
                "default_heartbeat_frequency": store.get_default_heartbeat_frequency(),
                "updated_clients": updated_clients,
            }
        )
