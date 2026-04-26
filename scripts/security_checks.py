#!/usr/bin/env python3
"""Run OpAMP security and quality checks used by wheel build workflows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_ENABLE_DEV_FEATURES_ENV = "APP_ENABLE_DEV_FEATURES"
SECURITY_CHECKS_HEADER = "=== OpAMP Security Checks ==="
DETECT_SECRETS_EXCLUDE_REGEX = (
    r"(^\.git/|^\.venv/|^dist/|^logs/|^runtime/|^server-state/|^dev-notes/)"
)


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    """Run one command and stream output."""
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def _run_capture(
    cmd: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run one command and return captured stdout/stderr."""
    print(f"+ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


def _ensure_cli_tool(
    *,
    python_exe: str,
    tool_name: str,
    pip_package: str,
    repo_root: Path,
) -> None:
    """Ensure one CLI tool is installed and available on PATH."""
    if shutil.which(tool_name):
        return
    print(f"CLI tool `{tool_name}` not found; installing `{pip_package}`...")
    _run(
        [python_exe, "-m", "pip", "install", pip_package],
        cwd=repo_root,
        env=os.environ.copy(),
    )
    if not shutil.which(tool_name):
        raise RuntimeError(
            f"required CLI tool `{tool_name}` is unavailable after install"
        )


def _scan_for_secrets(*, repo_root: Path, env: dict[str, str]) -> None:
    """Run detect-secrets scan and fail when findings are present."""
    completed = _run_capture(
        [
            "detect-secrets",
            "scan",
            "--all-files",
            "--force-use-all-plugins",
            "--exclude-files",
            DETECT_SECRETS_EXCLUDE_REGEX,
        ],
        cwd=repo_root,
        env=env,
    )
    raw = completed.stdout.strip()
    if not raw:
        raise RuntimeError("detect-secrets returned empty output")
    scan_payload = json.loads(raw)
    findings = scan_payload.get("results", {})
    flattened: list[tuple[str, int]] = []
    for file_path, matches in findings.items():
        if not isinstance(matches, list):
            continue
        for match in matches:
            if not isinstance(match, dict):
                continue
            line_number = int(match.get("line_number", 0) or 0)
            flattened.append((str(file_path), line_number))
    if flattened:
        print("Potential secrets found:")
        for file_path, line_number in flattened:
            print(f"- {file_path}:{line_number}")
        raise RuntimeError(
            "detect-secrets reported potential secrets; review findings above"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run security checks for OpAMP: UI compaction, unit tests, "
            "ruff security rules, detect-secrets, and pip-audit."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        help="Repository root path (default: parent of scripts folder).",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use (default: current interpreter).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        raise RuntimeError(f"repo root not found: {repo_root}")

    print(SECURITY_CHECKS_HEADER)
    checks_env = os.environ.copy()
    if APP_ENABLE_DEV_FEATURES_ENV in checks_env:
        current_value = checks_env.get(APP_ENABLE_DEV_FEATURES_ENV, "")
        print(
            (
                f"{APP_ENABLE_DEV_FEATURES_ENV} is currently set "
                f"('{current_value}'); unsetting for security checks run."
            )
        )
        checks_env.pop(APP_ENABLE_DEV_FEATURES_ENV, None)
    else:
        print(f"{APP_ENABLE_DEV_FEATURES_ENV} is not set.")

    _ensure_cli_tool(
        python_exe=args.python,
        tool_name="ruff",
        pip_package="ruff",
        repo_root=repo_root,
    )
    _ensure_cli_tool(
        python_exe=args.python,
        tool_name="detect-secrets",
        pip_package="detect-secrets",
        repo_root=repo_root,
    )
    _ensure_cli_tool(
        python_exe=args.python,
        tool_name="pip-audit",
        pip_package="pip-audit",
        repo_root=repo_root,
    )
    _ensure_cli_tool(
        python_exe=args.python,
        tool_name="pytest",
        pip_package="pytest",
        repo_root=repo_root,
    )

    # 1) Regenerate minified provider UI assets.
    _run(
        [
            args.python,
            str(repo_root / "scripts" / "build_provider_ui_compact_assets.py"),
            "--repo-root",
            str(repo_root),
        ],
        cwd=repo_root,
        env=checks_env,
    )

    # 2) Full unit test stack.
    _run(
        [args.python, "-m", "pytest", "-s"],
        cwd=repo_root,
        env=checks_env,
    )

    # 3) Ruff security rules.
    _run(
        ["ruff", "check", "--select", "S", "."],
        cwd=repo_root,
        env=checks_env,
    )

    # 4) detect-secrets.
    _scan_for_secrets(repo_root=repo_root, env=checks_env)

    # 5) pip-audit against declared requirement sets.
    _run(
        [
            "pip-audit",
            "-r",
            "requirements.txt",
            "-r",
            "provider/requirements.txt",
            "-r",
            "consumer/requirements.txt",
            "-r",
            "agent_broker/requirements.txt",
        ],
        cwd=repo_root,
        env=checks_env,
    )

    print("Security checks complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
