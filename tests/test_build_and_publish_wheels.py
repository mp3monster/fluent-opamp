"""Tests for the repository wheel build/publish helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "build_and_publish_wheels.py"
    spec = importlib.util.spec_from_file_location("build_and_publish_wheels", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_component_selection_includes_independent_deployables() -> None:
    """Default build selection includes provider, consumer, catalog, CLI, and simulator."""
    tool = _load_module()

    args = tool._parse_args([])

    assert args.component_keys == [
        "provider",
        "consumer",
        "catalog",
        "cli",
        "consumer-sim",
    ]


def test_component_sbom_overrides_support_new_targets() -> None:
    """Per-component SBOM overrides work for newer independent artefacts too."""
    tool = _load_module()

    args = tool._parse_args(
        [
            "--components",
            "catalog,cli",
            "--component-sbom-path",
            "catalog=dist/sbom/custom-catalog.cdx.json",
        ]
    )

    assert args.component_keys == ["catalog", "cli"]
    assert args.resolved_sbom_paths["catalog"].name == "custom-catalog.cdx.json"
    assert args.resolved_sbom_paths["cli"].name == "opamp_cli_deployable_artifacts.cyclonedx.json"
