# Broker Startup and Shutdown

This runbook describes how to start `opamp_broker`, stop it cleanly, and configure logging.

## Startup

### 1. Configure environment

Required Slack values:

- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_APP_TOKEN`

LLM planner value (recommended):

- `OPENAI_API_KEY` (used when `planner.llm_enabled` is true with default config)

Important API key mapping note:

1. The broker reads the key name defined by `planner.api_key_env_var`.
2. Default is `OPENAI_API_KEY`.
3. If you set `planner.api_key_env_var` to another name, `.env` must provide that exact env var.
4. There is no automatic aliasing between env var names.

Optional runtime/config values:

- `BROKER_CONFIG_PATH` (defaults to `./opamp_broker/config/broker.ui_responses.json` in the `opamp-cli` broker start action)

Use the helper setup script if needed:

- Linux/macOS: `./scripts/configure_slack.sh`
- Windows PowerShell: `.\scripts\configure_slack.ps1`

### 2. `.env` vs `broker.json`

The broker intentionally uses both an environment file and a JSON config file.

Use `.env` for:

1. Secrets and deployment-specific credentials.
2. Values that differ per machine/environment.
3. Environment variable wiring (`BROKER_CONFIG_PATH`, API key env vars).

Typical `.env` values:

- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_APP_TOKEN`
- `OPENAI_API_KEY`
- `BROKER_CONFIG_PATH`

Use `broker.json` for:

1. Broker runtime behavior and defaults.
2. Non-secret operational settings you want versioned/reviewed.
3. User-facing messages, timeouts, and planner/config paths.

Typical `broker.json` values:

- `broker.log_level`
- `messages.help`
- `messages.server_offline`
- `messages.slack_error_reply`
- `messages.ai_mode_off_ack_text`
- `mcp.request_timeout_seconds`
- `mcp.connection_mode`
- `mcp.startup_discovery_max_attempts`
- `mcp_server.enabled`
- `mcp_server.port`
- `planner.model`
- `paths.opamp_config_path`
- `paths.provider_port_override`

Why keep them separate:

1. Better security posture by keeping secrets out of committed config JSON.
2. Same `broker.json` can be reused across environments with different `.env` values.
3. Easier operations: rotate credentials without rewriting behavioral config.

### 3. Configure `broker.json`

The broker runtime config file is JSON and is loaded in this order:

1. `--config-path` CLI value (if provided)
2. `BROKER_CONFIG_PATH` environment variable (if set)
3. bundled default file: `opamp_broker/config/broker.ui_responses.json`

The file is merged with internal defaults, so you can provide a full file or a partial override.

If no config file is provided, the broker still starts using built-in defaults.
In that mode:

1. Runtime behavior falls back to default values from the loader.
2. OpAMP route derivation falls back to `http://localhost:8080` when no OpAMP config is found.
3. Planner falls back to deterministic rule-first mode if required AI key env var is missing.

Even with default config behavior, Slack credentials are still required for Slack mode:

- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_APP_TOKEN`

Recommended minimum values to set explicitly:

1. `paths.opamp_config_path`
2. `social_collaboration.implementation`
3. `planner.provider`, `planner.base_url`, and `planner.api_key_env_var` if you are not using default AI service settings

Bundled baseline example

The bundled file `opamp_broker/config/broker.ui_responses.json` is the versioned
baseline overlay that ships with the broker. The example below mirrors the
current bundled file contents so operators can see exactly which keys are
present out of the box.

Example `broker.json`:

```json
{
  "broker": {
    "name": "opamp-conversation-broker",
    "log_level": "DEBUG",
    "idle_timeout_seconds": 240,
    "sweeper_interval_seconds": 30,
    "send_idle_goodbye": true,
    "send_shutdown_goodbye": true
  },
  "slack": {
    "command_name": "/opamp",
    "app_mention_enabled": true,
    "dm_enabled": true
  },
  "social_collaboration": {
    "implementation": "slack"
  },
  "messages": {
    "idle_goodbye": "I've been idle for a while, so I've cleared my working context for this thread. Reply here to start again.",
    "shutdown_goodbye": "I'm going to bed now, so I'm clearing my working context for this thread. When I wake up, please remind me what you want to do.",
    "restart_notice": "I'm awake again, but I don't have my earlier working context for this thread. Tell me what you want to check.",
    "server_offline": "The OpAMP server is currently offline. Please try again shortly.",
    "immediate_ack_messages": ["ok", "let me think", "hmmmm", "ack", "working on it"],
    "slack_error_reply": "sorry, I stumbled, you might want to try that again",
    "ai_mode_off_ack_text": "Affirmative, Dave. I read you.",
    "help": "Try `/opamp help`, `/opamp tools`, `/opamp opstate`, or mention me with a question."
  },
  "paths": {
    "opamp_project_root": "../fluent-opamp",
    "opamp_config_path": "../fluent-opamp/config/opamp.json",
    "provider_port_override": 8070
  },
  "mcp": {
    "request_timeout_seconds": 30,
    "connection_mode": "auto",
    "protocol_version_attempts": ["2025-06-18", "2025-03-26"],
    "startup_discovery_max_attempts": 5,
    "startup_discovery_initial_backoff_seconds": 0.5,
    "startup_discovery_max_backoff_seconds": 5.0,
    "startup_discovery_backoff_multiplier": 2.0,
    "startup_discovery_jitter_seconds": 0.25
  },
  "mcp_server": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080,
    "path": "/mcp"
  },
  "planner": {
    "mode": "rule-first",
    "llm_enabled": true,
    "AIState": "on",
    "provider": "openai",
    "model": "gpt-5.3",
    "request_timeout_seconds": 30,
    "temperature": 0.0,
    "api_key_env_var": "OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "max_completion_tokens": 1024,
    "verify_max_completion_tokens_attempts": [64, 512],
    "max_execution_steps": 4,
    "prompts_config_path": "planner_prompts.json"
  }
}
```

Field reference:

1. `broker`
   Runtime behavior controls for logging level, idle timeout, and shutdown/idle message behavior.
2. `slack`
   Slack interaction behavior, including slash command name and whether mention/DM handlers are enabled.
3. `social_collaboration`
   Which social adapter to use at startup.
4. `messages`
   User-facing text for help, offline behavior, and lifecycle messages.
   `messages.ai_mode_off_ack_text` controls the response text for exact `AI Off` commands.
   `messages.slack_error_reply` is retained for config compatibility, but the broker now returns a fixed fallback sentence for unhandled exceptions: `sorry, I stumbled, you might want to try that again`.
5. `paths`
   File locations and route overrides used to discover OpAMP provider/consumer settings. `paths.opamp_config_path` is the key value for deriving MCP route URLs. `paths.provider_port_override` lets the broker replace the port in the derived provider base URL when the broker must call a different listener than the one declared in the OpAMP config.
6. `mcp`
   MCP client behavior, including connection strategy (`auto`/`json`/`sse`), protocol-version attempts, request timeout, and startup discovery retry/backoff controls.
7. `mcp_server`
   Optional broker-hosted MCP proxy listener for local desktop clients. When enabled, the broker exposes its own local `/mcp` endpoint and forwards supported MCP requests to the upstream provider MCP endpoint.
8. `planner`
   AI planner behavior (provider, model, timeout, temperature, token limits, API key env var, base URL, and prompts file path).

### Bundled `broker.ui_responses.json` field coverage

This section documents every field currently present in the bundled
`opamp_broker/config/broker.ui_responses.json` file.

#### `broker`

- `broker.name`
  Human-readable broker label bundled with the config. It is currently informational and not a primary runtime selector.
- `broker.log_level`
  Fallback log level used when no external logging config file overrides logging behavior.
- `broker.idle_timeout_seconds`
  Number of idle seconds before a thread-scoped session is expired.
- `broker.sweeper_interval_seconds`
  Interval between idle-session sweeper passes.
- `broker.send_idle_goodbye`
  Controls whether the broker posts the configured idle sign-off when a session expires.
- `broker.send_shutdown_goodbye`
  Controls whether the broker posts shutdown sign-off messages during graceful process termination.

#### `slack`

- `slack.command_name`
  Slash command name registered for the Slack app integration.
- `slack.app_mention_enabled`
  Enables handling for app-mention events.
- `slack.dm_enabled`
  Enables handling for direct-message conversations with the Slack app.

#### `social_collaboration`

- `social_collaboration.implementation`
  Social adapter selected at startup. Current supported value is `slack`.

#### `messages`

- `messages.idle_goodbye`
  Text posted when a session is expired for inactivity and `broker.send_idle_goodbye=true`.
- `messages.shutdown_goodbye`
  Text posted to active threads during graceful broker shutdown when `broker.send_shutdown_goodbye=true`.
- `messages.restart_notice`
  Bundled restart-era text. It is currently retained in config but is not emitted by the current runtime path.
- `messages.server_offline`
  Fallback user-facing message when the provider MCP server is unavailable during planning or execution.
- `messages.immediate_ack_messages`
  List of short phrases used to build randomized immediate acknowledgements while the broker continues processing a request.
- `messages.slack_error_reply`
  Retained for config compatibility. Unhandled exceptions still resolve to one fixed fallback sentence rather than variable per-config wording.
- `messages.ai_mode_off_ack_text`
  Reply used when a user issues the exact `AI Off` command and per-client AI mode switching is allowed.
- `messages.help`
  Default help text returned for help-oriented interactions.

#### `paths`

- `paths.opamp_project_root`
  Bundled project-root hint retained in config for operator context. It is not currently used by the runtime loader for route derivation.
- `paths.opamp_config_path`
  Primary OpAMP config file path used to derive provider routes such as the broker MCP endpoint.

#### `mcp`

- `mcp.request_timeout_seconds`
  Timeout applied to MCP HTTP operations.
- `mcp.connection_mode`
  Transport parsing strategy: `auto`, `json`, or `sse`.
- `mcp.protocol_version_attempts`
  Ordered MCP protocol versions attempted during client initialization.
- `mcp.startup_discovery_max_attempts`
  Maximum discovery retries during startup tool refresh.
- `mcp.startup_discovery_initial_backoff_seconds`
  Initial retry delay for startup discovery backoff.
- `mcp.startup_discovery_max_backoff_seconds`
  Maximum retry delay cap for startup discovery backoff.
- `mcp.startup_discovery_backoff_multiplier`
  Exponential multiplier applied between retry attempts.
- `mcp.startup_discovery_jitter_seconds`
  Random jitter added to discovery retry delays.

#### `planner`

- `planner.mode`
  Bundled planner mode label. It is currently descriptive only; active planner selection is driven by `planner.llm_enabled`, provider config validity, and API key availability.
- `planner.llm_enabled`
  Enables AI-backed planning when configuration is complete; otherwise runtime falls back to deterministic rule-first planning.
- `planner.AIState`
  Initial per-client AI mode. Supported semantics are `on`, `off`, and `disabled`, where `disabled` locks the UI toggle off entirely.
- `planner.provider`
  AI provider selector. Current runtime supports OpenAI-compatible behavior via the provider factory.
- `planner.model`
  Model name sent to the configured AI provider.
- `planner.request_timeout_seconds`
  Timeout for planner/provider requests.
- `planner.temperature`
  Sampling temperature for AI-backed planner requests.
- `planner.api_key_env_var`
  Environment variable name that holds the provider API key.
- `planner.base_url`
  Base URL for the provider API.
- `planner.max_completion_tokens`
  Response token budget for planner/model requests.
- `planner.verify_max_completion_tokens_attempts`
  Token budgets used for verification retries during startup AI-service checks.
- `planner.max_execution_steps`
  Upper bound for bounded multi-step planner/tool iteration in the runtime graph.
- `planner.prompts_config_path`
  Path to the external prompts JSON file. Relative paths resolve from the folder containing the broker config file being loaded.

### 4. Start the broker

Recommended startup commands:

- Preferred: `opamp-cli start broker`
- Stop: `opamp-cli stop broker`
- Status/log discovery: `opamp-cli status`
- Generate a reusable launcher script: `opamp-cli script broker-launch python -m opamp_broker.broker_app --config-path ./opamp_broker/config/broker.ui_responses.json`

If `opamp-cli` is not installed yet, you can run it from the repo:

- `PYTHONPATH=cli/src python3 -m opamp_cli start broker`
- `PYTHONPATH=cli/src python3 -m opamp_cli stop broker`
- `PYTHONPATH=cli/src python3 -m opamp_cli script broker-launch python -m opamp_broker.broker_app --config-path ./opamp_broker/config/broker.ui_responses.json`

The guided CLI starts the broker directly with:

- `python -m opamp_broker.broker_app`

The CLI-managed broker action sets:

- `PYTHONUNBUFFERED=1`
- `BROKER_CONFIG_PATH` (if not already set by the environment)

Runtime artifacts for CLI-managed broker runs live under `cli/runtime/`:

1. Process state: `cli/runtime/managed_processes.json`
2. Logs: `cli/runtime/logs/`

### 4a. Implementing custom script or OS-managed startup

If you want to run the broker under your own shell script, Windows service wrapper, `systemd` unit, Task Scheduler job, or similar OS-native launcher, build it around the broker module entrypoint instead of the retired repo-local wrapper scripts.

Required launch command:

- `python -m opamp_broker.broker_app`

Typical wrapper responsibilities:

1. Set the working directory to `agent_broker/` so relative paths resolve consistently.
2. Set `PYTHONUNBUFFERED=1` so logs flush promptly.
3. Set `BROKER_CONFIG_PATH` when you want a specific runtime config file.
4. Ensure required environment values are present:
   - `SLACK_BOT_TOKEN`
   - `SLACK_SIGNING_SECRET`
   - `SLACK_APP_TOKEN`
   - the API key env var named by `planner.api_key_env_var` (default `OPENAI_API_KEY`)
5. Ensure Python dependencies are already installed before launch.
6. Capture stdout/stderr into your chosen OS log destination.
7. Persist the process identifier or service handle if your platform needs it for later stop operations.

Recommended launch example:

- `python -m opamp_broker.broker_app --config-path ./opamp_broker/config/broker.ui_responses.json`

You can generate a starter script with the CLI and adapt it for your platform:

- `opamp-cli script broker-launch python -m opamp_broker.broker_app --config-path ./opamp_broker/config/broker.ui_responses.json`

### 4b. Implementing custom script or OS-managed shutdown

The broker does not expose a separate shutdown subcommand. Custom wrappers must stop the running broker process through the operating system or service manager.

Required shutdown behavior:

1. Send a graceful termination signal to the broker process.
2. Allow enough time for broker cleanup and Slack shutdown messaging.
3. Escalate to force termination only if graceful shutdown fails and your platform policy requires it.

Preferred shutdown mechanisms:

- Linux/macOS: send `SIGTERM` or `SIGINT`
- Windows service wrapper: request a normal process stop through the service manager first
- CLI-managed broker runs: `opamp-cli stop broker`

When designing your own stop script or service definition, make sure it can:

1. Find the running broker process or service instance reliably.
2. Wait for termination completion before reporting success.
3. Clean up any wrapper-owned PID/state files if you create them.
4. Preserve access to broker logs for post-stop troubleshooting.

### Deployment packaging note

Broker deployment packaging also checks whether the separate `opamp-cli` component is available.
If the CLI is not detected in the workspace or installed Python environment, the package scripts print
a warning so the deployment operator can decide whether the CLI should be installed alongside the broker.

Direct broker entrypoint examples:

- Help: `python -m opamp_broker.broker_app -h`
- Version: `python -m opamp_broker.broker_app --version`
- Explicit adapter: `python -m opamp_broker.broker_app --social-collaboration slack`

### 5. Broker CLI options

The broker supports runtime behavior selection from the command line.

Command format:

- `python -m opamp_broker.broker_app [OPTIONS]`

#### Option reference

1. `-h`, `--help`
   Prints broker CLI options and version metadata (version, git label, commit, commit date), then exits.
2. `--config-path <path>`
   Use an explicit runtime config file instead of `BROKER_CONFIG_PATH` or bundled defaults.
   Example: `--config-path ./opamp_broker/config/broker.ui_responses.json`
3. `--social-collaboration <name>`
   Selects the social collaboration adapter implementation.
   Default: `slack`
   Current supported value: `slack`
   Resolution precedence: CLI value, then `social_collaboration.implementation` from config, then default `slack`.
4. `--verify-startup <mode>`
   Runs startup connectivity checks and exits without entering the long-running broker event loop.
   Allowed values: `none`, `social`, `ai_svc`, `all`
   Default: `none`
   Exit code behavior in verification mode: `0` when all requested checks pass, `1` when any requested check fails.
5. `--version`
   Prints broker version string and exits.

#### Verification modes

1. `social`
   Verifies connection/authentication for the selected social collaboration adapter (Slack by default).
2. `ai_svc`
   Verifies AI service connectivity/authentication using planner settings (`planner.model`, `planner.base_url`, and API key env var).
3. `all`
   Runs both `social` and `ai_svc` verification checks.

#### Verification output behavior

1. Logs per-check success/failure details.
2. Logs a final verification summary event.
3. Exits immediately after checks complete.

#### Examples

- Normal broker startup:
  `python -m opamp_broker.broker_app`
- Start with explicit adapter:
  `python -m opamp_broker.broker_app --social-collaboration slack`
- Start with explicit runtime config:
  `python -m opamp_broker.broker_app --config-path ./opamp_broker/config/broker.ui_responses.json`
- Check social adapter connectivity only:
  `python -m opamp_broker.broker_app --verify-startup social`
- Check AI service connectivity only:
  `python -m opamp_broker.broker_app --verify-startup ai_svc`
- Check both social adapter and AI service:
  `python -m opamp_broker.broker_app --verify-startup all`

#### Common dependency error

If startup fails with:

- `ModuleNotFoundError: No module named 'aiohttp'`

Install/update dependencies in your active environment:

- `pip install -r requirements.txt`

### 6. LLM planner configuration

The broker planner processes user requests using an LLM and is constrained to
the MCP tools currently discovered from the provider.

Planner config fields (in broker config JSON):

The default values listed below are loader fallback defaults. The effective
runtime values may differ when you load the bundled
`opamp_broker/config/broker.ui_responses.json` overlay or your own override
file.

- `planner.llm_enabled` (default: `true`)
- `planner.provider` (default: `openai`)
- `planner.model` (default: `gpt-5.2`)
- `planner.request_timeout_seconds` (default: `30`)
- `planner.temperature` (default: `0.0`)
- `planner.api_key_env_var` (default: `OPENAI_API_KEY`)
- `planner.base_url` (default: `https://api.openai.com/v1`)
- `planner.max_completion_tokens` (default: `1024`)
- `planner.verify_max_completion_tokens_attempts` (default: `[64, 512]`)
- `planner.prompts_config_path` (default: `planner_prompts.json`)

