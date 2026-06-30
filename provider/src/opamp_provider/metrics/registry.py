"""Prometheus-compatible provider metrics and retained gauge series."""

from __future__ import annotations

import math
import threading
import time
from collections import Counter, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from opamp_provider import config as provider_config

if TYPE_CHECKING:
    from opamp_provider.state import ClientStore

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
BACKEND_JSON_FILE = "json_file"
UNKNOWN_LABEL_VALUE = "unknown"
TRUE_LABEL_VALUE = "true"
FALSE_LABEL_VALUE = "false"
DEFAULT_LAST_CHECKPOINT_TIMESTAMP = 0.0
HEARTBEAT_EXPECTED_BUCKETS = (
    5.0,
    10.0,
    15.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1800.0,
    3600.0,
)
HEARTBEAT_LAG_BUCKETS = (
    0.0,
    1.0,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1800.0,
)
PERSISTENCE_WRITE_BUCKETS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
)


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def _graph_retention_minutes() -> int:
    """Return configured retained graph history length in whole minutes."""
    try:
        return max(0, int(provider_config.CONFIG.metrics.graph_history_minutes))
    except Exception:
        return 0


def _metrics_enabled() -> bool:
    """Return whether provider metrics endpoints and runtime recording are enabled."""
    try:
        return provider_config.CONFIG.metrics.enabled is True
    except Exception:
        return False


def _normalize_bool_label(value: Any) -> str:
    """Return normalized boolean label text for stored record values."""
    if isinstance(value, bool):
        return TRUE_LABEL_VALUE if value else FALSE_LABEL_VALUE
    normalized = str(value or "").strip().lower()
    if normalized == TRUE_LABEL_VALUE:
        return TRUE_LABEL_VALUE
    if normalized == FALSE_LABEL_VALUE:
        return FALSE_LABEL_VALUE
    return UNKNOWN_LABEL_VALUE


def _normalize_label_value(value: Any) -> str:
    """Return a non-empty Prometheus label value."""
    normalized = str(value or "").strip()
    return normalized or UNKNOWN_LABEL_VALUE


