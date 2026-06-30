"""Helpers for tracking and serializing outbound remote-config status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.agent_remote_config import calculate_agent_config_map_hash

from opamp_consumer.proto import opamp_pb2

REMOTE_CONFIG_STATUS_UNSET = opamp_pb2.RemoteConfigStatuses.RemoteConfigStatuses_UNSET


@dataclass(frozen=True)
class RemoteConfigStatusSnapshot:
    """Immutable remote-config status snapshot stored on the client."""

    last_remote_config_hash: bytes = b""
    status: int = REMOTE_CONFIG_STATUS_UNSET
    error_message: str = ""

    def is_meaningful(self) -> bool:
        """Return whether this snapshot contains reportable status content."""
        return bool(
            self.last_remote_config_hash
            or self.status != REMOTE_CONFIG_STATUS_UNSET
            or self.error_message
        )


def resolve_remote_config_hash(remote_config: opamp_pb2.AgentRemoteConfig) -> bytes:
    """Return the explicit config hash or calculate one from the config map."""
    if remote_config.config_hash:
        return bytes(remote_config.config_hash)
    return calculate_agent_config_map_hash(remote_config.config)


def build_remote_config_status_snapshot(
    *,
    remote_config: opamp_pb2.AgentRemoteConfig,
    status: int,
    error_message: str = "",
) -> RemoteConfigStatusSnapshot:
    """Construct a normalized status snapshot for a remote-config payload."""
    return RemoteConfigStatusSnapshot(
        last_remote_config_hash=resolve_remote_config_hash(remote_config),
        status=int(status),
        error_message=str(error_message or "").strip(),
    )


def build_remote_config_status_message(
    snapshot: RemoteConfigStatusSnapshot,
) -> opamp_pb2.RemoteConfigStatus | None:
    """Convert a stored snapshot into a protobuf message when needed."""
    if not snapshot.is_meaningful():
        return None
    return opamp_pb2.RemoteConfigStatus(
        last_remote_config_hash=snapshot.last_remote_config_hash,
        status=snapshot.status,
        error_message=snapshot.error_message,
    )


def remote_config_status_snapshot_from_message(
    message: opamp_pb2.RemoteConfigStatus,
) -> RemoteConfigStatusSnapshot:
    """Copy a protobuf status message into the immutable snapshot form."""
    return RemoteConfigStatusSnapshot(
        last_remote_config_hash=bytes(message.last_remote_config_hash),
        status=int(message.status),
        error_message=str(message.error_message or "").strip(),
    )


def set_remote_config_status(
    *,
    data: Any,
    remote_config: opamp_pb2.AgentRemoteConfig,
    status: int,
    error_message: str = "",
) -> RemoteConfigStatusSnapshot:
    """Persist the current remote-config status snapshot on client data."""
    snapshot = build_remote_config_status_snapshot(
        remote_config=remote_config,
        status=status,
        error_message=error_message,
    )
    data.remote_config_status = snapshot
    return snapshot


def populate_agent_to_server_remote_config_status(
    *,
    data: Any,
    msg: opamp_pb2.AgentToServer,
) -> opamp_pb2.AgentToServer:
    """Populate `remote_config_status` only when it changed since the last send."""
    snapshot = getattr(data, "remote_config_status", RemoteConfigStatusSnapshot())
    last_sent = getattr(data, "last_sent_remote_config_status", None)
    if not snapshot.is_meaningful() or snapshot == last_sent:
        return msg

    remote_config_status = build_remote_config_status_message(snapshot)
    if remote_config_status is not None:
        msg.remote_config_status.CopyFrom(remote_config_status)
    return msg


def mark_remote_config_status_sent(
    *,
    data: Any,
    msg: opamp_pb2.AgentToServer | None,
) -> None:
    """Record the last successfully sent remote-config status snapshot."""
    if msg is None or not msg.HasField("remote_config_status"):
        return
    data.last_sent_remote_config_status = remote_config_status_snapshot_from_message(
        msg.remote_config_status
    )
