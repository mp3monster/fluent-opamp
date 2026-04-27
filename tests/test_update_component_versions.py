from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_component_versions.py"
_SPEC = importlib.util.spec_from_file_location("update_component_versions", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
update_component_versions = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(update_component_versions)


def test_effective_label_semver_advances_with_commit_distance() -> None:
    assert (
        update_component_versions._resolve_effective_label("1.2.3", commits_since_label=0)
        == "1.2.4"
    )
    assert (
        update_component_versions._resolve_effective_label("1.2.3", commits_since_label=5)
        == "1.2.9"
    )


def test_effective_label_major_minor_advances_with_commit_distance() -> None:
    assert (
        update_component_versions._resolve_effective_label("v2.7", commits_since_label=0)
        == "v2.7.1"
    )
    assert (
        update_component_versions._resolve_effective_label("v2.7", commits_since_label=3)
        == "v2.7.4"
    )


def test_effective_label_non_semver_is_unchanged() -> None:
    assert (
        update_component_versions._resolve_effective_label(
            "release-candidate", commits_since_label=8
        )
        == "release-candidate"
    )


def test_resolve_commits_since_label_handles_missing_and_invalid(monkeypatch) -> None:
    repo_root = Path(".")

    def _mock_run_git_command(_: Path, args: list[str]) -> str | None:
        if args[:2] == ["rev-list", "--count"]:
            return "12"
        return None

    monkeypatch.setattr(update_component_versions, "_run_git_command", _mock_run_git_command)
    assert update_component_versions._resolve_commits_since_label(repo_root, "v1.0.0") == 12

    def _mock_run_git_command_invalid(_: Path, __: list[str]) -> str | None:
        return "invalid-count"

    monkeypatch.setattr(
        update_component_versions, "_run_git_command", _mock_run_git_command_invalid
    )
    assert update_component_versions._resolve_commits_since_label(repo_root, "v1.0.0") == 0
    assert update_component_versions._resolve_commits_since_label(repo_root, "") == 0
