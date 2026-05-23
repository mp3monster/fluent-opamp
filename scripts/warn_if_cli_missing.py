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

"""Print a warning when the OpAMP CLI is not available in the workspace/runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Warn when the OpAMP CLI is missing during packaging or deployment.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Repository root used to probe for the CLI component.",
    )
    parser.add_argument(
        "--component-label",
        required=True,
        help="Human-readable label for the component being built or deployed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    if str(SCRIPT_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPT_REPO_ROOT))

    from shared.packaging_warnings import warn_if_cli_missing

    warn_if_cli_missing(
        component_label=args.component_label,
        repo_root=repo_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
