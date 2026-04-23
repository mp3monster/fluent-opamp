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


def _resolve_latest_git_label(repo_root: Path) -> str:
    """Return latest reachable git tag label or empty string when unavailable."""
    label = _run_git_command(repo_root, ["describe", "--tags", "--abbrev=0"])
    return str(label or "").strip()


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse ISO timestamp values while handling optional `Z` suffix."""
    candidate = str(value).strip()
    if not candidate:
        return None
    normalized = candidate.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _friendly_datetime_text(iso_value: str) -> str:
    """Return a human-friendly datetime string from an ISO timestamp."""
    parsed = _parse_iso_datetime(iso_value)
    if parsed is None:
        return str(iso_value)
    offset = parsed.strftime("%z")
    if offset:
        offset = f"{offset[:3]}:{offset[3:]}"
    else:
        offset = "+00:00"
    return f"{parsed.strftime('%d %b %Y %H:%M:%S')} UTC{offset}"


def _build_version_text(
    *,
    label: str,
    commit: str,
    commit_date_friendly: str,
) -> str:
    """Return version text with optional leading git label."""
    if str(label).strip():
        return f"{label} {commit} ({commit_date_friendly})"
    return f"{commit} ({commit_date_friendly})"


def _build_version_payload(
    *,
    component: str,
    commit: str,
    commit_date: str,
    label: str,
) -> dict[str, str]:
    """Build stable version payload shape used across all components."""
    commit_date_friendly = _friendly_datetime_text(commit_date)
    version_text = _build_version_text(
        label=label,
        commit=commit,
        commit_date_friendly=commit_date_friendly,
    )
    return {
        "component": component,
        "git_label": label,
        "git_commit": commit,
        "git_commit_date": commit_date,
        "git_commit_date_friendly": commit_date_friendly,
        "version": version_text,
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
    label = _resolve_latest_git_label(repo_root)

    for component, relative_target in COMPONENT_VERSION_TARGETS.items():
        target_path = repo_root / relative_target
        payload = _build_version_payload(
            component=component,
            commit=commit,
            commit_date=commit_date,
            label=label,
        )
        _write_json(target_path, payload)
        if not args.quiet:
            print(f"[version] updated {component}: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
