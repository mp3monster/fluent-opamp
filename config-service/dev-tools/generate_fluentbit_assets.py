#!/usr/bin/env python3
# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_SERVICE_ROOT = REPO_ROOT / "config-service"
SRC_ROOT = CONFIG_SERVICE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from config_service.fluentbit_docs_support import build_catalog_from_docs  # noqa: E402

import add_fluentbit_processors  # noqa: E402
import generate_runtime_schemas  # noqa: E402

LOGGER = logging.getLogger("generate_fluentbit_assets")
DEFINITIONS_DIR = CONFIG_SERVICE_ROOT / "json-definitions"
SRC_DEFINITIONS_DIR = SRC_ROOT / "config_service" / "json-definitions"
CATALOG_REGISTRY_PATH = CONFIG_SERVICE_ROOT / "config" / "catalog-registry.json"
CLI_DEV_TOOL_SPEC = {
    "id": "fluentbit_assets",
    "label": "Generate Fluent Bit assets",
    "description": "Scrape Fluent Bit docs, update catalog JSON, and optionally compile runtime schemas.",
    "script_relpath": "config-service/dev-tools/generate_fluentbit_assets.py",
    "arguments": [
        {
            "name": "versions",
            "flag": "--version",
            "prompt": "Fluent Bit version(s), comma-separated",
            "required": True,
            "multiple": True,
            "default": "5.0.7",
        },
        {
            "name": "source",
            "flag": "--source",
            "prompt": "Documentation source",
            "choices": ["auto", "website", "github"],
            "default": "auto",
        },
        {
            "name": "github_ref",
            "flag": "--github-ref",
            "prompt": "GitHub ref (optional)",
            "default": "",
        },
        {
            "name": "timeout",
            "flag": "--timeout",
            "prompt": "HTTP timeout in seconds",
            "default": "20",
        },
        {
            "name": "register",
            "prompt": "Update catalog registry",
            "kind": "bool",
            "default": True,
            "args_when_false": ["--no-register"],
        },
        {
            "name": "generate_schemas",
            "prompt": "Generate runtime schemas",
            "kind": "bool",
            "default": True,
            "args_when_false": ["--no-schemas"],
        },
    ],
}


def cli_dev_tool_spec() -> dict:
    return json.loads(json.dumps(CLI_DEV_TOOL_SPEC))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _artifact_filename(version: str) -> str:
    return f"fluent-bit-{version}-all-plugins-catalog.json"


def _registry_ref(version: str) -> str:
    return f"json-definitions/{_artifact_filename(version)}"


def _update_catalog_registry(version: str) -> None:
    payload = json.loads(CATALOG_REGISTRY_PATH.read_text(encoding="utf-8"))
    catalogs = payload.setdefault("catalogs_by_type", {}).setdefault("fluentbit", {})
    catalogs[version] = _registry_ref(version)
    CATALOG_REGISTRY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def generate_version(
    version: str,
    *,
    source: str,
    timeout: int,
    github_ref: str | None,
    register: bool,
    generate_schemas_flag: bool,
) -> None:
    LOGGER.info("building fluent bit catalog version=%s source=%s", version, source)
    payload = build_catalog_from_docs(
        version,
        source=source,
        timeout=timeout,
        github_ref=github_ref,
        logger=LOGGER,
    )
    filename = _artifact_filename(version)
    root_path = DEFINITIONS_DIR / filename
    src_path = SRC_DEFINITIONS_DIR / filename
    _write_json(root_path, payload)
    _write_json(src_path, payload)

    add_fluentbit_processors.update_catalog(root_path, timeout=timeout, logger=LOGGER, page_cache={})
    add_fluentbit_processors.update_catalog(src_path, timeout=timeout, logger=LOGGER, page_cache={})

    if register:
        _update_catalog_registry(version)
        LOGGER.info("registered fluent bit catalog version=%s", version)

    if generate_schemas_flag:
        generate_runtime_schemas.generate_runtime_schemas(
            config_types=["fluentbit"],
            versions=[version],
        )
        LOGGER.info("generated runtime schemas version=%s", version)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Fluent Bit documentation and generate catalog JSON plus runtime schemas. "
            "Supports the docs website, the fluent-bit-docs GitHub repo, or auto fallback."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="append",
        dest="versions",
        required=True,
        help="Fluent Bit version to generate. Repeat for multiple versions.",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "website", "github"),
        default="auto",
        help="Documentation source to scrape.",
    )
    parser.add_argument(
        "--github-ref",
        help="Optional GitHub branch/tag/ref to use when --source github or auto prefers GitHub.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds for docs fetches.",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="Do not update config-service/config/catalog-registry.json.",
    )
    parser.add_argument(
        "--no-schemas",
        action="store_true",
        help="Do not generate runtime schemas after writing catalogs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for version in args.versions:
        generate_version(
            version,
            source=args.source,
            timeout=args.timeout,
            github_ref=args.github_ref,
            register=not args.no_register,
            generate_schemas_flag=not args.no_schemas,
        )


if __name__ == "__main__":
    main()
