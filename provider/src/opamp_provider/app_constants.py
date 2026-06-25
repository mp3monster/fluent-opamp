"""Shared constants and UI help metadata for the provider app."""

from __future__ import annotations

MODEL_DUMP_MODE = "json"  # Pydantic model_dump mode used for API JSON payloads.
AGENT_DESCRIPTION_CACHE_SIZE = 512  # LRU size for parsed AgentDescription text payloads.
AGENT_DESCRIPTION_ATTRIBUTE_SPLIT_PATTERN = r"[,\s]+"  # Split pattern for host.ip lists.
BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "on"}  # Accepted true-like query values.
BOOLEAN_FALSE_VALUES = {"0", "false", "no", "off"}  # Accepted false-like query values.
ERROR_INVALID_BOOLEAN_FILTER = (
    "invalid boolean query parameter '%s'; expected one of: true, false, "
    "1, 0, yes, no, on, off"
)  # Validation message for malformed boolean query values.

GLOBAL_SETTINGS_HELP: dict[str, dict[str, str]] = {
    "delayed_comms_seconds": {
        "label": "Delayed Communications Threshold (seconds)",
        "tooltip": (
            "Seconds before a client is marked delayed (amber). "
            "This overrides the config file value."
        ),
    },
    "significant_comms_seconds": {
        "label": "Significant Communications Threshold (seconds)",
        "tooltip": (
            "Seconds before a client is marked late (red). "
            "Must be greater than delayed_comms_seconds. "
            "This overrides the config file value."
        ),
    },
    "minutes_keep_disconnected": {
        "label": "Disconnected Retention Window (minutes)",
        "tooltip": (
            "Minutes to keep disconnected clients in provider state before purge. "
            "This overrides the config file value."
        ),
    },
    "client_event_history_size": {
        "label": "Client Event History Size",
        "tooltip": (
            "Maximum number of recent per-client events retained by the provider. "
            "Older events are dropped when this limit is exceeded."
        ),
    },
    "human_in_loop_approval": {
        "label": "Human In Loop Approval",
        "tooltip": (
            "When enabled, unknown agents are staged for manual review and must "
            "be approved before normal processing continues."
        ),
    },
    "state_persistence_enabled": {
        "label": "Enable State Persistence",
        "tooltip": (
            "When enabled, provider state snapshots can be saved/restored using "
            "state persistence settings."
        ),
    },
    "state_save_folder": {
        "label": "State Save Folder",
        "tooltip": (
            "Folder path where provider state snapshots are written and restored from."
        ),
    },
    "retention_count": {
        "label": "State Snapshot Retention Count",
        "tooltip": "Number of latest provider state snapshot files to retain.",
    },
    "autosave_interval_seconds_since_change": {
        "label": "Autosave Interval Since Change (seconds)",
        "tooltip": (
            "Seconds between autosaves for non-heartbeat OpAMP state changes."
        ),
    },
    "default_heartbeat_frequency": {
        "label": "Default Heartbeat Frequency (seconds)",
        "tooltip": (
            "Default heartbeat interval in seconds applied to clients when globally updated."
        ),
    },
}
