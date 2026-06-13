# Simulator Design And Intent

## Purpose

The simulator exists to help us exercise **OpAMP server behavior at scale** without
needing many real agents installed and running.

Primary goal:
- make the server believe there are many distinct agents connected
- vary identity/version/config metadata per agent
- control server-to-agent interaction outcomes predictably

This is intended for server functional testing, workflow validation, and
operational behavior checks (filtering, command dispatch, status handling,
state transitions), not performance benchmarking of real telemetry pipelines.

Production scope:
- Simulator components are non-production tooling and are not intended to be deployed in production environments.
- Production environments should deploy real consumer agent types (`fluentbit`/`fluentd`) rather than simulator clients.

## High-Level Approach

The simulator uses the existing consumer architecture with a dedicated
`service_type=simulator` client implementation.

Key components:
- `consumer/src/opamp_consumer/simulator_client.py`
- `consumer-sim/src/consumer_sim_launcher.py`
- `consumer-sim/config/consumer_instances.json`

The launcher starts many simulator instances, each with its own process, config,
and metadata overrides, so the provider stores them as independent agents.

## Startup Safety Gate

Simulator runtime is protected by development-flag gating:

- Required flag: `APP_ENABLE_DEV_FEATURES=true`
- If missing or false, simulator startup is blocked.
- On block, the simulator logs the reason and exits gracefully before reporting any agent details to the server.

Operational note:
- The CLI demo-consumer flow sets this flag automatically.
- Direct/manual simulator launches must set the flag explicitly.

## Identity And Version Simulation

Each simulator instance can declare unique identity/version data via
`--agent-additional-params` as a single JSON object:

```json
{
  "service_instance_uid": "sim-001",
  "client_version": "2.1.0",
  "config_version": "cfg-002"
}
```

How these map into reported agent data:
- `service_instance_uid` (or `service_instance_id`) -> `service.instance.id`
- `client_version` -> `service.version`
- `config_version` -> non-identifying attribute `config.version`

This is what enables the server UI and APIs to show many distinct simulated
agents and support realistic filtering/use-case validation.

## Server Request Simulation

The simulator loads a response-plan file:
- `consumer.simulator_responses_path`
- example: `consumer/simulator-responses.example.json`

Per server request type, it supports scripted actions:
- `accept` = run normal handling
- `ignore` = drop request
- `error` = simulate handler failure

The response list for each request type is cyclical:
- once the list ends, it wraps to the first entry

This gives deterministic, repeatable sequences for testing server reactions to:
- accepted commands
- ignored requests
- transient/repeating failures

## Why This Design Helps Server Testing

The design intentionally separates:
- **agent population control** (launcher + per-instance metadata)
- **behavior control** (scripted request handling)

With this split we can:
- start many unique simulated agents quickly
- test UI/API filtering and table behavior on heterogeneous populations
- validate command and control workflows under mixed outcomes
- reproduce scenarios by reusing fixed configs and scripts

## Lifecycle Model

Start:
- launcher reads `config/consumer_instances.json`
- spawns one simulator process per entry
- records PID/process metadata in launcher state file

Stop:
- launcher sets simulator status to `shutdown` in launcher process record file
- each simulator polls its own status every 30 seconds, updates to `shuttingdown`,
  then exits gracefully
- waits up to 90 seconds for graceful exit
- force-terminates if needed
- removes each stopped instance record from state file immediately
- deletes state file when all are stopped

This keeps cleanup reliable and avoids stale state on partial failures.

## Typical Usage Pattern

1. Define many simulator instances in `consumer-sim/config/consumer_instances.json`.
2. Give each instance distinct metadata JSON in `agent-additional-params`.
3. Run the simulator directly or use the CLI demo-consumer flow.
4. Exercise server UI/API/tooling against the simulated population.
5. Stop the simulator directly or use the CLI stop flow.

## Scope And Limitations

What it is good at:
- server-side behavior and correctness testing
- scenario reproduction
- metadata/filter/command workflow testing

What it is not:
- realistic Fluent Bit/Fluentd pipeline execution
- network/throughput/load benchmark substitute
- full fidelity production agent behavior
