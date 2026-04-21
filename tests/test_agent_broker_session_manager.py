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

import asyncio
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_BROKER_ROOT = REPO_ROOT / "agent_broker"
if str(AGENT_BROKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_BROKER_ROOT))

session_manager_module = importlib.import_module("opamp_broker.session.manager")


def test_session_manager_defaults_ai_enabled_to_true() -> None:
    manager = session_manager_module.SessionManager()
    session = asyncio.run(
        manager.upsert(
            team_id="T123",
            channel_id="C123",
            thread_ts="111.1",
            user_id="U123",
        )
    )

    assert session.ai_enabled is True


def test_session_manager_applies_ai_mode_per_client_across_threads() -> None:
    manager = session_manager_module.SessionManager()

    first_session = asyncio.run(
        manager.upsert(
            team_id="T123",
            channel_id="C123",
            thread_ts="111.1",
            user_id="U123",
        )
    )
    assert first_session.ai_enabled is True

    updated_session = asyncio.run(
        manager.update(first_session.key, ai_enabled=False)
    )
    assert updated_session is not None
    assert updated_session.ai_enabled is False

    second_session_same_client = asyncio.run(
        manager.upsert(
            team_id="T123",
            channel_id="C456",
            thread_ts="222.2",
            user_id="U123",
        )
    )
    assert second_session_same_client.ai_enabled is False

    third_session_different_client = asyncio.run(
        manager.upsert(
            team_id="T123",
            channel_id="C789",
            thread_ts="333.3",
            user_id="U999",
        )
    )
    assert third_session_different_client.ai_enabled is True
