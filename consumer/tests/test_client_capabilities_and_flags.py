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
import pathlib

import pytest
from shared.opamp_config import AGENT_CAPABILITIES_MAP

import opamp_consumer.fluentbit_client as client
from opamp_consumer.config import ConsumerConfig
from opamp_consumer.exceptions import RemoteAgentConfigWriteError
from opamp_consumer.fluentbit_client import CONFIG_DOCS_URL
from opamp_consumer.proto import opamp_pb2


def _set_config(
    agent_capabilities,
    *,
    preserve_previous_config: bool = False,
) -> None:
    """Install a test config with the requested agent capabilities."""
    config = ConsumerConfig(
        server_url="http://localhost",
        agent_config_path="unused",
        agent_additional_params=[],
        heartbeat_frequency=30,
        agent_capabilities=agent_capabilities,
        preserve_previous_config=preserve_previous_config,
        log_level="debug",
        service_name="Fluentbit",
        service_namespace="FluentBitNS",
    )
    client.CONFIG = config


def test_get_agent_capabilities_from_names(caplog) -> None:
    """Configured capability names should merge with mandatory capabilities."""
    _set_config(["ReportsStatus", "ReportsHealth", "ReportsHeartbeat"])
    caplog.set_level(logging.INFO)
    instance = client.OpAMPClient("http://localhost")

    mask = instance.get_agent_capabilities()
    expected = (
        AGENT_CAPABILITIES_MAP["ReportsStatus"]
        | AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
        | AGENT_CAPABILITIES_MAP["ReportsHealth"]
        | AGENT_CAPABILITIES_MAP["ReportsHeartbeat"]
    )
    assert mask == expected
    assert instance.config.enabled_agent_capabilities == [
        "ReportsStatus",
        "AcceptsRestartCommand",
        "ReportsHealth",
        "ReportsHeartbeat",
    ]
    assert "supported capability not enabled capability=AcceptsRemoteConfig" in caplog.text


def test_get_agent_capabilities_warns_unknown(caplog) -> None:
    """Configured unsupported capabilities should be warned and ignored."""
    _set_config(["ReportsStatus", "UnknownCapability"])
    caplog.set_level(logging.INFO)
    instance = client.OpAMPClient("http://localhost")

    mask = instance.get_agent_capabilities()
    assert mask == (
        AGENT_CAPABILITIES_MAP["ReportsStatus"]
        | AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
        | AGENT_CAPABILITIES_MAP["ReportsHealth"]
    )
    assert (
        "configured capability cannot be supported capability=UnknownCapability; "
        "ignoring config"
    ) in caplog.text


def test_populate_agent_to_server_uses_configured_capability_override() -> None:
    """Configured optional capabilities should merge into the outbound mask."""
    _set_config(["AcceptsRestartCommand", "AcceptsRemoteConfig"])
    instance = client.OpAMPClient("http://localhost")
    message = opamp_pb2.AgentToServer()

    populated = instance._populate_agent_to_server(message)

    expected_mask = (
        AGENT_CAPABILITIES_MAP["ReportsStatus"]
        | AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
        | AGENT_CAPABILITIES_MAP["ReportsHealth"]
        | AGENT_CAPABILITIES_MAP["AcceptsRemoteConfig"]
    )
    assert populated.capabilities == expected_mask
    assert instance.config.agent_capabilities == expected_mask
    assert "AcceptsRemoteConfig" in instance.config.enabled_agent_capabilities


def test_get_agent_capabilities_derives_default_mask_when_unset() -> None:
    """Missing override should derive and cache the mandatory capability mask."""
    _set_config(None)
    instance = client.OpAMPClient("http://localhost")

    mask = instance.get_agent_capabilities()

    assert mask == (
        AGENT_CAPABILITIES_MAP["ReportsStatus"]
        | AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
        | AGENT_CAPABILITIES_MAP["ReportsHealth"]
    )
    assert instance.config.agent_capabilities == mask
    assert instance.config.enabled_agent_capabilities == [
        "ReportsStatus",
        "AcceptsRestartCommand",
        "ReportsHealth",
    ]


