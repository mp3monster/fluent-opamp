# OTel Collector Consumer Configuration

This page documents the expected configuration shape for an OpenTelemetry Collector
consumer plugin.

There is currently no built-in `otel_collector` entry point in `consumer/pyproject.toml`.
Use this page for external plugin configuration, or as the target shape if a built-in
collector plugin is added later.

## Plugin Identity

Suggested plugin key:

- `consumer.service_type`: `otel_collector`

External plugin mapping example:

```json
{
  "service_type": "otel_collector",
  "entry_point": "your_otel_collector_consumer.client:main",
  "enabled": true
}
```

Unified command:

```bash
opamp-consumer --config-path ./opamp.json
```

## Consumer Keys

| Key | Required | Notes |
|---|---:|---|
| `consumer.agent_config_path` | Usually | Collector config file path. An external plugin normally passes this to `otelcol --config`. |
| `consumer.agent_additional_params` | No | Extra collector CLI args, such as additional `--set` overrides. |
| `consumer.client_status_port` | Plugin-defined | Set this if the plugin exposes or polls a local collector health/check endpoint. |
| `consumer.processTracking` | No | `Supervisor` can launch a collector process. `Observer` can attach to a process by regex if implemented by the plugin. |
| `consumer.processDetectionRegex` | Observer only | Regex used to discover an already running collector process. |
| `consumer.agent_capabilities` | No | External plugin should declare only the capabilities it implements safely. |

## Collector Health Extension

An OTel Collector plugin should configure a collector health endpoint if it wants
consumer heartbeat status to reflect collector health.

Example collector config fragment:

```yaml
extensions:
  health_check:
    endpoint: 0.0.0.0:13133

service:
  extensions:
    - health_check
```

The corresponding consumer config should point status polling at that port when
the plugin relies on the shared heartbeat path:

```json
{
  "consumer": {
    "client_status_port": 13133
  }
}
```

## OTLP Export From This Project

Do not confuse an OTel Collector consumer plugin with this project's own OTLP
observability export. Process telemetry export for provider, consumer, services,
and broker is configured through the top-level `otlp-endpoints` block:

- [OTLP observability config](../../../docs/otlp_observability.md)

## Minimal External Plugin Example

```json
{
  "consumer": {
    "server_url": "http://localhost:4320",
    "server-authorization": "none",
    "service_type": "otel_collector",
    "plugins": [
      {
        "service_type": "otel_collector",
        "entry_point": "your_otel_collector_consumer.client:main",
        "enabled": true
      }
    ],
    "agent_config_path": "./otel-collector.yaml",
    "agent_additional_params": [],
    "client_status_port": 13133,
    "processTracking": "Supervisor",
    "heartbeat_frequency": 30
  }
}
```

## Implementation Expectations

An external collector plugin should provide its own config processing method if it
needs collector-specific keys. The shared consumer plugin loader can route to the
plugin entry point from either package entry points or `consumer.plugins` config.
