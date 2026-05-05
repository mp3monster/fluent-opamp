from __future__ import annotations

import json
from pathlib import Path

from config_service.services.catalog_service import CatalogService
from config_service.services.schema_service import SchemaService


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config-service" / "config"
OUTPUT_DIR = REPO_ROOT / "config-service" / "json-schemas"


def main() -> None:
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