`ai_svc` is a generic AI service label. By default it is configured for OpenAI.
To use a different compatible API, override:

- `planner.provider`
- `planner.base_url`
- `planner.api_key_env_var`

Supported provider values in this build:

- `openai` (default)
- `openai-compatible` / `openai_compatible` (alias of `openai`)
- `template` (scaffold only, intentionally non-runnable)

Ensure `.env` contains the env var named by `planner.api_key_env_var`.

Token settings:

1. `planner.max_completion_tokens` limits each planner call response budget.
2. `planner.verify_max_completion_tokens_attempts` controls retry token caps for startup verification.
3. Startup verification output includes configured token limits, attempt count, and token usage.

Prompt configuration:

1. Prompt text is loaded from the JSON file referenced by `planner.prompts_config_path`.
2. Each required prompt entry must be an object with:
   - `description` (documents where the prompt is used)
   - `text` (the actual prompt content)
3. Required prompt keys are:
   - `system_prompt`
   - `verification_prompt`
   - `slack_format_system_prompt`
4. Prompt strings do not have code defaults; if the prompt file is missing or invalid, broker startup fails with a configuration error.
5. `system_prompt` controls response style. The bundled prompt is tuned so capability questions like `tools` / `what can you do` return tool descriptions and argument hints, not only tool names.

