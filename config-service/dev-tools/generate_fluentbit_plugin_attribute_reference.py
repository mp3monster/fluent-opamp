#!/usr/bin/env python3
# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
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
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS_DIR = REPO_ROOT / "config-service" / "json-definitions"
OUTPUT_DIR = REPO_ROOT / "config-service" / "dev-notes"
DEFAULT_VERSIONS = ("3.2.10", "4.2.4", "5.0.4")
SECTION_TITLES = (
    ("inputs", "Inputs"),
    ("filters", "Filters"),
    ("outputs", "Outputs"),
)


def _link(title: str, reference: str) -> str:
    if reference:
        return f"[{title}]({reference})"
    return title


def _section_rows(section_plugins: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for plugin_name in sorted(section_plugins):
        plugin_def = section_plugins.get(plugin_name)
        if not isinstance(plugin_def, dict):
            continue
        plugin_title = str(plugin_def.get("title") or plugin_name)
        fields = plugin_def.get("fields")
        if not isinstance(fields, list):
            continue
        for field_def in fields:
            if not isinstance(field_def, dict):
                continue
            field_name = str(field_def.get("name") or "").strip()
            if not field_name:
                continue
            reference = str(field_def.get("reference") or plugin_def.get("doc_url") or "").strip()
            rows.append(
                f"| `{plugin_name}` | `{field_name}` | {_link(plugin_title, reference)} |"
            )
    return rows


def _render_markdown(version: str, payload: dict[str, Any]) -> str:
    plugins = payload.get("plugins", {})
    lines: list[str] = [
        f"# Fluent Bit {version} Plugin Attribute Reference",
        "",
        "Generated from the local catalog JSON only.",
        "",
        "Scope: this reference includes the field-based `inputs`, `filters`, and `outputs` plugin groups from the catalog JSON. The `custom_plugins` block is not tabulated because it does not provide per-attribute documentation links in the same structure.",
    ]
    for section_key, section_title in SECTION_TITLES:
        section_plugins = plugins.get(section_key, {})
        if not isinstance(section_plugins, dict):
            continue
        lines.extend(
            [
                "",
                f"## {section_title}",
                "",
                "| Plugin Name | Attribute Name | Fluent Bit Page |",
                "| --- | --- | --- |",
            ]
        )
        lines.extend(_section_rows(section_plugins))
    return "\n".join(lines) + "\n"


def generate_reference(version: str) -> None:
    input_path = DEFINITIONS_DIR / f"fluent-bit-{version}-all-plugins-catalog.json"
    output_path = OUTPUT_DIR / f"fluent-bit-{version}-plugin-attribute-reference.md"
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.write_text(_render_markdown(version, payload), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Fluent Bit plugin attribute reference markdown from catalog JSON.",
    )
    parser.add_argument(
        "--version",
        action="append",
        dest="versions",
        help="Fluent Bit version to generate. Repeat for multiple versions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    versions = tuple(args.versions) if args.versions else DEFAULT_VERSIONS
    for version in versions:
        generate_reference(version)


if __name__ == "__main__":
    main()