def test_populate_agent_to_server_includes_mandatory_capabilities_when_unset() -> None:
    """Outbound payload should advertise the built-in three capabilities by default."""
    _set_config(None)
    instance = client.OpAMPClient("http://localhost")
    message = opamp_pb2.AgentToServer()

    populated = instance._populate_agent_to_server(message)

    assert populated.capabilities & AGENT_CAPABILITIES_MAP["ReportsStatus"]
    assert populated.capabilities & AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
    assert populated.capabilities & AGENT_CAPABILITIES_MAP["ReportsHealth"]


def test_get_agent_capabilities_enables_remote_config_when_configured() -> None:
    """Configured optional remote config should be enabled when supported."""
    _set_config(["AcceptsRemoteConfig"])
    instance = client.OpAMPClient("http://localhost")

    mask = instance.get_agent_capabilities()

    assert mask == (
        AGENT_CAPABILITIES_MAP["ReportsStatus"]
        | AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
        | AGENT_CAPABILITIES_MAP["ReportsHealth"]
        | AGENT_CAPABILITIES_MAP["AcceptsRemoteConfig"]
    )
    assert instance.is_capability_allowed("AcceptsRemoteConfig") is True
    assert instance.is_capability_allowed("AcceptsPackages") is False


def test_get_agent_capabilities_enables_effective_config_when_configured() -> None:
    """Configured effective-config reporting should be enabled when supported."""
    _set_config(["ReportsEffectiveConfig"])
    instance = client.OpAMPClient("http://localhost")

    mask = instance.get_agent_capabilities()

    assert mask == (
        AGENT_CAPABILITIES_MAP["ReportsStatus"]
        | AGENT_CAPABILITIES_MAP["AcceptsRestartCommand"]
        | AGENT_CAPABILITIES_MAP["ReportsHealth"]
        | AGENT_CAPABILITIES_MAP["ReportsEffectiveConfig"]
    )
    assert instance.is_capability_allowed("ReportsEffectiveConfig") is True


def test_populate_agent_to_server_includes_effective_config_when_enabled(
    tmp_path,
    caplog,
) -> None:
    """Effective config should be attached when the reporting capability is enabled."""
    config_path = tmp_path / "effective.yaml"
    config_path.write_text("service:\n  flush: 1\n", encoding="utf-8")
    config = ConsumerConfig(
        server_url="http://localhost",
        agent_config_path=str(config_path),
        agent_additional_params=[],
        heartbeat_frequency=30,
        agent_capabilities=["ReportsEffectiveConfig"],
        log_level="debug",
        service_name="Fluentbit",
        service_namespace="FluentBitNS",
    )
    instance = client.OpAMPClient("http://localhost", config)
    message = opamp_pb2.AgentToServer()
    caplog.set_level(logging.INFO)

    populated = instance._populate_agent_to_server(message)

    config_map = populated.effective_config.config_map.config_map
    assert str(config_path) in config_map
    assert config_map[str(config_path)].body == b"service:\n  flush: 1\n"
    assert config_map[str(config_path)].content_type == "application/x-yaml"
    assert "generated effective_config payload" in caplog.text


def test_populate_agent_to_server_omits_effective_config_when_not_enabled(
    tmp_path,
) -> None:
    """Effective config should be omitted when the reporting capability is disabled."""
    config_path = tmp_path / "effective.yaml"
    config_path.write_text("service:\n  flush: 1\n", encoding="utf-8")
    config = ConsumerConfig(
        server_url="http://localhost",
        agent_config_path=str(config_path),
        agent_additional_params=[],
        heartbeat_frequency=30,
        agent_capabilities=None,
        log_level="debug",
        service_name="Fluentbit",
        service_namespace="FluentBitNS",
    )
    instance = client.OpAMPClient("http://localhost", config)
    message = opamp_pb2.AgentToServer()

    populated = instance._populate_agent_to_server(message)

    assert not populated.HasField("effective_config")


