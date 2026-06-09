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

"""CLI end-to-end test coverage.

Test-case reference: cli/docs/TEST_CASES.md
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cli_entrypoint() -> Path:
    return (_repo_root() / "cli" / "main.py").resolve()


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(_cli_entrypoint()), *args],
        cwd=str(cwd or _repo_root()),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_command_prints_usage() -> None:
    completed = _run_cli("--help")

    assert completed.returncode == 0
    assert "Usage:" in completed.stdout
    assert "opamp-cli start server" in completed.stdout


def test_status_command_reports_runtime_paths() -> None:
    completed = _run_cli("status")

    assert completed.returncode == 0
    assert "OpAMP config file:" in completed.stdout
    assert "OpAMP config loaded:" in completed.stdout
    assert "State file:" in completed.stdout
    assert "Log directory:" in completed.stdout
    assert "CLI log file:" in completed.stdout


def test_list_command_reports_option_hierarchy() -> None:
    completed = _run_cli("list")

    assert completed.returncode == 0
    assert "Control flags:" in completed.stdout
    assert "Top-level commands:" in completed.stdout
    assert "Guided actions:" in completed.stdout


def test_direct_execution_runs_python_command() -> None:
    completed = _run_cli(sys.executable, "-c", "print('cli-e2e-ok')")

    assert completed.returncode == 0
    assert "cli-e2e-ok" in completed.stdout


def test_script_generation_writes_os_native_script(tmp_path: Path) -> None:
    completed = _run_cli("script", "demo-start", "echo", "hello", cwd=tmp_path)

    expected = tmp_path / "scripts" / f"demo-start{'.cmd' if os.name == 'nt' else '.sh'}"
    assert completed.returncode == 0
    assert expected.exists()
    assert "Generated script:" in completed.stdout
    assert "echo hello" in expected.read_text(encoding="utf-8")


def test_unknown_guided_target_returns_error() -> None:
    completed = _run_cli("start", "does-not-exist")

    assert completed.returncode == 1
    assert "Unknown start target" in completed.stderr


def test_unknown_restart_target_returns_error() -> None:
    completed = _run_cli("restart", "does-not-exist")

    assert completed.returncode == 1
    assert "Unknown restart target" in completed.stderr
