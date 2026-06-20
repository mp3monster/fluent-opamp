"""Persistence and autosave helpers for the provider app."""

from __future__ import annotations

import os
import signal
from datetime import datetime, timezone
from typing import Any

from opamp_provider.proto import opamp_pb2
from opamp_provider.state_persistence import list_snapshot_files, save_state_snapshot


class PersistenceTracker:
    """Track provider restore/save status and autosave eligibility state."""

    def __init__(self) -> None:
        self._last_autosave_eligible_change_at: datetime | None = None
        self._status: dict[str, object] = {
            "restore_status": "not_requested",
            "restore_detail": "",
            "last_save_status": "not_run",
            "last_save_path": None,
            "last_save_reason": None,
            "last_save_at": None,
        }

    @property
    def status(self) -> dict[str, object]:
        """Return a copy of current persistence status metadata."""
        return dict(self._status)

    def set_state_restore_status(self, status: str, detail: str = "") -> None:
        """Record persisted-state restore status for diagnostics and logs."""
        self._status["restore_status"] = str(status).strip() or "unknown"
        self._status["restore_detail"] = str(detail or "")

    def record_snapshot_status(
        self,
        *,
        status: str,
        path: str | None,
        reason: str,
        at: datetime | None = None,
    ) -> None:
        """Record latest snapshot save status for diagnostics."""
        self._status["last_save_status"] = str(status).strip() or "unknown"
        self._status["last_save_path"] = path
        self._status["last_save_reason"] = reason
        self._status["last_save_at"] = (
            (at or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
        )

    def is_heartbeat_only_message(self, agent_msg: opamp_pb2.AgentToServer) -> bool:
        """Return whether AgentToServer payload only contains instance_uid/sequence_num."""
        field_names = {descriptor.name for descriptor, _value in agent_msg.ListFields()}
        if not field_names:
            return False
        return field_names.issubset({"instance_uid", "sequence_num"})

    def save_state_snapshot(
        self,
        *,
        reason: str,
        store: Any,
        persistence: Any,
        logger: Any,
    ) -> None:
        """Save one persisted-state snapshot if persistence is enabled."""
        if persistence.enabled is not True:
            return
        now = datetime.now(timezone.utc)
        try:
            path = save_state_snapshot(
                store=store,
                persistence=persistence,
                reason=reason,
                logger=logger,
                now=now,
            )
            self.record_snapshot_status(
                status="saved",
                path=str(path) if path is not None else None,
                reason=reason,
                at=now,
            )
        except Exception as exc:
            logger.exception("state snapshot save failed reason=%s", reason, exc_info=exc)
            self.record_snapshot_status(
                status="failed",
                path=None,
                reason=reason,
                at=now,
            )

    def note_non_heartbeat_state_change_and_maybe_autosave(
        self,
        *,
        store: Any,
        persistence: Any,
        logger: Any,
    ) -> None:
        """Track non-heartbeat state change timing and run autosave checks."""
        now = datetime.now(timezone.utc)
        if self._last_autosave_eligible_change_at is None:
            self._last_autosave_eligible_change_at = now

        if persistence.enabled is not True:
            return
        interval = max(1, int(persistence.autosave_interval_seconds_since_change))
        elapsed = (now - self._last_autosave_eligible_change_at).total_seconds()
        if elapsed < interval:
            return
        self.save_state_snapshot(
            reason="autosave_non_heartbeat_opamp",
            store=store,
            persistence=persistence,
            logger=logger,
        )
        self._last_autosave_eligible_change_at = None

    def state_snapshot_file_count(self, *, state_file_prefix: str, logger: Any) -> int:
        """Return count of snapshot files currently present for configured prefix."""
        try:
            return len(list_snapshot_files(state_file_prefix))
        except Exception as exc:
            logger.warning("failed counting state snapshot files", exc_info=exc)
            return 0


def request_process_shutdown() -> None:
    """Trigger a process shutdown via SIGINT (fallback to immediate exit)."""
    try:
        os.kill(os.getpid(), signal.SIGINT)
    except Exception:
        os._exit(0)
