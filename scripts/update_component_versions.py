#!/usr/bin/env python3
"""Compatibility wrapper for the shared developer-tools version metadata logic."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_TOOLS_SRC = REPO_ROOT / "dev-tools" / "src"
if str(DEV_TOOLS_SRC) not in sys.path:
    sys.path.insert(0, str(DEV_TOOLS_SRC))

from opamp_dev_tools.version_metadata import (  # noqa: E402
    COMPONENT_VERSION_TARGETS,
    MAJOR_MINOR_LABEL_PATTERN,
    SECONDARY_COMPONENT_VERSION_TARGETS,
    SEMVER_LABEL_PATTERN,
    UNKNOWN_VALUE,
    _build_parser,
    _build_version_payload,
    _build_version_text,
    _friendly_datetime_text,
    _parse_iso_datetime,
    _write_json,
    main,
)


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
    commit = _run_git_command(repo_root, ["rev-parse", "--short=12", "HEAD"])
    return commit or UNKNOWN_VALUE


def _resolve_git_commit_date(repo_root: Path) -> str:
    commit_date = _run_git_command(repo_root, ["show", "-s", "--format=%cI", "HEAD"])
    if commit_date:
        return commit_date
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_latest_git_label(repo_root: Path) -> str:
    label = _run_git_command(repo_root, ["describe", "--tags", "--abbrev=0"])
    return str(label or "").strip()


def _increment_patch_semver_label(label: str, *, patch_delta: int = 1) -> str | None:
    safe_patch_delta = max(1, int(patch_delta))
    candidate = str(label or "").strip()
    if not candidate:
        return None
    match = SEMVER_LABEL_PATTERN.fullmatch(candidate)
    if match is not None:
        prefix = str(match.group("prefix") or "")
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch")) + safe_patch_delta
        return f"{prefix}{major}.{minor}.{patch}"
    major_minor_match = MAJOR_MINOR_LABEL_PATTERN.fullmatch(candidate)
    if major_minor_match is not None:
        prefix = str(major_minor_match.group("prefix") or "")
        major = int(major_minor_match.group("major"))
        minor = int(major_minor_match.group("minor"))
        return f"{prefix}{major}.{minor}.{safe_patch_delta}"
    return None


def _resolve_commits_since_label(repo_root: Path, label: str) -> int:
    candidate = str(label or "").strip()
    if not candidate:
        return 0
    commits_since = _run_git_command(repo_root, ["rev-list", "--count", f"{candidate}..HEAD"])
    if commits_since is None:
        return 0
    try:
        return max(0, int(commits_since))
    except ValueError:
        return 0


def _resolve_effective_label(label: str, *, commits_since_label: int = 0) -> str:
    patch_delta = max(0, int(commits_since_label)) + 1
    bumped = _increment_patch_semver_label(label, patch_delta=patch_delta)
    if bumped is not None:
        return bumped
    return str(label or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
