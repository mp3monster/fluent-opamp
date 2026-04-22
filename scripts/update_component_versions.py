#!/usr/bin/env python3
"""Generate component version metadata from the current git commit.

The generated payload is used by runtime help pages/CLI help and packaged with
each component so version details remain available outside a git checkout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

COMPONENT_VERSION_TARGETS: dict[str, str] = {
    "server": "provider/src/opamp_provider/version.json",
    "broker": "agent_broker/opamp_broker/version.json",
    "consumer": "consumer/src/opamp_consumer/version.json",
    "consumer-sim": "consumer-sim/version.json",
}

UNKNOWN_VALUE = "unknown"


def _run_git_command(repo_root: Path, args: list[str]) -> str | None:
    """Return git command output text or ``None`` when unavailable."""
    try:
        output = subprocess.check_output(
            ["git", *args],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return output or None


def _resolve_git_commit(repo_root: Path) -> str:
    """Return short git commit reference for HEAD."""
    commit = _run_git_command(repo_root, ["rev-parse", "--short=12", "HEAD"])
    return commit or UNKNOWN_VALUE


def _resolve_git_commit_date(repo_root: Path) -> str:
    """Return ISO-8601 git commit date for HEAD."""
    commit_date = _run_git_command(repo_root, ["show", "-s", "--format=%cI", "HEAD"])
    if commit_date:
        return commit_date
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_version_payload(*, component: str, commit: str, commit_date: str) -> dict[str, str]:
    """Build stable version payload shape used across all components."""
    return {
        "component": component,
        "git_commit": commit,
        "git_commit_date": commit_date,
        "version": f"{commit} ({commit_date})",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _write_json(path: Path, payload: dict[str, str]) -> None:
    """Persist JSON payload with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate component version metadata from git HEAD."
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=str(Path(__file__).resolve().parents[1]),
        help="repository root path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-file update output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    commit = _resolve_git_commit(repo_root)
    commit_date = _resolve_git_commit_date(repo_root)

    for component, relative_target in COMPONENT_VERSION_TARGETS.items():
        target_path = repo_root / relative_target
        payload = _build_version_payload(
            component=component,
            commit=commit,
            commit_date=commit_date,
        )
        _write_json(target_path, payload)
        if not args.quiet:
            print(f"[version] updated {component}: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
