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

from types import SimpleNamespace

import opamp_consumer.client_mixins as client_mixins


class _FakeFinalizerTarget:
    """Lightweight object exposing fields/methods used by ClientRuntimeMixin.__del__."""

    def __init__(self) -> None:
        self.data = SimpleNamespace(allow_heartbeat=True)
        self.finalize_calls = 0

    def finalize(self) -> None:
        self.finalize_calls += 1


def test_del_skips_finalize_while_interpreter_finalizing(monkeypatch) -> None:
    """`__del__` should not attempt finalize while interpreter teardown is active."""
    target = _FakeFinalizerTarget()
    monkeypatch.setattr(client_mixins.sys, "is_finalizing", lambda: True)

    client_mixins.ClientRuntimeMixin.__del__(target)

    assert target.data.allow_heartbeat is False
    assert target.finalize_calls == 0


def test_del_calls_finalize_when_not_finalizing(monkeypatch) -> None:
    """`__del__` should still call finalize during normal object destruction."""
    target = _FakeFinalizerTarget()
    monkeypatch.setattr(client_mixins.sys, "is_finalizing", lambda: False)

    client_mixins.ClientRuntimeMixin.__del__(target)

    assert target.data.allow_heartbeat is False
    assert target.finalize_calls == 1
