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

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "json-schemas"
SRC_OUTPUT_DIR = SRC_ROOT / "config_service" / "json-schemas"
PLUGIN_SECTIONS = ("inputs", "filters", "outputs")
PIPELINE_PROPS_PATH = (
    "properties",
    "config",
    "properties",
    "pipeline",
    "properties",
)


def _pipeline_properties(schema: dict[str, Any]) -> dict[str, Any]:
    container: dict[str, Any] | Any = schema
    for segment in PIPELINE_PROPS_PATH:
        container = container[segment]
    return container


def _plugin_variant_name(variant: dict[str, Any]) -> str:
    return str(variant["properties"]["name"]["const"])


def _clear_legacy_flat_parts(directory: Path, filename: str) -> None:
    manifest_path = directory / filename
    for stale_path in directory.glob(f"{manifest_path.stem}.*{manifest_path.suffix}"):
        stale_path.unlink(missing_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _plugin_variant_payload(
    *,
    version_dir: Path,
    config_type: str,
    section: str,
    variant: dict[str, Any],
    shared_processors_written: set[Path],
) -> dict[str, Any]:
    if config_type != "fluentbit" or section not in {"inputs", "outputs"}:
        return variant

    properties = variant.get("properties", {})
    processors_schema = properties.get("processors")
    if not isinstance(properties, dict) or not isinstance(processors_schema, dict):
        return variant

    plugin_name = _plugin_variant_name(variant)
    shared_processors_path = version_dir / "processors.json"
    if shared_processors_path not in shared_processors_written:
        _write_json(shared_processors_path, processors_schema)
        shared_processors_written.add(shared_processors_path)

    base_variant = copy.deepcopy(variant)
    base_variant["properties"]["processors"] = {"$ref": "../processors.json"}
    return base_variant


def _write_schema_artifact(directory: Path, config_type: str, version: str, schema: dict[str, Any]) -> None:
    from config_service.json_artifacts import (
        KEY_FILE,
        KEY_OPERATION,
        KEY_PAYLOAD,
        KEY_POINTER,
        OPERATION_APPEND,
        write_manifest_json_artifact,
    )

    filename = f"{config_type}-{version}-config-schema.json"
    manifest_path = directory / filename
    version_dir = directory / config_type / version

    shutil.rmtree(version_dir, ignore_errors=True)
    _clear_legacy_flat_parts(directory, filename)

    base_schema = copy.deepcopy(schema)
    pipeline_props = _pipeline_properties(base_schema)
    top_level_parts: list[dict[str, Any]] = []
    shared_processors_written: set[Path] = set()

    for section in PLUGIN_SECTIONS:
        section_schema = copy.deepcopy(pipeline_props[section])
        section_base = copy.deepcopy(section_schema)
        section_base["items"]["oneOf"] = []

        nested_parts = [
            {
                KEY_POINTER: "/items/oneOf",
                KEY_OPERATION: OPERATION_APPEND,
                KEY_FILE: f"{section}/{_plugin_variant_name(variant)}.json",
                KEY_PAYLOAD: _plugin_variant_payload(
                    version_dir=version_dir,
                    config_type=config_type,
                    section=section,
                    variant=variant,
                    shared_processors_written=shared_processors_written,
                ),
            }
            for variant in section_schema["items"]["oneOf"]
        ]
        nested_manifest_path = version_dir / f"{section}.json"
        nested_manifest = write_manifest_json_artifact(
            nested_manifest_path,
            base_file=f"{section}.base.json",
            base_payload=section_base,
            parts=nested_parts,
        )
        pipeline_props[section] = {}
        top_level_parts.append(
            {
                KEY_POINTER: f"/properties/config/properties/pipeline/properties/{section}",
                KEY_FILE: f"{config_type}/{version}/{section}.json",
                KEY_PAYLOAD: nested_manifest,
            }
        )

    write_manifest_json_artifact(
        manifest_path,
        base_file=f"{config_type}/{version}/config-schema.base.json",
        base_payload=base_schema,
        parts=top_level_parts,
    )


def main() -> None:
    from config_service.services.catalog_service import CatalogService
    from config_service.services.schema_service import SchemaService

    catalog_service = CatalogService(CONFIG_DIR / "catalog-registry.json")
    catalog_service.load_all_catalogs()
    schema_service = SchemaService()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SRC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for config_type in catalog_service.get_supported_config_types():
        for version in catalog_service.get_versions(config_type=config_type):
            catalog = catalog_service.get_catalog(version, config_type=config_type)
            schema = schema_service.compile_schema(catalog, strict_mode=True)
            _write_schema_artifact(OUTPUT_DIR, config_type, version, schema)
            _write_schema_artifact(SRC_OUTPUT_DIR, config_type, version, schema)


if __name__ == "__main__":
    main()
