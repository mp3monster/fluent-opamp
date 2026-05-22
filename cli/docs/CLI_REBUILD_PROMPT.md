# OpAMP CLI Rebuild Prompt

## Purpose

Use this document as a prompt to recreate the `opamp-cli` component from scratch if needed.

This prompt is intentionally implementation-oriented. It includes:

- required behavior
- folder layout
- packaging and deployment needs
- documentation deliverables
- test expectations
- runtime artifact expectations

## Prompt

Create a standalone `cli/` component for the OpAMP repository.

The CLI should be a Python package named `opamp-cli` with console entrypoint `opamp-cli`.
Its purpose is to provide a guided local operator workflow for launching, stopping, inspecting,
and script-generating commands for the OpAMP server, config service, catalog UI, broker, simulator,
and client utilities.

The implementation should be designed so that:

1. it is easy to extend with new launchable components
2. it is easy to add new command parameters or action variants
3. the guided menu order is explicit and stable
4. the CLI can be packaged and deployed independently from the provider/config-service/catalog-service/broker

## Required Folder Structure

Create the component with this structure:

```text
cli/
  README.md
  pyproject.toml
  requirements.txt
  main.py
  __init__.py
  __main__.py
  docs/
    README.md
    IMPLEMENTATION_PROMPT.md
    CLI_EXTENSION_GUIDE.md
    CLI_REBUILD_PROMPT.md
  runtime/
    .gitkeep
  src/
    opamp_cli/
      __init__.py
      __main__.py
      main.py
      version.json
  tests/
    conftest.py
    test_main_unit.py
    test_main_e2e.py
```

Notes:

- `cli/main.py` is a compatibility launcher for `python cli/main.py`
- `cli/src/opamp_cli/main.py` contains the real implementation
- `cli/runtime/` is for generated state and logs, not checked-in runtime payloads except `.gitkeep`

## Packaging Requirements

Implement packaging with:

- `pyproject.toml`
- build backend: `hatchling`
- package name: `opamp-cli`
- console script:
  - `opamp-cli = "opamp_cli.main:main"`

Runtime dependencies:

- `prompt_toolkit>=3.0`

Dev/test dependency:

- `pytest>=8.0`

Add pytest config so the CLI component naturally runs its own tests:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

## Core CLI Behavior

The CLI must support both direct command execution and a guided operator flow.

### Required top-level modes

1. Interactive mode
   - entered when no arguments are supplied
   - presents `opamp>` prompt
2. Direct command mode
   - entered when command arguments are supplied
3. Script generation mode
   - entered when first token is `script`

### Script generation rule

If the first token is `script`, interpret the command as:

```text
script <output_name> <command...>
```

Behavior:

- generate an OS-native script
- Windows extension: `.cmd`
- non-Windows extension: `.sh`
- plain names should default under `scripts/`
- no command validation is required in script mode

### Immediate execution rule

If the first token is not `script`, execute the command immediately.

### Python script normalization

If the command begins with a `.py` or `.pyw` path and is not already prefixed by a Python launcher,
automatically prefix it with Python so direct runs like `cli/main.py --help` work.

### Help commands

Support:

- `help`
- `-h`
- `--help`

## Guided Command Requirements

The CLI must support guided `start` and `stop` commands.

### Required guided targets

For `start`:

- `Server`
- `Config Catalog UI`
- `Config Service`
- `Broker`
- `Simulator`
- `Fluent Bit client`
- `Fluentd client`

For `stop`:

- `Server`
- `Broker`
- `Simulator`
- `Config Service`
- `Fluent Bit client`
- `Fluentd client`
- `All clients`

### Important design rule

The start/stop menus must be driven by explicit ordered action identifiers, not by separately maintained label lists.

Implement constants similar to:

```python
GUIDED_START_ACTION_ORDER = [...]
GUIDED_STOP_ACTION_ORDER = [...]
GUIDED_ACTION_ALIASES = {...}
```

The order is user-visible and position-sensitive because it defines:

- numbered menu ordering
- selection by number
- examples in help/docs
- implicit operator expectations

Add code comments that make this explicit.

### Alias support

Direct guided commands should work both by full label and by aliases.

Examples:

- `start server`
- `start config service`
- `start catalog`
- `stop broker`
- `stop clients`

### Availability rule for catalog UI

`Config Catalog UI` should only appear when catalog sources are configured in `config/opamp.json`.
If required, the CLI should generate a temporary runtime config under `cli/runtime/` to enable catalog launch without mutating the repo config.

## Process Management Requirements

The CLI must manage long-running background processes.

### Runtime artifacts

Use:

- `cli/runtime/managed_processes.json`
- `cli/runtime/settings.json`
- `cli/runtime/logs/`

### Managed process behavior

When starting a background-managed process:

