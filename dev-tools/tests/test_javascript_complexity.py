from __future__ import annotations

import subprocess
from pathlib import Path

import opamp_dev_tools.javascript_complexity as javascript_complexity


class _RuntimeStub:
    def __init__(self, repo_root: Path, *, completed: subprocess.CompletedProcess[str]) -> None:
        self.repo_root = repo_root
        self.completed = completed
        self.commands: list[list[str]] = []
        self.messages: list[str] = []
        self.issues: list[tuple[str, dict[str, object]]] = []
        self.errors: list[tuple[str, dict[str, object]]] = []

    def run(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return self.completed

    def info(self, message: str) -> None:
        self.messages.append(message)

    def record_issue(self, message: str, **kwargs: object) -> None:
        self.issues.append((message, dict(kwargs)))

    def record_error(self, message: str, **kwargs: object) -> None:
        self.errors.append((message, dict(kwargs)))


def test_run_javascript_complexity_checks_runs_eslint_for_matching_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_file(tmp_path / "provider" / "src" / "opamp_provider" / "html" / "web_ui.js", "function ok() {}\n")
    _write_file(tmp_path / "provider" / "src" / "opamp_provider" / "html" / "web_ui.mini.js", "minified();\n")
    _write_file(tmp_path / "config-service" / "frontend" / "src" / "App.tsx", "export function App() { return null; }\n")
    monkeypatch.setattr(javascript_complexity.shutil, "which", lambda tool: "/usr/bin/npx" if tool == "npx" else None)
    runtime = _RuntimeStub(
        tmp_path,
        completed=subprocess.CompletedProcess(
            args=["eslint"],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    issues_found = javascript_complexity.run_javascript_complexity_checks(
        runtime,
        target_paths=["provider/src", "config-service/frontend/src"],
    )

    assert issues_found is False
    assert len(runtime.commands) == 1
    command = runtime.commands[0]
    assert command[0:3] == ["npx", "--yes", "--package"]
    assert "eslint" in command
    assert "provider/src/opamp_provider/html/web_ui.js" in command
    assert "config-service/frontend/src/App.tsx" in command
    assert "provider/src/opamp_provider/html/web_ui.mini.js" not in command
    assert runtime.messages[-1] == "JavaScript/TypeScript complexity checks passed."


def test_run_javascript_complexity_checks_records_issue_on_complexity_violation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_file(tmp_path / "config-service" / "src" / "config_service" / "html" / "config_ui.js", "function tooComplex() {}\n")
    monkeypatch.setattr(javascript_complexity.shutil, "which", lambda tool: "/usr/bin/npx" if tool == "npx" else None)
    runtime = _RuntimeStub(
        tmp_path,
        completed=subprocess.CompletedProcess(
            args=["eslint"],
            returncode=1,
            stdout="config_ui.js\n  1:1  error  Function has a complexity of 21  complexity\n",
            stderr="",
        ),
    )

    issues_found = javascript_complexity.run_javascript_complexity_checks(
        runtime,
        max_complexity=20,
        target_paths=["config-service/src"],
    )

    assert issues_found is True
    assert len(runtime.issues) == 1
    message, details = runtime.issues[0]
    assert "cyclomatic-complexity violations" in message
    assert details["category"] == "javascript-complexity"
    assert details["details"]["max_complexity"] == 20
    assert "Function has a complexity of 21" in str(details["details"]["output"])


def _write_file(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
