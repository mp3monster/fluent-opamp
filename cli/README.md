# OpAMP CLI Component

This component provides a prompt-driven command tool for local OpAMP workflows.
Autocomplete support is provided via `prompt_toolkit` (cross-platform).
Its guided `start`, `stop`, and `restart` flows run components directly instead of depending on repo wrapper scripts.
Guided starts record launched PIDs in `cli/runtime/managed_processes.json`.
CLI-managed process logs are written under `cli/runtime/logs/`.
Managed process entries are only recorded after the launched utility survives the CLI startup liveness check.
The CLI can also open a separate tail shell for managed process logs when `enable-process-tail` is enabled.

## Structure

- `README.md`: component overview and startup guide
- `scripts/`: shell-specific helper scripts for alias / macro setup
- `docs/`: component-specific documentation and implementation notes
- `src/opamp_cli/`: implementation package
- `runtime/`: generated runtime metadata, process state, and log files
- `pyproject.toml`: packaging metadata and console entrypoint
- `requirements.txt`: runtime requirements

## How To Run

You can run the CLI either from the repository root or from inside the `cli/` directory.

From repository root:

- `python3 cli/main.py`
- `PYTHONPATH=cli/src python3 -m opamp_cli`
- `python3 -m cli`
- `python3 -m pip install -e cli && opamp-cli`

From the `cli/` directory:

- `python3 main.py`
- `PYTHONPATH=src python3 -m opamp_cli`
- `python3 -m pip install -e . && opamp-cli`

## Shell Setup

If you want a persistent shell shortcut for `opamp-cli` and `opamp`, use the helper script for your shell:

Linux / macOS shells:

```bash
./cli/scripts/install_cli_aliases.sh
```

Windows `cmd.exe`:

```cmd
cli\scripts\install_cli_aliases.cmd
```

Windows PowerShell:

```powershell
.\cli\scripts\install_cli_aliases.ps1
```

What these do:

- `install_cli_aliases.sh`: updates `~/.bashrc` and `~/.zshrc`
- `install_cli_aliases.cmd`: writes a `doskey` macro file and shows the optional `AutoRun` command
- `install_cli_aliases.ps1`: updates the current PowerShell profile and legacy Windows PowerShell profile when needed

All three create:

- `opamp-cli`
- `opamp`

Both shortcuts run the compatibility entrypoint:

- `python .../cli/main.py`

## Documentation

- [docs/README.md](/mnt/d/dev/opamp/cli/docs/README.md)
- [docs/CLI_EXTENSION_GUIDE.md](/mnt/d/dev/opamp/cli/docs/CLI_EXTENSION_GUIDE.md)
- [docs/CLI_REBUILD_PROMPT.md](/mnt/d/dev/opamp/cli/docs/CLI_REBUILD_PROMPT.md)

## Basic Usage

- Guided multi-stage flow:
  - Type `start` in interactive mode, then choose what to start
    (for example `server`, `config catalog ui`, `config service`, `broker`, `simulator`, `fluentbit client`, `fluentd client`).
  - Type `stop` in interactive mode, then choose what to stop.
  - `stop all` stops all CLI-managed recorded processes.
  - Type `restart` in interactive mode, then choose what to restart.
  - You can also run guided actions directly on one line, for example `start server`, `stop config service`, or `restart server`.
  - Type `status` in interactive mode to list the effective OpAMP config file,
    config load status, managed processes, PID liveness, and log paths.
  - Type `list` in interactive mode to display the current command hierarchy and guided options (including flag-gated options).
  - Type `enable-process-tail` to open a separate tail shell for each future managed start log.
  - Type `disable-process-tail` to turn that behavior off again.
  - `Config Catalog UI` is shown when catalog sources are configured in `config/opamp.json`. The CLI writes a temporary runtime config under `cli/runtime/` so the catalog can be launched without editing the repo config.
- If the first word is `script`, a script file is generated for the current OS:
  - Linux/macOS: `.sh`
  - Windows: `.cmd`
- Otherwise, the command is executed immediately.
- Direct Python script commands are supported. If a command starts with a `.py`/`.pyw` file path
  (for example `cli/main.py --help`), the CLI automatically runs it via Python.

Examples:

```text
script demo-start-clients python -m opamp_consumer.fluentbit_client
python -m pytest -s
cli/main.py --help
opamp-cli status
opamp-cli list
opamp-cli enable-process-tail
```

Guided examples:

```text
opamp-cli start server
opamp-cli stop all

opamp-cli
opamp> start config service
```

Demo consumer mode:

- Set `OPAMP_DEMO=true` to expose profile-based demo consumer actions in guided `start` and `stop`.
- Demo profiles are loaded from `cli/config/demo_consumer_profiles.json`.
- In interactive or direct CLI mode, `demo` acts as shorthand for `start demo consumers`.
- Each profile maps a logical profile name to:
  - simulator instances file
  - Fluent Bit OpAMP config + agent config
  - Fluentd OpAMP config + agent config
- CLI records profile-scoped PIDs in `cli/runtime/managed_processes.json`, so `stop` can terminate one demo profile independently.

Example:

```text
OPAMP_DEMO=true opamp-cli start
OPAMP_DEMO=true opamp-cli demo
OPAMP_DEMO=true opamp-cli stop "demo consumers script-defaults"
```

Type `exit` or `quit` to leave interactive mode.
Type `help` (or `-h` / `--help`) to print CLI usage and examples.
The process-tail preference is stored in `cli/runtime/settings.json`.

## Autocomplete

- Press `Tab` in interactive mode for suggestions.
- `start` and `stop` suggestions are context-aware, so the CLI offers guided targets like `Config Service` instead of unrelated global words.
- `start`, `stop`, and `restart` suggestions are context-aware, so the CLI offers guided targets like `Config Service` instead of unrelated global words.
- File and script arguments use path completion when `prompt_toolkit` is available.
- Direct `python cli/main.py` runs on Windows include a built-in Tab completion fallback even when `prompt_toolkit` is not installed.
- On Windows, install dependencies first so `prompt_toolkit` is available:

```bash
python -m pip install -e cli
```

## Windows Note

If PowerShell reports an error such as:

`Start-Process ... The system cannot find the file specified`

it usually means a `.py` file was being launched as if it were an executable.
Use `python cli/main.py` directly, or run it through this CLI which now auto-prefixes
direct `.py` commands with Python.
