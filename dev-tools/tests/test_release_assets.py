from __future__ import annotations

from pathlib import Path

from opamp_dev_tools.release_assets import (
    DEFAULT_RELEASE_COMPONENT_KEYS,
    parse_release_component_keys,
    resolve_release_sbom_paths,
)


def test_default_release_component_selection_includes_independent_deployables() -> None:
    component_keys = parse_release_component_keys(",".join(DEFAULT_RELEASE_COMPONENT_KEYS))

    assert component_keys == [
        "provider",
        "consumer",
        "catalog-service",
        "cli",
        "consumer-sim",
    ]


def test_release_component_parsing_accepts_legacy_catalog_alias() -> None:
    component_keys = parse_release_component_keys("catalog,cli")

    assert component_keys == ["catalog-service", "cli"]


def test_release_component_sbom_overrides_support_new_targets(tmp_path: Path) -> None:
    resolved = resolve_release_sbom_paths(
        repo_root=tmp_path,
        component_keys=["catalog-service", "cli"],
        provider_sbom_path="dist/sbom/provider.cdx.json",
        consumer_sbom_path="dist/sbom/consumer.cdx.json",
        component_sbom_path_overrides=["catalog=dist/sbom/custom-catalog.cdx.json"],
    )

    assert resolved["catalog-service"].name == "custom-catalog.cdx.json"
    assert resolved["cli"].name == "opamp_cli_deployable_artifacts.cyclonedx.json"
