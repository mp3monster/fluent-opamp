# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helpers for mirroring config-service JSON artifacts into packaged copies."""

from __future__ import annotations

import shutil
from pathlib import Path

from .runtime import CommandRuntime


def sync_config_service_json_assets(runtime: CommandRuntime) -> bool:
    """Mirror config-service JSON definitions and schemas from source into packaged copies."""
    config_service_root = runtime.repo_root / "config-service"
    sync_pairs = (
        (
            config_service_root / "src" / "config_service" / "json-definitions",
            config_service_root / "json-definitions",
        ),
        (
            config_service_root / "src" / "config_service" / "json-schemas",
            config_service_root / "json-schemas",
        ),
    )
    for source_dir, target_dir in sync_pairs:
        _mirror_directory(source_dir, target_dir)
        runtime.info(f"Synchronized {source_dir} -> {target_dir}")
    return False


def _mirror_directory(source_dir: Path, target_dir: Path) -> None:
    """Replace the target tree with an exact copy of the source tree."""
    if not source_dir.exists():
        raise RuntimeError(f"expected source directory at {source_dir}")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)
