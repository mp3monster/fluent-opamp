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

"""Generate a CycloneDX-style SBOM for the standalone config-service package."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "sbom" / "config-service-sbom.cdx.json"


def _requirement_name(requirement: str) -> str:
    return re.split(r"[<>=!~;\\[]", requirement, maxsplit=1)[0].strip()


def _distribution_metadata(name: str) -> tuple[str, dict[str, Any]]:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return ("unknown", {"license": "unknown"})

    meta = dist.metadata
    license_value = meta.get("License") or "unknown"
    return (
        dist.version,
        {
            "license": license_value,
            "summary": meta.get("Summary") or "",
            "homepage": meta.get("Home-page") or meta.get("Project-URL") or "",
        },
    )


def _component(name: str, version: str, *, component_type: str = "library", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    component = {
        "type": component_type,
        "name": name,
        "version": version,
        "bom-ref": f"pkg:pypi/{name}@{version}",
        "purl": f"pkg:pypi/{name}@{version}",
    }
    if extra:
        license_name = extra.get("license")
        if license_name:
            component["licenses"] = [{"license": {"name": str(license_name)}}]
        description = extra.get("summary")
        if description:
            component["description"] = str(description)
        homepage = extra.get("homepage")
        if homepage:
            component["externalReferences"] = [{"type": "website", "url": str(homepage)}]
    return component


def build_sbom() -> dict[str, Any]:
    from build_config import INSTALL_REQUIRES, PACKAGE_NAME, PACKAGE_VERSION

    components = [
        _component(PACKAGE_NAME, PACKAGE_VERSION, component_type="application", extra={"license": "Apache-2.0"})
    ]

    dependency_refs = []
    for requirement in INSTALL_REQUIRES:
        name = _requirement_name(requirement)
        version, extra = _distribution_metadata(name)
        components.append(_component(name, version, extra=extra))
        dependency_refs.append(f"pkg:pypi/{name}@{version}")

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{PACKAGE_NAME}-{PACKAGE_VERSION}",
        "version": 1,
        "metadata": {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "component": _component(PACKAGE_NAME, PACKAGE_VERSION, component_type="application", extra={"license": "Apache-2.0"}),
            "tools": [{"vendor": "OpenAI Codex", "name": "generate_sbom.py"}],
        },
        "components": components,
        "dependencies": [
            {
                "ref": f"pkg:pypi/{PACKAGE_NAME}@{PACKAGE_VERSION}",
                "dependsOn": dependency_refs,
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate config-service SBOM")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output SBOM path")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_sbom(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
