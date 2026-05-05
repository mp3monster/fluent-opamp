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
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS_DIR = REPO_ROOT / "config-service" / "json-definitions"

LOG_LEVELS = ["off", "trace", "debug", "info", "warn", "error"]


def field(
    name: str,
    *,
    description: str,
    reference: str,
    data_type: str = "string",
    required: bool = False,
    default: Any | None = None,
    validation_rule: dict[str, Any] | None = None,
    enum_options: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "required": required,
        "description": description,
        "reference": reference,
        "data_type": data_type,
        "validation_rule": validation_rule,
    }
    if default is not None:
        payload["default"] = default
    if enum_options:
        payload["called_enum_options"] = enum_options
    return payload


def processor_def(
    *,
    title: str,
    doc_url: str,
    description: str,
    fields: list[dict[str, Any]],
    supports_condition: bool = False,
) -> dict[str, Any]:
    return {
        "title": title,
        "doc_url": doc_url,
        "description": description,
        "fields": fields,
        "supports_condition": supports_condition,
    }


def condition_object(reference: str) -> dict[str, Any]:
    return {
        "title": "condition",
        "description": "Optional conditional processing block for logs processors.",
        "reference": reference,
        "fields": [
            field(
                "op",
                description="How to evaluate the condition rules.",
                reference=reference,
                data_type="enum",
                required=True,
                validation_rule={"kind": "enum", "values": ["and", "or"]},
                enum_options=["and", "or"],
            ),
            field(
                "rules",
                description="Array of condition rules expressed as JSON objects with field, op, and value keys.",
                reference=reference,
                data_type="list",
                required=True,
                validation_rule={"kind": "list"},
            ),
        ],
    }


