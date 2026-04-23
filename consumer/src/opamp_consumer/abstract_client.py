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

"""Shared abstract OpAMP client implementation and runtime data model."""

from __future__ import annotations

import logging
import pathlib
import platform
import socket
import subprocess
import threading
import uuid  # noqa: F401 - retained as stable monkeypatch seam in unit tests
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

import httpx  # noqa: F401 - legacy monkeypatch seam for auth token tests

from opamp_consumer import config as consumer_config
from opamp_consumer.client_bootstrap import (
    _get_local_ip,
    _get_local_mac,
    resolve_service_instance_id_template_with_values,
)
from opamp_consumer.client_message_builder import (
    parse_fluentbit_metrics_health,
    populate_agent_to_server,
    populate_agent_to_server_health,
)
from opamp_consumer.client_mixins import ClientRuntimeMixin, ServerMessageHandlingMixin
from opamp_consumer.client_transport_auth_mixin import (
    AUTH_RETRY_STATUS_CODES as _AUTH_RETRY_STATUS_CODES,
    ENV_OPAMP_TOKEN as _ENV_OPAMP_TOKEN,
    HEADER_AUTHORIZATION as _HEADER_AUTHORIZATION,
    TRANSPORT_HTTP as _TRANSPORT_HTTP,
    TRANSPORT_WEBSOCKET as _TRANSPORT_WEBSOCKET,
    ClientTransportAuthorizationMixin,
)
from opamp_consumer.component_version import component_version_text
from opamp_consumer.config import ConsumerConfig
from opamp_consumer.custom_handlers import build_factory_lookup, create_handler  # noqa: F401
from opamp_consumer.full_update_controller import (
    AlwaysSend,
    FullUpdateControllerInterface,
    SentCount,
    TimeSend,
)
from opamp_consumer.opamp_client_interface import OpAMPClientInterface
from opamp_consumer.proto import anyvalue_pb2, opamp_pb2
from opamp_consumer.reporting_flag import ReportingFlag
from opamp_consumer.client_transport import (  # noqa: F401 - legacy monkeypatch seam
    send_http_message,
    send_websocket_message,
)
from shared.opamp_config import (
    AgentCapabilities,
    parse_capabilities,
)
from shared.uuid_utils import generate_uuid7_bytes

LOCALHOST_BASE = "http://localhost"  # Base URL for local agent endpoints.
ERR_PREFIX = "error: "  # Prefix for error values stored in results.
TRANSPORT_HTTP = _TRANSPORT_HTTP  # Re-exported transport selector for HTTP mode.
TRANSPORT_WEBSOCKET = _TRANSPORT_WEBSOCKET  # Re-exported transport selector for WebSocket mode.
ENV_OPAMP_TOKEN = _ENV_OPAMP_TOKEN  # Re-exported env-var token key for compatibility.
HEADER_AUTHORIZATION = _HEADER_AUTHORIZATION  # Re-exported auth header key for compatibility.
AUTH_RETRY_STATUS_CODES = _AUTH_RETRY_STATUS_CODES  # Re-exported status codes for compatibility.
KEY_FLUENTBIT_VERSION = "fluentbit_version"  # Result key for version response.
KEY_SERVICE_INSTANCE_ID_COMMENT = "service_instance_id"  # Comment key for service instance ID.
KEY_SERVICE_NAME = "service.name"  # Agent description service name key.
KEY_SERVICE_NAMESPACE = "service.namespace"  # Agent description service namespace key.
KEY_SERVICE_INSTANCE_ID = "service.instance.id"  # Agent description instance id key.
KEY_SERVICE_TYPE = "service.type"  # Agent description service type key.
KEY_SERVICE_VERSION = "service.version"  # Agent description version key.
KEY_HEALTH = "health"  # Heartbeat dictionary key for health endpoint results.
VALUE_HEARTBEAT_STATUS = "heartbeat"  # Health status value used in heartbeats.
VALUE_SUPERVISOR_NO_STATE = "Supervisor has not state"  # Error message when no heartbeat data.
CAPABILITY_PREFIX_REQUEST = "request:"  # Prefix used for custom request capability FQDN.
HOST_META_KEY_OS_TYPE = "os_type"  # Host metadata key for OS type.
HOST_META_KEY_OS_VERSION = "os_version"  # Host metadata key for OS version.
HOST_META_KEY_HOSTNAME = "hostname"  # Host metadata key for hostname.
HOST_META_KEY_MAC_ADDRESS = "mac_address"  # Host metadata key for client MAC address.
CONFIG_DOCS_URL = (
    "https://github.com/mp3monster/fluent-opamp"  # Reference docs for consumer config.
)

