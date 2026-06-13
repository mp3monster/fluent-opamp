"""Helpers for packaged consumer-sim resources and runtime file locations."""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

PACKAGE_NAME = "opamp_consumer_sim"
CONFIG_DIRNAME = "config"
CONFIG_FILENAME = "consumer_instances.json"
SCHEMA_FILENAME = "consumer_instances.schema.json"
VERSION_FILENAME = "version.json"
APP_NAMESPACE = ("opamp", "consumer-sim")


def _resource_relative_path(filename: str) -> Path:
    """Return one resource path relative to the component/package root."""
    if filename in {CONFIG_FILENAME, SCHEMA_FILENAME}:
        return Path(CONFIG_DIRNAME) / filename
    return Path(filename)


def source_component_root() -> Path | None:
    """Return the repo component root when running from the source tree."""
    candidate = Path(__file__).resolve().parents[2]
    config_dir = candidate / CONFIG_DIRNAME
    if (
        (config_dir / CONFIG_FILENAME).is_file()
        and (config_dir / SCHEMA_FILENAME).is_file()
        and (candidate / VERSION_FILENAME).is_file()
    ):
        return candidate
    return None


def source_resource_path(filename: str) -> Path | None:
    """Return one source-tree resource path when running from the repo."""
    component_root = source_component_root()
    if component_root is None:
        return None
    return (component_root / _resource_relative_path(filename)).resolve()


def source_repo_root() -> Path | None:
    """Return the repository root when running from a source checkout."""
    component_root = source_component_root()
    if component_root is None:
        return None
    repo_root = component_root.parent
    if (repo_root / "consumer" / "src").is_dir():
        return repo_root
    return None


def running_from_source_tree() -> bool:
    """Return True when consumer-sim is executing from the repository tree."""
    return source_component_root() is not None


def _user_home() -> Path:
    return Path.home().expanduser().resolve()


def user_config_root() -> Path:
    """Return the per-user configuration directory for installed use."""
    if os.name == "nt":
        base = Path(
            str(
                os.getenv("APPDATA")
                or (_user_home() / "AppData" / "Roaming")
            )
        )
    else:
        base = Path(str(os.getenv("XDG_CONFIG_HOME") or (_user_home() / ".config")))
    return base.joinpath(*APP_NAMESPACE).resolve()


def user_state_root() -> Path:
    """Return the per-user state directory for installed use."""
    if os.name == "nt":
        base = Path(
            str(
                os.getenv("LOCALAPPDATA")
                or os.getenv("APPDATA")
                or (_user_home() / "AppData" / "Local")
            )
        )
    else:
        base = Path(str(os.getenv("XDG_STATE_HOME") or (_user_home() / ".local" / "state")))
    return base.joinpath(*APP_NAMESPACE).resolve()


def read_packaged_text(filename: str) -> str:
    """Read one packaged resource file as UTF-8 text."""
    resource = resources.files(PACKAGE_NAME)
    for part in _resource_relative_path(filename).parts:
        resource = resource.joinpath(part)
    return resource.read_text(encoding="utf-8")


def ensure_user_default_config() -> Path:
    """Ensure the installed-user default config file exists and return it."""
    target_dir = user_config_root()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / CONFIG_FILENAME
    if target_path.exists():
        return target_path.resolve()
    target_path.write_text(read_packaged_text(CONFIG_FILENAME), encoding="utf-8")
    return target_path.resolve()
