"""Metrics route registration for the provider app."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from quart import Quart, Response, jsonify, request
from quart.typing import ResponseReturnValue

from opamp_provider.metrics.registry import PROMETHEUS_CONTENT_TYPE


def register_metrics_routes(
    app: Quart,
    *,
    provider_config: Any,
    metrics_registry: Any,
    store: Any,
) -> None:
    """Register Prometheus and internal graph metrics routes."""

    @app.get("/metrics")
    async def get_prometheus_metrics() -> ResponseReturnValue:
        """Return provider metrics using Prometheus text exposition format."""
        if provider_config.CONFIG.metrics.enabled is not True:
            return jsonify({"error": "provider metrics are disabled"}), HTTPStatus.NOT_FOUND
        return Response(
            metrics_registry.render_prometheus_text(store),
            content_type=PROMETHEUS_CONTENT_TYPE,
            status=HTTPStatus.OK,
        )

    @app.get("/api/metrics/graphs")
    async def get_metrics_graphs() -> ResponseReturnValue:
        """Return retained graph data for graphable gauge metrics."""
        if provider_config.CONFIG.metrics.enabled is not True:
            return jsonify({"error": "provider metrics are disabled"}), HTTPStatus.NOT_FOUND
        metric_names = request.args.getlist("metric")
        return jsonify(
            metrics_registry.build_graph_payload(
                store,
                metric_names=metric_names,
            )
        )
