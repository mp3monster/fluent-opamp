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

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SECTION_TITLES = {
    "inputs": "Inputs",
    "filters": "Filters",
    "outputs": "Outputs",
}
DEFAULT_VERSIONS = ("3.2.10", "4.2.4", "5.0.4")


def schema_path(version: str) -> Path:
    return REPO_ROOT / "json-schemas" / f"fluentbit-{version}-config-schema.json"


def output_path(version: str) -> Path:
    return REPO_ROOT / "dev-notes" / f"fluent-bit-{version}-schema-quick-reference.md"


def load_schema(version: str) -> dict[str, Any]:
    return json.loads(schema_path(version).read_text(encoding="utf-8"))


def plugin_variants(schema: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return (
        schema["properties"]["config"]["properties"]["pipeline"]["properties"][section]["items"]["oneOf"]
    )


def plugin_name(variant: dict[str, Any]) -> str:
    return str(variant["properties"]["name"]["const"])


def plugin_doc_url(variant: dict[str, Any]) -> str:
    for field_name, field_schema in variant.get("properties", {}).items():
        if field_name == "name":
            continue
        ref = field_schema.get("x-doc-reference")
        if ref:
            return str(ref)
    return ""


def anchor_for(section: str, name: str) -> str:
    return f"{section}-{name.lower().replace('_', '-').replace('.', '-')}"


def format_default(field_schema: dict[str, Any], *, fallback: str = "") -> str:
    if "const" in field_schema:
        return str(field_schema["const"])
    if "default" not in field_schema:
        return fallback
    value = field_schema["default"]
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if isinstance(value, str):
        return re.sub(r",\s*", ", ", value)
    return str(value)


def mandatory_label(field_name: str, variant: dict[str, Any], field_schema: dict[str, Any]) -> str:
    required = set(variant.get("required", []))
    if field_name in required:
        return "Yes"
    if field_schema.get("x-doc-required") is True:
        return "Yes"
    return "No"


def attribute_description(field_name: str, field_schema: dict[str, Any]) -> str:
    if field_name == "name":
        return "Plugin identifier."
    return re.sub(r",\s*", ", ", str(field_schema.get("description", "")).strip())


def escape_pipes(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def sort_field_names(variant: dict[str, Any]) -> list[str]:
    properties = variant.get("properties", {})
    required = set(variant.get("required", []))

    def sort_key(field_name: str) -> tuple[int, int, str]:
        is_required = field_name in required or properties[field_name].get("x-doc-required") is True
        is_name = field_name == "name"
        return (0 if is_required else 1, 0 if is_name else 1, field_name.lower())

    return sorted(properties.keys(), key=sort_key)


def build_plugin_table(section: str, variant: dict[str, Any]) -> list[str]:
    name = plugin_name(variant)
    title = str(variant.get("title", name))
    doc_url = plugin_doc_url(variant)
    anchor = anchor_for(section, name)

    lines = [
        f'<a id="{anchor}"></a>',
        f"### `{name}`: {title}",
    ]
    if doc_url:
        lines.append(f"Fluent Bit page: [{title}]({doc_url})")
    lines.extend(
        [
            "",
            "| Attribute | Mandatory | Default | Description |",
            "| --- | --- | --- | --- |",
        ]
    )

    properties = variant.get("properties", {})
    for field_name in sort_field_names(variant):
        field_schema = properties[field_name]
        default_value = format_default(
            field_schema,
            fallback=name if field_name == "name" else "",
        )
        description = attribute_description(field_name, field_schema)
        attribute = f"`{escape_pipes(field_name)}`"
        if doc_url:
            attribute = f"[{attribute}]({doc_url})"
        lines.append(
            "| {attribute} | {mandatory} | {default_value} | {description} |".format(
                attribute=attribute,
                mandatory=mandatory_label(field_name, variant, field_schema),
                default_value=(
                    f"`{escape_pipes(default_value)}`" if default_value else ""
                ),
                description=escape_pipes(description),
            )
        )
    lines.append("")
    return lines


def build_section(section: str, variants: list[dict[str, Any]]) -> list[str]:
    sorted_variants = sorted(variants, key=lambda item: plugin_name(item).lower())
    links = [
        f"[`{plugin_name(variant)}`](#{anchor_for(section, plugin_name(variant))})"
        for variant in sorted_variants
    ]
    lines = [
        f"## {SECTION_TITLES[section]}",
        "",
        ", ".join(links),
        "",
    ]
    for variant in sorted_variants:
        lines.extend(build_plugin_table(section, variant))
    return lines


def generate_markdown(schema: dict[str, Any], version: str) -> str:
    version_schema_path = schema_path(version)
    lines = [
        f"# Fluent Bit {version} Schema Quick Reference",
        "",
        f"Generated from the local Fluent Bit {version} JSON schema only:",
        f"- `{version_schema_path.relative_to(REPO_ROOT)}`",
        "",
        "Scope:",
        "1. Pipeline plugin definitions only",
        "2. Grouped by `inputs`, `filters`, and `outputs`",
        "3. Includes mandatory flags, defaults, descriptions, and Fluent Bit documentation links",
        "",
        "## Jump Lists",
        "",
    ]
    for section in ("inputs", "filters", "outputs"):
        variants = plugin_variants(schema, section)
        links = [
            f"[`{plugin_name(variant)}`](#{anchor_for(section, plugin_name(variant))})"
            for variant in sorted(variants, key=lambda item: plugin_name(item).lower())
        ]
        lines.append(f"- **{SECTION_TITLES[section]}**: {', '.join(links)}")
    lines.append("")

    for section in ("inputs", "filters", "outputs"):
        lines.extend(build_section(section, plugin_variants(schema, section)))

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Fluent Bit schema quick reference markdown.",
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
        schema = load_schema(version)
        version_output_path = output_path(version)
        version_output_path.write_text(generate_markdown(schema, version), encoding="utf-8")
        print(f"Wrote {version_output_path}")


if __name__ == "__main__":
    main()
