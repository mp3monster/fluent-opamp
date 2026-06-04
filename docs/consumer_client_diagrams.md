# Consumer Client Diagrams Guide

This page explains the rendered consumer client diagrams and links each one back to the Mermaid source.
For the latest architecture (including process-tracking strategy split), use the Mermaid source as canonical.

## Source and Related Docs

- Mermaid source: [docs/dev/consumer_client_diagram.md](dev/consumer_client_diagram.md)
- Consumer mixin behavior: [docs/dev/consumer_mixins.md](dev/consumer_mixins.md)
- Consumer reporting/update cadence: [docs/dev/consumer_update_controllers.md](dev/consumer_update_controllers.md)

## Diagram 1: Class and Module Relationships

![Consumer class and module relationships](consumer_client_diagram_1.png)

What this shows:

- `AbstractOpAMPClient` composes core send/reporting behavior.
- `ClientTransportAuthorizationMixin`, `ClientRuntimeMixin`, and `ServerMessageHandlingMixin` contribute transport/auth, runtime, and server-message handling behavior.
- Runtime lifecycle delegation now routes to `ClientSupervisorMixin` or `ClientObserverMixin` based on config.
- Concrete clients (`OpAMPClient` for Fluent Bit and `FluentdOpAMPClient` for Fluentd) extend/override where needed.
- Update controller implementations (`AlwaysSend`, `SentCount`, `TimeSend`) control reporting flag reset cadence.

## Diagram 2: Runtime Entrypoints

![Consumer runtime entrypoints](consumer_client_diagram_2.png)

What this shows:

- Script and CLI entrypoints for Fluent Bit and Fluentd clients.
- Bootstrap path through `client_bootstrap.run_default_client_main(...)`.
- Shared runtime behavior flowing into `AbstractOpAMPClient` + mixins.
- Provider endpoint target still comes from `consumer.server_url`.

## Diagram 3: Mixin Dispatch Model

![Consumer mixin method dispatch](consumer_client_diagram_3.png)

What this shows:

- Which methods resolve in mixins vs `AbstractOpAMPClient`.
- How `ClientRuntimeMixin` delegates process lifecycle calls to strategy classes selected from `consumer.processTracking`.
- How subclass overrides (for example `FluentdOpAMPClient.add_agent_version`) win over mixin/base implementations via MRO.

## Diagram 4: Reporting Flags and Update Controllers

![Consumer reporting flags and update controllers](consumer_client_diagram_4.png)

What this shows:

- How report flags gate which payload fields are emitted.
- When controller implementations reset flags for future sends.
- How `ReportFullState` from the server forces full reporting state.

## Diagram 5: Transport URL and TLS Resolution

![Consumer transport URL and TLS resolution](consumer_client_diagram_5.png)

What this shows:

- How `consumer.server_url` and `consumer.transport` select HTTP vs WebSocket send path.
- URL normalization for WebSocket mode (`http->ws`, `https->wss`).
- How `consumer.tls.verify_server` and `consumer.tls.ca_file` control TLS verification behavior.

## Diagram 6: Runtime Process Tracking Strategy

No rendered PNG panel is currently published for this diagram section.
Use the Mermaid source in [docs/dev/consumer_client_diagram.md](dev/consumer_client_diagram.md) for the current strategy flow.

What this shows:

- `consumer.processTracking` normalization and strategy selection.
- default/fallback to `Supervisor`.
- required `consumer.processDetectionRegex` when using `Observer`.
