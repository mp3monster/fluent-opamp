# CLI Configuration Reference

The OpAMP CLI is mostly command-driven, but it does read and write a small
number of JSON files. This page documents those files, with extra detail for
the demo profile `containers` block because that block drives real Docker or
Podman commands.

## Files

| File | Owner | Purpose |
|---|---|---|
| `cli/config/demo_consumer_profiles.json` | checked in | Defines demo consumer profiles and optional dependency containers. |
| `cli/runtime/settings.json` | generated | Stores local CLI preferences such as process-tail behavior. |
| `cli/runtime/managed_processes.json` | generated | Records processes and containers started by the CLI so `stop`, `restart`, and `status` can find them. |
| `.venv/` | generated | Default repository-level virtual environment created by `opamp-cli setup-venv`. |

Do not edit files under `cli/runtime/` to add new workflows. They are runtime
state, not source configuration. Add source-controlled demo and container
definitions to `cli/config/demo_consumer_profiles.json`.

## Demo Consumer Profiles

Demo profiles are enabled by setting `OPAMP_DEMO=true`. When enabled, the CLI
loads:

```text
cli/config/demo_consumer_profiles.json
```

The top-level shape is:

```json
{
  "profiles": [
    {
      "name": "Demo setup (Simx1, Flbx1, Fdx1)",
      "scenario_description": "Human-readable description shown with d<number>.",
      "simulator": {
        "instances_path": "consumer-sim/config/consumer_instances.json"
      },
      "fluentbit": {
        "config_path": "config/opamp.json",
        "agent_config_path": "consumer/fluent-bit.yaml"
      },
      "fluentd": {
        "config_path": "consumer/opamp-fluentd.json",
        "agent_config_path": "consumer/fluentd.conf"
      },
      "elastic_agent": {
        "config_path": "tests/logstash/opamp-consumer-elastic-agent-logstash-plugin.json",
        "agent_config_path": "tests/logstash/elastic-agent.yml"
      },
      "containers": []
    }
  ]
}
```

Paths in this file are resolved relative to the repository root unless they are
already absolute.

## Profile Attributes

| Attribute | Type | Required | Description |
|---|---|---:|---|
| `name` | string | Yes | Stable display name and lookup key for the profile. The profile index can also be used in guided selection. |
| `scenario_description` | string | No | Description shown when the user enters `d<number>` in guided demo selection. |
| `description` | string | No | Fallback description used when `scenario_description` is absent. |
| `simulator` | object | No | Simulator launch configuration. |
| `fluentbit` | object | No | Fluent Bit consumer launch configuration. |
| `fluentd` | object | No | Fluentd consumer launch configuration. |
| `elastic_agent` | object | No | Elastic Agent consumer launch configuration. |
| `containers` | array | No | Dependency containers started before consumers in the same profile. |

A profile must configure at least one launchable component: a container, a
simulator instances file, a complete Fluent Bit pair, a complete Fluentd pair,
or an Elastic Agent config.

## Consumer Component Blocks

`simulator` supports:

| Attribute | Type | Required | Description |
|---|---|---:|---|
| `instances_path` | string | Yes, when simulator is configured | Path to the simulator instances JSON. |

`fluentbit` and `fluentd` support the same pair of attributes:

| Attribute | Type | Required | Description |
|---|---|---:|---|
| `config_path` | string | Yes, when the component is configured | Consumer OpAMP JSON config. |
| `agent_config_path` | string | Yes, when the component is configured | Agent config passed as `--agent-config-path`. |

Elastic Agent supports:

| Attribute | Type | Required | Description |
|---|---|---:|---|
| `config_path` | string | Yes, when Elastic Agent is configured | Consumer OpAMP JSON config. This should select the `elastic_agent` plugin. |
| `agent_config_path` | string | No | Elastic Agent YAML passed as `--agent-config-path` when present. |

The Elastic Agent demo path starts `python -m opamp_consumer.client`, not the
legacy direct module entrypoint, so plugin routing is exercised.

## Container Entries

Container entries can appear inside a profile:

```json
{
  "profiles": [
    {
      "name": "Demo setup (Elastic Agent self-monitoring to Logstash in container)",
      "containers": [
        {
          "id": "logstash-local",
          "label": "Logstash local pipeline",
          "container_name": "opamp-logstash",
          "replace_existing": true,
          "image_candidates": [
            "docker.elastic.co/logstash/logstash:9.5.1",
            "logstash:9.5.1"
          ],
          "ports": [
            "127.0.0.1:5044:5044"
          ],
          "volumes": [
            {
              "host_path": "tests/logstash/logstash.container.conf",
              "container_path": "/usr/share/logstash/pipeline/logstash.conf",
              "read_only": true
            },
            {
              "host_path": "tests/logstash/out",
              "container_path": "/usr/share/logstash/out"
            }
          ],
          "ensure_dirs": [
            "tests/logstash/out"
          ],
          "command": [
            "logstash",
            "-f",
            "/usr/share/logstash/pipeline/logstash.conf"
          ],
          "aliases": [
            "logstash",
            "local logstash"
          ]
        }
      ]
    }
  ]
}
```

They may also appear in a top-level `containers` array in the same file. The
CLI combines top-level entries and profile entries, then de-duplicates them by
entry id/name/label for `opamp-cli dev-containers`.

## Container Attribute Reference

