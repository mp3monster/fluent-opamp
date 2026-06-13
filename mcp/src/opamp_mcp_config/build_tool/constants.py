"""Shared constants for the MCP build-tool packaging helpers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = ROOT.parent
UTF8_ENCODING = "utf-8"
DEFAULT_CONFIG_FILENAME = "mcp-client-defaults.json"
DEFAULT_DIST_DIR = REPO_ROOT / "dist" / "mcp"
DEFAULT_SBOM_PATH = REPO_ROOT / "dist" / "sbom" / "opamp_mcp_config.cyclonedx.json"
SOURCE_DEFAULTS_PATH = ROOT / DEFAULT_CONFIG_FILENAME
PACKAGED_DEFAULTS_PATH = ROOT / "src" / "opamp_mcp_config" / DEFAULT_CONFIG_FILENAME
SOURCE_BUILD_DIR = ROOT / "build"
SOURCE_EGG_INFO_DIR = ROOT / "opamp_mcp_config.egg-info"

PACKAGE_NAME_BUILD = "build"
PACKAGE_NAME_DISTRIBUTION = "opamp_mcp_config"
ARTIFACT_GLOB = f"{PACKAGE_NAME_DISTRIBUTION}-*"
WHEEL_GLOB = f"{PACKAGE_NAME_DISTRIBUTION}-*.whl"
DIST_INFO_METADATA_SUFFIX = ".dist-info/METADATA"

MODULE_PIP = "pip"
MODULE_BUILD = "build"
PIP_SHOW_SUBCOMMAND = "show"
PIP_INSTALL_SUBCOMMAND = "install"
BUILD_FLAG_WHEEL = "--wheel"
BUILD_FLAG_SDIST = "--sdist"
BUILD_FLAG_OUTDIR = "--outdir"
OUTPUT_COMMAND_PREFIX = "+ "
OUTPUT_PACKAGE_INSTALLING_TEMPLATE = (
    "Python package `{package_name}` not found; installing it now..."
)
OUTPUT_BUILT_WHEEL_TEMPLATE = "Built wheel: {wheel_path}"
OUTPUT_WROTE_SBOM_TEMPLATE = "Wrote SBOM: {sbom_path}"

SBOM_SCHEMA_URL = "http://cyclonedx.org/schema/bom-1.6.schema.json"
SBOM_FORMAT = "CycloneDX"
SBOM_SPEC_VERSION = "1.6"
SBOM_VERSION = 1
LICENSE_ID_APACHE_2 = "Apache-2.0"
HASH_ALGORITHM_SHA256 = "SHA-256"
PYPI_PURL_PREFIX = "pkg:pypi"
EXTERNAL_REF_TYPE_DISTRIBUTION = "distribution"
TIMESTAMP_Z_SUFFIX_FROM = "+00:00"
TIMESTAMP_Z_SUFFIX_TO = "Z"

JSON_INDENT = 2
STREAM_READ_CHUNK_SIZE = 1024 * 1024
REQUIREMENT_MARKER_EXTRA = "extra =="
REQUIREMENT_NAME_TERMINATORS = (" ", "(", "[", "!", "<", ">", "=", "~", ";")

ERROR_CONFIG_ROOT_NOT_OBJECT = "config root must be a JSON object: {path}"
ERROR_DEPLOYMENT_NOT_OBJECT = "deployment must be a JSON object: {path}"
ERROR_NO_WHEEL_FOUND = f"no {PACKAGE_NAME_DISTRIBUTION} wheel found in {{out_dir}}"
ERROR_WHEEL_MISSING_METADATA = "wheel missing dist-info/METADATA: {wheel_path}"
