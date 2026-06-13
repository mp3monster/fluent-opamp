# OTLP Observability Configuration

This project supports one shared top-level configuration block named `otlp-endpoints`.

Use it to enable OpenTelemetry OTLP export for:

- provider
- consumer
- standalone config-service
- standalone catalog-service
- broker

When config-service and catalog-service are embedded inside the provider, they share the
provider process observability configuration and `service.name`.

## Configuration shape

```json
{
  "otlp-endpoints": {
    "ALL": "http://collector:4317",
    "logs": "http://logs-collector:4317",
    "metrics": "http://metrics-collector:4317",
    "traces": "http://traces-collector:4317",
    "export_interval": 300
  }
}
```

## Fields

- `otlp-endpoints.ALL`
  Optional URL. When present, it is used as the default endpoint for logs, metrics, and traces.
- `otlp-endpoints.logs`
  Optional URL. Overrides `ALL` for log export.
- `otlp-endpoints.metrics`
  Optional URL. Overrides `ALL` for metric export.
- `otlp-endpoints.traces`
  Optional URL. Overrides `ALL` for trace export.
- `otlp-endpoints.export_interval`
  Optional positive integer in seconds. Default is `300`. This controls the metric export interval.

## Resolution rules

- If only `ALL` is set, the same endpoint is used for logs, metrics, and traces.
- If a signal-specific key is also set, that signal-specific value wins over `ALL`.
- If the block is absent, OTLP export is disabled.

## Runtime notes

- Provider uses `service.name=opamp-provider`.
- Broker uses `service.name=opamp-broker`.
- Standalone config-service uses `service.name=config-service`.
- Standalone catalog-service uses `service.name=catalog-service`.
- Consumer runtimes use the configured `consumer.service_name` when present, otherwise a runtime-specific default.

## Broker note

The broker accepts `otlp-endpoints` in its own runtime config file. If the block is omitted there,
the broker inherits it from the `opamp.json` file referenced by `paths.opamp_config_path`.