For extension details, see:

- [AI Provider Connection Extension Guide](./ai_provider_connections.md)

Runtime behavior:

1. If `llm_enabled=true` and API key is present, LLM planner is used.
2. If API key is missing, broker falls back to deterministic rule-based planning.
3. Tool execution remains restricted to discovered MCP tool names.

### 7. MCP connectivity configuration

Broker MCP connectivity is fixed to the OpAMP provider MCP endpoint derived at runtime:

- `<provider_base_url>/mcp`

Recommended boundary:

1. Send desktop, agentic, or otherwise less-trusted MCP traffic to the broker's local `/mcp` proxy when `mcp_server.enabled=true`.
2. Keep the provider's richer HTTP APIs and direct MCP/SSE transports on an internal/trusted surface where possible.
3. This separation gives you one narrower endpoint to expose externally while reserving the full provider API surface for internal automation and operators.

If broker logs show `HTTP ... POST <provider_base_url>/mcp ... 404`, the provider is reachable but not exposing streamable HTTP MCP on `/mcp`.
With current provider builds, `/mcp` is exposed only when `provider.allow-mcp=true`. If you still see 404:

1. Restart the provider with the latest code/build.
2. Confirm provider config sets `provider.allow-mcp=true` where broker-to-provider MCP is required.
3. Confirm provider startup logs include MCP streamable HTTP exposure at `/mcp`.
4. Re-run broker startup or verification.

