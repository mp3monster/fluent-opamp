#!/usr/bin/env python3
# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Prompt-driven command builder and executor for OpAMP workflows.

Behavior:
- If first token is `script`, generate an OS-native script file.
- Otherwise, execute the command immediately.

Extension guide:
- See `cli/docs/CLI_EXTENSION_GUIDE.md` for the component layout, action catalog
  conventions, and step-by-step guidance for adding new commands/components.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

TRUE_VALUES = {"1", "true", "yes", "on"}
SCRIPT_KEYWORD = "script"
DEFAULT_OUTPUT_DIR = Path("scripts")
CLI_RUNTIME_DIRNAME = "runtime"
CLI_LOG_DIRNAME = "cli"
CLI_PROCESS_STATE_FILENAME = "managed_processes.json"
CLI_SETTINGS_FILENAME = "settings.json"
CLI_COMPONENT_LOG_FILENAME = "opamp_cli.log"
CLI_SETTING_ENABLE_PROCESS_TAIL = "enable_process_tail"
DEFAULT_SERVER_PORT = 4320
DEFAULT_CATALOG_WEB_PORT = 8090
PROCESS_START_CHECK_DELAY_SECONDS = 1.0
PROCESS_READY_TIMEOUT_SECONDS = 5.0
PROCESS_READY_POLL_INTERVAL_SECONDS = 0.25
PROCESS_STOP_TIMEOUT_SECONDS = 20.0
PROCESS_STOP_POLL_INTERVAL_SECONDS = 0.25
PROCESS_TAIL_INITIAL_LINES = 50
STARTUP_FAILURE_MARKERS = (
    "address already in use",
    "traceback (most recent call last):",
    "modulenotfounderror:",
    "importerror:",
)
# The order of these identifiers is user-visible and position-sensitive.
# It defines:
# - the numbered menu order shown by interactive `start` / `stop`
# - the examples in help/docs
# - which item a user gets when they type a menu number
# Update docs/tests alongside any reordering.
GUIDED_START_ACTION_ORDER = [
    "server",
    "catalog_ui",
    "config_service",
    "broker",
    "simulator",
    "fluentbit_client",
    "fluentd_client",
]
GUIDED_STOP_ACTION_ORDER = [
    "server",
    "catalog_ui",
    "broker",
    "simulator",
    "config_service",
    "fluentbit_client",
    "fluentd_client",
    "all_clients",
]
GUIDED_ACTION_ALIASES = {
    "server": ["srv"],
    "catalog_ui": ["catalog", "catalog ui", "config catalog", "config catalog ui"],
    "config_service": ["config", "cfg", "config service", "config-service"],
    "broker": ["brk"],
    "simulator": ["sim"],
    "fluentbit_client": ["fluent bit", "fluentbit", "fluent bit client", "fb"],
    "fluentd_client": ["fluentd", "fluentd client", "fd"],
    "all_clients": ["clients"],
}
HELP_TEXT = """Usage:
  opamp-cli
  opamp-cli script <output_name> <command...>
  opamp-cli <command...>
  opamp-cli help
  opamp-cli status
  opamp-cli enable-process-tail
  opamp-cli disable-process-tail

Behavior:
  - Interactive `start`, `stop`, and `restart` commands open guided multi-stage choices.
  - `status` shows recorded managed processes, PID liveness, and log paths.
  - `enable-process-tail` opens a new shell tailing each managed process log after start.
  - If first token is `script`, generate an OS-native script file.
  - Otherwise execute the command immediately.
  - Direct `.py`/`.pyw` targets are auto-run via Python.

Examples:
  # Start server
  opamp-cli start server

  # Start config catalog UI
  opamp-cli start "config catalog ui"

  # Stop server
  opamp-cli stop server

  # Restart server
  opamp-cli restart server

  # Show managed process status
  opamp-cli status

  # Enable log tail windows for future managed starts
  opamp-cli enable-process-tail

Notes:
  - Interactive autocomplete uses prompt_toolkit when installed.
  - Fallback completion uses readline when available.
  - Guided actions can be run directly, for example `start config service`.
  - Guided start/stop/restart actions run components directly instead of relying on repo wrapper scripts.
  - Guided starts record launched PIDs in cli/runtime/managed_processes.json.
  - Process-tail shells are opened on a best-effort basis and may be unavailable in headless terminals.
"""

CLI_LOGGER_NAME = "opamp_cli"
_CLI_LOGGER: logging.Logger | None = None
_CLI_LOGGER_PATH: Path | None = None


def _dev_features_enabled() -> bool:
    """Return whether APP_ENABLE_DEV_FEATURES is enabled for this process."""
    raw_value = os.environ.get("APP_ENABLE_DEV_FEATURES", "")
    return str(raw_value or "").strip().lower() in TRUE_VALUES


def _is_windows() -> bool:
    """Return whether the current OS is Windows."""
    return os.name == "nt"


def _target_extension() -> str:
    """Return script extension for the current OS."""
    return ".cmd" if _is_windows() else ".sh"


def _repo_root() -> Path:
    """Return repository root for this CLI component."""
    return Path(__file__).resolve().parents[3]


def _cli_runtime_dir() -> Path:
    """Return CLI runtime metadata directory."""
    runtime_dir = (_repo_root() / "cli" / CLI_RUNTIME_DIRNAME).resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _cli_process_state_path() -> Path:
    """Return CLI-managed process state file path."""
    return (_cli_runtime_dir() / CLI_PROCESS_STATE_FILENAME).resolve()


def _cli_settings_path() -> Path:
    """Return CLI settings file path."""
    return (_cli_runtime_dir() / CLI_SETTINGS_FILENAME).resolve()


def _cli_log_dir() -> Path:
    """Return log directory used for CLI-started background processes."""
    log_dir = (_cli_runtime_dir() / "logs").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _cli_component_log_path() -> Path:
    """Return the component log file used for CLI lifecycle and error events."""
    return (_cli_log_dir() / CLI_COMPONENT_LOG_FILENAME).resolve()


