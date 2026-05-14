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

"""Generate a CycloneDX SBOM for the standalone config-service package."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "sbom" / "config-service-sbom.cdx.json"


def _run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _ensure_python_package(package_name: str) -> None:
    probe = subprocess.run(
        [sys.executable, "-m", "pip", "show", package_name],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return
    print(f"Python package `{package_name}` not found; installing it now...")
    _run([sys.executable, "-m", "pip", "install", package_name])


def _normalize_component_refs(sbom: dict[str, Any]) -> list[str]:
    components = sbom.get("components")
    if not isinstance(components, list):
        sbom["components"] = []
        return []

    dep_refs: list[str] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        purl = str(component.get("purl") or "").strip()
        if purl.startswith("pkg:pypi/"):
            component["bom-ref"] = purl
            dep_refs.append(purl)
    return sorted(set(dep_refs))


def _build_with_cyclonedx() -> dict[str, Any]:
    from build_config import INSTALL_REQUIRES

    with tempfile.TemporaryDirectory(prefix="config-service-sbom-") as temp_dir:
        temp_root = Path(temp_dir)
        requirements_path = temp_root / "requirements.txt"
        requirements_path.write_text(
            "".join(f"{requirement}\n" for requirement in INSTALL_REQUIRES),
            encoding="utf-8",
        )
        intermediate_output = temp_root / "sbom.json"
        _run(
            [
                sys.executable,
                "-m",
                "cyclonedx_py",
                "requirements",
                str(requirements_path),
                "--output-format",
                "JSON",
                "--spec-version",
                "1.6",
                "--output-file",
                str(intermediate_output),
            ]
        )
        return json.loads(intermediate_output.read_text(encoding="utf-8"))


def build_sbom() -> dict[str, Any]:
    from build_config import PACKAGE_NAME, PACKAGE_VERSION

    sbom = _build_with_cyclonedx()
    dependency_refs = _normalize_component_refs(sbom)

    root_ref = f"pkg:pypi/{PACKAGE_NAME}@{PACKAGE_VERSION}"
    root_component = {
        "type": "application",
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "bom-ref": root_ref,
        "purl": root_ref,
        "licenses": [{"license": {"id": "Apache-2.0"}}],
    }

    metadata = sbom.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["component"] = root_component
    sbom["metadata"] = metadata

    components = sbom.get("components")
    if not isinstance(components, list):
        components = []
    components = [component for component in components if isinstance(component, dict)]
    components = [root_component] + [
        component
        for component in components
        if str(component.get("bom-ref") or "").strip() != root_ref
    ]
    sbom["components"] = components

    dependencies = sbom.get("dependencies")
    if not isinstance(dependencies, list):
        dependencies = []
    dependencies = [entry for entry in dependencies if isinstance(entry, dict)]
    dependencies = [entry for entry in dependencies if str(entry.get("ref") or "").strip() != root_ref]
    dependencies.insert(
        0,
        {
            "ref": root_ref,
            "dependsOn": dependency_refs,
        },
    )
    sbom["dependencies"] = dependencies
    return sbom


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate config-service SBOM")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output SBOM path")
    args = parser.parse_args()

    _ensure_python_package("cyclonedx-bom")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_sbom(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