def _config_parameters_payload(config: ConsumerConfig) -> dict[str, object]:
    """Build config parameters payload with documentation URL.

    Args:
        config: Consumer configuration instance to serialize.

    Returns:
        Dictionary of config fields plus `documentation_url`.
    """
    config_params: dict[str, object] = asdict(config)
    config_params["documentation_url"] = CONFIG_DOCS_URL
    config_params["component_version"] = component_version_text()
    return config_params


@dataclass
class OpAMPClientData:
    """Container for OpAMP client instance data."""

    config: ConsumerConfig
    base_url: str
    uid_instance: bytes | None = field(default_factory=generate_uuid7_bytes)
    allow_heartbeat: bool = True
    msg_sequence_number: int = 0
    last_heartbeat_http_codes: dict[str, int] | None = None
    last_heartbeat_call: int = 0
    last_heartbeat_results: dict[str, str] | None = field(default_factory=dict)
    launched_at: int = 0
    agent_process: subprocess.Popen[bytes] | None = None
    process_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    logFLB = False
    agent_type_name: str = "Fluent Bit"
    agent_version: str = ""
    reporting_flags: dict[ReportingFlag, bool] = field(
        default_factory=lambda: {flag: True for flag in ReportingFlag}
    )
    full_update_controller: FullUpdateControllerInterface | None = None

    def set_all_reporting_flags(self, value: bool = True) -> None:
        """Set every reporting flag value to the provided boolean.

        Args:
            value: Boolean value assigned to all reporting flags.
        """
        ReportingFlag.set_all_reporting_flags(self.reporting_flags, value)


