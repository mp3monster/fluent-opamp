from __future__ import annotations

from pathlib import Path

from opamp_dev_tools.versioning import VERSION_TARGETS


def test_version_targets_cover_primary_component_metadata_files() -> None:
    target_paths = {target.path for target in VERSION_TARGETS}
    assert "cli/pyproject.toml" in target_paths
    assert "provider/pyproject.toml" in target_paths
    assert "config-service/build_config.py" in target_paths
    assert "catalog-service/pyproject.toml" in target_paths
    assert "catalog-service/setup.py" not in target_paths
