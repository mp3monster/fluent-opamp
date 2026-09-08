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

"""Consumer plugin action builders for the OpAMP CLI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from .common import _slugify
    from .constants import (
        ACTION_ID_FLUENTBIT_CLIENT,
        ACTION_ID_FLUENTD_CLIENT,
        ARG_AGENT_CONFIG_PATH,
        ARG_CONFIG_PATH,
        ACTION_KEY_LOG_NAME,
        ACTION_KEY_METADATA,
        ACTION_KEY_RECORD_NAME,
        LABEL_FLUENTBIT_CLIENT,
        LABEL_FLUENTD_CLIENT,
        OPAMP_CONFIG_PATH_ENV,
    )
except ImportError:
    from common import _slugify  # type: ignore[no-redef]
    from constants import (  # type: ignore[no-redef]
        ACTION_ID_FLUENTBIT_CLIENT,
        ACTION_ID_FLUENTD_CLIENT,
        ARG_AGENT_CONFIG_PATH,
        ARG_CONFIG_PATH,
        ACTION_KEY_LOG_NAME,
        ACTION_KEY_METADATA,
        ACTION_KEY_RECORD_NAME,
        LABEL_FLUENTBIT_CLIENT,
        LABEL_FLUENTD_CLIENT,
        OPAMP_CONFIG_PATH_ENV,
    )

LABEL_ELASTIC_AGENT_CLIENT = "Elastic Agent client"
LABEL_ELASTIC_HEARTBEAT_CLIENT = "Elastic Heartbeat client"
CONSUMER_PYTHON_PATH = Path("consumer/src")
DEFAULT_OPAMP_CONFIG_PATH = Path("config/opamp.json")
MODULE_CONSUMER_GENERIC_CLIENT = "opamp_consumer.client"
MODULE_FLUENTBIT_CLIENT = "opamp_consumer.fluentbit.client"
MODULE_FLUENTD_CLIENT = "opamp_consumer.fluentd.client"


def default_fluentbit_start_action(
    *,
    repo_root: Path,
    existing_path: Callable[..., Path | None],
    python_module_command: Callable[..., str],
    python_module_argv: Callable[..., list[str]],
    background_start_action: Callable[..., dict[str, Any]],
    build_exec_env: Callable[..., dict[str, str]],
) -> dict[str, Any]:
    """Build the default Fluent Bit client start action."""
    opamp_config = (repo_root / DEFAULT_OPAMP_CONFIG_PATH).resolve()
    fluentbit_config = existing_path(
        repo_root / "tests" / "opamp.json",
        opamp_config,
    )
    fluentbit_agent_config = existing_path(
        repo_root / "tests" / "fluent-bit.yaml",
        repo_root / "consumer" / "fluent-bit.yaml",
    )
    fluentbit_args = [
        ARG_CONFIG_PATH,
        str(fluentbit_config) if fluentbit_config else str(opamp_config),
        ARG_AGENT_CONFIG_PATH,
        str(fluentbit_agent_config)
        if fluentbit_agent_config
        else str((repo_root / "consumer" / "fluent-bit.yaml").resolve()),
    ]
    fluentbit_env = {OPAMP_CONFIG_PATH_ENV: str(fluentbit_config or opamp_config)}
    return background_start_action(
        action_id=ACTION_ID_FLUENTBIT_CLIENT,
        label=LABEL_FLUENTBIT_CLIENT,
        command_text=python_module_command(
            module_name=MODULE_FLUENTBIT_CLIENT,
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            args=fluentbit_args,
            env=fluentbit_env,
            cwd=repo_root,
        ),
        argv=python_module_argv(module_name=MODULE_FLUENTBIT_CLIENT, args=fluentbit_args),
        cwd=repo_root,
        env=build_exec_env(
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            env=fluentbit_env,
        ),
        clear_supervisor_signal=True,
    )


def default_fluentd_start_action(
    *,
    repo_root: Path,
    existing_path: Callable[..., Path | None],
    python_module_command: Callable[..., str],
    python_module_argv: Callable[..., list[str]],
    background_start_action: Callable[..., dict[str, Any]],
    build_exec_env: Callable[..., dict[str, str]],
) -> dict[str, Any]:
    """Build the default Fluentd client start action."""
    opamp_config = (repo_root / DEFAULT_OPAMP_CONFIG_PATH).resolve()
    fluentd_config = existing_path(
        repo_root / "consumer" / "opamp-fluentd.json",
        repo_root / "tests" / "opamp.json",
        opamp_config,
    )
    fluentd_args = [
        ARG_CONFIG_PATH,
        str(fluentd_config) if fluentd_config else str(opamp_config),
        ARG_AGENT_CONFIG_PATH,
        str((repo_root / "consumer" / "fluentd.conf").resolve()),
    ]
    fluentd_env = {OPAMP_CONFIG_PATH_ENV: str(fluentd_config or opamp_config)}
    return background_start_action(
        action_id=ACTION_ID_FLUENTD_CLIENT,
        label=LABEL_FLUENTD_CLIENT,
        command_text=python_module_command(
            module_name=MODULE_FLUENTD_CLIENT,
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            args=fluentd_args,
            env=fluentd_env,
            cwd=repo_root,
        ),
        argv=python_module_argv(module_name=MODULE_FLUENTD_CLIENT, args=fluentd_args),
        cwd=repo_root,
        env=build_exec_env(
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            env=fluentd_env,
        ),
        clear_supervisor_signal=True,
    )


def demo_fluentbit_start_action(
    *,
    repo_root: Path,
    profile_name: str,
    prefix: str,
    config_path: Path,
    agent_config_path: Path,
    common_metadata: dict[str, Any],
    python_module_command: Callable[..., str],
    python_module_argv: Callable[..., list[str]],
    background_start_action: Callable[..., dict[str, Any]],
    build_exec_env: Callable[..., dict[str, str]],
) -> dict[str, Any]:
    """Build a demo-profile Fluent Bit client start action."""
    args = [ARG_CONFIG_PATH, str(config_path), ARG_AGENT_CONFIG_PATH, str(agent_config_path)]
    action = background_start_action(
        action_id=f"demo_fluentbit_{_slugify(profile_name)}",
        label=f"{LABEL_FLUENTBIT_CLIENT} ({profile_name})",
        command_text=python_module_command(
            module_name=MODULE_FLUENTBIT_CLIENT,
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            args=args,
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
            cwd=repo_root,
        ),
        argv=python_module_argv(module_name=MODULE_FLUENTBIT_CLIENT, args=args),
        cwd=repo_root,
        env=build_exec_env(
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
        ),
        clear_supervisor_signal=True,
    )
    action[ACTION_KEY_RECORD_NAME] = f"{prefix}:{LABEL_FLUENTBIT_CLIENT}"
    action[ACTION_KEY_METADATA] = dict(common_metadata)
    action[ACTION_KEY_LOG_NAME] = f"demo-{_slugify(profile_name)}-fluentbit-client"
    return action


def demo_fluentd_start_action(
    *,
    repo_root: Path,
    profile_name: str,
    prefix: str,
    config_path: Path,
    agent_config_path: Path,
    common_metadata: dict[str, Any],
    python_module_command: Callable[..., str],
    python_module_argv: Callable[..., list[str]],
    background_start_action: Callable[..., dict[str, Any]],
    build_exec_env: Callable[..., dict[str, str]],
) -> dict[str, Any]:
    """Build a demo-profile Fluentd client start action."""
    args = [ARG_CONFIG_PATH, str(config_path), ARG_AGENT_CONFIG_PATH, str(agent_config_path)]
    action = background_start_action(
        action_id=f"demo_fluentd_{_slugify(profile_name)}",
        label=f"{LABEL_FLUENTD_CLIENT} ({profile_name})",
        command_text=python_module_command(
            module_name=MODULE_FLUENTD_CLIENT,
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            args=args,
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
            cwd=repo_root,
        ),
        argv=python_module_argv(module_name=MODULE_FLUENTD_CLIENT, args=args),
        cwd=repo_root,
        env=build_exec_env(
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
        ),
        clear_supervisor_signal=True,
    )
    action[ACTION_KEY_RECORD_NAME] = f"{prefix}:{LABEL_FLUENTD_CLIENT}"
    action[ACTION_KEY_METADATA] = dict(common_metadata)
    action[ACTION_KEY_LOG_NAME] = f"demo-{_slugify(profile_name)}-fluentd-client"
    return action


def demo_elastic_agent_start_action(
    *,
    repo_root: Path,
    profile_name: str,
    prefix: str,
    config_path: Path,
    agent_config_path: Path | None,
    common_metadata: dict[str, Any],
    python_module_command: Callable[..., str],
    python_module_argv: Callable[..., list[str]],
    background_start_action: Callable[..., dict[str, Any]],
    build_exec_env: Callable[..., dict[str, str]],
) -> dict[str, Any]:
    """Build a demo-profile Elastic Agent client start action."""
    args = [ARG_CONFIG_PATH, str(config_path)]
    if agent_config_path is not None:
        args.extend([ARG_AGENT_CONFIG_PATH, str(agent_config_path)])
    action = background_start_action(
        action_id=f"demo_elastic_agent_{_slugify(profile_name)}",
        label=f"{LABEL_ELASTIC_AGENT_CLIENT} ({profile_name})",
        command_text=python_module_command(
            module_name=MODULE_CONSUMER_GENERIC_CLIENT,
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            args=args,
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
            cwd=repo_root,
        ),
        argv=python_module_argv(module_name=MODULE_CONSUMER_GENERIC_CLIENT, args=args),
        cwd=repo_root,
        env=build_exec_env(
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
        ),
        clear_supervisor_signal=True,
    )
    action[ACTION_KEY_RECORD_NAME] = f"{prefix}:{LABEL_ELASTIC_AGENT_CLIENT}"
    action[ACTION_KEY_METADATA] = dict(common_metadata)
    action[ACTION_KEY_LOG_NAME] = f"demo-{_slugify(profile_name)}-elastic-agent-client"
    return action


def demo_elastic_heartbeat_start_action(
    *,
    repo_root: Path,
    profile_name: str,
    prefix: str,
    config_path: Path,
    agent_config_path: Path,
    common_metadata: dict[str, Any],
    python_module_command: Callable[..., str],
    python_module_argv: Callable[..., list[str]],
    background_start_action: Callable[..., dict[str, Any]],
    build_exec_env: Callable[..., dict[str, str]],
) -> dict[str, Any]:
    """Build a demo-profile Elastic Heartbeat client start action."""
    args = [ARG_CONFIG_PATH, str(config_path), ARG_AGENT_CONFIG_PATH, str(agent_config_path)]
    action = background_start_action(
        action_id=f"demo_elastic_heartbeat_{_slugify(profile_name)}",
        label=f"{LABEL_ELASTIC_HEARTBEAT_CLIENT} ({profile_name})",
        command_text=python_module_command(
            module_name=MODULE_CONSUMER_GENERIC_CLIENT,
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            args=args,
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
            cwd=repo_root,
        ),
        argv=python_module_argv(module_name=MODULE_CONSUMER_GENERIC_CLIENT, args=args),
        cwd=repo_root,
        env=build_exec_env(
            python_paths=[repo_root / CONSUMER_PYTHON_PATH],
            env={OPAMP_CONFIG_PATH_ENV: str(config_path)},
        ),
        clear_supervisor_signal=True,
    )
    action[ACTION_KEY_RECORD_NAME] = f"{prefix}:{LABEL_ELASTIC_HEARTBEAT_CLIENT}"
    action[ACTION_KEY_METADATA] = dict(common_metadata)
    action[ACTION_KEY_LOG_NAME] = f"demo-{_slugify(profile_name)}-elastic-heartbeat-client"
    return action