def _get_logger() -> logging.Logger:
    """Return a configured component logger that writes to the CLI runtime log."""
    global _CLI_LOGGER, _CLI_LOGGER_PATH

    log_path = _cli_component_log_path()
    if _CLI_LOGGER is not None and _CLI_LOGGER_PATH == log_path:
        return _CLI_LOGGER

    logger = logging.getLogger(CLI_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover - defensive handler cleanup
            pass

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    _CLI_LOGGER = logger
    _CLI_LOGGER_PATH = log_path
    return logger


def _resolve_script_path(raw_name: str) -> Path:
    """Resolve output script path for current OS.

    Plain names are written under `scripts/`.
    """
    base = Path(raw_name.strip()).expanduser()
    if not base.name:
        raise ValueError("script name cannot be empty")

    target_ext = _target_extension()
    resolved = base.with_suffix(target_ext)
    if resolved.parent == Path("."):
        resolved = DEFAULT_OUTPUT_DIR / resolved.name
    return resolved.resolve()


def _render_script(command_text: str) -> str:
    """Render platform-specific script content."""
    launcher = "python" if _is_windows() else "python3"
    rendered_command = _normalize_python_script_command(
        command_text,
        launcher=launcher,
    )
    if _is_windows():
        return "\n".join([
            "@echo off",
            "setlocal",
            "",
            rendered_command,
            "",
        ])

    return "\n".join([
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        rendered_command,
        "",
    ])


def _write_script(output_path: Path, command_text: str) -> Path:
    """Write the generated script file to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_script(command_text), encoding="utf-8")
    if not _is_windows():
        output_path.chmod(output_path.stat().st_mode | 0o111)
    return output_path


def _split_script_directive(raw: str) -> tuple[str, str]:
    """Parse `script <name> <command...>` directive without command validation."""
    parts = raw.strip().split(maxsplit=2)
    if len(parts) < 3:
        raise ValueError("script mode requires: script <output_name> <command...>")
    _, output_name, command_text = parts
    return output_name, command_text.strip()


def _first_token(command_text: str) -> str:
    """Return first shell token or empty string when tokenization fails."""
    text = str(command_text or "").strip()
    if not text:
        return ""
    try:
        tokens = shlex.split(text, posix=not _is_windows())
    except ValueError:
        tokens = text.split()
    if not tokens:
        return ""
    return str(tokens[0] or "").strip().strip("\"'")


def _is_python_launcher(token: str) -> bool:
    """Return whether token is a Python interpreter command."""
    normalized = Path(str(token or "").strip().strip("\"'")).name.lower()
    return normalized in {"python", "python3", "py", "python.exe", "py.exe"}


def _is_python_script_target(token: str) -> bool:
    """Return whether token points to a Python source script."""
    cleaned = str(token or "").strip().strip("\"'")
    return Path(cleaned).suffix.lower() in {".py", ".pyw"}


def _normalize_python_script_command(command_text: str, *, launcher: str) -> str:
    """Prefix direct .py/.pyw invocations with a Python launcher."""
    first = _first_token(command_text)
    if not first:
        return command_text
    if _is_python_launcher(first):
        return command_text
    if not _is_python_script_target(first):
        return command_text
    return f"\"{launcher}\" {command_text}"


def _execute_command(command_text: str) -> int:
    """Execute command text immediately in a shell."""
    logger = _get_logger()
    normalized_command = _normalize_python_script_command(
        command_text,
        launcher=sys.executable,
    )
    logger.info("executing direct command command=%s", normalized_command)
    completed = subprocess.run(normalized_command, shell=True, check=False)
    if int(completed.returncode) != 0:
        logger.warning(
            "direct command exited non-zero command=%s exit_code=%s",
            normalized_command,
            int(completed.returncode),
        )
    else:
        logger.info("direct command completed command=%s exit_code=0", normalized_command)
    return int(completed.returncode)


def _command_text_from_args(args: list[str]) -> str:
    """Reconstruct shell-safe command text from parsed CLI argv items."""
    return " ".join(_shell_quote(arg) for arg in args)


def _script_mode_enabled(command_text: str) -> bool:
    """Return whether command begins with `script`."""
    stripped = command_text.lstrip()
    if not stripped:
        return False
    first, *_ = stripped.split(maxsplit=1)
    return first.lower() == SCRIPT_KEYWORD


def _handle_command(raw_command: str) -> int:
    """Process one command line according to Phase 1 rules."""
    logger = _get_logger()
    command_text = raw_command.strip()
    if not command_text:
        logger.info("ignored empty command input")
        return 0

    lowered = command_text.lower()
    if lowered in {
        "enable-process-tail",
        "enable process-tail",
        "enable process tail",
        "enable enable-process-tail",
    }:
        logger.info("enabling process tail feature")
        _set_process_tail_enabled(True)
        return 0
    if lowered in {
        "disable-process-tail",
        "disable process-tail",
        "disable process tail",
        "disable enable-process-tail",
    }:
        logger.info("disabling process tail feature")
        _set_process_tail_enabled(False)
        return 0
    if lowered == "status":
        logger.info("printing CLI status")
        return _print_status()

    if _script_mode_enabled(command_text):
        output_name, script_command = _split_script_directive(command_text)
        output_path = _resolve_script_path(output_name)
        _write_script(output_path, script_command)
        logger.info(
            "generated script output_path=%s command=%s",
            output_path,
            script_command,
        )
        print(f"Generated script: {output_path}")
        return 0

    return _execute_command(command_text)


def _top_level_commands() -> list[str]:
    """Return top-level interactive commands and common executables."""
    return [
        "help",
        "--help",
        "-h",
        "start",
        "stop",
        "restart",
        "status",
        "enable-process-tail",
        "disable-process-tail",
        "exit",
        "quit",
        "script",
        "python",
        "python3",
        "py",
        "pip",
        "pytest",
        "uv",
        "curl",
    ]


def _catalog_start_available() -> bool:
    """Return whether the catalog UI start action should be available."""
    repo_root = _repo_root()
    opamp_config_path = (repo_root / "config" / "opamp.json").resolve()
    opamp_config = _load_json_file(opamp_config_path)
    opamp_section = opamp_config.get("opamp", {})
    if not isinstance(opamp_section, dict):
        return False
    catalog_config = opamp_section.get("config_catalog", {})
    if not isinstance(catalog_config, dict):
        return False
    sources = catalog_config.get("sources", [])
    return isinstance(sources, list) and bool(sources)


def _materialize_ordered_actions(
    *,
    order: list[str],
    action_map: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Return ordered `(label, action)` pairs from one action map.

    The `order` list is intentionally position-sensitive because the interactive
    numbered menus expose this exact sequence to the user.
    """
    actions: list[tuple[str, dict[str, Any]]] = []
    for action_id in order:
        action = action_map.get(action_id)
        if not action:
            continue
        label = str(action.get("label") or action_id)
        actions.append((label, action))
    return actions


def _start_action_labels() -> list[str]:
    """Return start labels without constructing launch actions."""
    return [label for label, _action in _start_actions()]


def _stop_action_labels() -> list[str]:
    """Return stop labels without constructing stop actions."""
    return [label for label, _action in _stop_actions()]


def _restart_action_labels() -> list[str]:
    """Return restart labels without constructing restart actions."""
    return [label for label, _action in _restart_actions()]


def _guided_action_aliases(action: dict[str, Any]) -> list[str]:
    """Return labels and short aliases accepted for guided selections."""
    label = str(action.get("label") or "").strip()
    action_id = str(action.get("id") or _slugify(label).replace("-", "_")).strip()
    normalized = _normalized_label(label)
    aliases: list[str] = [label, str(label).lower(), _slugify(label)]
    aliases.extend(GUIDED_ACTION_ALIASES.get(action_id, []))
    if action_id == normalized:
        aliases.extend(GUIDED_ACTION_ALIASES.get(normalized, []))

    deduped: list[str] = []
    seen: set[str] = set()
    for entry in aliases:
        cleaned = str(entry or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(cleaned)
    return deduped


def _guided_labels_for_intent(intent: str) -> list[str]:
    """Return guided labels for the requested intent."""
    if intent == "start":
        return _start_action_labels()
    if intent == "stop":
        return _stop_action_labels()
    if intent == "restart":
        return _restart_action_labels()
    return []


def _matches_guided_label(selection: str, label: str) -> bool:
    """Return whether a selection matches a guided label or one of its aliases."""
    normalized = _normalized_label(selection)
    if not normalized:
        return False
    action = _resolve_guided_action_by_label(label)
    if action is None:
        return False
    for candidate in _guided_action_aliases(action):
        if _normalized_label(candidate) == normalized:
            return True
    return False


def _matching_guided_labels(intent: str, partial_selection: str) -> list[str]:
    """Return guided labels that match a partial typed selection."""
    normalized_prefix = _normalized_label(partial_selection)
    matches: list[str] = []
    for label in _guided_labels_for_intent(intent):
        if not normalized_prefix:
            matches.append(label)
            continue
        action = _resolve_guided_action_by_label(label, intent=intent)
        if action is None:
            continue
        for alias in _guided_action_aliases(action):
            if _normalized_label(alias).startswith(normalized_prefix):
                matches.append(label)
                break
    return matches


def _setup_readline_completion(words: Iterable[str]) -> None:
    """Enable simple TAB completion when readline is available."""
    try:
        import readline  # type: ignore
    except ImportError:
        return

    entries = list(words)

    def completer(text: str, state: int) -> str | None:
        matches = [entry for entry in entries if entry.startswith(text)]
        if state < len(matches):
            return matches[state]
        return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")


def _prompt_toolkit_input_reader(words: Iterable[str]) -> Callable[[str], str] | None:
    """Return prompt_toolkit-backed input reader with autocomplete when available."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    try:
        from prompt_toolkit import prompt as pt_prompt  # type: ignore
        from prompt_toolkit.completion import Completer, Completion, PathCompleter  # type: ignore
    except ImportError:
        return None

    top_level_words = sorted({str(word).strip() for word in words if str(word).strip()})
    path_completer = PathCompleter(expanduser=True)

    def _line_prefix(document: Any) -> str:
        """Return the current token-like prefix up to the cursor."""
        before_cursor = str(document.text_before_cursor or "")
        if not before_cursor:
            return ""
        last_space = max(before_cursor.rfind(" "), before_cursor.rfind("\t"))
        if last_space < 0:
            return before_cursor
        return before_cursor[last_space + 1 :]

    def _yield_word_matches(
        *,
        options: Iterable[str],
        prefix: str,
    ) -> Iterable[Any]:
        lowered_prefix = prefix.lower()
        start_position = -len(prefix)
        seen: set[str] = set()
        for option in options:
            text = str(option or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            if lowered_prefix and lowered.startswith(lowered_prefix) is not True:
                continue
            seen.add(lowered)
            yield Completion(text, start_position=start_position)

    class _OpampCliCompleter(Completer):
        """Context-aware completer for top-level and guided CLI commands."""

        def get_completions(self, document: Any, complete_event: Any) -> Iterable[Any]:
            text = str(document.text_before_cursor or "")
            stripped = text.lstrip()
            lowered = stripped.lower()

            if not stripped:
                yield from _yield_word_matches(options=top_level_words, prefix="")
                return

            if lowered.startswith("start "):
                selection = stripped[6:]
                yield from _yield_word_matches(
                    options=_matching_guided_labels("start", selection),
                    prefix=selection,
                )
                return

            if lowered == "start":
                yield Completion("start ", start_position=0)
                return

            if lowered.startswith("stop "):
                selection = stripped[5:]
                yield from _yield_word_matches(
                    options=_matching_guided_labels("stop", selection),
                    prefix=selection,
                )
                return

            if lowered == "stop":
                yield Completion("stop ", start_position=0)
                return

            if lowered.startswith("restart "):
                selection = stripped[8:]
                yield from _yield_word_matches(
                    options=_matching_guided_labels("restart", selection),
                    prefix=selection,
                )
                return

            if lowered == "restart":
                yield Completion("restart ", start_position=0)
                return

            line_prefix = _line_prefix(document)
            if len(stripped.split()) <= 1:
                yield from _yield_word_matches(options=top_level_words, prefix=line_prefix)

            pathish = (
                "/" in line_prefix
                or "\\" in line_prefix
                or line_prefix.startswith((".", "~"))
                or (":" in line_prefix and _is_windows())
                or line_prefix.endswith(".py")
                or line_prefix.endswith(".json")
            )
            if pathish or lowered.startswith("script ") or lowered.startswith("python ") or lowered.startswith("python3 ") or lowered.startswith("py "):
                yield from path_completer.get_completions(document, complete_event)

    completer = _OpampCliCompleter()

    def reader(prompt_text: str) -> str:
        return str(
            pt_prompt(
                prompt_text,
                completer=completer,
                complete_while_typing=True,
            )
        )

    return reader


def _builtin_tty_input_reader(words: Iterable[str]) -> Callable[[str], str] | None:
    """Return a lightweight built-in reader with tab completion for TTY use.

    This is primarily a Windows fallback for direct `python cli/main.py` runs
    where `prompt_toolkit` is not installed and `readline` is unavailable.
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    if _is_windows() is not True:
        return None

    try:
        import msvcrt  # type: ignore
    except ImportError:
        return None

    entries = sorted({str(word) for word in words if str(word).strip()})

    def _render_prompt(prompt_text: str, buffer_text: str) -> None:
        sys.stdout.write("\r")
        sys.stdout.write(f"{prompt_text}{buffer_text}")
        sys.stdout.write(" ")
        sys.stdout.write("\r")
        sys.stdout.write(f"{prompt_text}{buffer_text}")
        sys.stdout.flush()

    def _matches(prefix: str) -> list[str]:
        lowered = prefix.lower()
        return [entry for entry in entries if entry.lower().startswith(lowered)]

    def reader(prompt_text: str) -> str:
        buffer: list[str] = []
        tab_prefix = ""
        tab_matches: list[str] = []
        tab_index = -1

        sys.stdout.write(prompt_text)
        sys.stdout.flush()

        while True:
            char = msvcrt.getwch()
            if char in {"\r", "\n"}:
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buffer)
            if char == "\003":
                raise KeyboardInterrupt
            if char == "\x1a":
                raise EOFError
            if char in {"\x00", "\xe0"}:
                msvcrt.getwch()
                continue
            if char in {"\b", "\x7f"}:
                if buffer:
                    buffer.pop()
                    _render_prompt(prompt_text, "".join(buffer))
                tab_prefix = ""
                tab_matches = []
                tab_index = -1
                continue
            if char == "\t":
                current = "".join(buffer)
                matches = _matches(current)
                if not matches:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                    continue
                if len(matches) == 1:
                    completion = matches[0]
                    buffer = list(completion)
                    _render_prompt(prompt_text, completion)
                    tab_prefix = completion
                    tab_matches = matches
                    tab_index = 0
                    continue
                common_prefix = os.path.commonprefix(matches)
                if len(common_prefix) > len(current):
                    buffer = list(common_prefix)
                    _render_prompt(prompt_text, common_prefix)
                    tab_prefix = common_prefix
                    tab_matches = _matches(common_prefix)
                    tab_index = -1
                    continue
                if current != tab_prefix or matches != tab_matches:
                    tab_prefix = current
                    tab_matches = matches
                    tab_index = 0
                else:
                    tab_index = (tab_index + 1) % len(tab_matches)
                completion = tab_matches[tab_index]
                buffer = list(completion)
                _render_prompt(prompt_text, completion)
                continue
            if char.isprintable():
                buffer.append(char)
                sys.stdout.write(char)
                sys.stdout.flush()
                tab_prefix = ""
                tab_matches = []
                tab_index = -1

    return reader


def _shell_quote(value: str) -> str:
    """Return shell-safe quoting for one argument fragment."""
    if _is_windows():
        escaped = str(value).replace('"', '""')
        return f'"{escaped}"'
    return shlex.quote(str(value))


def _utc_timestamp() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(label: str) -> str:
    """Convert a human label into a stable lowercase slug."""
    cleaned = "".join(
        char.lower() if char.isalnum() else "-"
        for char in str(label or "").strip()
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "process"


def _normalized_label(label: str) -> str:
    """Return a stable comparison key for guided action labels."""
    return _slugify(label).replace("-", "")


def _is_process_running(pid: int) -> bool:
    """Return whether a process ID appears to still be running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _load_cli_process_state() -> dict[str, Any]:
    """Load persisted CLI-managed process records."""
    state_path = _cli_process_state_path()
    if state_path.is_file() is not True:
        return {"processes": []}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"processes": []}
    if not isinstance(payload, dict):
        return {"processes": []}
    processes = payload.get("processes", [])
    if not isinstance(processes, list):
        processes = []
    return {"processes": [item for item in processes if isinstance(item, dict)]}


def _load_cli_settings() -> dict[str, Any]:
    """Load persisted CLI settings."""
    settings_path = _cli_settings_path()
    if settings_path.is_file() is not True:
        return {}
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_cli_process_state(payload: dict[str, Any]) -> None:
    """Persist CLI-managed process records to disk."""
    state_path = _cli_process_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "updated_at": _utc_timestamp(),
        "processes": payload.get("processes", []),
    }
    state_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")


def _save_cli_settings(payload: dict[str, Any]) -> None:
    """Persist CLI settings to disk."""
    settings_path = _cli_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = dict(payload)
    normalized["updated_at"] = _utc_timestamp()
    settings_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")


def _process_tail_enabled() -> bool:
    """Return whether process tail shells should be opened for managed starts."""
    payload = _load_cli_settings()
    value = payload.get(CLI_SETTING_ENABLE_PROCESS_TAIL, False)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in TRUE_VALUES


def _set_process_tail_enabled(enabled: bool) -> None:
    """Persist process tail preference and print the resulting state."""
    payload = _load_cli_settings()
    payload[CLI_SETTING_ENABLE_PROCESS_TAIL] = bool(enabled)
    _save_cli_settings(payload)
    _get_logger().info("process tailing toggled enabled=%s", bool(enabled))
    print(f"Process tailing {'enabled' if enabled else 'disabled'}.")
    print(f"Settings file: {_cli_settings_path()}")


def _prune_cli_process_state() -> dict[str, Any]:
    """Remove stale process records and persist the cleaned state."""
    payload = _load_cli_process_state()
    active: list[dict[str, Any]] = []
    for record in payload.get("processes", []):
        pid = int(record.get("pid", 0) or 0)
        if _is_process_running(pid):
            active.append(record)
    cleaned = {"processes": active}
    _save_cli_process_state(cleaned)
    return cleaned


def _record_cli_process(
    *,
    name: str,
    pid: int,
    command_text: str,
    cwd: Path,
    log_file: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one managed process record to CLI state."""
    payload = _prune_cli_process_state()
    payload.setdefault("processes", [])
    payload["processes"].append(
        {
            "name": str(name),
            "pid": int(pid),
            "command": str(command_text),
            "cwd": str(cwd.resolve()),
            "log_file": str(log_file.resolve()) if log_file is not None else "",
            "started_at": _utc_timestamp(),
            "metadata": metadata or {},
        }
    )
    _save_cli_process_state(payload)


def _append_log_line(log_file: Path, text: str) -> None:
    """Append one UTF-8 log line to a managed CLI log file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip("\n") + "\n")


def _prepare_launch_log(*, label: str, command_text: str, cwd: Path, log_name: str) -> Path:
    """Create a launch log file and write a small banner before execution."""
    log_file = (_cli_log_dir() / f"{log_name}.log").resolve()
    # Reset per-process launch logs so stale startup markers from previous runs
    # do not trigger false negatives in current startup checks.
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("", encoding="utf-8")
    _append_log_line(log_file, f"[{_utc_timestamp()}] launch={label}")
    _append_log_line(log_file, f"[{_utc_timestamp()}] cwd={cwd}")
    _append_log_line(log_file, f"[{_utc_timestamp()}] command={command_text}")
    return log_file


def _powershell_single_quote(value: str) -> str:
    """Return a PowerShell-safe single-quoted string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def _launch_process_tail_shell(*, label: str, log_file: Path) -> bool:
    """Open a new shell window tailing the provided log file."""
    resolved_log = log_file.resolve()
    if resolved_log.exists() is not True:
        return False

    if _is_windows():
        command = (
            f"Write-Host 'Tailing {label}'; "
            f"Get-Content -Path {_powershell_single_quote(str(resolved_log))} "
            f"-Wait -Tail {PROCESS_TAIL_INITIAL_LINES}"
        )
        subprocess.Popen(  # pylint: disable=consider-using-with
            ["powershell.exe", "-NoExit", "-Command", command],
            cwd=str(_repo_root()),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return True

    bash_path = shutil.which("bash") or "/bin/bash"
    tail_command = (
        f"printf 'Tailing {label}\\n'; "
        f"tail -n {PROCESS_TAIL_INITIAL_LINES} -f {_shell_quote(str(resolved_log))}"
    )
    terminal_candidates = [
        ["x-terminal-emulator", "-e", bash_path, "-lc", tail_command],
        ["gnome-terminal", "--", bash_path, "-lc", tail_command],
        ["konsole", "-e", bash_path, "-lc", tail_command],
        ["xfce4-terminal", "--command", f"{bash_path} -lc {shlex.quote(tail_command)}"],
        ["mate-terminal", "--", bash_path, "-lc", tail_command],
        ["lxterminal", "-e", f"{bash_path} -lc {shlex.quote(tail_command)}"],
        ["xterm", "-e", bash_path, "-lc", tail_command],
    ]
    for candidate in terminal_candidates:
        executable = shutil.which(candidate[0])
        if not executable:
            continue
        subprocess.Popen(  # pylint: disable=consider-using-with
            [executable, *candidate[1:]],
            cwd=str(_repo_root()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    return False


def _open_process_tail_if_enabled(*, label: str, log_file: Path) -> None:
    """Open a tail shell for a managed process log when the feature is enabled."""
    logger = _get_logger()
    if _process_tail_enabled() is not True:
        logger.info("process tailing skipped because feature is disabled label=%s", label)
        return
    print(f"Process tailing enabled for {label}; log file: {log_file}")
    try:
        opened = _launch_process_tail_shell(label=label, log_file=log_file)
    except Exception as exc:  # pragma: no cover - defensive shell-launch guard
        logger.exception(
            "failed to open process tail shell label=%s log_file=%s",
            label,
            log_file,
            exc_info=exc,
        )
        print(f"Warning: failed to open process tail for {label}: {exc}", file=sys.stderr)
        return
    if opened:
        logger.info("opened process tail shell label=%s log_file=%s", label, log_file)
        print(f"Opened tail shell for {label}: {log_file}")
        return
    logger.warning("no terminal launcher available for process tail label=%s", label)
    print(
        f"Warning: no terminal launcher was available for process tailing {label}",
        file=sys.stderr,
    )


def _terminate_process(pid: int) -> None:
    """Best-effort termination of one managed process ID."""
    if pid <= 0:
        return
    try:
        if _is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, 15)
    except OSError:
        return


def _log_has_startup_failure(log_file: Path) -> str | None:
    """Return a matching startup failure marker from the log, if present."""
    if log_file.is_file() is not True:
        return None
    try:
        contents = log_file.read_text(encoding="utf-8").lower()
    except OSError:
        return None
    for marker in STARTUP_FAILURE_MARKERS:
        if marker in contents:
            return marker
    return None


def _http_ready(url: str) -> bool:
    """Return whether an HTTP endpoint responds successfully."""
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=1.0) as response:
            return int(getattr(response, "status", 200)) < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _wait_for_background_start(
    *,
    process: subprocess.Popen[Any],
    log_file: Path,
    readiness_url: str,
) -> tuple[bool, str]:
    """Wait for early exit, startup failure markers, and optional readiness."""
    deadline = time.monotonic() + PROCESS_READY_TIMEOUT_SECONDS
    ready_seen = False
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            return False, f"exited early with code {int(exit_code)}"
        failure_marker = _log_has_startup_failure(log_file)
        if failure_marker:
            return False, f"startup failure detected: {failure_marker}"
        if readiness_url:
            if _http_ready(readiness_url):
                ready_seen = True
        else:
            return True, ""
        time.sleep(PROCESS_READY_POLL_INTERVAL_SECONDS)
    if readiness_url:
        if ready_seen and process.poll() is None and _log_has_startup_failure(log_file) is None:
            return True, ""
        return False, f"readiness probe timed out for {readiness_url}"
    return True, ""


def _remove_cli_process_records(names: Iterable[str]) -> None:
    """Remove managed process records for the provided names."""
    target_names = {str(name) for name in names}
    payload = _load_cli_process_state()
    kept = [
        record
        for record in payload.get("processes", [])
        if str(record.get("name")) not in target_names
    ]
    _save_cli_process_state({"processes": kept})


def _print_status() -> int:
    """Print a summary of managed processes and current PID liveness."""
    settings_path = _cli_settings_path()
    state_path = _cli_process_state_path()
    log_dir = _cli_log_dir()
    cli_log_path = _cli_component_log_path()
    payload = _load_cli_process_state()
    processes = payload.get("processes", [])

    print(f"Settings file: {settings_path}")
    print(f"State file: {state_path}")
    print(f"Log directory: {log_dir}")
    print(f"CLI log file: {cli_log_path}")
    print(f"Process tailing: {'enabled' if _process_tail_enabled() else 'disabled'}")

    if state_path.exists() is not True:
        print("Managed processes: none recorded")
        return 0

    print(f"Managed processes: {len(processes)}")
    if not processes:
        return 0

    for index, record in enumerate(processes, start=1):
        name = str(record.get("name") or "process")
        pid = int(record.get("pid", 0) or 0)
        started_at = str(record.get("started_at") or "")
        cwd = str(record.get("cwd") or "")
        log_file = str(record.get("log_file") or "")
        status = "running" if _is_process_running(pid) else "stopped"
        print(f"{index}. {name}")
        print(f"   pid: {pid}")
        print(f"   status: {status}")
        if started_at:
            print(f"   started_at: {started_at}")
        if cwd:
            print(f"   cwd: {cwd}")
        if log_file:
            print(f"   log: {log_file}")
    return 0


def _existing_path(*candidates: Path) -> Path | None:
    """Return the first existing path from ordered candidates."""
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _shell_command(
    *,
    command_text: str,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> str:
    """Return one shell command with optional cwd and environment prefixes."""
    parts: list[str] = []
    if cwd is not None:
        if _is_windows():
            parts.append(f"cd /d {_shell_quote(str(cwd.resolve()))}")
        else:
            parts.append(f"cd {_shell_quote(str(cwd.resolve()))}")
    for key, value in (env or {}).items():
        if _is_windows():
            parts.append(f"set {_shell_quote(f'{key}={value}')}")
        else:
            parts.append(f"{key}={_shell_quote(value)}")
    if _is_windows():
        parts.append(command_text)
        return " && ".join(parts)
    if env:
        env_prefix = " ".join(parts[-len(env):]) if env else ""
        prefix_parts = parts[:-len(env)] if env else parts
        if env_prefix:
            prefix = " && ".join(prefix_parts) if prefix_parts else ""
            if prefix:
                return f"{prefix} && {env_prefix} {command_text}"
            return f"{env_prefix} {command_text}"
    prefix = " && ".join(parts)
    if prefix:
        return f"{prefix} && {command_text}"
    return command_text


def _python_module_command(
    *,
    module_name: str,
    python_paths: list[Path] | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> str:
    """Build a current-platform command for `python -m <module>` with PYTHONPATH."""
    interpreter = _shell_quote(sys.executable)
    module_bits = [interpreter, "-m", module_name]
    for arg in args or []:
        module_bits.append(_shell_quote(arg))
    module_command = " ".join(module_bits)

    extra_paths = [str(path.resolve()) for path in (python_paths or [])]
    existing = os.environ.get("PYTHONPATH", "")
    all_paths = [*extra_paths]
    if existing.strip():
        all_paths.append(existing)
    merged_env = dict(env or {})
    if all_paths:
        merged_env["PYTHONPATH"] = os.pathsep.join(all_paths)
    return _shell_command(command_text=module_command, env=merged_env, cwd=cwd)


def _python_module_argv(
    *,
    module_name: str,
    args: list[str] | None = None,
) -> list[str]:
    """Return argv list for `python -m <module>` launches."""
    return [sys.executable, "-m", module_name, *(args or [])]


def _python_script_argv(
    *,
    script_path: Path,
    args: list[str] | None = None,
) -> list[str]:
    """Return argv list for direct Python script launches."""
    return [sys.executable, str(script_path.resolve()), *(args or [])]


def _build_exec_env(
    *,
    python_paths: list[Path] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build child-process environment including merged PYTHONPATH."""
    merged = dict(os.environ)
    merged.update(env or {})
    extra_paths = [str(path.resolve()) for path in (python_paths or [])]
    existing = str(merged.get("PYTHONPATH", "")).strip()
    if existing:
        extra_paths.append(existing)
    if extra_paths:
        merged["PYTHONPATH"] = os.pathsep.join(extra_paths)
    return merged


def _load_json_file(path: Path) -> dict[str, Any]:
    """Load one JSON file into a dictionary, or return an empty mapping."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _catalog_launch_config_path(
    *,
    base_config_path: Path,
    base_config: dict[str, Any],
) -> Path | None:
    """Write a CLI runtime config that enables the provider catalog feature."""
    opamp_config = base_config.get("opamp", {})
    if not isinstance(opamp_config, dict):
        return None
    catalog_config = opamp_config.get("config_catalog", {})
    if not isinstance(catalog_config, dict):
        return None
    sources = catalog_config.get("sources", [])
    if not isinstance(sources, list) or not sources:
        return None

    payload = json.loads(json.dumps(base_config))
    payload.setdefault("opamp", {})
    payload["opamp"].setdefault("config_catalog", {})
    payload["opamp"]["config_catalog"]["enabled"] = True
    payload["_generated_from"] = str(base_config_path.resolve())

    runtime_config_path = (_cli_runtime_dir() / "catalog-service.json").resolve()
    runtime_config_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return runtime_config_path


def _python_script_command(
    *,
    script_path: Path,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> str:
    """Build a current-platform command for a Python script path."""
    interpreter = _shell_quote(sys.executable)
    parts = [interpreter, _shell_quote(str(script_path.resolve()))]
    for arg in args or []:
        parts.append(_shell_quote(arg))
    return _shell_command(command_text=" ".join(parts), env=env, cwd=cwd)


def _broker_stop_command(pid_file: Path) -> str:
    """Build a direct cross-platform broker stop command using the PID file."""
    code = (
        "import os, pathlib, signal, sys; "
        "pid_file = pathlib.Path(sys.argv[1]); "
        "runtime_pid = pid_file.read_text(encoding='utf-8').strip() if pid_file.exists() else ''; "
        "print(f'Broker PID file not found: {pid_file}') if not pid_file.exists() else None; "
        "sys.exit(0) if not pid_file.exists() else None; "
        "pid = int(runtime_pid) if runtime_pid else 0; "
        "pid_file.unlink(missing_ok=True) if not runtime_pid else None; "
        "sys.exit(0) if not runtime_pid else None; "
        "os.kill(pid, signal.SIGTERM); "
        "print(f'Requested broker shutdown for pid={pid}')"
    )
    return _shell_command(
        command_text=(
            f"{_shell_quote(sys.executable)} -c {_shell_quote(code)} "
            f"{_shell_quote(str(pid_file.resolve()))}"
        ),
    )


def _background_start_action(
    *,
    action_id: str,
    label: str,
    command_text: str,
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    launch_url: str | None = None,
    readiness_url: str | None = None,
) -> dict[str, Any]:
    """Create one background-launch guided action."""
    return {
        "id": action_id,
        "kind": "background_start",
        "label": label,
        "command_text": command_text,
        "argv": argv,
        "cwd": str(cwd.resolve()),
        "env": env,
        "record_name": label,
        "log_name": _slugify(label),
        "launch_url": str(launch_url or "").strip(),
        "readiness_url": str(readiness_url or "").strip(),
    }


def _simulator_start_action(
    *,
    action_id: str,
    label: str,
    command_text: str,
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    state_file: Path,
) -> dict[str, Any]:
    """Create one simulator batch-start guided action."""
    return {
        "id": action_id,
        "kind": "simulator_start",
        "label": label,
        "command_text": command_text,
        "argv": argv,
        "cwd": str(cwd.resolve()),
        "env": env,
        "state_file": str(state_file.resolve()),
    }


def _stop_recorded_action(
    *,
    action_id: str | None = None,
    label: str,
    record_names: list[str],
) -> dict[str, Any]:
    """Create one stop action that terminates recorded managed processes."""
    return {
        "id": str(action_id or _slugify(label).replace("-", "_")).strip(),
        "kind": "stop_recorded",
        "label": label,
        "record_names": list(record_names),
    }


def _start_actions() -> list[tuple[str, dict[str, Any]]]:
    """Return guided start actions available in current workspace."""
    action_map: dict[str, dict[str, Any]] = {}
    repo_root = _repo_root()
    opamp_config_path = (repo_root / "config" / "opamp.json").resolve()

    server_args = ["--port", str(DEFAULT_SERVER_PORT)]
    server_env = {"OPAMP_CONFIG_PATH": str(opamp_config_path)}
    server_cmd = _python_module_command(
        module_name="opamp_provider.server",
        python_paths=[repo_root / "provider" / "src"],
        args=server_args,
        env=server_env,
        cwd=repo_root,
    )
    action_map["server"] = _background_start_action(
        action_id="server",
        label="Server",
        command_text=server_cmd,
        argv=_python_module_argv(module_name="opamp_provider.server", args=server_args),
        cwd=repo_root,
        env=_build_exec_env(
            python_paths=[repo_root / "provider" / "src"],
            env=server_env,
        ),
        launch_url=f"http://127.0.0.1:{DEFAULT_SERVER_PORT}/ui",
        readiness_url=f"http://127.0.0.1:{DEFAULT_SERVER_PORT}/ui",
    )

    catalog_service_config_path = (
        repo_root / "catalog-service" / "src" / "catalog_service" / "config" / "catalog-service.json"
    ).resolve()
    if catalog_service_config_path.is_file():
        catalog_payload = _load_json_file(catalog_service_config_path)
        catalog_opamp = catalog_payload.get("opamp", {})
        if isinstance(catalog_opamp, dict):
            catalog_config = catalog_opamp.get("config_catalog", {})
        else:
            catalog_config = {}
        if not isinstance(catalog_config, dict):
            catalog_config = {}
        catalog_route_path = str(catalog_config.get("route_path") or "/catalog").strip() or "/catalog"
        if not catalog_route_path.startswith("/"):
            catalog_route_path = "/" + catalog_route_path
        try:
            catalog_port = int(catalog_config.get("web_port") or DEFAULT_CATALOG_WEB_PORT)
        except (TypeError, ValueError):
            catalog_port = DEFAULT_CATALOG_WEB_PORT
        catalog_args = ["--config-path", str(catalog_service_config_path)]
        catalog_server_cmd = _python_module_command(
            module_name="catalog_service",
            python_paths=[repo_root / "catalog-service" / "src"],
            args=catalog_args,
            cwd=repo_root,
        )
        action_map["catalog_ui"] = _background_start_action(
            action_id="catalog_ui",
            label="Config Catalog UI",
            command_text=catalog_server_cmd,
            argv=_python_module_argv(module_name="catalog_service", args=catalog_args),
            cwd=repo_root,
            env=_build_exec_env(
                python_paths=[repo_root / "catalog-service" / "src"],
            ),
            launch_url=f"http://127.0.0.1:{catalog_port}{catalog_route_path}",
            readiness_url=f"http://127.0.0.1:{catalog_port}{catalog_route_path}",
        )

    config_service_args = [
        "--config-path",
        str(
            repo_root
            / "config-service"
            / "src"
            / "config_service"
            / "config"
            / "config-service.json"
        ),
    ]
    config_service_cmd = _python_module_command(
        module_name="config_service",
        python_paths=[
            repo_root / "config-service" / "src",
            repo_root / "provider" / "src",
        ],
        args=config_service_args,
        cwd=repo_root,
    )
    action_map["config_service"] = _background_start_action(
        action_id="config_service",
        label="Config Service",
        command_text=config_service_cmd,
        argv=_python_module_argv(module_name="config_service", args=config_service_args),
        cwd=repo_root,
        env=_build_exec_env(
            python_paths=[
                repo_root / "config-service" / "src",
                repo_root / "provider" / "src",
            ],
        ),
        launch_url="http://127.0.0.1:8080/config-service/ui",
        readiness_url="http://127.0.0.1:8080/config-service/ui",
    )

    broker_env = {
        "BROKER_CONFIG_PATH": str(
            (repo_root / "agent_broker" / "opamp_broker" / "config" / "broker.ui_responses.json").resolve()
        ),
        "PYTHONUNBUFFERED": "1",
    }
    broker_cmd = _python_module_command(
        module_name="opamp_broker.broker_app",
        python_paths=[repo_root / "agent_broker"],
        env=broker_env,
        cwd=repo_root / "agent_broker",
    )
    action_map["broker"] = _background_start_action(
        action_id="broker",
        label="Broker",
        command_text=broker_cmd,
        argv=_python_module_argv(module_name="opamp_broker.broker_app"),
        cwd=repo_root / "agent_broker",
        env=_build_exec_env(
            python_paths=[repo_root / "agent_broker"],
            env=broker_env,
        ),
    )

    simulator_env = {"APP_ENABLE_DEV_FEATURES": "true"}
    simulator_state_file = repo_root / "consumer-sim" / "runtime" / "launcher_state.json"
    simulator_cmd = _python_script_command(
        script_path=repo_root / "consumer-sim" / "src" / "consumer_sim_launcher.py",
        args=["start"],
        env=simulator_env,
        cwd=repo_root,
    )
    action_map["simulator"] = _simulator_start_action(
        action_id="simulator",
        label="Simulator",
        command_text=simulator_cmd,
        argv=_python_script_argv(
            script_path=repo_root / "consumer-sim" / "src" / "consumer_sim_launcher.py",
            args=["start"],
        ),
        cwd=repo_root,
        env=_build_exec_env(env=simulator_env),
        state_file=simulator_state_file,
    )

    fluentbit_config = _existing_path(
        repo_root / "tests" / "opamp.json",
        repo_root / "config" / "opamp.json",
    )
    fluentbit_agent_config = _existing_path(
        repo_root / "tests" / "fluent-bit.yaml",
        repo_root / "consumer" / "fluent-bit.yaml",
    )
    fluentbit_args = [
        "--config-path",
        str(fluentbit_config) if fluentbit_config else str((repo_root / "config" / "opamp.json").resolve()),
        "--agent-config-path",
        str(fluentbit_agent_config) if fluentbit_agent_config else str((repo_root / "consumer" / "fluent-bit.yaml").resolve()),
    ]
    fluentbit_env = {
        "OPAMP_CONFIG_PATH": str(fluentbit_config or (repo_root / "config" / "opamp.json").resolve())
    }
    fluentbit_cmd = _python_module_command(
        module_name="opamp_consumer.fluentbit_client",
        python_paths=[repo_root / "consumer" / "src"],
        args=fluentbit_args,
        env=fluentbit_env,
        cwd=repo_root,
    )
    action_map["fluentbit_client"] = _background_start_action(
        action_id="fluentbit_client",
        label="Fluent Bit client",
        command_text=fluentbit_cmd,
        argv=_python_module_argv(module_name="opamp_consumer.fluentbit_client", args=fluentbit_args),
        cwd=repo_root,
        env=_build_exec_env(
            python_paths=[repo_root / "consumer" / "src"],
            env=fluentbit_env,
        ),
    )

    fluentd_config = _existing_path(
        repo_root / "consumer" / "opamp-fluentd.json",
        repo_root / "tests" / "opamp.json",
        repo_root / "config" / "opamp.json",
    )
    fluentd_args = [
        "--config-path",
        str(fluentd_config) if fluentd_config else str((repo_root / "config" / "opamp.json").resolve()),
        "--agent-config-path",
        str((repo_root / "consumer" / "fluentd.conf").resolve()),
    ]
    fluentd_env = {
        "OPAMP_CONFIG_PATH": str(fluentd_config or (repo_root / "config" / "opamp.json").resolve())
    }
    fluentd_cmd = _python_module_command(
        module_name="opamp_consumer.fluentd_client",
        python_paths=[repo_root / "consumer" / "src"],
        args=fluentd_args,
        env=fluentd_env,
        cwd=repo_root,
    )
    action_map["fluentd_client"] = _background_start_action(
        action_id="fluentd_client",
        label="Fluentd client",
        command_text=fluentd_cmd,
        argv=_python_module_argv(module_name="opamp_consumer.fluentd_client", args=fluentd_args),
        cwd=repo_root,
        env=_build_exec_env(
            python_paths=[repo_root / "consumer" / "src"],
            env=fluentd_env,
        ),
    )

    return _materialize_ordered_actions(
        order=GUIDED_START_ACTION_ORDER,
        action_map=action_map,
    )


def _stop_actions() -> list[tuple[str, dict[str, Any]]]:
    """Return guided stop actions available in current workspace."""
    action_map: dict[str, dict[str, Any]] = {}
    repo_root = _repo_root()

    server_stop_cmd = (
        "curl -sS -X POST http://127.0.0.1:4320/api/shutdown "
        "-H \"Content-Type: application/json\" -d \"{\\\"confirm\\\": true}\""
    )
    action_map["server"] = {
        "id": "server",
        "kind": "shell",
        "label": "Server",
        "command_text": server_stop_cmd,
    }

    broker_stop_cmd = _broker_stop_command(repo_root / "agent_broker" / ".broker" / "broker.pid")
    action_map["broker"] = {
        "id": "broker",
        "kind": "shell",
        "label": "Broker",
        "command_text": broker_stop_cmd,
    }

    action_map["catalog_ui"] = _stop_recorded_action(
        action_id="catalog_ui",
        label="Config Catalog UI",
        record_names=["Config Catalog UI"],
    )

    simulator_stop_cmd = _python_script_command(
        script_path=repo_root / "consumer-sim" / "src" / "consumer_sim_launcher.py",
        args=["stop"],
        cwd=repo_root,
    )
    action_map["simulator"] = {
        "id": "simulator",
        "kind": "shell",
        "label": "Simulator",
        "command_text": simulator_stop_cmd,
    }

    action_map["config_service"] = _stop_recorded_action(
        action_id="config_service",
        label="Config Service",
        record_names=["Config Service"],
    )
    action_map["fluentbit_client"] = _stop_recorded_action(
        action_id="fluentbit_client",
        label="Fluent Bit client",
        record_names=["Fluent Bit client"],
    )
    action_map["fluentd_client"] = _stop_recorded_action(
        action_id="fluentd_client",
        label="Fluentd client",
        record_names=["Fluentd client"],
    )

    semaphore_path = repo_root / "OpAMPSupervisor.signal"
    if _is_windows():
        client_stop_cmd = _shell_command(
            command_text=(
                f"type nul > {_shell_quote(str(semaphore_path.resolve()))} "
                "&& powershell -NoProfile -Command "
                "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "
                "'opamp_consumer\\.fluentbit_client|opamp_consumer\\.fluentd_client' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\""
            ),
            cwd=repo_root,
        )
    else:
        client_stop_cmd = _shell_command(
            command_text=(
                f"touch {_shell_quote(str(semaphore_path.resolve()))} "
                "&& pkill -TERM -f 'opamp_consumer\\.fluentbit_client' || true "
                "&& pkill -TERM -f 'opamp_consumer\\.fluentd_client' || true"
            ),
            cwd=repo_root,
        )
    action_map["all_clients"] = {
        "id": "all_clients",
        "kind": "shell",
        "label": "All clients",
        "command_text": client_stop_cmd,
    }
    return _materialize_ordered_actions(
        order=GUIDED_STOP_ACTION_ORDER,
        action_map=action_map,
    )


def _restart_actions() -> list[tuple[str, dict[str, Any]]]:
    """Return guided restart actions available in current workspace."""
    start_actions = _start_actions()
    stop_actions_by_id = {
        str(action.get("id") or "").strip(): action
        for _label, action in _stop_actions()
    }
    actions: list[tuple[str, dict[str, Any]]] = []
    for label, start_action in start_actions:
        action_id = str(start_action.get("id") or "").strip()
        if not action_id:
            continue
        stop_action = stop_actions_by_id.get(action_id)
        if stop_action is None:
            continue
        actions.append(
            (
                label,
                {
                    "id": action_id,
                    "kind": "restart",
                    "label": label,
                    "start_action": start_action,
                    "stop_action": stop_action,
                },
            )
        )
    return actions


def _guided_actions_for_intent(intent: str) -> list[tuple[str, dict[str, Any]]]:
    """Return guided action list for one intent."""
    if intent == "start":
        return _start_actions()
    if intent == "stop":
        return _stop_actions()
    if intent == "restart":
        return _restart_actions()
    return []


def _select_guided_action(
    *,
    input_reader: Callable[[str], str] | None,
    intent: str,
    actions: list[tuple[str, Any]],
) -> Any | None:
    """Prompt for one guided action and return command text or None."""
    if not actions:
        print(f"No {intent} options are currently available.")
        return None
    print(f"Choose what to {intent}:")
    for index, (label, _command) in enumerate(actions, start=1):
        print(f"  {index}. {label}")
    print("  0. cancel")

    while True:
        try:
            # Always use plain input for numbered guided selection so only
            # explicit options are shown, not global autocomplete words.
            selected = input(f"{intent}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if selected in {"0", "cancel", "c", ""}:
            return None
        if selected.isdigit():
            index = int(selected)
            if 1 <= index <= len(actions):
                return actions[index - 1][1]
        normalized = _normalized_label(selected)
        if normalized:
            for label, action in actions:
                if _matches_guided_label(selected, label):
                    return action
        print("Please choose a valid number from the list.")


def _split_guided_command(command_text: str) -> tuple[str, str] | None:
    """Return guided intent and selection for `start`/`stop`/`restart` commands."""
    stripped = str(command_text or "").strip()
    for intent in ("start", "stop", "restart"):
        if stripped.lower() == intent:
            return intent, ""
        if stripped.lower().startswith(f"{intent} "):
            return intent, stripped[len(intent) :].strip()
    return None


def _resolve_guided_action(intent: str, selection: str) -> dict[str, Any] | None:
    """Resolve one guided action from a typed selection."""
    actions = _guided_actions_for_intent(intent)
    for label, action in actions:
        if _matches_guided_label(selection, label):
            return action
    return None


def _resolve_guided_action_by_label(
    label: str,
    *,
    intent: str | None = None,
) -> dict[str, Any] | None:
    """Resolve one action from its current display label."""
    intents = [intent] if intent in {"start", "stop", "restart"} else ["start", "stop", "restart"]
    for current_intent in intents:
        actions = _guided_actions_for_intent(current_intent)
        for current_label, action in actions:
            if current_label == label:
                return action
    return None


def _execute_start_action(action: dict[str, Any]) -> int:
    """Execute one start action by kind."""
    kind = str(action.get("kind", "")).strip().lower()
    if kind == "background_start":
        return _launch_background_process(action)
    if kind == "simulator_start":
        return _record_simulator_batch(action)
    raise ValueError(f"unsupported start action kind: {kind}")


def _execute_stop_action(action: dict[str, Any]) -> int:
    """Execute one stop action by kind."""
    kind = str(action.get("kind", "")).strip().lower()
    if kind == "shell":
        command_text = str(action.get("command_text") or "").strip()
        print(f"Executing: {command_text}")
        return _handle_command(command_text)
    if kind == "stop_recorded":
        return _stop_recorded_processes(
            [str(item) for item in action.get("record_names", [])]
        )
    raise ValueError(f"unsupported stop action kind: {kind}")


def _record_name_matches_restart(
    *,
    action_id: str,
    record_name: str,
    tracked_names: set[str],
) -> bool:
    """Return whether one record name should be tracked for restart waiting."""
    if record_name in tracked_names:
        return True
    if action_id == "simulator" and record_name.startswith("Simulator:"):
        return True
    return False


def _tracked_restart_pids(*, action_id: str, start_action: dict[str, Any], stop_action: dict[str, Any]) -> list[int]:
    """Return running process IDs to watch while restarting one action."""
    tracked_names = {
        str(item).strip()
        for item in stop_action.get("record_names", [])
        if str(item).strip()
    }
    start_record_name = str(start_action.get("record_name") or "").strip()
    if start_record_name:
        tracked_names.add(start_record_name)

    if not tracked_names and action_id != "simulator":
        return []

    payload = _prune_cli_process_state()
    pids: list[int] = []
    for record in payload.get("processes", []):
        if not isinstance(record, dict):
            continue
        record_name = str(record.get("name") or "").strip()
        if not _record_name_matches_restart(
            action_id=action_id,
            record_name=record_name,
            tracked_names=tracked_names,
        ):
            continue
        pid = int(record.get("pid", 0) or 0)
        if pid <= 0:
            continue
        if _is_process_running(pid):
            pids.append(pid)
    return sorted(set(pids))


def _wait_for_pids_to_exit(*, pids: list[int], timeout_seconds: float) -> tuple[bool, list[int]]:
    """Wait until all provided process IDs are no longer running."""
    if not pids:
        return True, []
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    while True:
        remaining = [pid for pid in pids if _is_process_running(pid)]
        if not remaining:
            return True, []
        if time.monotonic() >= deadline:
            return False, remaining
        time.sleep(PROCESS_STOP_POLL_INTERVAL_SECONDS)


def _execute_restart_action(action: dict[str, Any]) -> int:
    """Restart one guided component by stop, wait, cleanup, and start."""
    logger = _get_logger()
    label = str(action.get("label") or "component")
    start_action = dict(action.get("start_action", {}))
    stop_action = dict(action.get("stop_action", {}))
    action_id = str(action.get("id") or start_action.get("id") or "").strip()
    if not action_id:
        raise ValueError("restart action is missing id")
    if not start_action or not stop_action:
        raise ValueError(f"restart action is incomplete for {label}")

    tracked_pids = _tracked_restart_pids(
        action_id=action_id,
        start_action=start_action,
        stop_action=stop_action,
    )
    logger.info(
        "restart requested label=%s action_id=%s tracked_pids=%s",
        label,
        action_id,
        tracked_pids,
    )
    print(f"Restarting {label}...")

    stop_code = _execute_stop_action(stop_action)
    if int(stop_code) != 0:
        logger.warning(
            "restart aborted because stop failed label=%s action_id=%s exit_code=%s",
            label,
            action_id,
            int(stop_code),
        )
        return int(stop_code)

    exited, remaining = _wait_for_pids_to_exit(
        pids=tracked_pids,
        timeout_seconds=PROCESS_STOP_TIMEOUT_SECONDS,
    )
    if not exited:
        logger.warning(
            "restart timed out waiting for process exit label=%s action_id=%s remaining=%s",
            label,
            action_id,
            remaining,
        )
        print(
            f"Restart wait timed out for {label}; still running pids: {', '.join(str(pid) for pid in remaining)}",
            file=sys.stderr,
        )
        return 1

    _prune_cli_process_state()
    logger.info("restart cleanup completed label=%s action_id=%s", label, action_id)
    return _execute_start_action(start_action)


def _execute_guided_action(
    *,
    input_reader: Callable[[str], str] | None,
    intent: str,
    selection: str,
) -> int:
    """Execute a guided start/stop/restart action from prompt or direct text."""
    logger = _get_logger()
    actions = _guided_actions_for_intent(intent)
    selected_action = None
    if selection:
        selected_action = _resolve_guided_action(intent, selection)
        if selected_action is None:
            available = ", ".join(label for label, _action in actions)
            logger.warning(
                "rejected guided action intent=%s selection=%s available=%s",
                intent,
                selection,
                available,
            )
            print(
                f"Unknown {intent} target '{selection}'. Available: {available}",
                file=sys.stderr,
            )
            return 1
    else:
        selected_action = _select_guided_action(
            input_reader=input_reader,
            intent=intent,
            actions=actions,
        )
        if not selected_action:
            logger.info("guided selection cancelled intent=%s", intent)
            return 0

    kind = str(selected_action.get("kind", "")).strip().lower()
    logger.info(
        "executing guided action intent=%s label=%s kind=%s",
        intent,
        selected_action.get("label", f"{intent} action"),
        kind,
    )
    print(f"Selected: {selected_action.get('label', f'{intent} action')}")
    if intent == "start":
        return _execute_start_action(selected_action)
    if intent == "stop":
        return _execute_stop_action(selected_action)
    if intent == "restart":
        return _execute_restart_action(selected_action)
    raise ValueError(f"unsupported guided intent: {intent}")


def _launch_background_process(action: dict[str, Any]) -> int:
    """Launch one long-running process in background and record its PID."""
    logger = _get_logger()
    label = str(action.get("label", "Process"))
    argv = [str(item) for item in action.get("argv", [])]
    cwd = Path(str(action.get("cwd") or _repo_root())).resolve()
    env = {
        str(key): str(value)
        for key, value in dict(action.get("env", {})).items()
    }
    log_name = str(action.get("log_name") or _slugify(label))
    log_file = _prepare_launch_log(
        label=label,
        command_text=str(action.get("command_text") or ""),
        cwd=cwd,
        log_name=log_name,
    )

    log_handle = log_file.open("a", encoding="utf-8")
    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if _is_windows():
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        if creationflags:
            popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(argv, **popen_kwargs)  # pylint: disable=consider-using-with
    except Exception as exc:
        log_handle.close()
        _append_log_line(log_file, f"[{_utc_timestamp()}] launch_failed={exc}")
        logger.exception(
            "background process launch failed label=%s cwd=%s argv=%s log_file=%s",
            label,
            cwd,
            argv,
            log_file,
            exc_info=exc,
        )
        raise
    finally:
        log_handle.close()

    logger.info(
        "background process spawned label=%s pid=%s cwd=%s log_file=%s",
        label,
        process.pid,
        cwd,
        log_file,
    )
    time.sleep(PROCESS_START_CHECK_DELAY_SECONDS)
    exit_code = process.poll()
    if exit_code is not None:
        _append_log_line(log_file, f"[{_utc_timestamp()}] exited_early={int(exit_code)}")
        logger.warning(
            "background process exited before startup completed label=%s pid=%s exit_code=%s log_file=%s",
            label,
            process.pid,
            int(exit_code),
            log_file,
        )
        print(
            f"{label} exited before it was considered started "
            f"(exit_code={int(exit_code)}) log={log_file}",
            file=sys.stderr,
        )
        return int(exit_code) if int(exit_code) != 0 else 1

    readiness_url = str(action.get("readiness_url") or "").strip()
    ready, reason = _wait_for_background_start(
        process=process,
        log_file=log_file,
        readiness_url=readiness_url,
    )
    if ready is not True:
        _append_log_line(log_file, f"[{_utc_timestamp()}] startup_check_failed={reason}")
        _terminate_process(process.pid)
        logger.warning(
            "background process failed startup check label=%s pid=%s reason=%s log_file=%s",
            label,
            process.pid,
            reason,
            log_file,
        )
        print(f"{label} failed startup check: {reason} log={log_file}", file=sys.stderr)
        return 1

    _record_cli_process(
        name=str(action.get("record_name") or label),
        pid=process.pid,
        command_text=str(action.get("command_text") or ""),
        cwd=cwd,
        log_file=log_file,
    )
    _append_log_line(log_file, f"[{_utc_timestamp()}] pid={process.pid}")
    logger.info(
        "background process recorded label=%s record_name=%s pid=%s readiness_url=%s log_file=%s",
        label,
        str(action.get("record_name") or label),
        process.pid,
        readiness_url,
        log_file,
    )
    print(f"Started {label} pid={process.pid} log={log_file}")
    launch_url = str(action.get("launch_url") or "").strip()
    if launch_url:
        print(f"Open: {launch_url}")
    _open_process_tail_if_enabled(label=label, log_file=log_file)
    return 0


def _record_simulator_batch(action: dict[str, Any]) -> int:
    """Run simulator launcher start and record all spawned instance PIDs."""
    logger = _get_logger()
    argv = [str(item) for item in action.get("argv", [])]
    cwd = Path(str(action.get("cwd") or _repo_root())).resolve()
    env = {
        str(key): str(value)
        for key, value in dict(action.get("env", {})).items()
    }
    log_file = _prepare_launch_log(
        label=str(action.get("label") or "Simulator"),
        command_text=str(action.get("command_text") or ""),
        cwd=cwd,
        log_name=_slugify(str(action.get("label") or "Simulator")),
    )
    with log_file.open("a", encoding="utf-8") as log_handle:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            check=False,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    _append_log_line(log_file, f"[{_utc_timestamp()}] exit_code={int(completed.returncode)}")
    if int(completed.returncode) != 0:
        logger.warning(
            "simulator batch launcher exited non-zero argv=%s cwd=%s exit_code=%s log_file=%s",
            argv,
            cwd,
            int(completed.returncode),
            log_file,
        )
        return int(completed.returncode)

    state_file = Path(str(action.get("state_file") or "")).resolve()
    if state_file.is_file() is not True:
        logger.warning(
            "simulator batch rejected because state file was not created state_file=%s",
            state_file,
        )
        print(f"Simulator state file not found after start: {state_file}")
        return 1
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        logger.exception(
            "failed to read simulator state file state_file=%s",
            state_file,
            exc_info=exc,
        )
        print(f"Failed to read simulator state file {state_file}: {exc}", file=sys.stderr)
        return 1
    instances = payload.get("instances", []) if isinstance(payload, dict) else []
    if not isinstance(instances, list):
        instances = []
    recorded = 0
    for instance in instances:
        if not isinstance(instance, dict):
            continue
        pid = int(instance.get("pid", 0) or 0)
        name = str(instance.get("name", "simulator")).strip() or "simulator"
        if pid <= 0:
            continue
        if _is_process_running(pid) is not True:
            _append_log_line(log_file, f"[{_utc_timestamp()}] simulator_not_running={name}:{pid}")
            logger.warning(
                "simulator instance was not running when discovered name=%s pid=%s state_file=%s",
                name,
                pid,
                state_file,
            )
            continue
        _record_cli_process(
            name=f"Simulator:{name}",
            pid=pid,
            command_text=str(action.get("command_text") or ""),
            cwd=Path(str(instance.get("working_dir") or cwd)).resolve(),
            log_file=log_file,
            metadata={"state_file": str(state_file)},
        )
        recorded += 1
    logger.info(
        "simulator batch recorded instances recorded=%s state_file=%s log_file=%s",
        recorded,
        state_file,
        log_file,
    )
    print(f"Started Simulator batch with {recorded} recorded process(es)")
    _open_process_tail_if_enabled(
        label=str(action.get("label") or "Simulator"),
        log_file=log_file,
    )
    return 0


def _stop_recorded_processes(record_names: list[str]) -> int:
    """Stop all recorded managed processes that match provided names."""
    logger = _get_logger()
    payload = _prune_cli_process_state()
    targets = {str(name) for name in record_names}
    matches = [
        record
        for record in payload.get("processes", [])
        if str(record.get("name")) in targets
    ]
    if not matches:
        logger.info("no recorded processes matched stop request targets=%s", sorted(targets))
        print("No recorded process IDs found for that selection.")
        return 0

    for record in matches:
        pid = int(record.get("pid", 0) or 0)
        name = str(record.get("name") or "process")
        if pid <= 0:
            continue
        try:
            if _is_windows():
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.kill(pid, 15)
        except OSError:
            pass
        logger.info("stopped recorded process name=%s pid=%s", name, pid)
        print(f"Stopped {name} pid={pid}")

    _remove_cli_process_records(targets)
    return 0


def _interactive_loop() -> int:
    """Run a REPL that executes or generates on each submitted line."""
    logger = _get_logger()
    words = _top_level_commands()
    input_reader = _prompt_toolkit_input_reader(words)
    if input_reader is None:
        input_reader = _builtin_tty_input_reader(words)
    if input_reader is None:
        _setup_readline_completion(words)
        if _is_windows():
            print(
                "Autocomplete fallback is unavailable in this terminal. "
                "Install prompt_toolkit with: python -m pip install prompt_toolkit"
            )
    print("Prompt CLI ready. Prefix with 'script' to generate a script file.")
    print(
        "Example: script demo-start-clients "
        "python -m opamp_consumer.fluentbit_client"
    )
    print("You can type `start server`, `stop config service`, or `restart server` directly.")
    print("Use `enable-process-tail` to tail managed process logs in a new shell.")
    print("Type 'exit' or press Ctrl+D to quit.")
    logger.info("interactive CLI loop started")

    while True:
        try:
            if input_reader is not None:
                raw = input_reader("opamp> ")
            else:
                raw = input("opamp> ")
        except EOFError:
            logger.info("interactive CLI loop exited via EOF")
            print()
            return 0
        except KeyboardInterrupt:
            logger.info("interactive CLI input interrupted by user")
            print()
            continue

        if raw.strip().lower() in {"exit", "quit"}:
            logger.info("interactive CLI loop exited via explicit command")
            return 0
        if raw.strip().lower() in {"help", "-h", "--help"}:
            logger.info("interactive help requested")
            print(HELP_TEXT)
            continue
        if raw.strip().lower() == "status":
            logger.info("interactive status requested")
            _print_status()
            continue
        guided = _split_guided_command(raw)
        if guided is not None:
            intent, selection = guided
            try:
                code = _execute_guided_action(
                    input_reader=input_reader,
                    intent=intent,
                    selection=selection,
                )
            except Exception as exc:  # pragma: no cover - defensive CLI guard
                logger.exception(
                    "guided action failed in interactive loop intent=%s selection=%s",
                    intent,
                    selection,
                    exc_info=exc,
                )
                print(f"Error: {exc}", file=sys.stderr)
                code = 1
            if code != 0:
                print(f"Command exited with code {code}")
            continue

        try:
            code = _handle_command(raw)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            logger.exception("interactive command failed raw=%s", raw, exc_info=exc)
            print(f"Error: {exc}", file=sys.stderr)
            code = 1

        if code != 0:
            print(f"Command exited with code {code}")


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    logger = _get_logger()
    args = list(sys.argv[1:] if argv is None else argv)
    logger.info("CLI main started argv=%s", args)
    if not args:
        exit_code = _interactive_loop()
        logger.info("CLI main completed interactive exit_code=%s", exit_code)
        return exit_code
    if args[0] in {"-h", "--help", "help"}:
        logger.info("CLI help requested argv=%s", args)
        print(HELP_TEXT)
        return 0

    raw_command = _command_text_from_args(args)
    try:
        guided = _split_guided_command(raw_command)
        if guided is not None:
            intent, selection = guided
            exit_code = _execute_guided_action(
                input_reader=None,
                intent=intent,
                selection=selection,
            )
            logger.info(
                "CLI main completed guided command intent=%s selection=%s exit_code=%s",
                intent,
                selection,
                exit_code,
            )
            return exit_code
        exit_code = _handle_command(raw_command)
        logger.info("CLI main completed command raw=%s exit_code=%s", raw_command, exit_code)
        return exit_code
    except ValueError as exc:
        logger.warning("CLI rejected command raw=%s error=%s", raw_command, exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        logger.exception("CLI main failed raw=%s", raw_command, exc_info=exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
