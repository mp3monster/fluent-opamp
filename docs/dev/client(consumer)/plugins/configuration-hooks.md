# Configuration Hooks

The base consumer config file has a shared `consumer` object. Some settings are
common to every plugin, and some are specific to one agent type.

Common settings belong directly under `consumer`:

```json
{
  "consumer": {
    "server_url": "http://localhost:8080",
    "transport": "http",
    "service_type": "my_agent",
    "agent_config_path": "./my-agent.yml",
    "agent_additional_params": []
  }
}
```

Plugin-specific settings should live in a nested block named after the
normalized service type:

```json
{
  "consumer": {
    "service_type": "my_agent",
    "my_agent": {
      "api_host": "localhost",
      "api_port": 19090,
      "status_timeout_seconds": 5
    }
  }
}
```

That nested block is processed by the plugin, not by a growing list of
agent-specific branches in `config.py`.

## The Hook Name

If the active config contains `consumer.<service_type>`, the consumer looks for
this function on the selected plugin module:

```python
def process_consumer_config(
    context: ConsumerPluginConfigContext,
) -> Mapping[str, Any] | None:
    ...
```

The hook receives a `ConsumerPluginConfigContext` with:

- `service_type`: normalized plugin key, such as `my_agent`
- `section_name`: the nested config section name
- `raw_section`: the nested plugin config block
- `consumer_raw`: the full raw `consumer` mapping
- `config_path`: path to the JSON file being loaded

Return a mapping of `ConsumerConfig` attribute names to values. The loader will
apply those attributes to the `ConsumerConfig` instance and log each loaded
plugin config value.

## Example Hook

```python
from __future__ import annotations

from typing import Any

from opamp_consumer.plugin_config import (
    ConsumerPluginConfigContext,
    resolve_optional_path_from_config,
)


def process_consumer_config(
    context: ConsumerPluginConfigContext,
) -> dict[str, Any]:
    raw = context.raw_section
    return {
        "my_agent_api_host": str(raw.get("api_host") or "localhost"),
        "my_agent_api_port": int(raw.get("api_port") or 19090),
        "my_agent_home_path": resolve_optional_path_from_config(
            raw_value=raw.get("home_path"),
            config_path=context.config_path,
        ),
    }
```

Use `resolve_optional_path_from_config(...)` for plugin-owned paths. It resolves
relative paths from the config file directory, which is much friendlier than
resolving from whatever process working directory happens to be active.

## How The Hook Is Found

The hook discovery order is:

1. module named by the matching `consumer.plugins` entry
2. module discovered from the installed `opamp_consumer.plugins` entry point
3. conventional built-in module name:
   `opamp_consumer.<service_type>.client`

This lets external packages work cleanly, while still keeping built-in plugins
simple.

## Keep Common And Plugin Config Separate

Use common `ConsumerConfig` fields when the concept is shared by all plugins:

- `server_url`
- `transport`
- `tls`
- `server-authorization`
- `agent_config_path`
- `agent_additional_params`
- `processTracking`
- `processDetectionRegex`
- `heartbeat_frequency`
- `agent_capabilities`
- `service_name`
- `service_namespace`

Use a plugin-specific block when the field is only meaningful to your agent:

- CLI executable path
- daemon home directory
- custom status API host/port
- custom timeout
- credentials for a local agent API
- feature toggles that only your plugin understands

The rule of thumb is: if another plugin would need a paragraph explaining why
the setting exists, keep it in your nested plugin block.

## Document The Config

Add or update a plugin-specific page under `consumer/docs/plugins/`.

For a new plugin, create:

```text
consumer/docs/plugins/my-agent.md
```

Then link it from the "Plugin Configuration Pages" section of
`consumer/README.md`. Keep the operator-facing config details there, and keep
developer mechanics in this guide.

