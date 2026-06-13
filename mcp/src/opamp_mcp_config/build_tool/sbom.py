"""CycloneDX SBOM helpers for the MCP packaging utility.

This wrapper delegates to the vendored `opamp_build_tools.sbom` copy so the
standalone MCP wheel keeps SBOM support without depending on repo-local
developer tooling modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opamp_build_tools.sbom import (
    read_wheel_metadata as _read_wheel_metadata,
    normalize_dist_name as _normalize_dist_name,
    requirement_name as _requirement_name,
    sha256 as _sha256,
    write_sbom_file,
    build_wheel_artifact_sbom_payload,
)


def _build_sbom_payload(wheel_path: Path) -> dict[str, Any]:
    """Build a CycloneDX SBOM payload for one wheel artifact."""
    return build_wheel_artifact_sbom_payload(
        repo_root=wheel_path.parent,
        python_exe="python",
        artifact=wheel_path,
        root_component_name="opamp-mcp-config",
        metadata_component_mode="artifact",
    )


def _write_sbom(wheel_path: Path, sbom_path: Path) -> Path:
    """Write one CycloneDX SBOM document and return its output path."""
    return write_sbom_file(_build_sbom_payload(wheel_path), sbom_path)
