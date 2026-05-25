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

"""Build shim for catalog-service wheel packaging."""

from __future__ import annotations

import sys
from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
for candidate in (ROOT, ROOT / "src", REPO_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    from shared.packaging_warnings import warn_if_cli_missing
except ModuleNotFoundError:  # pragma: no cover - build fallback when shared package is unavailable
    warn_if_cli_missing = None

if warn_if_cli_missing is not None:
    warn_if_cli_missing(
        component_label="catalog-service wheel build",
        repo_root=REPO_ROOT,
    )

setup(
    name="catalog-service",
    version="0.1.0",
    description="Standalone OpAMP configuration catalog backend and UI",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(where="src", include=["catalog_service", "catalog_service.*"]),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "catalog_service": [
            "config/*.json",
            "html/*.html",
            "html/*.css",
            "html/*.png",
        ],
    },
    install_requires=[
        "quart>=0.20.0",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "catalog-service=catalog_service.app:main",
        ]
    },
)
