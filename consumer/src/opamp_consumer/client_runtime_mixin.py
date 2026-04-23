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

"""Client runtime lifecycle mixin extracted from the legacy client_mixins module."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING

import httpx

from opamp_consumer.exceptions import AgentException
from opamp_consumer.proto import opamp_pb2
from opamp_consumer.reporting_flag import ReportingFlag

if TYPE_CHECKING:
    from opamp_consumer.abstract_client import OpAMPClientData
    from opamp_consumer.config import ConsumerConfig


class ClientRuntimeMixin:
    """Agent process lifecycle and heartbeat polling behavior."""

    data: OpAMPClientData
    config: ConsumerConfig

    async def send(self) -> opamp_pb2.ServerToAgent | None:
        """Send AgentToServer payloads and return the provider response."""
        raise NotImplementedError

    _runtime_agent_command = "agent"
    _runtime_config_flag = "-c"
    _heartbeat_paths = ("/health",)
    _localhost_base = "http://localhost"
    _http_timeout_seconds = 5.0
    _error_prefix = "error: "
    _error_status = "error"
    _heartbeat_skew_seconds = 1
    _semaphore_filename = "OpAMPSupervisor.signal"
    _finalize_started = False
    _key_agent_version = "version"
    _key_agent_edition = "edition"
    _json_key_agent = "agent"
    _json_key_agent_fallback: str | None = None
    _json_key_version = "version"
    _json_key_edition = "edition"
    _value_agent_type = "Agent"

    def _resolve_launch_command(self, raw_command: list[str]) -> list[str]:
        """Resolve the runtime executable from PATH and normalize Windows wrappers."""
        executable = str(raw_command[0] if raw_command else "").strip()
        if not executable:
            raise FileNotFoundError("agent runtime command is empty")

        resolved_executable = shutil.which(executable)
        if not resolved_executable:
            raise FileNotFoundError(executable)

        command = [resolved_executable, *raw_command[1:]]
        if os.name == "nt" and resolved_executable.lower().endswith((".bat", ".cmd")):
            return ["cmd", "/c", resolved_executable, *raw_command[1:]]
        return command

    def launch_agent_process(self) -> bool:
        """Launch the configured agent process using runtime command metadata."""
        logger = logging.getLogger(__name__)
        raw_command = [
            self._runtime_agent_command,
            *(self.config.agent_additional_params or []),
            self._runtime_config_flag,
            self.config.agent_config_path,
        ]
        logger.debug(
            "About to start agent process with config %s and command %s",
            self.config.agent_config_path,
            raw_command,
        )
        try:
            command = self._resolve_launch_command(raw_command)
            logger.debug("Resolved runtime command: %s", command)
            with self.data.process_lock:
                process_response: subprocess.Popen[bytes] = subprocess.Popen(command)
                self.data.agent_process = process_response
                self.data.launched_at = time.time_ns()
        except FileNotFoundError as file_error:
            logger.error(
                "Agent launch failed because command was not found (%s): %s",
                self._runtime_agent_command,
                file_error,
            )
            return False
        except Exception as launch_error:  # pragma: no cover - env-dependent
            logger.exception("Agent launch failed for command %s", command)
            logger.debug("Agent launch exception detail: %s", launch_error)
            return False
        logger.info("Launch result = %s", process_response)
        return True

    def terminate_agent_process(self) -> None:
        """Terminate the launched Agent process if available."""
        logger = logging.getLogger(__name__)
        with self.data.process_lock:
            process = self.data.agent_process
            self.data.allow_heartbeat = False
            if process is None:
                return
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Agent did not terminate in time; killing process")
                print("Agent did not terminate in time; killing process")
                process.kill()
                process.wait(timeout=5)
            self.data.agent_process = None

    def restart_agent_process(self) -> bool:
        """Stop the current agent process and start a new instance."""
        logger = logging.getLogger(__name__)
        logger.info("Restarting agent process")
        lock_acquired = self.data.process_lock.acquire(timeout=30)
        if not lock_acquired:
            raise AgentException(
                "Timed out waiting for process lock while restarting agent process"
            )
        try:
            self.terminate_agent_process()
            relaunched = self.launch_agent_process()
        finally:
            self.data.process_lock.release()
        if not relaunched:
            raise AgentException("Failed to restart agent process")
        logger.info("Agent process restarted")
        return relaunched

    def _populate_disconnect(
        self, msg: opamp_pb2.AgentToServer
    ) -> opamp_pb2.AgentToServer:
        """Populate disconnect data and ensure instance UID is set."""
        if self.data.uid_instance is not None:
            msg.instance_uid = self.data.uid_instance
            logging.getLogger(__name__).warning(
                "Set disconnect message instance UID to %s", self.data.uid_instance
            )
        msg.agent_disconnect.SetInParent()
        return msg

    async def send_disconnect(self) -> None:
        """Implements `OpAMPClientInterface.send_disconnect` with best-effort send."""
        msg = self._populate_disconnect(opamp_pb2.AgentToServer())
        logging.getLogger(__name__).debug("Built disconnect message")

        try:
            await self.send(msg, send_as_is=True)
            self.data.allow_heartbeat = False
        except Exception as err:  # pragma: no cover - error path varies by env
            logging.getLogger(__name__).warning(
                "Failed to send disconnect message - %s", err
            )

    async def _send_disconnect_with_timeout(self, timeout_seconds: float = 1.0) -> None:
        """Best-effort disconnect send with a short timeout."""
        try:
            logging.getLogger(__name__).warning("_send_disconnect_with_timeout exiting")
            await asyncio.wait_for(self.send_disconnect(), timeout=timeout_seconds)
        except Exception as err:  # pragma: no cover - error path varies by env
            logging.getLogger(__name__).error("Disconnect send timed out-- %s", err)

        logging.getLogger(__name__).warning("_send_disconnect_with_timeout exiting")

    def finalize(self) -> None:
        """Implements `OpAMPClientInterface.finalize` with async-loop fallback."""
        if self._finalize_started:
            return
        self._finalize_started = True
        if getattr(self, "data", None) is not None:
            self.data.allow_heartbeat = False
        try:
            loop = asyncio.get_running_loop()
            logging.getLogger(__name__).debug("finalize - got loop")
        except RuntimeError:

            def _runner() -> None:
                """Run best-effort async disconnect send inside a dedicated thread."""
                try:
                    logging.getLogger(__name__).debug(
                        "About to send disconnect message"
                    )
                    asyncio.run(self._send_disconnect_with_timeout())
                except Exception as err:
                    logging.getLogger(__name__).error(
                        "Failed to send disconnect message, error is:\n %s", err
                    )
                    return

            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
        else:
            if loop.is_closed():
                return
            loop.create_task(self._send_disconnect_with_timeout())

    def __del__(self) -> None:
        """Attempt graceful disconnect/finalize during object destruction."""
        try:
            if getattr(self, "data", None) is not None:
                self.data.allow_heartbeat = False
            if sys.is_finalizing():
                return
            self.finalize()
        except Exception:
            return

    def _heartbeat_key(self, path: str) -> str:
        """Return the last URL path component as the dictionary key."""
        return path.rstrip("/").split("/")[-1]

    def poll_local_status_with_codes(
        self, port: int
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Poll local health endpoints and collect response bodies and status codes.

        Args:
            port: Local agent HTTP status port to query.

        Returns:
            Tuple of `(results, codes)` maps keyed by heartbeat endpoint name.
        """
        results: dict[str, str] = {}
        codes: dict[str, str] = {}
        for path in self._heartbeat_paths:
            url = f"{self._localhost_base}:{port}{path}"
            key = self._heartbeat_key(path)
            try:
                response = httpx.get(url, timeout=self._http_timeout_seconds)
                results[key] = response.text
                codes[key] = str(response.status_code)
                response.raise_for_status()
                if (response.status_code < 200) or (response.status_code > 299):
                    self.data.reporting_flags[ReportingFlag.REPORT_HEALTH] = True
                    results[key] = f"{path}={response.status_code}"
                    logging.getLogger(__name__).warning(
                        "Err checking status using %s got code %s",
                        path,
                        response.status_code,
                    )
            except Exception as error:  # pragma: no cover - error path varies by env
                results[key] = f"{self._error_prefix}{error}"
                codes[key] = self._error_status
                self.data.reporting_flags[ReportingFlag.REPORT_HEALTH] = True
                logging.getLogger(__name__).warning(
                    "Err checking status using %s got error %s", path, error
                )
        return results, codes

    def add_agent_version(self, port: int) -> None:
        """Fetch Fluent Bit version endpoint and store in client runtime metadata.

        Args:
            port: Local agent HTTP status port used for version endpoint calls.
        """
        url = f"{self._localhost_base}:{port}"
        try:
            response = httpx.get(url, timeout=self._http_timeout_seconds)
            response.raise_for_status()
            value = response.text
            try:
                data = response.json()
                version = None
                edition = None
                if isinstance(data, dict):
                    version = data.get(self._key_agent_version)
                    edition = data.get(self._key_agent_edition)
                    agent_payload = data.get(self._json_key_agent)
                    if (
                        agent_payload is None
                        and self._json_key_agent_fallback is not None
                    ):
                        agent_payload = data.get(self._json_key_agent_fallback)
                    if isinstance(agent_payload, dict):
                        self.data.agent_type_name = self._value_agent_type
                        version = version or agent_payload.get(
                            self._json_key_version
                        )
                        edition = edition or agent_payload.get(
                            self._json_key_edition
                        )
                if version or edition:
                    if version and edition:
                        value = f"{version} ({edition})"
                    else:
                        value = version or edition
                self.data.agent_version = value
            except ValueError as parse_error:
                logging.getLogger(__name__).warning(
                    "failed to parse Agent version response: %s", parse_error
                )
        except Exception as error:  # pragma: no cover # pylint: disable=broad-exception-caught
            logging.getLogger(__name__).warning(
                "failed to parse Agent version response: %s", error
            )

    def check_semaphore(self) -> bool:
        """Return True when the supervisor semaphore file exists on local disk."""
        if os.path.isfile(self._semaphore_filename):
            logging.getLogger(__name__).warning("Spotted Semaphore file")
            return True
        return False

    async def _heartbeat_loop(self, port: int) -> None:
        """Run a periodic polling loop that updates last heartbeat results.

        Args:
            port: Local agent HTTP status port used for heartbeat polling.
        """
        logger = logging.getLogger(__name__)
        interval = max(
            0, int(self.config.heartbeat_frequency) - self._heartbeat_skew_seconds
        )
        logger.debug("Heartbeat cycle start - checking every %s", interval)
        while self.data.allow_heartbeat:
            try:
                await asyncio.sleep(interval)
                if self.check_semaphore():
                    await self._send_disconnect_with_timeout()
                    self.data.allow_heartbeat = False
                    continue
                try:
                    with self.data.process_lock:
                        results, codes = self.poll_local_status_with_codes(port)
                        self.data.last_heartbeat_results.clear()
                        self.data.last_heartbeat_results.update(results)
                        self.add_agent_version(port)
                        self.data.last_heartbeat_http_codes = codes
                    if self.config.log_agent_api_responses and self.data.logFLB:
                        logger.debug("Heartbeat outcome --> %s", results)

                    logger.info("Heartbeat response codes: %s", codes)

                except KeyboardInterrupt as keyboard_interrupt:
                    logger.error(
                        "Error - a disturbance in the force\n %s", keyboard_interrupt
                    )
                    self.data.allow_heartbeat = False
                    await self._send_disconnect_with_timeout()
                    break
                except Exception as error:  # pylint: disable=broad-exception-caught
                    logger.error(
                        "Something stumbled - we catch and carry on\n %s", error
                    )
                    self.data.last_heartbeat_results = {}
                    self.data.last_heartbeat_http_codes = {}

                self._handle_server_to_agent(await self.send())
            except asyncio.CancelledError:
                await self._send_disconnect_with_timeout()
                logger.info("Heartbeat loop cancelled; disconnect signal sent")
                raise
            except (KeyboardInterrupt, SystemExit):
                await self._send_disconnect_with_timeout()
                logger.error("Heartbeat loop interrupted by shutdown signal")
                raise
            except Exception as loop_error:  # pylint: disable=broad-exception-caught
                await self._send_disconnect_with_timeout()
                logger.exception(
                    "Heartbeat loop recovered from unexpected cycle error: %s",
                    loop_error,
                )
                self.data.last_heartbeat_results = {}
                self.data.last_heartbeat_http_codes = {}