1. create a log file immediately
2. write a launch header into the log
3. launch the process in background
4. wait briefly and confirm it is still alive
5. optionally run an HTTP readiness probe for services with a URL
6. record the process only after the startup check succeeds

If startup fails:

- write failure details to the log
- print a useful error
- do not add a managed-process record

### Status command

Provide:

- `status`

It should print:

- settings file path
- state file path
- log directory path
- process tailing enabled/disabled
- each recorded process with PID, status, cwd, start time, and log path

### Stop behavior

Support:

- HTTP shutdown where appropriate
- recorded PID termination where appropriate
- shell-based multi-client stop where appropriate

## Process Tailing Feature

Provide:

- `enable-process-tail`
- `disable-process-tail`

When enabled:

- each managed process start should attempt to open a new terminal window tailing that process log
- use best-effort shell spawning
- if no terminal launcher is available, warn but do not fail the process start

Persist this setting in:

- `cli/runtime/settings.json`

## Autocomplete Requirements

Preferred autocomplete:

- `prompt_toolkit`

Fallbacks:

- `readline` when available
- built-in Windows TTY fallback when `prompt_toolkit` is unavailable

Autocomplete behavior:

- top-level commands should be suggested in interactive mode
- `start` and `stop` should have context-aware suggestions
- path completion should be supported for script/file-like arguments
- avoid suggesting raw wrapper-script filenames as guided menu choices

## Launch Behavior Requirements

The CLI should prefer launching components directly rather than using legacy repo wrapper scripts.

Expected direct-launch style:

- provider via `python -m opamp_provider.server`
- config-service via `python -m config_service`
- broker via `python -m opamp_broker.broker_app`
- clients via direct consumer modules
- simulator via the simulator Python launcher

Use `PYTHONPATH` augmentation where necessary.

## Deployment and Packaging Requirements

The CLI is a separate deployable component.

The implementation and docs must reflect that:

- provider wheel builds may warn if the CLI is not present
- config-service standalone wheel builds may warn if the CLI is not present
- catalog-service standalone wheel builds may warn if the CLI is not present
- broker deployment packaging may warn if the CLI is not present

The CLI itself should not assume it is bundled inside those components.

Documentation must clearly distinguish:

- component runtime commands such as `opamp-provider`
- the operator launcher command `opamp-cli`

## Documentation Requirements

Create and maintain the following documentation.

### 1. `cli/README.md`

Must describe:

- purpose of the CLI
- how to start it
- direct run methods
- installed command usage
- basic commands
- interactive examples
- autocomplete behavior
- Windows notes
- runtime files

### 2. `cli/docs/README.md`

Must act as a small index of CLI component docs.

### 3. `cli/docs/IMPLEMENTATION_PROMPT.md`

Must preserve a phased implementation summary for the CLI’s original creation path.

### 4. `cli/docs/CLI_EXTENSION_GUIDE.md`

Must explain:

- component layout
- runtime dependencies
- internal architecture
- how guided actions work
- how to add a new component
- how to add new parameters
- which data structures are position-sensitive
- at least one worked example

### 5. `cli/docs/CLI_REBUILD_PROMPT.md`

Must be a prompt for recreating the CLI from scratch.

### Code-to-doc link requirement

The main implementation file should include a header comment/docstring reference to:

- `cli/docs/CLI_EXTENSION_GUIDE.md`

## Testing Requirements

Provide both unit tests and end-to-end tests.

### Unit tests

Cover:

- script directive parsing
- Python script normalization
- shell-safe command reconstruction from argv
- ordered action materialization
- alias matching
- catalog runtime config generation
- process-tail settings persistence
- stable start/stop action order

### End-to-end tests

Run the real CLI process using:

- `python cli/main.py ...`

Cover:

- `--help`
- `status`
- direct command execution
- script generation
- invalid guided target handling

Keep E2E tests non-destructive:

- do not launch long-running real services unless explicitly mocked or isolated
- use temporary directories for generated scripts

## Worked Example Requirement

The extension documentation must include a concrete worked example showing how to add a new launchable component such as:

- `Catalog Service`

The example must include:

- adding ordered action IDs
- adding aliases
- adding start action wiring
- adding stop action wiring
- updating docs/tests

## Quality Requirements

Use these coding conventions:

- copyright header on source and test files
- ASCII by default
- concise comments only where they add clarity
- stable naming for guided action IDs
- explicit code comments wherever position/order is important

## Success Criteria

The recreation is complete when:

1. `python cli/main.py --help` works
2. `python -m opamp_cli` works
3. `opamp-cli` works after install
4. `start` / `stop` guided actions are ordered and alias-driven
5. `status`, `enable-process-tail`, and `disable-process-tail` work
6. managed process state/log files are written under `cli/runtime/`
7. docs are present and internally consistent
8. unit tests and E2E tests pass