class AbstractOpAMPClient(
    ClientTransportAuthorizationMixin,
    ClientRuntimeMixin,
    ServerMessageHandlingMixin,
    OpAMPClientInterface,
    ABC,
):
    """Abstract OpAMP client base for HTTP/WebSocket-capable implementations.

    This class provides the full `OpAMPClientInterface` behavior and leaves
    environment-specific custom-handler discovery to concrete subclasses.
    """

    def __init__(self, base_url: str, config: ConsumerConfig | None = None) -> None:
        """Create a client bound to a base URL."""
        if config is None:
            config = globals().get("CONFIG")
        if config is None:
            try:
                from opamp_consumer import fluentbit_client as client_module

                config = getattr(client_module, "CONFIG", None)
            except Exception:  # pragma: no cover - defensive import fallback
                config = None
        if config is None:
            config = consumer_config.CONFIG
        if config is None:
            logging.getLogger(__name__).warning("No config supplied to OpAMPClient")
            raise ValueError("OpAMP client requires a consumer config")

        self.data = OpAMPClientData(
            config=config,
            base_url=base_url.rstrip("/"),
        )
        self.data.full_update_controller = self._create_full_update_controller()
        self._custom_handler_folder = self.get_custom_handler_folder()
        self._custom_handler_lookup = build_factory_lookup(
            self._custom_handler_folder,
            client_data=self.data,
            allow_custom_capabilities=bool(self.config.allow_custom_capabilities),
        )

    @abstractmethod
    def get_custom_handler_folder(self) -> pathlib.Path:
        """Return the folder path containing custom handler implementations."""

    def _create_full_update_controller(self) -> FullUpdateControllerInterface:
        """Build a configured full update controller instance for this client."""
        controller_type = str(
            self.config.full_update_controller_type or "SentCount"
        ).strip()
        normalized_type = controller_type.lower()
        if normalized_type == "alwayssend":
            controller = AlwaysSend(
                set_all_reporting_flags=self.data.set_all_reporting_flags,
            )
        elif normalized_type == "timesend":
            controller = TimeSend(
                set_all_reporting_flags=self.data.set_all_reporting_flags,
            )
        else:
            if normalized_type != "sentcount":
                logging.getLogger(__name__).warning(
                    "Unknown full_update_controller_type=%s; defaulting to SentCount",
                    controller_type,
                )
            controller = SentCount(
                set_all_reporting_flags=self.data.set_all_reporting_flags,
            )
        controller.configure(self.config.full_update_controller)
        return controller

    @property
    def config(self) -> ConsumerConfig:
        """Return the active consumer configuration bound to this client instance."""
        return self.data.config

    @config.setter
    def config(self, value: ConsumerConfig) -> None:
        """Replace the active consumer configuration used by this client instance.

        Args:
            value: Consumer configuration object to bind to this client.
        """
        self.data.config = value

    def get_config_parameters(self) -> dict[str, object]:
        """Return active configuration parameters with a documentation reference.

        Returns:
            Config parameter dictionary plus a `documentation_url` entry.
        """
        return _config_parameters_payload(self.config)

    def _get_config_value(self, key: str) -> str:
        """Fetch a config value by key and normalize missing values to an empty string.

        Args:
            key: Configuration attribute name to retrieve from `self.data.config`.

        Returns:
            The string value for the key, or `""` when missing/unset.
        """
        value = getattr(self.data.config, key, None)
        if value is None:
            logging.getLogger(__name__).error(
                "Error handling request for %s",
                key,
            )
            return ""
        return str(value)

    def _populate_agent_to_server_health(
        self, msg: opamp_pb2.AgentToServer
    ) -> opamp_pb2.AgentToServer:
        """Populate health fields on AgentToServer using latest heartbeat poll state.

        Args:
            msg: Outbound AgentToServer message being assembled.

        Returns:
            The same message instance with health fields updated.
        """
        return populate_agent_to_server_health(
            data=self.data,
            msg=msg,
            health_from_metrics=self._health_from_metrics,
            health_key=KEY_HEALTH,
            err_prefix=ERR_PREFIX,
            value_heartbeat_status=VALUE_HEARTBEAT_STATUS,
            value_supervisor_no_state=VALUE_SUPERVISOR_NO_STATE,
        )

    def _health_from_metrics(self, msg, text) -> opamp_pb2.AgentToServer:
        """Parse Fluent Bit metrics text and update component health entries in-place.

        Args:
            msg: AgentToServer message whose health map is updated.
            text: Metrics response text to parse.

        Returns:
            The same message instance with component health updates applied.
        """
        return parse_fluentbit_metrics_health(msg, text)

    def _populate_agent_to_server(
        self, msg: opamp_pb2.AgentToServer
    ) -> opamp_pb2.AgentToServer:
        """Fill outbound AgentToServer payload with description, caps, IDs, and health.

        Args:
            msg: Base AgentToServer message to populate.

        Returns:
            Populated AgentToServer message ready to send.
        """
        return populate_agent_to_server(
            data=self.data,
            msg=msg,
            get_agent_description=self.get_agent_description,
            get_agent_capabilities=self.get_agent_capabilities,
            get_custom_capabilities_payload=self.get_custom_capabilities_payload,
            populate_agent_to_server_health=self._populate_agent_to_server_health,
        )

    def get_agent_description(
        self, instance_uid: bytes | str | None = None
    ) -> opamp_pb2.AgentDescription:
        """Implements `OpAMPClientInterface.get_agent_description`.

        Build AgentDescription for outbound AgentToServer messages.

        Args:
            instance_uid: Optional explicit service instance id override.

        Returns:
            Populated AgentDescription protobuf message.
        """
        logger = logging.getLogger(__name__)
        desc = opamp_pb2.AgentDescription()
        service_name = self.config.service_name
        service_namespace = self.config.service_namespace
        fluentbit_version = self.data.agent_type_name + " - " + self.data.agent_version
        metadata = self.get_host_metadata()

        if service_name:
            desc.identifying_attributes.append(
                anyvalue_pb2.KeyValue(
                    key=KEY_SERVICE_NAME,
                    value=anyvalue_pb2.AnyValue(string_value=service_name),
                )
            )
        else:
            logger.warning("No Service name to provide")

        if service_namespace:
            desc.identifying_attributes.append(
                anyvalue_pb2.KeyValue(
                    key=KEY_SERVICE_NAMESPACE,
                    value=anyvalue_pb2.AnyValue(string_value=service_namespace),
                )
            )
        else:
            logger.warning("No Service Namespace to provide")

        for key, value in metadata.items():
            desc.non_identifying_attributes.append(
                anyvalue_pb2.KeyValue(
                    key=key,
                    value=anyvalue_pb2.AnyValue(string_value=value),
                )
            )

        desc.identifying_attributes.append(
            anyvalue_pb2.KeyValue(
                key=KEY_SERVICE_TYPE,
                value=anyvalue_pb2.AnyValue(string_value="Fluent Bit"),
            )
        )

        service_instance_id = (
            instance_uid
            if instance_uid is not None
            else self.config.service_instance_id
        )
        if isinstance(service_instance_id, str):
            service_instance_id = resolve_service_instance_id_template(
                service_instance_id
            )
        if service_instance_id:
            desc.identifying_attributes.append(
                anyvalue_pb2.KeyValue(
                    key=KEY_SERVICE_INSTANCE_ID,
                    value=anyvalue_pb2.AnyValue(
                        string_value=(
                            service_instance_id.hex()
                            if isinstance(service_instance_id, (bytes, bytearray))
                            else str(service_instance_id)
                        )
                    ),
                )
            )

        if fluentbit_version:
            desc.identifying_attributes.append(
                anyvalue_pb2.KeyValue(
                    key=KEY_SERVICE_VERSION,
                    value=anyvalue_pb2.AnyValue(string_value=fluentbit_version),
                )
            )
        else:
            logger.warning("No Client version to provide")

        logger.debug("Agent description is :%s", desc)

        return desc

    def get_agent_capabilities(self) -> int:
        """Implements `OpAMPClientInterface.get_agent_capabilities`.

        Return the required agent capability bitmask.

        Returns:
            Bitmask built from the hardwired required capability names.
        """
        required_agent_capabilities = (
            "ReportsStatus",
            "AcceptsRestartCommand",
            "ReportsHealth",
        )
        return parse_capabilities(
            required_agent_capabilities,
            AgentCapabilities,
        )

    def get_custom_capabilities_payload(self) -> opamp_pb2.CustomCapabilities:
        """Build CustomCapabilities from the custom handler registry."""
        if not self._custom_handler_lookup:
            self._custom_handler_lookup = build_factory_lookup(
                self._custom_handler_folder,
                client_data=self.data,
                allow_custom_capabilities=bool(self.config.allow_custom_capabilities),
            )
        logging.getLogger(__name__).debug(
            "custom capability lookup entries=%s",
            sorted(self._custom_handler_lookup.keys()),
        )

        capabilities = sorted(
            {
                f"{CAPABILITY_PREFIX_REQUEST}{str(fqdn).strip()}"
                for fqdn in self._custom_handler_lookup.keys()
                if str(fqdn).strip()
            }
        )
        payload = opamp_pb2.CustomCapabilities()
        payload.capabilities.extend(capabilities)
        logging.getLogger(__name__).debug(
            "custom capabilities payload generated=%s",
            capabilities,
        )
        return payload

    def get_host_metadata(self) -> dict[str, str]:
        """Collect basic host metadata as key/value pairs."""
        return {
            HOST_META_KEY_OS_TYPE: platform.system(),
            HOST_META_KEY_OS_VERSION: platform.version(),
            HOST_META_KEY_HOSTNAME: socket.gethostname(),
            HOST_META_KEY_MAC_ADDRESS: _get_local_mac(),
        }

def resolve_service_instance_id_template(value: str | None) -> str | None:
    """Resolve service_instance_id template tokens into runtime host values."""
    return resolve_service_instance_id_template_with_values(
        value=value,
        hostname=socket.gethostname(),
        ip_address=_get_local_ip(),
        mac_address=_get_local_mac(),
    )