The broker uses provider MCP JSON-RPC calls in this sequence:

1. `initialize`
2. `tools/list`
3. `tools/call`

Supported MCP config fields:

As with planner settings, these defaults describe loader fallback values before
any bundled or operator-supplied config overlay is merged.

- `mcp.request_timeout_seconds` (default: `30`)
- `mcp.connection_mode` (default: `auto`, supported: `auto`, `json`, `sse`)
- `mcp.protocol_version_attempts` (default: `["2025-06-18", "2025-03-26"]`)
- `mcp.startup_discovery_max_attempts` (default: `5`)
- `mcp.startup_discovery_initial_backoff_seconds` (default: `0.5`)
- `mcp.startup_discovery_max_backoff_seconds` (default: `5.0`)
- `mcp.startup_discovery_backoff_multiplier` (default: `2.0`)
- `mcp.startup_discovery_jitter_seconds` (default: `0.25`)

Connection behavior notes:

1. `connection_mode=auto` negotiates JSON or SSE response handling based on provider response content type.
2. `connection_mode=json` forces JSON body parsing and uses `Accept: application/json`.
3. `connection_mode=sse` forces streamed SSE parsing and uses `Accept: text/event-stream`.
4. Broker MCP mode must match provider/server behavior:
   - if provider responds with streamable HTTP/SSE (`text/event-stream`), use `sse` or `auto`
   - if provider responds with plain JSON (`application/json`), use `json` or `auto`