def test_write_config_file_preserves_previous_file_when_enabled(tmp_path) -> None:
    """A replaced config should be renamed with the required preserved postfix."""
    _set_config(None, preserve_previous_config=True)
    instance = client.OpAMPClient("http://localhost")
    target_path = tmp_path / "agent.conf"
    target_path.write_text("before=true\n", encoding="utf-8")

    instance.write_config_file(str(target_path), b"after=true\n")

    preserved_paths = list(tmp_path.glob("agent.conf.replaced_*"))
    assert target_path.read_text(encoding="utf-8") == "after=true\n"
    assert len(preserved_paths) == 1
    assert preserved_paths[0].read_text(encoding="utf-8") == "before=true\n"


def test_write_config_file_restores_original_when_write_fails(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An I/O failure after preservation should raise a controlled write error."""
    _set_config(None, preserve_previous_config=True)
    instance = client.OpAMPClient("http://localhost")
    target_path = tmp_path / "agent.conf"
    target_path.write_text("before=true\n", encoding="utf-8")
    original_write_text = pathlib.Path.write_text

    def _failing_write_text(
        self: pathlib.Path,
        data: str,
        *args,
        **kwargs,
    ) -> int:
        if self == target_path:
            raise OSError("disk full")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "write_text", _failing_write_text)

    with pytest.raises(RemoteAgentConfigWriteError, match="disk full"):
        instance.write_config_file(str(target_path), b"after=true\n")

    assert target_path.read_text(encoding="utf-8") == "before=true\n"
    assert list(tmp_path.glob("agent.conf.replaced_*")) == []


def test_get_config_parameters_includes_docs_url() -> None:
    """Return config parameters plus documentation URL reference."""
    _set_config(["ReportsStatus"])
    instance = client.OpAMPClient("http://localhost")
    config_params = instance.get_config_parameters()
    assert config_params["server_url"] == "http://localhost"
    assert config_params["documentation_url"] == CONFIG_DOCS_URL
    assert isinstance(config_params["component_version"], str)


def test_reporting_flags_default_to_true() -> None:
    """OpAMPClientData should default all ReportingFlag values to True."""
    _set_config(["ReportsStatus"])
    instance = client.OpAMPClient("http://localhost")
    assert instance.data.reporting_flags
    assert set(instance.data.reporting_flags.keys()) == set(client.ReportingFlag)
    assert all(instance.data.reporting_flags.values())


def test_reporting_flags_setall_updates_all_values() -> None:
    """set_all_reporting_flags should apply the given value to all reporting flags."""
    _set_config(["ReportsStatus"])
    instance = client.OpAMPClient("http://localhost")

    instance.data.set_all_reporting_flags(False)
    assert all(value is False for value in instance.data.reporting_flags.values())

    instance.data.set_all_reporting_flags()
    assert all(value is True for value in instance.data.reporting_flags.values())


def test_reportingflag_setall_updates_all_values() -> None:
    """ReportingFlag.set_all_reporting_flags should update every flag entry in-place."""
    flags = {flag: True for flag in client.ReportingFlag}
    client.ReportingFlag.set_all_reporting_flags(flags, False)
    assert all(value is False for value in flags.values())


def test_handle_flags_logs_names_and_sets_all_for_report_full_state(caplog) -> None:
    """handle_flags should decode names and set all flags when ReportFullState is present."""
    _set_config(["ReportsStatus"])
    instance = client.OpAMPClient("http://localhost")
    instance.data.set_all_reporting_flags(False)
    caplog.set_level(logging.INFO)

    instance.handle_flags(
        opamp_pb2.ServerToAgentFlags.ServerToAgentFlags_ReportFullState
        | opamp_pb2.ServerToAgentFlags.ServerToAgentFlags_ReportAvailableComponents
    )

    assert all(instance.data.reporting_flags.values())
    assert "ReportFullState" in caplog.text
    assert "ReportAvailableComponents" in caplog.text


def test_handle_flags_without_report_full_state_does_not_set_all() -> None:
    """handle_flags should not force-enable reporting flags without ReportFullState."""
    _set_config(["ReportsStatus"])
    instance = client.OpAMPClient("http://localhost")
    instance.data.set_all_reporting_flags(False)

    instance.handle_flags(
        opamp_pb2.ServerToAgentFlags.ServerToAgentFlags_ReportAvailableComponents
    )

    assert not any(instance.data.reporting_flags.values())