def processors_definition(version: str) -> dict[str, Any]:
    base_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors"
    content_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/content-modifier"
    labels_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/labels"
    metrics_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/metrics-selector"
    otel_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/opentelemetry-envelope"
    sampling_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/sampling"
    sql_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/sql"
    filters_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/filters"
    c2d_ref = "https://docs.fluentbit.io/manual/4.2/data-pipeline/processors/cumulative-to-delta"
    tda_ref = "https://docs.fluentbit.io/manual/data-pipeline/processors/tda"

    supports_condition = version != "3.2.10"

    return {
        "description": "Shared Fluent Bit processors available to input and output plugins in YAML configuration.",
        "yaml_only": True,
        "supported_sections": ["inputs", "outputs"],
        "condition": condition_object("https://docs.fluentbit.io/manual/data-pipeline/processors/conditional-processing")
        if supports_condition
        else None,
        "signals": {
            "logs": {
                "allow_filters_as_processors": True,
                "processors": {
                    "content_modifier": processor_def(
                        title="content_modifier",
                        doc_url=content_ref,
                        description="Manipulates log or trace content and attributes.",
                        fields=[
                            field(
                                "action",
                                description="Content modifier action to perform.",
                                reference=content_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["convert", "delete", "extract", "hash", "insert", "rename", "upsert"]},
                                enum_options=["convert", "delete", "extract", "hash", "insert", "rename", "upsert"],
                            ),
                            field(
                                "context",
                                description="Context where the modification is applied.",
                                reference=content_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["attributes", "body", "otel_resource_attributes", "otel_scope_name", "otel_scope_version", "otel_scope_attributes", "otel_log_attributes"]},
                                enum_options=["attributes", "body", "otel_resource_attributes", "otel_scope_name", "otel_scope_version", "otel_scope_attributes", "otel_log_attributes"],
                            ),
                            field("key", description="Key targeted by the action.", reference=content_ref),
                            field("value", description="Value used by the action.", reference=content_ref),
                            field("pattern", description="Regular expression used by the extract action.", reference=content_ref),
                            field(
                                "converted_type",
                                description="Target type used by the convert action.",
                                reference=content_ref,
                                data_type="enum",
                                validation_rule={"kind": "enum", "values": ["string", "boolean", "int", "double"]},
                                enum_options=["string", "boolean", "int", "double"],
                            ),
                        ],
                        supports_condition=supports_condition,
                    ),
                    "opentelemetry_envelope": processor_def(
                        title="opentelemetry_envelope",
                        doc_url=otel_ref,
                        description="Wraps logs into an OpenTelemetry-compatible schema envelope.",
                        fields=[],
                        supports_condition=False,
                    ),
                    "sql": processor_def(
                        title="sql",
                        doc_url=sql_ref,
                        description="Runs a SQL query against the log stream.",
                        fields=[
                            field(
                                "query",
                                description="SQL statement executed against STREAM and ending with a semicolon.",
                                reference=sql_ref,
                                required=True,
                                data_type="code",
                                validation_rule={
                                    "kind": "code_syntax",
                                    "language": "sql",
                                    "parser": "lark",
                                    "dialect": "fluentbit_processor_sql",
                                },
                            ),
                        ],
                        supports_condition=False,
                    ),
                },
            },
            "metrics": {
                "allow_filters_as_processors": False,
                "processors": {
                    "labels": processor_def(
                        title="labels",
                        doc_url=labels_ref,
                        description="Manipulates labels on metrics.",
                        fields=[
                            field("insert", description="Insert operation expressed as 'key value'.", reference=labels_ref),
                            field("update", description="Update operation expressed as 'key value'.", reference=labels_ref),
                            field("upsert", description="Upsert operation expressed as 'key value'.", reference=labels_ref),
                            field("delete", description="Delete operation expressed as a label key.", reference=labels_ref),
                            field("hash", description="Hash operation expressed as a label key.", reference=labels_ref),
                        ],
                    ),
                    "metrics_selector": processor_def(
                        title="metrics_selector",
                        doc_url=metrics_ref,
                        description="Includes or excludes metrics using metric name and label matching.",
                        fields=[
                            field(
                                "action",
                                description="Whether matching metrics are included or excluded.",
                                reference=metrics_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["INCLUDE", "EXCLUDE"]},
                                enum_options=["INCLUDE", "EXCLUDE"],
                            ),
                            field(
                                "context",
                                description="Matching context.",
                                reference=metrics_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["metric_name", "delete_label_value"]},
                                enum_options=["metric_name", "delete_label_value"],
                            ),
                            field("metric_name", description="Metric name or regex used by the match operation.", reference=metrics_ref),
                            field("label", description="Label key/value pair used by delete_label_value matching.", reference=metrics_ref),
                            field(
                                "operation_type",
                                description="Metric-name matching mode.",
                                reference=metrics_ref,
                                data_type="enum",
                                validation_rule={"kind": "enum", "values": ["PREFIX", "SUBSTRING"]},
                                enum_options=["PREFIX", "SUBSTRING"],
                            ),
                        ],
                    ),
                    "cumulative_to_delta": processor_def(
                        title="cumulative_to_delta",
                        doc_url=c2d_ref,
                        description="Converts cumulative monotonic metrics to delta values.",
                        fields=[
                            field("drop_first", description="Compatibility option for first-sample handling when initial_value is unset.", reference=c2d_ref, data_type="boolean", default=True, validation_rule={"kind": "boolean"}),
                            field("drop_on_reset", description="Drop a sample when a reset is detected.", reference=c2d_ref, data_type="boolean", default=True, validation_rule={"kind": "boolean"}),
                            field(
                                "initial_value",
                                description="How the first sample for a new series is handled.",
                                reference=c2d_ref,
                                data_type="enum",
                                validation_rule={"kind": "enum", "values": ["auto", "keep", "drop"]},
                                enum_options=["auto", "keep", "drop"],
                            ),
                            field("max_series", description="Maximum number of series tracked in memory.", reference=c2d_ref, data_type="integer", default=65536, validation_rule={"kind": "range", "min": 0}),
                            field("max_staleness", description="How long to retain per-series state.", reference=c2d_ref, data_type="time", default="1h"),
                        ],
                    ),
                    "tda": processor_def(
                        title="tda",
                        doc_url=tda_ref,
                        description="Applies topological data analysis over a sliding window of metrics.",
                        fields=[
                            field("window_size", description="Number of samples kept in the sliding window.", reference=tda_ref, data_type="integer", default=60, validation_rule={"kind": "range", "min": 1}),
                            field("min_points", description="Minimum number of samples required before analysis runs.", reference=tda_ref, data_type="integer", default=10, validation_rule={"kind": "range", "min": 1}),
                            field("embed_dim", description="Delay embedding dimension.", reference=tda_ref, data_type="integer", default=3, validation_rule={"kind": "range", "min": 1}),
                            field("embed_delay", description="Embedding delay in samples.", reference=tda_ref, data_type="integer", default=1, validation_rule={"kind": "range", "min": 1}),
                            field("threshold", description="Distance threshold quantile or 0 for automatic scan.", reference=tda_ref, data_type="number", default=0, validation_rule={"kind": "range", "min": 0, "max": 1}),
                        ],
                    ),
                },
            },
            "traces": {
                "allow_filters_as_processors": False,
                "processors": {
                    "content_modifier": processor_def(
                        title="content_modifier",
                        doc_url=content_ref,
                        description="Manipulates trace span content and attributes.",
                        fields=[
                            field(
                                "action",
                                description="Content modifier action to perform.",
                                reference=content_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["convert", "delete", "extract", "hash", "insert", "rename", "upsert"]},
                                enum_options=["convert", "delete", "extract", "hash", "insert", "rename", "upsert"],
                            ),
                            field(
                                "context",
                                description="Trace context where the modification is applied.",
                                reference=content_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["span_name", "span_kind", "span_status", "span_attributes"]},
                                enum_options=["span_name", "span_kind", "span_status", "span_attributes"],
                            ),
                            field("key", description="Key targeted by the action.", reference=content_ref),
                            field("value", description="Value used by the action.", reference=content_ref),
                            field("pattern", description="Regular expression used by the extract action.", reference=content_ref),
                            field(
                                "converted_type",
                                description="Target type used by the convert action.",
                                reference=content_ref,
                                data_type="enum",
                                validation_rule={"kind": "enum", "values": ["string", "boolean", "int", "double"]},
                                enum_options=["string", "boolean", "int", "double"],
                            ),
                        ],
                    ),
                    "sampling": processor_def(
                        title="sampling",
                        doc_url=sampling_ref,
                        description="Applies probabilistic or tail sampling to trace telemetry.",
                        fields=[
                            field(
                                "type",
                                description="Sampling mode.",
                                reference=sampling_ref,
                                data_type="enum",
                                required=True,
                                validation_rule={"kind": "enum", "values": ["probabilistic", "tail"]},
                                enum_options=["probabilistic", "tail"],
                            ),
                            field("debug", description="Enable sampling debug output.", reference=sampling_ref, data_type="boolean", default=False, validation_rule={"kind": "boolean"}),
                            field("sampling_settings", description="Sampling settings object, such as percentage or decision_wait.", reference=sampling_ref, data_type="map", validation_rule={"kind": "map"}),
                            field("conditions", description="Array of tail-sampling condition objects.", reference=sampling_ref, data_type="list", validation_rule={"kind": "list"}),
                        ],
                    ),
                },
            },
        },
        "references": {
            "processors": base_ref,
            "filters_as_processors": filters_ref,
        },
    }


def update_catalog(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    version = str(data.get("fluent_bit_version"))
    common = data.setdefault("common", {})
    common["processors"] = processors_definition(version)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for version in ("3.2.10", "4.2.4", "5.0.4"):
        update_catalog(DEFINITIONS_DIR / f"fluent-bit-{version}-all-plugins-catalog.json")


if __name__ == "__main__":
    main()
