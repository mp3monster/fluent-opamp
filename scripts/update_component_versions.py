#!/usr/bin/env python3
"""Generate component version metadata from the current git commit.

The generated payload is used by runtime help pages/CLI help and packaged with
each component so version details remain available outside a git checkout.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

COMPONENT_VERSION_TARGETS: dict[str, str] = {
    "server": "provider/src/opamp_provider/version.json",
    "broker": "agent_broker/opamp_broker/version.json",
    "consumer": "consumer/src/opamp_consumer/version.json",
    "consumer-sim": "consumer-sim/version.json",
}
SECONDARY_COMPONENT_VERSION_TARGETS: dict[str, tuple[str, ...]] = {
    "consumer-sim": ("consumer-sim/src/opamp_consumer_sim/version.json",),
}

UNKNOWN_VALUE = "unknown"
SEMVER_LABEL_PATTERN = re.compile(
    r"^(?P<prefix>v?)"
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
MAJOR_MINOR_LABEL_PATTERN = re.compile(
    r"^(?P<prefix>v?)"
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)$"
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


def _increment_patch_semver_label(label: str, *, patch_delta: int = 1) -> str | None:
    """Return patch-incremented label when input is semver, else ``None``.

    Supported labels include optional leading ``v`` and optional prerelease/build
    suffixes. Incremented labels intentionally emit plain ``MAJOR.MINOR.PATCH``
    (plus optional ``v`` prefix) without prerelease/build suffixes.
    """
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
        # `major.minor` labels are treated as `<major>.<minor>.0`, then patch-advanced.
        prefix = str(major_minor_match.group("prefix") or "")
        major = int(major_minor_match.group("major"))
        minor = int(major_minor_match.group("minor"))
        return f"{prefix}{major}.{minor}.{safe_patch_delta}"
    return None


def _resolve_commits_since_label(repo_root: Path, label: str) -> int:
    """Return commit distance from latest reachable tag label to ``HEAD``."""
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
    """Return semver-patch-incremented label, or the original label when not semver."""
    patch_delta = max(0, int(commits_since_label)) + 1
    bumped = _increment_patch_semver_label(label, patch_delta=patch_delta)
    if bumped is not None:
        return bumped
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
    commits_since_label: int,
) -> dict[str, str]:
    """Build stable version payload shape used across all components."""
    effective_label = _resolve_effective_label(
        label,
        commits_since_label=commits_since_label,
    )
    commit_date_friendly = _friendly_datetime_text(commit_date)
    version_text = _build_version_text(
        label=effective_label,
        commit=commit,
        commit_date_friendly=commit_date_friendly,
    )
    return {
        "component": component,
        "git_label": label,
        "effective_label": effective_label,
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
    commits_since_label = _resolve_commits_since_label(repo_root, label)

    for component, relative_target in COMPONENT_VERSION_TARGETS.items():
        target_path = repo_root / relative_target
        payload = _build_version_payload(
            component=component,
            commit=commit,
            commit_date=commit_date,
            label=label,
            commits_since_label=commits_since_label,
        )
        _write_json(target_path, payload)
        if not args.quiet:
            print(f"[version] updated {component}: {target_path}")
        for secondary_target in SECONDARY_COMPONENT_VERSION_TARGETS.get(component, ()):
            secondary_path = repo_root / secondary_target
            _write_json(secondary_path, payload)
            if not args.quiet:
                print(f"[version] updated {component}: {secondary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
