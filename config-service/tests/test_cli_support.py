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

"""Unit tests for config-service CLI support helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config_service.cli_support import CliConfigSupport


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_cli_metadata_injection_preserves_existing_header_comment_block(
    tmp_path: Path,
) -> None:
    support = CliConfigSupport(repo_root=_repo_root())
    config_path = tmp_path / "sample.yaml"
    config_path.write_text(
        (
            "# owned by platform team\n"
            "# change-ticket: OPS-123\n"
            "\n"
            "service:\n"
            "  flush: 1\n"
            "pipeline:\n"
            "  inputs:\n"
            "    - name: dummy\n"
            "      tag: test\n"
            "  outputs:\n"
            "    - name: stdout\n"
            "      match: \"*\"\n"
        ),
        encoding="utf-8",
    )

    report = support.ensure_metadata_path(config_path)
    updated_text = config_path.read_text(encoding="utf-8")

    assert len(report.reports) == 1
    assert "Metadata status: applied missing metadata fields config_type, version" in report.render()
    assert updated_text.startswith(
        "# config-service: config_type=fluentbit\n"
        "# config-service: version=5.0.4\n"
        "# owned by platform team\n"
        "# change-ticket: OPS-123\n"
        "service:\n"
    )