5. Forcing the wrong mode can cause decode/parsing failures even when the provider is reachable.

## Clean Shutdown

Use graceful termination so in-memory session cleanup and Slack shutdown messaging can run.

### Preferred

- Press `Ctrl+C` in the terminal (sends `SIGINT`)
- Or send `SIGTERM` to the process
- Or use `opamp-cli stop broker`

### Avoid

- Forcing termination with `SIGKILL` / `kill -9`

### What graceful shutdown does

On `SIGINT`/`SIGTERM`, the broker:

1. Stops the session sweeper task.
2. Optionally sends the configured `messages.shutdown_goodbye` text to active Slack threads.
3. Clears active in-memory sessions.
4. Closes the MCP client.
5. Cancels background tasks and exits.

Control shutdown message behavior with:

- `broker.send_shutdown_goodbye` in your broker config JSON.

## Logging Setup and Overrides

Broker logging is configured in the main entrypoint via Python `logging.config.dictConfig`.
`broker_logging.json` therefore follows the standard Python logging dictionary schema:

- https://docs.python.org/3/library/logging.config.html#logging-config-dictschema

### Default logging config file

By default, the broker loads:

- `opamp_broker/broker_logging.json`

### Override logging config file path

Set this environment variable to use a different logging config file:

- `OPAMP_BROKER_LOGGING_CONFIG`

Examples:

- Linux/macOS:
  - `export OPAMP_BROKER_LOGGING_CONFIG=/path/to/custom_broker_logging.json`
- Windows PowerShell:
  - `$env:OPAMP_BROKER_LOGGING_CONFIG = "C:\path\to\custom_broker_logging.json"`

### Runtime log level override

The broker config file field below can set runtime root logger level:

- `broker.log_level` (for example `DEBUG`, `INFO`, `WARNING`, `ERROR`)

Precedence behavior:

1. If a logging config file is present (`broker_logging.json` or `OPAMP_BROKER_LOGGING_CONFIG` path), that file is used as-is and `broker.log_level` is ignored.
2. When this happens, the broker logs a warning that `broker.log_level` was ignored due to file-based logging config.
3. If no logging config file is found, broker falls back to built-in logging config and applies `broker.log_level`.

### If config loading fails

If the custom logging config path is missing or invalid, the broker falls back to a built-in console logging configuration.
