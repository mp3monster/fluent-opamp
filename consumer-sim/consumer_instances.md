# `consumer_instances.json` Reference

This document describes all supported parameters in `consumer-sim/consumer_instances.json`.

## File Location

- Default file: `consumer-sim/consumer_instances.json`
- Override file path with env var: `CONSUMER_SIM_CONFIG=/path/to/file.json`
- JSON schema: `consumer-sim/consumer_instances.schema.json`

## JSON Schema Validation

On `start`, launcher validates the config file against
`consumer-sim/consumer_instances.schema.json` before launching any process.

- Validation failure is fatal and startup is aborted.
- Error output includes:
  - config file path,
  - schema file path,
  - one or more validation issue locations and messages.

## Top-Level Schema

```json
{
  "state_file": "runtime/launcher_state.json",
  "instances": []
}
```

### Top-Level Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `state_file` | string | No | `consumer-sim/runtime/launcher_state.json` | Path to launcher runtime state file (stores PID/process-group data for `stop`). Relative paths resolve from the folder containing `consumer_instances.json`. |
| `instances` | array[object] | Yes (for `start`) | N/A | List of consumer instance launch definitions. Must be a non-empty array for `start`. |

## `instances[]` Schema

Each object in `instances` supports the fields below.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | Yes | N/A | Human-readable instance name used in console logs and state records. |
| `entrypoint` | string | No | `simulator` | Built-in runtime selector. Supported value: `simulator` only. Ignored when `command` is set. |
| `command` | string or array[string] | No | derived from `entrypoint` | Full command override. If provided, launcher uses this command instead of `entrypoint`. Command must still launch simulator client. |
| `config_path` | string | Yes | N/A | Consumer config file path. Launcher always appends `--config-path <resolved_path>`. |
| `agent_config_path` | string | No | unset | Optional agent runtime config path. Launcher appends `--agent-config-path <resolved_path>` when provided. |
| `overrides` | object | No | `{}` | Additional CLI flags appended after `--config-path`/`--agent-config-path`. |
| `env` | object | No | `{}` | Extra environment variables for that process. Values are stringified. |
| `working_dir` | string | No | repository root | Working directory for launched process (`cwd`). |

## Path Resolution Rules

- `state_file`, `config_path`, `agent_config_path`, `working_dir`:
  - Absolute paths are used as-is.
  - Relative paths are resolved from the directory containing `consumer_instances.json`.

## Built-In `entrypoint` Values

- `simulator` -> `python -m opamp_consumer.simulator_client`

## `command` Behavior

- If `command` exists, `entrypoint` is ignored.
- Supported `command` formats:
  - String: shell-split (e.g. `"python -m opamp_consumer.client"`)
  - Array: each non-empty item becomes one argv token
- Command must target simulator client (for example contains `opamp_consumer.simulator_client` or `opamp-consumer-simulator`).

## `overrides` Behavior

`overrides` is converted to CLI flags and values.

### Key Normalization

- If key starts with `-`, it is used as-is.
- Otherwise launcher prepends `--` and converts `_` to `-`.
  - Example: `heartbeat_frequency` -> `--heartbeat-frequency`

### Value Serialization

- `true` -> adds only the flag
  - Example: `"diagnostic": true` -> `--diagnostic`
- `false` -> adds flag plus literal `false`
  - Example: `"diagnostic": false` -> `--diagnostic false`
- Array -> adds flag once, followed by each array value
  - Example: `"agent-additional-params": ["-R", "--dry-run"]`
- Scalar -> adds `flag value`
  - Example: `"heartbeat-frequency": 30` -> `--heartbeat-frequency 30`

Simulator metadata pass-through example using one JSON object:

- `"agent-additional-params": ["{\"service_instance_uid\":\"sim-01\",\"client_version\":\"1.2.3\",\"config_version\":\"cfg-009\"}"]`

## `env` Behavior

- Launcher starts from current shell environment.
- It always prepends `PYTHONPATH` with:
  - `<repo_root>/consumer/src`
  - `<repo_root>`
- Then applies `env` key/value pairs from instance config.

## Example With All Fields

```json
{
  "state_file": "runtime/launcher_state.json",
  "instances": [
    {
      "name": "consumer-simulator-1",
      "entrypoint": "simulator",
      "config_path": "../consumer/opamp-simulator.json",
      "agent_config_path": "../consumer/fluent-bit.yaml",
      "overrides": {
        "heartbeat-frequency": 20,
        "log-level": "INFO",
        "diagnostic": true,
        "agent-additional-params": ["--dry-run"]
      },
      "env": {
        "OPAMP_SERVER_URL": "http://localhost:8080"
      },
      "working_dir": ".."
    }
  ]
}
```

## Validation Notes

Typical config errors raised by launcher:

- Missing/empty `instances` list
- Missing `instance.name`
- Missing `instance.config_path`
- `overrides` not an object
- `env` not an object
- Unsupported `entrypoint`
- Empty `command` string/list

## Stop Behavior

- Stop sets each simulator record status in the process record file to `shutdown`.
- Simulators poll their own record every 30 seconds and, when they see `shutdown`,
  they update status to `shuttingdown` and terminate gracefully.
- Graceful wait budget is 90 seconds per process.
- If graceful signaling errors or timeout occurs, launcher escalates to brute-force termination.
- Each successfully stopped process is removed from the state file immediately.
- When all are stopped, launcher deletes the state file and exits.
- Console emphasis:
  - `----- ... -----` when state moves to `shuttingdown`
  - `====== ... ======` when the process is no longer detected
