"""Tests for packaged consumer-sim resources and installed-mode fallbacks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    src_root = Path(__file__).resolve().parents[1] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    module_path = src_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ensure_user_default_config_copies_packaged_template(tmp_path: Path, monkeypatch) -> None:
    """Installed-mode config bootstrap writes the packaged default config once."""
    resources_mod = _load_module(
        "opamp_consumer_sim.resources",
        "opamp_consumer_sim/resources.py",
    )

    monkeypatch.setattr(resources_mod, "user_config_root", lambda: tmp_path)
    config_path = resources_mod.ensure_user_default_config()

    assert config_path == (tmp_path / resources_mod.CONFIG_FILENAME).resolve()
    assert config_path.read_text(encoding="utf-8") == resources_mod.read_packaged_text(
        resources_mod.CONFIG_FILENAME
    )


def test_component_version_falls_back_to_packaged_metadata(monkeypatch) -> None:
    """Version metadata still resolves when only packaged resources are available."""
    version_mod = _load_module("component_version", "component_version.py")

    monkeypatch.setattr(version_mod, "source_resource_path", lambda _filename: None)
    payload = version_mod.load_component_version_info()

    assert payload["component"] == "consumer-sim"
    assert payload["version"]


def test_launcher_schema_validation_uses_packaged_or_source_schema(tmp_path: Path) -> None:
    """Launcher schema validation resolves the schema without stale helper calls."""
    launcher_mod = _load_module("consumer_sim_launcher", "consumer_sim_launcher.py")
    resources_mod = _load_module(
        "opamp_consumer_sim.resources",
        "opamp_consumer_sim/resources.py",
    )
    config_path = tmp_path / "consumer_instances.json"
    payload = launcher_mod._load_launcher_payload(
        resources_mod.source_resource_path(launcher_mod.CONFIG_FILENAME)
    )

    config_path.write_text("{}", encoding="utf-8")
    launcher_mod._validate_payload_against_schema(payload, config_path=config_path)
