"""Tests for broker runtime configuration loading and derived routes."""

import json
from pathlib import Path

from opamp_broker.config.loader import load_runtime_config


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_runtime_config_applies_provider_port_override(tmp_path: Path) -> None:
    """Verifies broker config can override the provider port used for derived routes."""
    prompts_path = (
        Path(__file__).resolve().parents[1]
        / "opamp_broker"
        / "config"
        / "planner_prompts.json"
    )
    opamp_config_path = tmp_path / "opamp.json"
    broker_config_path = tmp_path / "broker.json"

    _write_json(
        opamp_config_path,
        {
            "consumer": {"server_url": "http://example.local:8080"},
            "provider": {"webui_port": 8080},
        },
    )
    _write_json(
        broker_config_path,
        {
            "paths": {
                "opamp_config_path": str(opamp_config_path),
                "provider_port_override": 8070,
            },
            "planner": {"prompts_config_path": str(prompts_path)},
        },
    )

    config = load_runtime_config(str(broker_config_path))

    assert config["derived"]["provider_port"] == 8070
    assert config["derived"]["provider_routes"]["base_url"] == "http://example.local:8070"
    assert config["derived"]["provider_routes"]["mcp_url"] == "http://example.local:8070/mcp"


def test_load_runtime_config_uses_provider_port_when_override_missing(
    tmp_path: Path,
) -> None:
    """Verifies derived routes fall back to the provider port when no override is set."""
    prompts_path = (
        Path(__file__).resolve().parents[1]
        / "opamp_broker"
        / "config"
        / "planner_prompts.json"
    )
    opamp_config_path = tmp_path / "opamp.json"
    broker_config_path = tmp_path / "broker.json"

    _write_json(
        opamp_config_path,
        {
            "consumer": {"server_url": "http://example.local:8080"},
            "provider": {"webui_port": 8080},
        },
    )
    _write_json(
        broker_config_path,
        {
            "paths": {"opamp_config_path": str(opamp_config_path)},
            "planner": {"prompts_config_path": str(prompts_path)},
        },
    )

    config = load_runtime_config(str(broker_config_path))

    assert config["derived"]["provider_port"] == 8080
    assert config["derived"]["provider_routes"]["base_url"] == "http://example.local:8080"


def test_load_runtime_config_inherits_otlp_endpoints_from_opamp_config(
    tmp_path: Path,
) -> None:
    """Broker should inherit otlp-endpoints from opamp.json when omitted locally."""
    prompts_path = (
        Path(__file__).resolve().parents[1]
        / "opamp_broker"
        / "config"
        / "planner_prompts.json"
    )
    opamp_config_path = tmp_path / "opamp.json"
    broker_config_path = tmp_path / "broker.json"

    _write_json(
        opamp_config_path,
        {
            "consumer": {"server_url": "http://example.local:8080"},
            "provider": {"webui_port": 8080},
            "otlp-endpoints": {
                "ALL": "http://collector:4317",
                "export_interval": 60,
            },
        },
    )
    _write_json(
        broker_config_path,
        {
            "paths": {"opamp_config_path": str(opamp_config_path)},
            "planner": {"prompts_config_path": str(prompts_path)},
        },
    )

    config = load_runtime_config(str(broker_config_path))

    assert config["otlp-endpoints"]["ALL"] == "http://collector:4317"
    assert config["otlp-endpoints"]["export_interval"] == 60
