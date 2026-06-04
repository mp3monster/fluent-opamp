# OpAMP Server & Supervisor for Fluent Bit & Fluentd

This repository hosts an implementation of the OpenTelemetry [Open Agent Management Protocol (OpAMP)](https://opentelemetry.io/docs/specs/opamp/). The OpAMP protocol allows us to perform tasks such as:

- manage & monitor any compliant agent
- Command and configure agents

The protocol is oriented towards agents supporting the observability domain such as OTel Collectors. The protocol does not mandate that the capabilities have to be directly embedded in the agent, in fact the protocol documentation calls out explicitly the idea of a supervisor model, where a separate process manages the agent.

This repository provide an agent implementation that specifically adopts the supervisor model, but also understands the characteristics of Fluent Bit and Fluentd to service the different operations.

Here we have provided both the agent/client(supervisor) and server functionality. Although the protocol is defined in such a manner, that it should be possible to mix and match.

Aside from providing out of the box support for Fluent Bit and Fluentd it provides a means to extend and customize features including:

- Modifying the way an agent is supervised (so the supervisor could be something other than Fluentd or Fluent Bit).
- Dynamic deployment and execution of custom commands.
- Easy tailoring of several areas such as full status updates - given the 'openness of the spec'.

The following documentation provides more information, including the deployment and configuration of the server and client/agent. More detail on the design ideas, and how it the functionality could be further extended. As the protocol definition is very flexible (part of the protocol is an exchange of what client and server operations can be performed) we've identified which features are supported, and which aren't with suggestions on how the non-supported features could be addressed in a Fluentd / Fluent Bit context.

The documentation includes background such as the implementation philosophies that have informed the capability, such as being able to get something running quickly.

## Docs

- [docs/README.md](docs/README.md) — full setup and run instructions.
- [docs/README.md#uml-component-view](docs/README.md#uml-component-view) — high-level architecture diagram showing required and optional components.
- [docs/index.md](docs/index.md) — documentation landing page and project overview.
- [docs/consumer_client_diagrams.md](docs/consumer_client_diagrams.md) — rendered consumer client diagrams with walkthrough notes.
- [docs/provider_server_diagrams.md](docs/provider_server_diagrams.md) — rendered provider/server diagrams with architecture walkthrough notes.
- [docs/features.md](docs/features.md) — feature notes and design direction.
- [mcp/README.md](mcp/README.md) — MCP setup wrappers/canonical script behavior, FastMCP client role, command-line parameters, and verification.
- [docs/scripts.md](docs/scripts.md) — script reference table by platform.
- [docs/dev/component_versioning.md](docs/dev/component_versioning.md) — git-derived component version metadata, help/UI exposure, and hook/build integration.
- [cli/README.md](cli/README.md) — CLI launcher/orchestration usage and local operator workflows.
- [consumer/README.md](consumer/README.md) — consumer configuration and CLI usage.
- [consumer-sim/README.md](consumer-sim/README.md) — simulator launcher usage and local multi-instance test flows.
- [provider/README.md](provider/README.md) — provider configuration and web UI notes.
- [catalog-service/README.md](catalog-service/README.md) — optional catalog service overview and setup notes.
- [config-service/README.md](config-service/README.md) — optional editor/config service overview and setup notes.
- [agent_broker/README.md](agent_broker/README.md) — optional conversation broker overview, setup, and run modes.
- [agent_broker/docs/README.md](agent_broker/docs/README.md) — broker documentation index and operational guides.

## Optional Components

The core OpAMP provider/server and consumer/client run without the optional
components listed below:

- `agent_broker/` — conversation broker
- `consumer-sim/` — simulator launcher and local demo/test helper
- `catalog-service/` — catalog browsing and supporting service components
- `config-service/` — editor/config validation service components

When used, these components run as separate processes or supporting services
with their own startup/shutdown flow and configuration.

## Folder summary

- `agent_broker` — optional standalone conversation broker package and docs.
- `catalog-service` — optional catalog service package, UI assets, and docs.
- `cli` — optional local launcher/orchestration utility and docs.
- `config` — default configuration files (including `opamp.json`).
- `config-service` — optional editor/config validation service package and docs.
- `consumer` — the OpAMP consumer (client) package, tests, and config samples.
- `consumer-sim` — optional simulator launcher utilities and docs.
- `dist` — SBOM and Wheel files.
- `docs` — project documentation.
- `logs` — runtime logs created by scripts.
- `proto` — protobuf definitions and generated artifacts.
- `provider` — the OpAMP provider (server) package, UI, and tests.
- `scripts` — helper run and shutdown scripts.
- `shared` — shared utilities used by provider/consumer.
- `tests` — repository-level tests.
