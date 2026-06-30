# Prometheus And Collector Setup For Provider Metrics

This page shows how to scrape the provider metrics endpoint from Prometheus or an OpenTelemetry Collector.

## Endpoint summary

- Metrics scrape endpoint: `GET /metrics`
- Internal graph endpoint: `GET /api/metrics/graphs`
- Both endpoints are disabled when `provider.metrics.enabled=false`.
- `/metrics` follows the provider's non-OpAMP auth mode, so it is protected by `provider.ui-use-authorization`.

## Recommended provider configuration

For machine-to-machine scraping, the simplest secure setup is a static bearer token:

```json
{
  "provider": {
    "ui-use-authorization": "config-token",
    "metrics": {
      "enabled": true,
      "graph_history_minutes": 15
    },
    "tls": {
      "cert_file": "/etc/opamp/provider.pem",
      "key_file": "/etc/opamp/provider-key.pem"
    }
  }
}
```

Environment:

```bash
export UI_AUTH_STATIC_TOKEN="replace-with-a-scrape-token"
```

Why this is usually the best fit:

- Prometheus and the OpenTelemetry Collector both work well with bearer-token auth.
- It avoids browser-oriented login flows.
- It keeps `/metrics` protected without changing the OpAMP transport auth mode.

If your environment already uses an identity provider for non-OpAMP routes, `provider.ui-use-authorization=idp` also works, but the scraper must then send a valid bearer token accepted by that IdP configuration.

## Prometheus example

```yaml
global:
  scrape_interval: 30s

scrape_configs:
  - job_name: opamp-provider
    scheme: https
    metrics_path: /metrics
    static_configs:
      - targets:
          - opamp.example.org:8443
    authorization:
      type: Bearer
      credentials: ${OPAMP_PROVIDER_METRICS_TOKEN}
    tls_config:
      ca_file: /etc/prometheus/certs/provider-ca.pem
```

Adjust as needed:

- Use `scheme: http` if you are not terminating TLS on the provider or an upstream proxy.
- Use port `8080` or your configured provider port when running the default local setup.
- If you leave `provider.ui-use-authorization=none`, remove the `authorization` block.

## OpenTelemetry Collector example

The Collector's Prometheus receiver accepts Prometheus-style `scrape_configs`, so the setup is very similar:

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: opamp-provider
          scheme: https
          metrics_path: /metrics
          static_configs:
            - targets:
                - opamp.example.org:8443
          authorization:
            type: Bearer
            credentials: REPLACE_WITH_SCRAPE_TOKEN
          tls_config:
            ca_file: /etc/otel/certs/provider-ca.pem

processors:
  batch: {}

exporters:
  debug: {}

service:
  pipelines:
    metrics:
      receivers: [prometheus]
      processors: [batch]
      exporters: [debug]
```

Notes:

- Replace `debug` with your real metrics exporter.
- If you already centralize secrets for the Collector, inject the bearer token through your normal configuration management path rather than hard-coding it.

## Local development example

If you are using the repository default config from `config/opamp.json`, the provider currently exposes:

- port `8080`
- `/metrics`
- `provider.metrics.enabled=true`
- `provider.metrics.graph_history_minutes=0`
- `provider.ui-use-authorization=none`

That means a local Prometheus scrape can be as small as:

```yaml
scrape_configs:
  - job_name: opamp-provider-local
    static_configs:
      - targets:
          - localhost:8080
```

## Internal graph data for product dashboards

If you want the provider itself to retain gauge history for built-in dashboards:

```json
{
  "provider": {
    "metrics": {
      "enabled": true,
      "graph_history_minutes": 15
    }
  }
}
```

Behavior:

- `graph_history_minutes=0`: no in-memory time-series retention
- `graph_history_minutes>0`: retained gauge history is available from `/api/metrics/graphs`

Example query:

```text
/api/metrics/graphs?metric=opamp_provider_clients_total
```

## Troubleshooting

- `401 Unauthorized` from `/metrics`: check `provider.ui-use-authorization` and the bearer token used by the scraper.
- `404` from `/metrics`: check `provider.metrics.enabled`.
- TLS errors: verify the provider certificate chain and the scraper CA file.
- Empty internal `series` arrays: check whether `provider.metrics.graph_history_minutes` is still `0`.

## References

- Repository docs:
  - [Provider metrics reference](provider_metrics_reference.md)
  - [Authentication](authentication.md)
  - [Provider config reference](provider_config_reference.md)
- External docs:
  - Prometheus configuration: https://prometheus.io/docs/prometheus/latest/configuration/configuration/
  - Prometheus scrape and HTTP auth settings: https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config
  - OpenTelemetry Collector Prometheus receiver: https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/prometheusreceiver
  - OpAMP specification: https://opentelemetry.io/docs/specs/opamp/
