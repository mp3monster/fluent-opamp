#!/usr/bin/env python3
"""Build compacted provider web UI JavaScript assets.

This script minifies the provider UI JavaScript files and writes deterministic
`.mini.js` outputs next to source files.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
from pathlib import Path

UTF8 = "utf-8"


def _run(cmd: list[str], *, cwd: Path) -> None:
    """Run one subprocess command and stream output."""
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _require_npx() -> None:
    """Require `npx` to be available for esbuild execution."""
    if shutil.which("npx"):
        return
    raise RuntimeError(
        "npx was not found on PATH. Install Node.js (which includes npm/npx) "
        "before running UI compaction."
    )


def _mini_filename(source_filename: str) -> str:
    """Return deterministic compacted filename for one source JS filename."""
    return source_filename.replace(".js", ".mini.js")


def _provider_ui_js_filenames(repo_root: Path) -> tuple[str, ...]:
    """Load the canonical provider UI asset list from provider source."""
    module_path = repo_root / "provider" / "src" / "opamp_provider" / "ui_assets.py"
    if not module_path.exists():
        raise RuntimeError(f"provider UI asset definitions not found: {module_path}")

    spec = importlib.util.spec_from_file_location("opamp_provider.ui_assets", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load provider UI asset definitions: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    filenames = getattr(module, "PROVIDER_UI_JS_FILENAMES", None)
    if not isinstance(filenames, tuple) or not all(
        isinstance(item, str) and item.endswith(".js") for item in filenames
    ):
        raise RuntimeError(
            "provider UI asset definitions must expose PROVIDER_UI_JS_FILENAMES "
            "as a tuple[str, ...] of .js filenames"
        )
    return filenames


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Minify provider web UI JS assets into `.mini.js` files using esbuild."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        help="Repository root path (default: parent of scripts folder).",
    )
    parser.add_argument(
        "--html-dir",
        default="provider/src/opamp_provider/html",
        help=(
            "HTML asset directory path relative to repo root "
            "(default: provider/src/opamp_provider/html)."
        ),
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Remove existing `.mini.js` files and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    html_dir = (repo_root / args.html_dir).resolve()
    js_filenames = _provider_ui_js_filenames(repo_root)
    if not html_dir.exists():
        raise RuntimeError(f"HTML directory not found: {html_dir}")

    for source_name in js_filenames:
        mini_path = html_dir / _mini_filename(source_name)
        if mini_path.exists():
            mini_path.unlink()
            print(f"removed {mini_path}")

    if args.clean_only:
        print("clean-only complete")
        return 0

    _require_npx()

    for source_name in js_filenames:
        source_path = html_dir / source_name
        if not source_path.exists():
            raise RuntimeError(f"source UI JS file not found: {source_path}")
        mini_path = html_dir / _mini_filename(source_name)
        _run(
            [
                "npx",
                "--yes",
                "esbuild",
                str(source_path),
                "--minify",
                "--legal-comments=none",
                f"--outfile={mini_path}",
            ],
            cwd=repo_root,
        )
        source_bytes = source_path.stat().st_size
        mini_bytes = mini_path.stat().st_size
        print(
            f"built {mini_path.name} ({mini_bytes} bytes) from "
            f"{source_name} ({source_bytes} bytes)"
        )

    print("provider UI compaction complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
