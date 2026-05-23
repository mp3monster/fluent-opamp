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

"""CLI unit test coverage.

Test-case reference: cli/docs/TEST_CASES.md
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

cli_main = importlib.import_module("opamp_cli.main")


def test_split_script_directive_parses_output_name_and_command() -> None:
    output_name, command_text = cli_main._split_script_directive(  # type: ignore[attr-defined]
        "script demo-start echo hello"
    )

    assert output_name == "demo-start"
    assert command_text == "echo hello"


def test_normalize_python_script_command_prefixes_python_launcher() -> None:
    normalized = cli_main._normalize_python_script_command(  # type: ignore[attr-defined]
        "cli/main.py --help",
        launcher="python3",
    )

    assert normalized == "\"python3\" cli/main.py --help"


def test_command_text_from_args_preserves_shell_quoting() -> None:
    command_text = cli_main._command_text_from_args(  # type: ignore[attr-defined]
        ["python", "-c", "print('cli-e2e-ok')"]
    )

    assert "python" in command_text
    assert "-c" in command_text
    assert "cli-e2e-ok" in command_text


def test_materialize_ordered_actions_preserves_order_and_skips_missing() -> None:
    actions = cli_main._materialize_ordered_actions(  # type: ignore[attr-defined]
        order=["two", "missing", "one"],
        action_map={
            "one": {"id": "one", "label": "One"},
            "two": {"id": "two", "label": "Two"},
        },
    )

    assert [label for label, _action in actions] == ["Two", "One"]


def test_catalog_launch_config_path_enables_catalog(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)

    config_path = tmp_path / "opamp.json"
    base_config = {
        "opamp": {
            "config_catalog": {
                "enabled": False,
                "sources": [{"folder": "config-service/json-definitions", "extensions": [".json"]}],
            }
        }
    }
    config_path.write_text(json.dumps(base_config) + "\n", encoding="utf-8")

    generated = cli_main._catalog_launch_config_path(  # type: ignore[attr-defined]
        base_config_path=config_path,
        base_config=base_config,
    )

    assert generated == (runtime_dir / "catalog-service.json").resolve()
    payload = json.loads(generated.read_text(encoding="utf-8"))
    assert payload["opamp"]["config_catalog"]["enabled"] is True
    assert payload["_generated_from"] == str(config_path.resolve())


def test_process_tail_setting_round_trip(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)

    cli_main._set_process_tail_enabled(True)  # type: ignore[attr-defined]

    assert cli_main._process_tail_enabled() is True  # type: ignore[attr-defined]
    payload = json.loads((runtime_dir / "settings.json").read_text(encoding="utf-8"))
    assert payload["enable_process_tail"] is True


def test_main_writes_component_lifecycle_log(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)

    exit_code = cli_main.main(["status"])

    log_path = runtime_dir / "logs" / "opamp_cli.log"
    assert exit_code == 0
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "CLI main started" in log_text
    assert "printing CLI status" in log_text
    assert "CLI main completed command" in log_text


def test_rejected_guided_action_is_logged(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)

    exit_code = cli_main._execute_guided_action(  # type: ignore[attr-defined]
        input_reader=None,
        intent="start",
        selection="does-not-exist",
    )

    log_path = runtime_dir / "logs" / "opamp_cli.log"
    assert exit_code == 1
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "rejected guided action" in log_text
    assert "does-not-exist" in log_text


def test_resolve_guided_action_matches_aliases() -> None:
    start_action = cli_main._resolve_guided_action("start", "catalog")  # type: ignore[attr-defined]
    stop_action = cli_main._resolve_guided_action("stop", "clients")  # type: ignore[attr-defined]

    assert start_action is not None
    assert start_action["label"] == "Config Catalog UI"
    assert stop_action is not None
    assert stop_action["label"] == "All clients"


def test_start_and_stop_action_orders_are_stable() -> None:
    start_labels = [label for label, _action in cli_main._start_actions()]  # type: ignore[attr-defined]
    stop_labels = [label for label, _action in cli_main._stop_actions()]  # type: ignore[attr-defined]

    assert start_labels == [
        "Server",
        "Config Catalog UI",
        "Config Service",
        "Broker",
        "Simulator",
        "Fluent Bit client",
        "Fluentd client",
    ]
    assert stop_labels == [
        "Server",
        "Broker",
        "Simulator",
        "Config Service",
        "Fluent Bit client",
        "Fluentd client",
        "All clients",
    ]
