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
- `docs/`: component-specific documentation and implementation notes
- `src/opamp_cli/`: implementation package
- `runtime/`: generated runtime metadata, process state, and log files
- `pyproject.toml`: packaging metadata and console entrypoint
- `requirements.txt`: runtime requirements

## Start the CLI Tool

From repository root, choose one of the following:

### Option 1: Run module directly (no install)

```bash
python3 cli/main.py
```

### Option 2: Run package module

```bash
PYTHONPATH=cli/src python3 -m opamp_cli
```

### Option 3: Use compatibility launcher

```bash
python3 -m cli
```

### Option 4: Install editable package and use command

```bash
python3 -m pip install -e cli
opamp-cli
```

## Documentation

- [docs/README.md](/mnt/d/dev/opamp/cli/docs/README.md)
- [docs/CLI_EXTENSION_GUIDE.md](/mnt/d/dev/opamp/cli/docs/CLI_EXTENSION_GUIDE.md)
- [docs/CLI_REBUILD_PROMPT.md](/mnt/d/dev/opamp/cli/docs/CLI_REBUILD_PROMPT.md)

## Basic Usage

- Guided multi-stage flow:
  - Type `start` in interactive mode, then choose what to start
    (for example `server`, `config catalog ui`, `config service`, `broker`, `simulator`, `fluentbit client`, `fluentd client`).
  - Type `stop` in interactive mode, then choose what to stop.
  - Type `restart` in interactive mode, then choose what to restart.
  - You can also run guided actions directly on one line, for example `start server`, `stop config service`, or `restart server`.
  - Type `status` in interactive mode to list managed processes, PID liveness, and log paths.
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
opamp-cli enable-process-tail
```

Guided examples:

```text
opamp-cli start server

opamp-cli
opamp> start config service
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
