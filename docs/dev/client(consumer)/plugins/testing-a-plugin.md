# Testing A Plugin

Plugin tests should make three things boring:

1. the plugin can be discovered
2. the plugin config block is processed correctly
3. the client behaves correctly in both supervisor and observer mode

If those are covered, most startup failures become straightforward to diagnose.

## Where Tests Live

For in-repo plugins, use the existing layout:

```text
consumer/tests/fluentbit/
consumer/tests/fluentd/
consumer/tests/elastic_agent/
consumer/tests/simulator/
```

For a new in-repo plugin, create a matching folder:

```text
consumer/tests/my_agent/
```

Shared behavior stays directly under `consumer/tests/`. Existing shared tests
worth reading before adding a plugin are:

- `consumer/tests/test_plugin_loader.py`
- `consumer/tests/test_client_plugin_e2e.py`
- `consumer/tests/test_config.py`
- `consumer/tests/test_client_runtime_strategy.py`
- `consumer/tests/test_startup_banner.py`

External plugin packages should keep their own unit tests in their own
repository. If they need to prove compatibility with this repo's deployment
container, add a small integration fixture or example under
`tests/test-containers/` rather than hiding it in the package.

## Where Test Configs Belong

Prefer generated temporary config in unit tests. The existing plugin loader and
plugin config tests build JSON with `tmp_path`, write it to a temporary
`opamp.json`, and point `OPAMP_CONFIG_PATH` or `--config-path` at that file.
That approach keeps test cases isolated and avoids accidental coupling to a
developer's local config.

Use stable checked-in config files only when they are scenario fixtures:

- `tests/opamp.json` for broad default consumer examples
- `tests/opamp-consumer-observer.json` for observer-mode examples
- `tests/logstash/` for Elastic Agent plus Logstash scenarios
- `tests/test-containers/.../examples/` for deployment container examples

Avoid adding plugin test configs to the repo root or `config/` unless the file
is meant to be a default operator-facing example.

## Discovery Tests

Start with tests like `consumer/tests/test_plugin_loader.py`.

Cover:

- no plugin found gives a useful error
- configured plugin builds a registry entry
- installed entry point can be overridden by config
- disabled config entry suppresses a matching installed entry point
- import failures are logged with `service_type` and entry point

These tests do not need a real agent process.

## Config Hook Tests

Add config hook coverage beside the plugin or in `consumer/tests/test_config.py`
when the behavior is shared.

Cover:

- `consumer.<service_type>` calls `process_consumer_config(...)`
- relative paths resolve from the JSON config directory
- environment variable overrides work, when your plugin supports them
- invalid plugin-specific values fail early with a useful message

Elastic Agent's config tests are a good reference because they exercise nested
config and path resolution.

## Runtime Strategy Tests

Every plugin should have explicit thinking around both modes:

- supervisor: does the launch command match the agent?
- observer: does the detection regex find the external process?

For plugins using the shared lifecycle machinery, you usually do not need to
retest every detail of `ClientSupervisorMixin` or `ClientObserverMixin`.
Instead, test that your client sets the right runtime fields:

- `_runtime_agent_command`
- `_runtime_config_flag`
- `_heartbeat_paths`
- `agent_config_path`
- `agent_additional_params`
- `process_tracking`
- `process_detection_regex`

If your plugin overrides lifecycle behavior directly, add focused tests for
launch, terminate, restart, and failure logging.

## Entrypoint E2E Tests

`consumer/tests/test_client_plugin_e2e.py` runs the real unified consumer
router in a subprocess with temporary fake plugins. That is the model to use
when you need to prove the command-line path really routes to your plugin.

Good E2E assertions include:

- the selected plugin ran
- other configured plugins did not run
- the active config was injected
- startup logs identify the selected `service_type` and entry point

## Verification Commands

For a normal plugin doc/code change, run at least:

```bash
pytest -q consumer/tests/test_plugin_loader.py
pytest -q consumer/tests/test_config.py
pytest -q consumer/tests/test_client_plugin_e2e.py
pytest -q consumer/tests/my_agent
```

For a broader change that touches shared bootstrap or lifecycle behavior, run:

```bash
pytest -q consumer/tests
```

When local socket tests fail under a restricted sandbox, rerun in a normal local
shell. Some tests intentionally open loopback sockets.

