# OpAMP CLI Extension Guide

## Purpose

This document explains how the `opamp-cli` component is structured, how it executes and manages utilities, and how to extend it safely.

The canonical implementation lives in:

- [main.py](/mnt/d/dev/opamp/cli/src/opamp_cli/main.py)

## Component Layout

- `cli/src/opamp_cli/main.py`
  Main implementation for command parsing, guided actions, process management, and interactive mode.
- `cli/src/opamp_cli/__main__.py`
  Package entrypoint for `python -m opamp_cli`.
- `cli/main.py`
  Compatibility launcher for `python cli/main.py`.
- `cli/pyproject.toml`
  Packaging metadata and `opamp-cli` console entrypoint.
- `cli/requirements.txt`
  Runtime dependency list.
- `cli/runtime/`
  Generated state:
  - `managed_processes.json`
  - `settings.json`
  - `logs/`

## Runtime Dependencies

- Python `>=3.10`
- `prompt_toolkit>=3.0`
  Used for cross-platform interactive autocomplete.

Optional platform-specific fallbacks:

- `readline`
  Used when available on non-Windows systems if `prompt_toolkit` is unavailable.
- `msvcrt`
  Used for the built-in Windows TTY fallback reader.

Standard-library features used heavily:

- `subprocess`
- `pathlib`
- `json`
- `urllib.request`
- `shlex`
- `os`
- `time`

## High-Level Flow

### 1. Entry

`main(argv)` decides between:

- interactive REPL when no arguments are supplied
- direct command execution when arguments are provided
- guided `start` / `stop` execution when the command begins with those intents

### 2. Non-guided commands

`_handle_command(...)` processes:

- `help`
- `status`
- `enable-process-tail`
- `disable-process-tail`
- `script <name> <command...>`
- everything else as immediate shell execution

### 3. Guided commands

Guided commands use:

- `_start_actions()`
- `_stop_actions()`
- `_execute_guided_action(...)`

Each action is represented as a dictionary with:

- `id`
- `kind`
- `label`
- additional fields required by the action kind

Supported action kinds today:

- `background_start`
- `simulator_start`
- `shell`
- `stop_recorded`

### 4. Managed processes

Long-running background starts are:

- launched with `subprocess.Popen`
- written to `cli/runtime/logs/*.log`
- verified with early liveness and optional HTTP readiness checks
- recorded in `cli/runtime/managed_processes.json`

## The Most Important Extension Rule

The start/stop menus are now driven by ordered action identifiers, not by separately maintained label lists.

Code references:

- [main.py](/mnt/d/dev/opamp/cli/src/opamp_cli/main.py#L48)
- [main.py](/mnt/d/dev/opamp/cli/src/opamp_cli/main.py#L343)

The important constants are:

- `GUIDED_START_ACTION_ORDER`
- `GUIDED_STOP_ACTION_ORDER`
- `GUIDED_ACTION_ALIASES`

These are intentionally position-sensitive.

That means the order controls:

- menu numbering shown to the user
- which action is selected by menu number
- the order shown in help text and examples
- expectations in tests and documentation

If you reorder one of these lists, also update:

- CLI help examples
- `cli/README.md`
- tests that assume menu order

## How Start/Stop Actions Are Built

### Start actions

`_start_actions()` does this:

1. Collect repo/config context.
2. Build an `action_map` keyed by stable action ID.
3. Skip unavailable actions, such as catalog UI when catalog sources are absent.
4. Materialize the visible menu order through `_materialize_ordered_actions(...)`.

### Stop actions

`_stop_actions()` follows the same pattern:

1. Build an `action_map`.
2. Define per-action stop behavior.
3. Materialize the visible order from `GUIDED_STOP_ACTION_ORDER`.

This is the main pattern to preserve when extending the CLI.

## How Aliases Work

Aliases are now keyed by stable action ID rather than inferred only from labels.

Example:

- `config_service`
  - `config`
  - `cfg`
  - `config service`
  - `config-service`

This means you can change a visible label with less risk of breaking direct command usage, as long as the action ID and alias set remain stable.

## Worked Example: Add a New `Catalog Service` Start/Stop Target

This example shows the recommended approach for adding a new component that can be started in the background and stopped from recorded PID state.

### Step 1. Add stable IDs to the ordered lists

In [main.py](/mnt/d/dev/opamp/cli/src/opamp_cli/main.py), update:

```python
GUIDED_START_ACTION_ORDER = [
    "server",
    "catalog_ui",
    "catalog_service",
    ...
]

GUIDED_STOP_ACTION_ORDER = [
    "server",
    "catalog_service",
    ...
]
```

If exact menu position matters, insert the new ID at the desired location.

### Step 2. Add aliases

```python
GUIDED_ACTION_ALIASES = {
    ...
    "catalog_service": ["catalog service", "catalog-service", "catcfg"],
}
```

### Step 3. Add the start action to `_start_actions()`

Add a new `action_map["catalog_service"] = ...` entry using `_background_start_action(...)`.

Typical fields:

```python
action_map["catalog_service"] = _background_start_action(
    action_id="catalog_service",
    label="Catalog Service",
    command_text=...,
    argv=...,
    cwd=...,
    env=...,
    launch_url="http://127.0.0.1:8090/catalog",
    readiness_url="http://127.0.0.1:8090/catalog",
)
```

### Step 4. Add the stop action to `_stop_actions()`

If the process is recorded in `managed_processes.json`, use:

```python
action_map["catalog_service"] = _stop_recorded_action(
    label="Catalog Service",
    record_names=["Catalog Service"],
)
```

### Step 5. Update user docs

Update:

- `cli/README.md`
- this extension guide
- help text in `main.py` if the examples should mention the new component

## How To Add Parameters To An Existing Utility

There are two common patterns.

### Pattern 1: fixed parameters in one guided action

Example: a start target always needs one config path.

Update the action builder in `_start_actions()`:

- change `args=[...]`
- change `env={...}`
- update `launch_url` or `readiness_url` if needed

### Pattern 2: future prompted variants

If you want multiple launch variants, prefer:

1. one stable action ID per visible target
2. a follow-up resolver/helper that derives `args` from a small option set

Avoid encoding variant logic by fragile string matching on display labels.

## Current Implicit Positional Relationships

These are the places where position matters today:

### 1. `GUIDED_START_ACTION_ORDER`

The list position is the interactive menu number.

### 2. `GUIDED_STOP_ACTION_ORDER`

Same rule for the stop menu.

### 3. Help and README examples

The CLI now prefers label-based examples such as:

- `start server`
- `start config service`

This is safer than numeric examples because numeric examples can drift when menu order changes.

## Recommended Extension Checklist

When adding a new launchable component:

1. Add or update the stable action ID.
2. Add aliases.
3. Add the action builder entry to the appropriate action map.
4. Confirm the action appears in the intended menu position.
5. Confirm direct command matching works, for example `start <name>`.
6. Update help text and `cli/README.md` if the new component is user-facing.
7. Add or update tests.

## Current Review Outcome

This review resulted in one structural change:

- start/stop labels and actions now share one ordered action catalog path, which makes future extension safer and more obvious

This keeps the CLI in a single file for now, but with clearer internal extension seams.
If the command catalog grows significantly, the next clean split would be:

- `catalog.py` for action definitions/order
- `processes.py` for state/log/process management
- `interactive.py` for prompt/completion behavior