def _format_metric_value(value: float) -> str:
    """Return a Prometheus text-format numeric representation."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    text = f"{float(value):.15g}"
    return "0" if text == "-0" else text


def _escape_label_value(value: str) -> str:
    """Escape a Prometheus label value."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _label_key(labels: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Return a stable series key from labels."""
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _labels_from_key(key: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """Convert a stable series key back into a mutable labels mapping."""
    return {name: value for name, value in key}


@dataclass(frozen=True)
class MetricDefinition:
    """Static metric metadata used for text rendering and graph responses."""

    name: str
    metric_type: str
    help_text: str
    label_names: tuple[str, ...] = ()
    graphable: bool = False
    buckets: tuple[float, ...] = ()


@dataclass
class HistogramAccumulator:
    """Cumulative histogram storage for runtime-observed metrics."""

    buckets: tuple[float, ...]
    cumulative_bucket_counts: list[int] = field(default_factory=list)
    count: int = 0
    total: float = 0.0

    def __post_init__(self) -> None:
        if not self.cumulative_bucket_counts:
            self.cumulative_bucket_counts = [0 for _ in self.buckets]

    def observe(self, value: float) -> None:
        """Add one observed value into the histogram."""
        observed = float(value)
        self.count += 1
        self.total += observed
        for index, upper_bound in enumerate(self.buckets):
            if observed <= upper_bound:
                self.cumulative_bucket_counts[index] += 1


@dataclass(frozen=True)
class MetricSample:
    """One metric sample value and label set."""

    labels: dict[str, str]
    value: float


def _build_metric_definitions() -> dict[str, MetricDefinition]:
    """Return the provider metric catalog in exposition order."""
    definitions = (
        MetricDefinition(
            name="opamp_provider_clients_total",
            metric_type="gauge",
            help_text="Current number of provider-side client records.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_clients_connected_total",
            metric_type="gauge",
            help_text="Current number of tracked clients that have not reported disconnect.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_clients_disconnected_total",
            metric_type="gauge",
            help_text="Current number of tracked clients marked disconnected.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_pending_approvals_total",
            metric_type="gauge",
            help_text="Current number of clients waiting for manual approval.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_blocked_agents_total",
            metric_type="gauge",
            help_text="Current number of blocked agent identities.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_clients_by_channel_total",
            metric_type="gauge",
            help_text="Current number of tracked clients grouped by their most recent transport channel.",
            label_names=("channel",),
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_clients_by_auth_mechanism_total",
            metric_type="gauge",
            help_text="Current number of tracked clients grouped by provider-side authentication mechanism.",
            label_names=("auth_mechanism",),
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_client_health_total",
            metric_type="gauge",
            help_text="Current number of tracked clients grouped by reported top-level health state.",
            label_names=("healthy", "status"),
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_component_health_total",
            metric_type="gauge",
            help_text="Current number of reported client components grouped by component name and health state.",
            label_names=("component", "healthy"),
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_heartbeat_expected_seconds",
            metric_type="histogram",
            help_text="Distribution of configured per-client heartbeat intervals in seconds.",
            buckets=HEARTBEAT_EXPECTED_BUCKETS,
        ),
        MetricDefinition(
            name="opamp_provider_heartbeat_lag_seconds",
            metric_type="histogram",
            help_text="Distribution of per-client heartbeat lag in seconds, clamped to zero when the client is not late.",
            buckets=HEARTBEAT_LAG_BUCKETS,
        ),
        MetricDefinition(
            name="opamp_provider_commands_queued_total",
            metric_type="counter",
            help_text="Total number of commands queued by the provider.",
            label_names=("classifier", "action"),
        ),
        MetricDefinition(
            name="opamp_provider_commands_sent_total",
            metric_type="counter",
            help_text="Total number of queued commands marked as sent to clients.",
            label_names=("classifier", "action"),
        ),
        MetricDefinition(
            name="opamp_provider_commands_unsent_total",
            metric_type="gauge",
            help_text="Current number of queued commands that have not yet been marked sent.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_client_events_retained_total",
            metric_type="gauge",
            help_text="Current number of retained client event-history entries across all records.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_persistence_mutations_total",
            metric_type="counter",
            help_text="Total number of successful provider persistence mutations.",
            label_names=("backend", "op"),
        ),
        MetricDefinition(
            name="opamp_provider_persistence_write_seconds",
            metric_type="histogram",
            help_text="Duration of provider persistence write-like operations in seconds.",
            label_names=("backend", "operation"),
            buckets=PERSISTENCE_WRITE_BUCKETS,
        ),
        MetricDefinition(
            name="opamp_provider_persistence_failures_total",
            metric_type="counter",
            help_text="Total number of provider persistence operation failures.",
            label_names=("backend", "operation"),
        ),
        MetricDefinition(
            name="opamp_provider_restore_operations_total",
            metric_type="counter",
            help_text="Total number of provider restore operations grouped by result.",
            label_names=("backend", "result"),
        ),
        MetricDefinition(
            name="opamp_provider_last_checkpoint_timestamp_seconds",
            metric_type="gauge",
            help_text="Unix timestamp of the most recent successfully saved or restored provider checkpoint.",
            graphable=True,
        ),
        MetricDefinition(
            name="opamp_provider_force_resync_queued_total",
            metric_type="counter",
            help_text="Total number of force-resync commands queued when the provider detected missing full-state coverage.",
        ),
        MetricDefinition(
            name="opamp_provider_sequence_gap_total",
            metric_type="counter",
            help_text="Total number of non-sequential AgentToServer message sequences detected after initial contact.",
        ),
    )
    return {definition.name: definition for definition in definitions}


class ProviderMetricsRegistry:
    """Runtime metrics recorder and Prometheus text exporter."""

    def __init__(self) -> None:
        self._definitions = _build_metric_definitions()
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = {}
        self._histograms: dict[
            str, dict[tuple[tuple[str, str], ...], HistogramAccumulator]
        ] = {}
        self._runtime_gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = {
            "opamp_provider_last_checkpoint_timestamp_seconds": {
                (): DEFAULT_LAST_CHECKPOINT_TIMESTAMP
            }
        }
        self._gauge_series: dict[
            str, dict[tuple[tuple[str, str], ...], deque[tuple[float, float]]]
        ] = {}

    def reset(self) -> None:
        """Reset all runtime counters, histograms, gauges, and retained series."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._runtime_gauges = {
                "opamp_provider_last_checkpoint_timestamp_seconds": {
                    (): DEFAULT_LAST_CHECKPOINT_TIMESTAMP
                }
            }
            self._gauge_series.clear()

    def increment_counter(
        self,
        metric_name: str,
        *,
        labels: Mapping[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        """Increment one runtime counter when metrics are enabled."""
        if _metrics_enabled() is not True:
            return
        label_key = _label_key(labels or {})
        with self._lock:
            metric = self._counters.setdefault(metric_name, {})
            metric[label_key] = metric.get(label_key, 0.0) + float(amount)

    def observe_histogram(
        self,
        metric_name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        """Observe one runtime histogram sample when metrics are enabled."""
        if _metrics_enabled() is not True:
            return
        definition = self._definitions[metric_name]
        label_key = _label_key(labels or {})
        with self._lock:
            metric = self._histograms.setdefault(metric_name, {})
            accumulator = metric.get(label_key)
            if accumulator is None:
                accumulator = HistogramAccumulator(definition.buckets)
                metric[label_key] = accumulator
            accumulator.observe(float(value))

    def set_runtime_gauge(
        self,
        metric_name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        """Set one runtime gauge value when metrics are enabled."""
        if _metrics_enabled() is not True:
            return
        label_key = _label_key(labels or {})
        with self._lock:
            metric = self._runtime_gauges.setdefault(metric_name, {})
            metric[label_key] = float(value)

    def record_force_resync_queued(self, *, amount: int = 1) -> None:
        """Record one or more queued force-resync commands."""
        if amount <= 0:
            return
        self.increment_counter(
            "opamp_provider_force_resync_queued_total",
            amount=float(amount),
        )
        self.increment_counter(
            "opamp_provider_commands_queued_total",
            labels={"classifier": "command", "action": "forceresync"},
            amount=float(amount),
        )

    def record_sequence_gap(self, *, amount: int = 1) -> None:
        """Record one or more detected message-sequence gaps."""
        if amount <= 0:
            return
        self.increment_counter(
            "opamp_provider_sequence_gap_total",
            amount=float(amount),
        )

    def capture_gauge_series(
        self,
        store: ClientStore,
        *,
        now: datetime | None = None,
    ) -> None:
        """Capture graphable gauge samples into retained in-memory series storage."""
        if _metrics_enabled() is not True:
            return
        retention_minutes = _graph_retention_minutes()
        if retention_minutes <= 0:
            return
        captured_at = now or _utc_now()
        gauge_samples = self._current_gauge_samples(store=store, now=captured_at)
        self._record_gauge_series(gauge_samples=gauge_samples, captured_at=captured_at)

    def render_prometheus_text(
        self,
        store: ClientStore,
        *,
        now: datetime | None = None,
    ) -> str:
        """Render all enabled provider metrics in Prometheus text format."""
        captured_at = now or _utc_now()
        gauge_samples = self._current_gauge_samples(store=store, now=captured_at)
        self.capture_gauge_series(store, now=captured_at)
        runtime_counters, runtime_histograms, runtime_gauges = self._runtime_snapshots()
        snapshot_histograms = self._snapshot_histogram_samples(
            store=store,
            now=captured_at,
        )

        lines: list[str] = []
        for definition in self._definitions.values():
            lines.append(f"# HELP {definition.name} {definition.help_text}")
            lines.append(f"# TYPE {definition.name} {definition.metric_type}")
            if definition.metric_type == "gauge":
                samples = list(gauge_samples.get(definition.name, []))
                if not samples:
                    for label_key, value in runtime_gauges.get(
                        definition.name, {}
                    ).items():
                        samples.append(
                            MetricSample(
                                labels=_labels_from_key(label_key),
                                value=value,
                            )
                        )
                for sample in samples:
                    lines.append(
                        self._sample_line(
                            definition.name,
                            labels=sample.labels,
                            value=sample.value,
                        )
                    )
                continue
            if definition.metric_type == "counter":
                for label_key, value in runtime_counters.get(definition.name, {}).items():
                    lines.append(
                        self._sample_line(
                            definition.name,
                            labels=_labels_from_key(label_key),
                            value=value,
                        )
                    )
                continue
            if definition.metric_type == "histogram":
                if definition.name in snapshot_histograms:
                    counts, count, total = snapshot_histograms[definition.name]
                    lines.extend(
                        self._histogram_lines(
                            definition=definition,
                            labels={},
                            bucket_counts=counts,
                            count=count,
                            total=total,
                        )
                    )
                    continue
                for label_key, accumulator in runtime_histograms.get(
                    definition.name, {}
                ).items():
                    lines.extend(
                        self._histogram_lines(
                            definition=definition,
                            labels=_labels_from_key(label_key),
                            bucket_counts=tuple(accumulator.cumulative_bucket_counts),
                            count=accumulator.count,
                            total=accumulator.total,
                        )
                    )
        return "\n".join(lines) + "\n"

    def build_graph_payload(
        self,
        store: ClientStore,
        *,
        metric_names: Iterable[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return a JSON-serializable payload for internal gauge graph consumers."""
        captured_at = now or _utc_now()
        requested = {
            name
            for name in (metric_names or [])
            if name in self._definitions and self._definitions[name].graphable
        }
        graphable_names = [
            definition.name
            for definition in self._definitions.values()
            if definition.graphable and (not requested or definition.name in requested)
        ]
        gauge_samples = self._current_gauge_samples(store=store, now=captured_at)
        self.capture_gauge_series(store, now=captured_at)
        series_snapshot = self._series_snapshot(selected_names=set(graphable_names))
        metrics_payload: list[dict[str, Any]] = []
        retention_minutes = _graph_retention_minutes()
        for metric_name in graphable_names:
            definition = self._definitions[metric_name]
            current_payload = [
                {
                    "labels": dict(sample.labels),
                    "value": sample.value,
                }
                for sample in gauge_samples.get(metric_name, [])
            ]
            series_payload = []
            for label_key, points in series_snapshot.get(metric_name, {}).items():
                series_payload.append(
                    {
                        "labels": _labels_from_key(label_key),
                        "points": [
                            {
                                "timestamp": datetime.fromtimestamp(
                                    ts, tz=timezone.utc
                                ).isoformat(),
                                "value": value,
                            }
                            for ts, value in points
                        ],
                    }
                )
            metrics_payload.append(
                {
                    "name": metric_name,
                    "type": definition.metric_type,
                    "help": definition.help_text,
                    "labels": list(definition.label_names),
                    "current": current_payload,
                    "series": series_payload if retention_minutes > 0 else [],
                }
            )
        return {
            "enabled": _metrics_enabled(),
            "retention_minutes": retention_minutes,
            "generated_at": captured_at.isoformat(),
            "metrics": metrics_payload,
        }

    def _runtime_snapshots(
        self,
    ) -> tuple[
        dict[str, dict[tuple[tuple[str, str], ...], float]],
        dict[str, dict[tuple[tuple[str, str], ...], HistogramAccumulator]],
        dict[str, dict[tuple[tuple[str, str], ...], float]],
    ]:
        """Return thread-safe copies of runtime metric stores."""
        with self._lock:
            counters = {
                name: dict(values)
                for name, values in self._counters.items()
            }
            histograms = {
                name: {
                    label_key: HistogramAccumulator(
                        accumulator.buckets,
                        cumulative_bucket_counts=list(
                            accumulator.cumulative_bucket_counts
                        ),
                        count=accumulator.count,
                        total=accumulator.total,
                    )
                    for label_key, accumulator in values.items()
                }
                for name, values in self._histograms.items()
            }
            gauges = {
                name: dict(values)
                for name, values in self._runtime_gauges.items()
            }
        return counters, histograms, gauges

    def _series_snapshot(
        self,
        *,
        selected_names: set[str],
    ) -> dict[str, dict[tuple[tuple[str, str], ...], list[tuple[float, float]]]]:
        """Return a filtered copy of retained gauge series."""
        retention_minutes = _graph_retention_minutes()
        if retention_minutes <= 0:
            return {}
        cutoff = time.time() - (retention_minutes * 60)
        with self._lock:
            snapshot: dict[
                str, dict[tuple[tuple[str, str], ...], list[tuple[float, float]]]
            ] = {}
            for metric_name, series_by_label in self._gauge_series.items():
                if metric_name not in selected_names:
                    continue
                for label_key, points in series_by_label.items():
                    while points and points[0][0] < cutoff:
                        points.popleft()
                    if not points:
                        continue
                    snapshot.setdefault(metric_name, {})[label_key] = list(points)
            return snapshot

    def _record_gauge_series(
        self,
        *,
        gauge_samples: dict[str, list[MetricSample]],
        captured_at: datetime,
    ) -> None:
        """Retain the latest graphable gauge samples in a bounded time window."""
        retention_minutes = _graph_retention_minutes()
        if retention_minutes <= 0:
            return
        retention_seconds = retention_minutes * 60
        captured_ts = captured_at.timestamp()
        cutoff = captured_ts - retention_seconds
        with self._lock:
            for metric_name, samples in gauge_samples.items():
                if self._definitions[metric_name].graphable is not True:
                    continue
                metric_series = self._gauge_series.setdefault(metric_name, {})
                for sample in samples:
                    key = _label_key(sample.labels)
                    points = metric_series.setdefault(key, deque())
                    while points and points[0][0] < cutoff:
                        points.popleft()
                    if points and points[-1][1] == sample.value and points[-1][0] == captured_ts:
                        points[-1] = (captured_ts, sample.value)
                    else:
                        points.append((captured_ts, sample.value))
            for metric_name, series_by_label in list(self._gauge_series.items()):
                for key, points in list(series_by_label.items()):
                    while points and points[0][0] < cutoff:
                        points.popleft()
                    if not points:
                        series_by_label.pop(key, None)
                if not series_by_label:
                    self._gauge_series.pop(metric_name, None)

    def _current_gauge_samples(
        self,
        *,
        store: ClientStore,
        now: datetime,
    ) -> dict[str, list[MetricSample]]:
        """Compute current snapshot gauge samples from provider store state."""
        records = store.list()
        samples: dict[str, list[MetricSample]] = {
            name: []
            for name, definition in self._definitions.items()
            if definition.metric_type == "gauge"
        }
        samples["opamp_provider_clients_total"].append(
            MetricSample(labels={}, value=float(len(records)))
        )
        connected_total = sum(1 for record in records if record.disconnected is not True)
        disconnected_total = sum(1 for record in records if record.disconnected is True)
        samples["opamp_provider_clients_connected_total"].append(
            MetricSample(labels={}, value=float(connected_total))
        )
        samples["opamp_provider_clients_disconnected_total"].append(
            MetricSample(labels={}, value=float(disconnected_total))
        )
        samples["opamp_provider_pending_approvals_total"].append(
            MetricSample(labels={}, value=float(store.pending_approval_count()))
        )
        samples["opamp_provider_blocked_agents_total"].append(
            MetricSample(labels={}, value=float(len(store.list_blocked_agents())))
        )

        channel_counts: Counter[tuple[str]] = Counter()
        auth_counts: Counter[tuple[str]] = Counter()
        health_counts: Counter[tuple[str, str]] = Counter()
        component_counts: Counter[tuple[str, str]] = Counter()
        commands_unsent_total = 0
        retained_events_total = 0
        for record in records:
            channel = _normalize_label_value(
                getattr(getattr(record, "last_channel", None), "value", record.last_channel)
            )
            channel_counts[(channel,)] += 1
            auth_counts[
                (
                    _normalize_label_value(
                        getattr(record.auth_mechanism, "value", record.auth_mechanism)
                    ),
                )
            ] += 1
            health = record.health or {}
            health_counts[
                (
                    _normalize_bool_label(health.get("healthy")),
                    _normalize_label_value(health.get("status")),
                )
            ] += 1
            for component, details in (record.component_health or {}).items():
                component_counts[
                    (
                        _normalize_label_value(component),
                        _normalize_bool_label(details.get("healthy")),
                    )
                ] += 1
            commands_unsent_total += sum(
                1 for command in record.commands if command.sent_at is None
            )
            retained_events_total += len(record.events)

        samples["opamp_provider_clients_by_channel_total"] = [
            MetricSample(labels={"channel": labels[0]}, value=float(count))
            for labels, count in sorted(channel_counts.items())
        ]
        samples["opamp_provider_clients_by_auth_mechanism_total"] = [
            MetricSample(
                labels={"auth_mechanism": labels[0]},
                value=float(count),
            )
            for labels, count in sorted(auth_counts.items())
        ]
        samples["opamp_provider_client_health_total"] = [
            MetricSample(
                labels={"healthy": labels[0], "status": labels[1]},
                value=float(count),
            )
            for labels, count in sorted(health_counts.items())
        ]
        samples["opamp_provider_component_health_total"] = [
            MetricSample(
                labels={"component": labels[0], "healthy": labels[1]},
                value=float(count),
            )
            for labels, count in sorted(component_counts.items())
        ]
        samples["opamp_provider_commands_unsent_total"].append(
            MetricSample(labels={}, value=float(commands_unsent_total))
        )
        samples["opamp_provider_client_events_retained_total"].append(
            MetricSample(labels={}, value=float(retained_events_total))
        )
        with self._lock:
            checkpoint_value = self._runtime_gauges.get(
                "opamp_provider_last_checkpoint_timestamp_seconds",
                {(): DEFAULT_LAST_CHECKPOINT_TIMESTAMP},
            ).get((), DEFAULT_LAST_CHECKPOINT_TIMESTAMP)
        samples["opamp_provider_last_checkpoint_timestamp_seconds"].append(
            MetricSample(labels={}, value=float(checkpoint_value))
        )
        return samples

    def _snapshot_histogram_samples(
        self,
        *,
        store: ClientStore,
        now: datetime,
    ) -> dict[str, tuple[tuple[int, ...], int, float]]:
        """Compute scrape-time histograms derived from current store state."""
        expected_values: list[float] = []
        lag_values: list[float] = []
        for record in store.list():
            heartbeat_frequency = max(1, int(record.heartbeat_frequency or 0))
            expected_values.append(float(heartbeat_frequency))
            if record.last_communication is None:
                continue
            lag_seconds = (
                now - record.last_communication
            ).total_seconds() - heartbeat_frequency
            lag_values.append(max(0.0, float(lag_seconds)))
        return {
            "opamp_provider_heartbeat_expected_seconds": self._bucket_counts_from_values(
                HEARTBEAT_EXPECTED_BUCKETS, expected_values
            ),
            "opamp_provider_heartbeat_lag_seconds": self._bucket_counts_from_values(
                HEARTBEAT_LAG_BUCKETS, lag_values
            ),
        }

    @staticmethod
    def _bucket_counts_from_values(
        buckets: tuple[float, ...],
        values: Iterable[float],
    ) -> tuple[tuple[int, ...], int, float]:
        """Return cumulative bucket counts, total sample count, and sum."""
        counts = [0 for _ in buckets]
        total = 0.0
        count = 0
        for raw_value in values:
            value = float(raw_value)
            total += value
            count += 1
            for index, upper_bound in enumerate(buckets):
                if value <= upper_bound:
                    counts[index] += 1
        return tuple(counts), count, total

    @staticmethod
    def _sample_line(
        metric_name: str,
        *,
        labels: Mapping[str, str],
        value: float,
    ) -> str:
        """Render one Prometheus sample line."""
        if labels:
            rendered_labels = ",".join(
                f'{key}="{_escape_label_value(labels[key])}"'
                for key in sorted(labels)
            )
            return f"{metric_name}{{{rendered_labels}}} {_format_metric_value(value)}"
        return f"{metric_name} {_format_metric_value(value)}"

    def _histogram_lines(
        self,
        *,
        definition: MetricDefinition,
        labels: Mapping[str, str],
        bucket_counts: tuple[int, ...],
        count: int,
        total: float,
    ) -> list[str]:
        """Render one histogram into Prometheus sample lines."""
        lines: list[str] = []
        for upper_bound, bucket_count in zip(definition.buckets, bucket_counts):
            bucket_labels = dict(labels)
            bucket_labels["le"] = _format_metric_value(upper_bound)
            lines.append(
                self._sample_line(
                    f"{definition.name}_bucket",
                    labels=bucket_labels,
                    value=float(bucket_count),
                )
            )
        inf_labels = dict(labels)
        inf_labels["le"] = "+Inf"
        lines.append(
            self._sample_line(
                f"{definition.name}_bucket",
                labels=inf_labels,
                value=float(count),
            )
        )
        lines.append(
            self._sample_line(
                f"{definition.name}_sum",
                labels=labels,
                value=total,
            )
        )
        lines.append(
            self._sample_line(
                f"{definition.name}_count",
                labels=labels,
                value=float(count),
            )
        )
        return lines


PROVIDER_METRICS = ProviderMetricsRegistry()
