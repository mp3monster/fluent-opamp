"""Compatibility wrappers for legacy `opamp_build_tools` imports."""

from opamp_build_tools.sbom import (
    build_requirements_application_sbom_payload,
    build_wheel_artifact_sbom_payload,
    ensure_python_package,
    expected_dependency_refs,
    normalize_dist_name,
    parse_iso8601_utc,
    read_wheel_metadata,
    requirement_name,
    sha256,
    validate_wheel_artifact_sbom,
    write_sbom_file,
    write_wheel_artifact_sbom,
)

__all__ = [
    "build_requirements_application_sbom_payload",
    "build_wheel_artifact_sbom_payload",
    "ensure_python_package",
    "expected_dependency_refs",
    "normalize_dist_name",
    "parse_iso8601_utc",
    "read_wheel_metadata",
    "requirement_name",
    "sha256",
    "validate_wheel_artifact_sbom",
    "write_sbom_file",
    "write_wheel_artifact_sbom",
]
