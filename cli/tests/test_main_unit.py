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
import subprocess
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


def test_split_guided_command_supports_restart() -> None:
    parsed = cli_main._split_guided_command("restart server")  # type: ignore[attr-defined]
    parsed_no_target = cli_main._split_guided_command("restart")  # type: ignore[attr-defined]

    assert parsed == ("restart", "server")
    assert parsed_no_target == ("restart", "")


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


def test_disable_enable_process_tail_alias_disables_setting(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)

    cli_main._set_process_tail_enabled(True)  # type: ignore[attr-defined]
    exit_code = cli_main._handle_command("disable enable-process-tail")  # type: ignore[attr-defined]

    assert exit_code == 0
    assert cli_main._process_tail_enabled() is False  # type: ignore[attr-defined]


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


def test_status_command_reports_default_opamp_config_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    runtime_dir = tmp_path / "runtime"
    repo_root = tmp_path / "repo"
    config_path = repo_root / "config" / "opamp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"opamp": {}}\n', encoding="utf-8")
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(cli_main, "_repo_root", lambda: repo_root)
    monkeypatch.delenv("OPAMP_CONFIG_PATH", raising=False)

    exit_code = cli_main.main(["status"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert f"OpAMP config file: {config_path.resolve()} (default)" in output
    assert "OpAMP config loaded: yes" in output


def test_status_command_reports_env_opamp_config_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    runtime_dir = tmp_path / "runtime"
    repo_root = tmp_path / "repo"
    config_path = repo_root / "config" / "custom-opamp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"opamp": {}}\n', encoding="utf-8")
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(cli_main, "_repo_root", lambda: repo_root)
    monkeypatch.setenv("OPAMP_CONFIG_PATH", "config/custom-opamp.json")

    exit_code = cli_main.main(["status"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert f"OpAMP config file: {config_path.resolve()} (OPAMP_CONFIG_PATH)" in output
    assert "OpAMP config loaded: yes" in output


def test_status_command_reports_invalid_opamp_config(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    runtime_dir = tmp_path / "runtime"
    repo_root = tmp_path / "repo"
    config_path = repo_root / "config" / "opamp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(cli_main, "_repo_root", lambda: repo_root)
    monkeypatch.delenv("OPAMP_CONFIG_PATH", raising=False)

    exit_code = cli_main.main(["status"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert f"OpAMP config file: {config_path.resolve()} (default)" in output
    assert "OpAMP config loaded: no (invalid JSON:" in output


def test_is_process_running_uses_tasklist_on_windows(monkeypatch) -> None:
    captured_commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        captured_commands.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='"python.exe","4321","Console","1","10,240 K"\n',
            stderr="",
        )

    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)

    is_running = cli_main._is_process_running(4321)  # type: ignore[attr-defined]

    assert is_running is True
    assert captured_commands == [["tasklist", "/FI", "PID eq 4321", "/FO", "CSV", "/NH"]]


def test_status_command_handles_windows_managed_processes(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime_dir = tmp_path / "runtime"
    state_path = runtime_dir / "managed_processes.json"
    monkeypatch.setattr(cli_main, "_cli_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(
        cli_main.os,
        "kill",
        lambda _pid, _signal: (_ for _ in ()).throw(AssertionError("os.kill should not be used")),
    )

    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "processes": [
                    {
                        "name": "Server",
                        "pid": 9876,
                        "started_at": "2026-06-03T15:50:04Z",
                        "cwd": "D:/dev/opamp",
                        "log_file": "D:/dev/opamp/cli/runtime/logs/server.log",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='"python.exe","9876","Console","1","10,240 K"\n',
            stderr="",
        )

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)

    exit_code = cli_main.main(["status"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Managed processes: 1" in output
    assert "status: running" in output


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
    stop_all_action = cli_main._resolve_guided_action("stop", "all")  # type: ignore[attr-defined]
    restart_action = cli_main._resolve_guided_action("restart", "catalog")  # type: ignore[attr-defined]

    assert start_action is not None
    assert start_action["label"] == "Catalog"
    assert "-m catalog_service " in str(start_action.get("command_text") or "")
    assert stop_action is not None
    assert stop_action["label"] == "All clients"
    assert stop_all_action is not None
    assert stop_all_action["label"] == "All managed processes"
    assert restart_action is not None
    assert restart_action["label"] == "Catalog"


def test_start_and_stop_action_orders_are_stable(monkeypatch) -> None:
    monkeypatch.delenv("OPAMP_DEMO", raising=False)
    start_labels = [label for label, _action in cli_main._start_actions()]  # type: ignore[attr-defined]
    stop_labels = [label for label, _action in cli_main._stop_actions()]  # type: ignore[attr-defined]
    restart_labels = [label for label, _action in cli_main._restart_actions()]  # type: ignore[attr-defined]

    assert start_labels == [
        "Server",
        "Catalog",
        "Config Editor",
        "Broker",
        "Simulator",
        "Fluent Bit client",
        "Fluentd client",
    ]
    assert stop_labels == [
        "Server",
        "Catalog",
        "Broker",
        "Simulator",
        "Config Editor",
        "Fluent Bit client",
        "Fluentd client",
        "All clients",
        "All managed processes",
    ]
    assert restart_labels == start_labels


def test_broker_stop_action_uses_cli_managed_process_records() -> None:
    stop_action = cli_main._resolve_guided_action("stop", "broker")  # type: ignore[attr-defined]

    assert stop_action is not None
    assert stop_action["kind"] == "stop_recorded"
    assert stop_action["record_names"] == ["Broker"]


def test_script_mode_generates_broker_launcher_script(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = cli_main._handle_command(  # type: ignore[attr-defined]
        "script broker-launch python -m opamp_broker.broker_app "
        "--config-path ./opamp_broker/config/broker.ui_responses.json"
    )

    suffix = ".cmd" if cli_main._is_windows() else ".sh"  # type: ignore[attr-defined]
    script_path = tmp_path / "scripts" / f"broker-launch{suffix}"

    assert exit_code == 0
    assert script_path.exists()
    script_text = script_path.read_text(encoding="utf-8")
    assert "python -m opamp_broker.broker_app" in script_text
    assert "--config-path ./opamp_broker/config/broker.ui_responses.json" in script_text


def test_list_command_prints_hierarchy(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPAMP_DEMO", raising=False)

    exit_code = cli_main._handle_command("list")  # type: ignore[attr-defined]
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Control flags:" in output
    assert "Top-level commands:" in output
    assert "Guided actions:" in output
    assert "start:" in output
    assert "stop:" in output
    assert "restart:" in output


def test_list_command_reflects_demo_flag(monkeypatch, tmp_path: Path, capsys) -> None:
    demo_config = tmp_path / "demo_profiles.json"
    demo_config.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "name": "script-defaults",
                        "simulator": {"instances_path": "consumer-sim/consumer_instances.json"},
                        "fluentbit": {
                            "config_path": "tests/opamp.json",
                            "agent_config_path": "tests/fluent-bit.yaml",
                        },
                        "fluentd": {
                            "config_path": "consumer/opamp-fluentd.json",
                            "agent_config_path": "consumer/fluentd.conf",
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPAMP_DEMO", "true")
    monkeypatch.setattr(cli_main, "_demo_consumer_config_path", lambda: demo_config)

    exit_code = cli_main._handle_command("list")  # type: ignore[attr-defined]
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "OPAMP_DEMO: enabled" in output
    assert "  - demo" in output
    assert "Demo consumers (script-defaults)" in output


def test_restart_action_runs_stop_wait_cleanup_then_start(monkeypatch) -> None:
    events: list[str] = []
    restart_action = {
        "id": "server",
        "kind": "restart",
        "label": "Server",
        "start_action": {"id": "server", "kind": "background_start", "label": "Server"},
        "stop_action": {"id": "server", "kind": "shell", "label": "Server"},
    }

    def fake_stop(_action):
        events.append("stop")
        return 0

    def fake_tracked_pids(**_kwargs):
        events.append("track")
        return [4242]

    def fake_wait(**_kwargs):
        events.append("wait")
        return True, []

    def fake_prune():
        events.append("cleanup")
        return {"processes": []}

    def fake_start(_action):
        events.append("start")
        return 0

    monkeypatch.setattr(cli_main, "_execute_stop_action", fake_stop)
    monkeypatch.setattr(cli_main, "_tracked_restart_pids", fake_tracked_pids)
    monkeypatch.setattr(cli_main, "_wait_for_pids_to_exit", fake_wait)
    monkeypatch.setattr(cli_main, "_prune_cli_process_state", fake_prune)
    monkeypatch.setattr(cli_main, "_execute_start_action", fake_start)

    code = cli_main._execute_restart_action(restart_action)  # type: ignore[attr-defined]

    assert code == 0
    assert events == ["track", "stop", "wait", "cleanup", "start"]


def test_demo_mode_adds_profile_actions(monkeypatch, tmp_path: Path) -> None:
    demo_config = tmp_path / "demo_profiles.json"
    demo_config.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "name": "script-defaults",
                        "simulator": {"instances_path": "consumer-sim/consumer_instances.json"},
                        "fluentbit": {
                            "config_path": "tests/opamp.json",
                            "agent_config_path": "tests/fluent-bit.yaml",
                        },
                        "fluentd": {
                            "config_path": "consumer/opamp-fluentd.json",
                            "agent_config_path": "consumer/fluentd.conf",
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("OPAMP_DEMO", "true")
    monkeypatch.setattr(cli_main, "_demo_consumer_config_path", lambda: demo_config)

    start_labels = [label for label, _action in cli_main._start_actions()]  # type: ignore[attr-defined]
    stop_labels = [label for label, _action in cli_main._stop_actions()]  # type: ignore[attr-defined]

    assert "Demo consumers (script-defaults)" in start_labels
    assert "Demo consumers (script-defaults)" in stop_labels


def test_demo_profile_alias_resolves_guided_action(monkeypatch, tmp_path: Path) -> None:
    demo_config = tmp_path / "demo_profiles.json"
    demo_config.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "name": "repo-defaults",
                        "simulator": {"instances_path": "consumer-sim/consumer_instances.json"},
                        "fluentbit": {
                            "config_path": "config/opamp.json",
                            "agent_config_path": "consumer/fluent-bit.yaml",
                        },
                        "fluentd": {
                            "config_path": "config/opamp.json",
                            "agent_config_path": "consumer/fluentd.conf",
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("OPAMP_DEMO", "true")
    monkeypatch.setattr(cli_main, "_demo_consumer_config_path", lambda: demo_config)

    action = cli_main._resolve_guided_action("start", "demo consumers repo-defaults")  # type: ignore[attr-defined]

    assert action is not None
    assert action["kind"] == "demo_consumers_start"
    assert action["profile_name"] == "repo-defaults"


def test_top_level_commands_include_demo_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("OPAMP_DEMO", "true")

    commands = cli_main._top_level_commands()  # type: ignore[attr-defined]

    assert "demo" in commands


def test_split_guided_command_maps_demo_shorthand_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("OPAMP_DEMO", "true")

    assert cli_main._split_guided_command("demo") == ("start", "demo consumers")  # type: ignore[attr-defined]
    assert cli_main._split_guided_command("demo repo-defaults") == ("start", "demo repo-defaults")  # type: ignore[attr-defined]


def test_split_guided_command_ignores_demo_shorthand_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("OPAMP_DEMO", raising=False)

    assert cli_main._split_guided_command("demo") is None  # type: ignore[attr-defined]


def test_start_demo_consumers_prompts_for_profile_choices(monkeypatch, tmp_path: Path) -> None:
    demo_config = tmp_path / "demo_profiles.json"
    demo_config.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "name": "script-defaults",
                        "simulator": {"instances_path": "consumer-sim/consumer_instances.json"},
                        "fluentbit": {
                            "config_path": "tests/opamp.json",
                            "agent_config_path": "tests/fluent-bit.yaml",
                        },
                        "fluentd": {
                            "config_path": "consumer/opamp-fluentd.json",
                            "agent_config_path": "consumer/fluentd.conf",
                        },
                    },
                    {
                        "name": "repo-defaults",
                        "simulator": {"instances_path": "consumer-sim/consumer_instances.json"},
                        "fluentbit": {
                            "config_path": "config/opamp.json",
                            "agent_config_path": "consumer/fluent-bit.yaml",
                        },
                        "fluentd": {
                            "config_path": "config/opamp.json",
                            "agent_config_path": "consumer/fluentd.conf",
                        },
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPAMP_DEMO", "true")
    monkeypatch.setattr(cli_main, "_demo_consumer_config_path", lambda: demo_config)

    captured_labels: list[str] = []

    def fake_select(*, input_reader, intent, actions):  # type: ignore[no-untyped-def]
        del input_reader
        del intent
        captured_labels.extend(label for label, _action in actions)
        return actions[0][1]

    monkeypatch.setattr(cli_main, "_select_guided_action", fake_select)
    monkeypatch.setattr(cli_main, "_execute_start_action", lambda action: 0)

    code = cli_main._execute_guided_action(  # type: ignore[attr-defined]
        input_reader=None,
        intent="start",
        selection="demo consumers",
    )

    assert code == 0
    assert captured_labels == [
        "Demo consumers (script-defaults)",
        "Demo consumers (repo-defaults)",
    ]


def test_stop_all_recorded_processes_loops_all_record_names(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_main,
        "_prune_cli_process_state",
        lambda: {
            "processes": [
                {"name": "Server", "pid": 1001},
                {"name": "Fluent Bit client", "pid": 1002},
                {"name": "Server", "pid": 1003},
            ]
        },
    )
    captured: dict[str, list[str]] = {"names": []}

    def fake_stop(names):
        captured["names"] = list(names)
        return 0

    monkeypatch.setattr(cli_main, "_stop_recorded_processes", fake_stop)

    code = cli_main._stop_all_recorded_processes()  # type: ignore[attr-defined]

    assert code == 0
    assert sorted(captured["names"]) == ["Fluent Bit client", "Server"]


def test_stop_recorded_processes_reports_when_nothing_matches(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli_main,
        "_prune_cli_process_state",
        lambda: {
            "processes": [
                {"name": "Config Editor", "pid": 1001},
            ]
        },
    )

    code = cli_main._stop_recorded_processes(["Server"])  # type: ignore[attr-defined]
    output = capsys.readouterr().out

    assert code == 0
    assert "No recorded process IDs found for that selection." in output


def test_execute_stop_server_propagates_failure_when_not_running(monkeypatch, capsys) -> None:
    action = cli_main._resolve_guided_action("stop", "server")  # type: ignore[attr-defined]
    captured: dict[str, str] = {"command": ""}

    def fake_handle_command(command_text: str) -> int:
        captured["command"] = command_text
        return 1

    monkeypatch.setattr(cli_main, "_handle_command", fake_handle_command)

    assert action is not None

    code = cli_main._execute_stop_action(action)  # type: ignore[attr-defined]
    output = capsys.readouterr().out

    assert code == 1
    assert "Executing:" in output
    assert "127.0.0.1:8080" in captured["command"]
    assert "/api/shutdown" in captured["command"]


def test_stop_all_recorded_processes_reports_when_none_recorded(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "_prune_cli_process_state", lambda: {"processes": []})

    code = cli_main._stop_all_recorded_processes()  # type: ignore[attr-defined]
    output = capsys.readouterr().out

    assert code == 0
    assert "No recorded managed processes to stop." in output


def test_record_simulator_batch_reports_logged_failure_detail(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    log_file = tmp_path / "simulator.log"
    state_file = tmp_path / "launcher_state.json"

    def fake_prepare_log(**_kwargs) -> Path:
        log_file.write_text("", encoding="utf-8")
        return log_file

    def fake_run(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        stdout_handle = kwargs["stdout"]
        stdout_handle.write(
            "[consumer-sim] cannot start: existing launched consumer instances are still running\n"
        )
        return subprocess.CompletedProcess(args=argv, returncode=1)

    monkeypatch.setattr(cli_main, "_prepare_launch_log", fake_prepare_log)
    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)

    code = cli_main._record_simulator_batch(  # type: ignore[attr-defined]
        {
            "label": "Simulator",
            "command_text": "python consumer-sim/src/consumer_sim_launcher.py start",
            "argv": ["python", "consumer-sim/src/consumer_sim_launcher.py", "start"],
            "cwd": str(tmp_path),
            "env": {},
            "state_file": str(state_file),
        }
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "Simulator failed to start:" in captured.err
    assert "existing launched consumer instances are still running" in captured.err
    assert str(log_file) in captured.err


def test_record_simulator_batch_short_circuits_when_already_running(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state_file = tmp_path / "launcher_state.json"
    state_file.write_text(
        json.dumps(
            {
                "instances": [
                    {"name": "consumer-simulator-1", "pid": 4321},
                    {"name": "consumer-simulator-2", "pid": 4322},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli_main, "_is_process_running", lambda pid: pid in {4321, 4322})
    monkeypatch.setattr(
        cli_main.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("launcher should not run")),
    )

    code = cli_main._record_simulator_batch(  # type: ignore[attr-defined]
        {
            "label": "Simulator",
            "command_text": "python consumer-sim/src/consumer_sim_launcher.py start",
            "argv": ["python", "consumer-sim/src/consumer_sim_launcher.py", "start"],
            "cwd": str(tmp_path),
            "env": {},
            "state_file": str(state_file),
        }
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "Simulator already running:" in captured.err
    assert "consumer-simulator-1" in captured.err
    assert "consumer-simulator-2" in captured.err
    assert "Stop simulator before starting it again." in captured.err


def test_detected_behavior_flags_returns_empty_when_none_set(monkeypatch) -> None:
    monkeypatch.delenv("OPAMP_DEMO", raising=False)
    monkeypatch.delenv("APP_ENABLE_DEV_FEATURES", raising=False)
    monkeypatch.setattr(cli_main, "_process_tail_enabled", lambda: False)

    detected = cli_main._detected_behavior_flags()  # type: ignore[attr-defined]

    assert detected == []


def test_detected_behavior_flags_returns_only_enabled_flags(monkeypatch) -> None:
    monkeypatch.setenv("OPAMP_DEMO", "true")
    monkeypatch.setenv("APP_ENABLE_DEV_FEATURES", "true")
    monkeypatch.setattr(cli_main, "_process_tail_enabled", lambda: True)

    detected = cli_main._detected_behavior_flags()  # type: ignore[attr-defined]

    assert "OPAMP_DEMO=true" in detected
    assert "APP_ENABLE_DEV_FEATURES=true" in detected
    assert "enable_process_tail=true" in detected


def test_top_level_commands_include_dev_flb_config_only_when_available(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_demo_mode_enabled", lambda: False)
    monkeypatch.setattr(cli_main, "_fluentbit_dev_tool_available", lambda: True)
    monkeypatch.setattr(cli_main, "_mcp_dev_tool_available", lambda: False)

    commands = cli_main._top_level_commands()  # type: ignore[attr-defined]

    assert "dev-flb-config" in commands

    monkeypatch.setattr(cli_main, "_fluentbit_dev_tool_available", lambda: False)
    commands = cli_main._top_level_commands()  # type: ignore[attr-defined]
    assert "dev-flb-config" not in commands


def test_top_level_commands_include_dev_mcp_config_only_when_available(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_demo_mode_enabled", lambda: False)
    monkeypatch.setattr(cli_main, "_fluentbit_dev_tool_available", lambda: False)
    monkeypatch.setattr(cli_main, "_mcp_dev_tool_available", lambda: True)

    commands = cli_main._top_level_commands()  # type: ignore[attr-defined]

    assert "dev-mcp-config" in commands

    monkeypatch.setattr(cli_main, "_mcp_dev_tool_available", lambda: False)
    commands = cli_main._top_level_commands()  # type: ignore[attr-defined]
    assert "dev-mcp-config" not in commands


def test_handle_command_routes_dev_flb_config_to_workflow(monkeypatch) -> None:
    called: dict[str, int] = {"count": 0}

    def fake_workflow(*, input_reader=None):  # type: ignore[no-untyped-def]
        assert input_reader is None
        called["count"] += 1
        return 0

    monkeypatch.setattr(cli_main, "_execute_dev_fluentbit_config_workflow", fake_workflow)

    code = cli_main._handle_command("dev-flb-config")  # type: ignore[attr-defined]

    assert code == 0
    assert called["count"] == 1


def test_handle_command_routes_dev_mcp_config_to_workflow(monkeypatch) -> None:
    called: dict[str, int] = {"count": 0}

    def fake_workflow(*, input_reader=None):  # type: ignore[no-untyped-def]
        assert input_reader is None
        called["count"] += 1
        return 0

    monkeypatch.setattr(cli_main, "_execute_dev_mcp_config_workflow", fake_workflow)

    code = cli_main._handle_command("dev-mcp-config")  # type: ignore[attr-defined]

    assert code == 0
    assert called["count"] == 1


def test_execute_dev_fluentbit_config_workflow_prompts_and_runs_selected_tool(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_dev_features_enabled", lambda: True)
    monkeypatch.setattr(
        cli_main,
        "_fluentbit_dev_tool_specs",
        lambda: [
            {
                "id": "fluentbit_assets",
                "label": "Generate Fluent Bit assets",
                "description": "Generate catalog artifacts.",
                "script_path": "/tmp/generate_fluentbit_assets.py",
                "arguments": [
                    {
                        "name": "versions",
                        "flag": "--version",
                        "prompt": "Version",
                        "required": True,
                        "multiple": True,
                        "default": "5.0.7",
                    },
                    {
                        "name": "generate_schemas",
                        "prompt": "Generate schemas",
                        "kind": "bool",
                        "default": True,
                        "args_when_false": ["--no-schemas"],
                    },
                ],
            }
        ],
    )

    prompts = iter(["1", "5.0.7,5.0.8", "n"])
    captured: dict[str, list[str]] = {"argv": []}

    def fake_reader(_prompt: str) -> str:
        return next(prompts)

    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        captured["argv"] = list(argv)
        return subprocess.CompletedProcess(args=argv, returncode=0)

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)

    code = cli_main._execute_dev_fluentbit_config_workflow(  # type: ignore[attr-defined]
        input_reader=fake_reader
    )

    assert code == 0
    assert captured["argv"] == [
        cli_main.sys.executable,
        "/tmp/generate_fluentbit_assets.py",
        "--version",
        "5.0.7",
        "--version",
        "5.0.8",
        "--no-schemas",
    ]


def test_execute_dev_mcp_config_workflow_prompts_and_runs_selected_tool(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_dev_features_enabled", lambda: True)
    monkeypatch.setattr(
        cli_main,
        "_mcp_dev_tool_specs",
        lambda: [
            {
                "id": "mcp_client_config",
                "label": "Configure MCP clients",
                "description": "Update MCP client settings.",
                "script_path": "/tmp/configure_mcp_clients.py",
                "fixed_args": ["--yes"],
                "arguments": [
                    {
                        "name": "clients",
                        "flag": "--clients",
                        "prompt": "Enabled clients",
                        "required": True,
                        "default": "claude,codex,vscode",
                    },
                    {
                        "name": "server_host",
                        "flag": "--server-host",
                        "prompt": "Server host",
                        "default": "localhost",
                    },
                    {
                        "name": "preview",
                        "prompt": "Preview only",
                        "kind": "bool",
                        "default": False,
                        "args_when_true": ["--preview"],
                    },
                ],
            }
        ],
    )

    prompts = iter(["1", "claude,codex", "broker.local", "y"])
    captured: dict[str, list[str]] = {"argv": []}

    def fake_reader(_prompt: str) -> str:
        return next(prompts)

    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        captured["argv"] = list(argv)
        return subprocess.CompletedProcess(args=argv, returncode=0)

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)

    code = cli_main._execute_dev_mcp_config_workflow(  # type: ignore[attr-defined]
        input_reader=fake_reader
    )

    assert code == 0
    assert captured["argv"] == [
        cli_main.sys.executable,
        "/tmp/configure_mcp_clients.py",
        "--yes",
        "--clients",
        "claude,codex",
        "--server-host",
        "broker.local",
        "--preview",
    ]
