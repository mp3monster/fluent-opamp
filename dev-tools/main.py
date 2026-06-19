#!/usr/bin/env python3
"""Compatibility wrapper for running the developer CLI from component root."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _src_path() -> Path:
    return (Path(__file__).resolve().parent / "src").resolve()


def main(argv: list[str] | None = None) -> int:
    src_path = _src_path()
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    cli_main = importlib.import_module("opamp_dev_tools.cli").main
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

