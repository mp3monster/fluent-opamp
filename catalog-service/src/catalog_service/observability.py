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

import logging
from typing import Optional

from quart import Quart

from opentelemetry import trace, metrics
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

from opentelemetry._logs import set_logger_provider


def attach_observability(
    app: Quart,
    service_name: str,
    otlp_endpoint: str = "http://localhost:4317",
    log_level: int = logging.INFO,
    metrics_export_interval_ms: int = 60_000,
) -> Quart:
    """
    Attach OpenTelemetry traces, metrics, and logs to a Quart app.

    Exports telemetry using OTLP/gRPC, typically to an OpenTelemetry Collector.

    Args:
        app: The Quart application instance.
        service_name: Logical service name shown in observability backends.
        otlp_endpoint: OTLP/gRPC endpoint, for example http://localhost:4317.
        log_level: Python logging level.
        metrics_export_interval_ms: Metric export interval in milliseconds.

    Returns:
        The same Quart app instance, with ASGI telemetry middleware attached.
    """

    resource = Resource.create(
        {
            "service.name": service_name,
            "telemetry.sdk.language": "python",
        }
    )

    # -------------------------
    # Traces
    # -------------------------
    trace_provider = TracerProvider(resource=resource)

    trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)

    trace_provider.add_span_processor(
        BatchSpanProcessor(trace_exporter)
    )

    trace.set_tracer_provider(trace_provider)

    # Wrap Quart's ASGI app so inbound HTTP requests create spans.
    app.asgi_app = OpenTelemetryMiddleware(app.asgi_app)

    # -------------------------
    # Metrics
    # -------------------------
    metric_exporter = OTLPMetricExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )

    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=metrics_export_interval_ms,
    )

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )

    metrics.set_meter_provider(meter_provider)

    # Example custom app metric.
    meter = metrics.get_meter(service_name)
    request_counter = meter.create_counter(
        name="app.requests",
        description="Application-level request counter",
        unit="1",
    )

    @app.before_request
    async def count_request() -> None:
        request_counter.add(1)

    # -------------------------
    # Logs
    # -------------------------
    logger_provider = LoggerProvider(resource=resource)

    log_exporter = OTLPLogExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )

    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )

    set_logger_provider(logger_provider)

    otel_log_handler = LoggingHandler(
        level=log_level,
        logger_provider=logger_provider,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(otel_log_handler)

    # Adds trace_id/span_id correlation fields to Python logs where possible.
    LoggingInstrumentor().instrument(set_logging_format=True)

    return app