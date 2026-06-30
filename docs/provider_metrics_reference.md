# Provider Metrics Reference

This page documents the provider metrics exposed by `GET /metrics` and the retained internal graph data exposed by `GET /api/metrics/graphs`.

## What this adds

- `GET /metrics` exposes provider metrics in Prometheus text format.
- `GET /api/metrics/graphs` exposes current gauge values plus optional retained time-series data for product dashboards.
- Gauge history retention is controlled by `provider.metrics.graph_history_minutes`.
- A value of `0` means the provider still reports current gauge values, but it does not retain historical graph points in memory.

## Configuration

```json
{
  "provider": {
    "ui-use-authorization": "config-token",
    "metrics": {
      "enabled": true,
      "graph_history_minutes": 15
    }
  }
}
```

Notes:

- `provider.metrics.enabled` controls both `/metrics` and `/api/metrics/graphs`.
- `provider.metrics.graph_history_minutes` controls in-memory retention for graphable gauge metrics only.
- `/metrics` uses the same non-OpAMP auth controls as `/ui` and `/api`. If `provider.ui-use-authorization` is `config-token` or `idp`, scrapers must present a bearer token.

## Internal Graph API

`GET /api/metrics/graphs`

Optional query parameters:

- `metric`: repeatable metric filter, for example `?metric=opamp_provider_clients_total&metric=opamp_provider_commands_unsent_total`

Behavior:

- When graph retention is greater than `0`, the response includes retained `series` points.
- When graph retention is `0`, the response still includes `current` values but `series` is empty.

## Metric Reference

### Core fleet metrics

| Metric | Type | Labels | Meaning | Source |
| --- | --- | --- | --- | --- |
| `opamp_provider_clients_total` | gauge | none | Current number of provider-side client records. A record exists once the provider is tracking an agent, even if that agent later disconnects. | `len(STORE.list())` |
| `opamp_provider_clients_connected_total` | gauge | none | Current number of tracked clients that are not marked disconnected. | `STORE.list()` filtered by `disconnected == False` |
| `opamp_provider_clients_disconnected_total` | gauge | none | Current number of tracked clients marked disconnected. | `STORE.list()` filtered by `disconnected == True` |
| `opamp_provider_pending_approvals_total` | gauge | none | Current number of agents waiting for manual approval when human-in-loop mode is used. | `STORE.pending_approval_count()` |
| `opamp_provider_blocked_agents_total` | gauge | none | Current number of blocked agent identities. A blocked identity is denied future OpAMP traffic until the block is removed from provider state. | `len(STORE.list_blocked_agents())` |
| `opamp_provider_clients_by_channel_total` | gauge | `channel` | Current number of clients grouped by the last transport channel seen by the provider, for example `HTTP` or `websocket`. | `record.last_channel` |
| `opamp_provider_clients_by_auth_mechanism_total` | gauge | `auth_mechanism` | Current number of clients grouped by the provider-side auth mechanism associated with their record, for example `mtls`, `jwt`, or `unknown`. | `record.auth_mechanism` |

### Health and status metrics

| Metric | Type | Labels | Meaning | Source |
| --- | --- | --- | --- | --- |
| `opamp_provider_client_health_total` | gauge | `healthy`, `status` | Current number of clients grouped by the last top-level health payload reported by each agent. `healthy` is normalized to `true`, `false`, or `unknown`. `status` is the agent-supplied status text or `unknown`. | `record.health` |
| `opamp_provider_component_health_total` | gauge | `component`, `healthy` | Current number of reported agent components grouped by component name and health state. This is useful when many agents report the same component names, such as outputs or collectors. | `record.component_health` |
| `opamp_provider_heartbeat_expected_seconds` | histogram | Prometheus histogram buckets | Distribution of configured heartbeat intervals across tracked clients. This shows the heartbeat frequency the provider expects from agents. | `record.heartbeat_frequency` |
| `opamp_provider_heartbeat_lag_seconds` | histogram | Prometheus histogram buckets | Distribution of how late tracked clients are relative to their configured heartbeat interval. Negative values are clamped to `0`, so the metric measures lateness rather than earliness. | `now - record.last_communication - record.heartbeat_frequency` |

### Command and event metrics

| Metric | Type | Labels | Meaning | Source |
| --- | --- | --- | --- | --- |
| `opamp_provider_commands_queued_total` | counter | `classifier`, `action` | Total number of provider commands queued for agents. This includes normal queued commands and queued force-resync commands. | incremented in `queue_command` and force-resync queueing |
| `opamp_provider_commands_sent_total` | counter | `classifier`, `action` | Total number of queued commands marked sent after the provider includes them in a response to an agent. | incremented in `mark_command_sent` |
| `opamp_provider_commands_unsent_total` | gauge | none | Current number of queued commands whose `sent_at` timestamp is still empty. This is the current backlog, not a lifetime total. | `record.commands` filtered by `sent_at is None` |
| `opamp_provider_client_events_retained_total` | gauge | none | Current total number of retained per-client event-history entries across all client records. This rises and falls with the configured event-history cap. | `sum(len(record.events))` |

### Persistence metrics

| Metric | Type | Labels | Meaning | Source |
| --- | --- | --- | --- | --- |
| `opamp_provider_persistence_mutations_total` | counter | `backend`, `op` | Total number of successful persistence mutations. The current backend label is `json_file`. Operations currently include `save` and `prune`. | persistence helpers |
| `opamp_provider_persistence_write_seconds` | histogram | `backend`, `operation` | Duration of persistence write-like operations. The current backend label is `json_file`. Operations currently include `snapshot_save` and `snapshot_prune`. | persistence helpers |
| `opamp_provider_persistence_failures_total` | counter | `backend`, `operation` | Total number of persistence operation failures, including save, prune, and restore failures. | persistence helpers |
| `opamp_provider_restore_operations_total` | counter | `backend`, `result` | Total number of restore attempts grouped by `success` or `failure`. | persistence helpers |
| `opamp_provider_last_checkpoint_timestamp_seconds` | gauge | none | Unix timestamp of the most recent successfully saved or restored provider checkpoint known to the running process. A value of `0` means the provider has not yet recorded one during this run. | persistence helpers |

### Sequence integrity metrics

| Metric | Type | Labels | Meaning | Source |
| --- | --- | --- | --- | --- |
| `opamp_provider_force_resync_queued_total` | counter | none | Total number of force-resync commands successfully queued because the provider determined it needed a full-state refresh from an agent. | `_queue_force_resync_if_missing_locked` success |
| `opamp_provider_sequence_gap_total` | counter | none | Total number of non-sequential `AgentToServer.sequence_num` gaps detected after initial contact. The very first message from a client does not count as a gap. | `check_sequence_num` |

## Notes for operators

- Counters are lifetime totals for the current provider process.
- Gauges describe the provider's current view of the world at scrape time.
- Histograms are emitted in standard Prometheus histogram form using `_bucket`, `_sum`, and `_count` samples.
- The internal graph endpoint retains gauge metrics only. Counter and histogram history should be handled by Prometheus, the OpenTelemetry Collector, or another external monitoring backend.

## Related docs

- [Provider config reference](provider_config_reference.md)
- [Endpoints](endpoints.md)
- [Authentication](authentication.md)
- [Prometheus and collector setup](provider_metrics_prometheus_setup.md)
