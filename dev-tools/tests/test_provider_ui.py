from __future__ import annotations

from pathlib import Path

import opamp_dev_tools.provider_ui as provider_ui


class _RuntimeStub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.commands: list[list[str]] = []
        self.messages: list[str] = []

    def run(self, command: list[str], *, cwd: Path | None = None, **_: object) -> None:
        del cwd
        self.commands.append(command)
        outfile_flag = next((part for part in command if part.startswith("--outfile=")), "")
        if outfile_flag:
            outfile = Path(outfile_flag.partition("=")[2])
            outfile.parent.mkdir(parents=True, exist_ok=True)
            outfile.write_text("minified();\n", encoding="utf-8")

    def info(self, message: str) -> None:
        self.messages.append(message)


def test_compact_provider_ui_assets_builds_mini_files(tmp_path: Path, monkeypatch) -> None:
    _write_provider_ui_assets_module(
        tmp_path,
        filenames=("web_ui_state.js", "web_ui_bindings.js"),
    )
    html_dir = tmp_path / "provider" / "src" / "opamp_provider" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    (html_dir / "web_ui_state.js").write_text("const state = 1;\n", encoding="utf-8")
    (html_dir / "web_ui_bindings.js").write_text("const bindings = 2;\n", encoding="utf-8")
    monkeypatch.setattr(provider_ui.shutil, "which", lambda tool: "/usr/bin/npx" if tool == "npx" else None)
    runtime = _RuntimeStub(tmp_path)

    issues_found = provider_ui.compact_provider_ui_assets(runtime)

    assert issues_found is False
    assert len(runtime.commands) == 2
    assert runtime.commands[0][0:3] == ["npx", "--yes", "esbuild"]
    assert (html_dir / "web_ui_state.mini.js").read_text(encoding="utf-8") == "minified();\n"
    assert (html_dir / "web_ui_bindings.mini.js").read_text(encoding="utf-8") == "minified();\n"
    assert runtime.messages[-1] == "Provider UI compaction complete."


def test_compact_provider_ui_assets_clean_only_removes_existing_minified_files(
    tmp_path: Path,
) -> None:
    _write_provider_ui_assets_module(
        tmp_path,
        filenames=("web_ui_state.js",),
    )
    html_dir = tmp_path / "provider" / "src" / "opamp_provider" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    (html_dir / "web_ui_state.mini.js").write_text("old-minified();\n", encoding="utf-8")
    runtime = _RuntimeStub(tmp_path)

    issues_found = provider_ui.compact_provider_ui_assets(runtime, clean_only=True)

    assert issues_found is False
    assert runtime.commands == []
    assert not (html_dir / "web_ui_state.mini.js").exists()
    assert runtime.messages[-1] == "Provider UI clean-only complete."


def _write_provider_ui_assets_module(repo_root: Path, *, filenames: tuple[str, ...]) -> None:
    module_path = repo_root / "provider" / "src" / "opamp_provider" / "ui_assets.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    filenames_repr = ", ".join(repr(name) for name in filenames)
    module_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                f"PROVIDER_UI_JS_FILENAMES = ({filenames_repr},)",
                "",
            ]
        ),
        encoding="utf-8",
    )
