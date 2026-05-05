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

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "json-schemas"


def main() -> None:
    from config_service.services.catalog_service import CatalogService
    from config_service.services.schema_service import SchemaService

    catalog_service = CatalogService(CONFIG_DIR / "catalog-registry.json")
    catalog_service.load_all_catalogs()
    schema_service = SchemaService()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for config_type in catalog_service.get_supported_config_types():
        for version in catalog_service.get_versions(config_type=config_type):
            catalog = catalog_service.get_catalog(version, config_type=config_type)
            schema = schema_service.compile_schema(catalog, strict_mode=True)
            output_path = OUTPUT_DIR / f"{config_type}-{version}-config-schema.json"
            output_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