| Attribute | Type | Required | Description |
|---|---|---:|---|
| `id` | string | Yes, unless `name` or `label` is supplied | Stable container entry identifier. Used for de-duplication, action IDs, aliases, and recorded metadata. |
| `name` | string | No | Fallback identifier when `id` is not supplied. |
| `label` | string | No | Human-readable label shown in CLI menus. Also used as fallback identifier and record label. |
| `container_name` | string | No | Name passed to the runtime as `--name`. Prefer setting this so `stop` can target a friendly stable name. |
| `replace_existing` | boolean | No | When true and the runtime is Podman, adds `--replace` to `run`. Docker does not receive `--replace`. |
| `image` | string | Yes, unless `image_candidates` supplies a value | Container image to run. |
| `image_candidates` | array[string] | No | Ordered image list. The CLI uses the first non-empty value. This is useful when you want a fully qualified image first and a local alias fallback. |
| `ports` | array[string] | No | Port mappings passed as `-p` values, for example `127.0.0.1:5044:5044`. The first valid mapping is also used as a TCP readiness probe. |
| `environment` | object | No | Environment variables passed as `-e KEY=value`. Values are stringified. |
| `volumes` | array[object] | No | Volume mounts passed as `-v host_path:container_path[:ro]`. |
| `ensure_dirs` | array[string] | No | Host directories created before launch. Useful for writable mounted output folders. |
| `extra_args` | array[string] | No | Extra runtime arguments inserted before the image name. Use for runtime flags such as network or platform options. |
| `command` | array[string] | No | Command and arguments appended after the image name. |
| `aliases` | array[string] | No | Additional names accepted by `opamp-cli dev-containers <selection>`. |

The generated runtime command has this shape:

```text
<runtime> run --rm [--replace] [--name <container_name>] [-p ...] [-e ...] [-v ...] <extra_args...> <image> <command...>
```

`--replace` is only emitted for Podman because the CLI currently treats Docker
as not supporting the same replacement flag.

## Volume Attributes

| Attribute | Type | Required | Description |
|---|---|---:|---|
| `host_path` | string | Yes | Host path to mount. Relative paths resolve from repository root. |
| `container_path` | string | Yes | Path inside the container. |
| `read_only` | boolean | No | When true, appends `:ro` to the mount. |

If a volume entry is missing either `host_path` or `container_path`, that entry
is ignored.

## Runtime Selection

The CLI chooses the container runtime in this order:

1. `OPAMP_CONTAINER_RUNTIME`, when set
2. `podman`
3. `docker`

The value may be a command name or a path, as long as it resolves through
`PATH`.

Examples:

```bash
OPAMP_CONTAINER_RUNTIME=docker opamp-cli dev-containers logstash
OPAMP_CONTAINER_RUNTIME=podman opamp-cli dev-containers logstash
```

Before starting a container, the CLI runs:

```text
<runtime> info
```

If that fails, the CLI reports a runtime-not-ready message. For Podman it hints
at `podman machine start`; for Docker it hints at starting Docker Desktop or
the Docker daemon.

## Readiness

For container starts, readiness is based on the first valid `ports` mapping.

Examples:

| Mapping | Readiness endpoint |
|---|---|
| `127.0.0.1:5044:5044` | `127.0.0.1:5044` |
| `5044:5044` | `127.0.0.1:5044` |

The CLI waits for the host TCP endpoint to accept connections. If no valid
port mapping is present, there is no TCP readiness probe and the CLI only uses
the normal early process liveness check.

## Stop Behavior

When the CLI starts a container, it records container metadata in:

```text
cli/runtime/managed_processes.json
```

Recorded metadata includes:

- `container_id`
- `container_name`
- `container_runtime`
- `container_image`
- `demo_profile`, when started as part of a demo profile

`opamp-cli stop` and `opamp-cli stop all` use that metadata to stop containers
cleanly with:

```text
<runtime> stop --time <timeout> <container_name-or-id>
```

If no container metadata is present, the CLI falls back to normal process stop
behavior for recorded non-container processes.

## Runtime Settings

The CLI stores local preferences in:

```text
cli/runtime/settings.json
```

Current settings:

| Attribute | Type | Commands | Description |
|---|---|---|---|
| `enable_process_tail` | boolean | `enable-process-tail`, `disable-process-tail` | Controls whether future managed starts open a separate shell tailing the launched process log. |

This file is generated and local to the developer machine. It should not be
used to configure demo profiles or container definitions.

## Related Commands

```bash
opamp-cli status
opamp-cli list
opamp-cli clear-logs
opamp-cli dev-containers
OPAMP_DEMO=true opamp-cli demo
```

`status` shows the effective config paths and managed process state. `list`
shows configured container starts when any are available. `clear-logs` removes
CLI-managed logs plus log files discovered from the effective OpAMP config and
demo profile defaults.

## Repository Virtual Environment Setup

`opamp-cli setup-venv` creates or updates the default repository-level Python
environment:

```text
.venv
```

The command also installs repository tooling:

- root `requirements.txt`
- editable local Python components with `dev` extras
- Python build tooling: `pip`, `setuptools`, `wheel`, `build`, and `hatchling`
- Node tooling packages through `npm install`

After a successful setup in an interactive terminal, the CLI prompts to open a
shell with the virtual environment activated. Type `exit` in that shell to
return to the original terminal session.

Options:

| Option | Description |
|---|---|
| `--venv <path>` | Override the environment directory. Relative paths resolve from the repository root. |
| `--dry-run` | Print planned commands without creating the environment or installing packages. |
| `--skip-node` | Skip Node tooling installs. |

The full tooling inventory is maintained in
[`../../docs/dev/tooling.md`](../../docs/dev/tooling.md).
