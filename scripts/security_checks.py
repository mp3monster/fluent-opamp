#!/usr/bin/env python3
"""Compatibility wrapper for repository-wide developer CLI security checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_TOOLS_SRC = REPO_ROOT / "dev-tools" / "src"
if str(DEV_TOOLS_SRC) not in sys.path:
    sys.path.insert(0, str(DEV_TOOLS_SRC))

from opamp_dev_tools.runtime import CommandRuntime  # noqa: E402
from opamp_dev_tools.security import run_repo_security_checks  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repository-wide OpAMP security checks.")
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
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
    runtime = CommandRuntime(
        repo_root=repo_root,
        tool_root=repo_root / "dev-tools",
        command_slug="legacy-security-checks",
    )
    exit_code = 0
    try:
        run_repo_security_checks(runtime, python_exe=args.python)
    except Exception as exc:  # pylint: disable=broad-except
        runtime.record_error(f"{type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        runtime.write_logs()
        runtime.print_log_summary()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
