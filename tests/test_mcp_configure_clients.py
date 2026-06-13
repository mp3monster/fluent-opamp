"""Unit tests for the Python MCP client configuration utility."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "mcp" / "configure_mcp_clients.py"
    spec = importlib.util.spec_from_file_location("configure_mcp_clients", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _base_settings(tmp_path: Path) -> dict:
    return {
        "server": {
            "host": "localhost",
            "port": 8080,
            "scheme": "http",
            "sse_path": "/sse",
        },
        "deployment": {
            "mode": "source",
            "source_server_spec": "provider/src/opamp_provider/mcptool/routes.py:mcpserver",
            "package_server_spec": "opamp_provider.mcptool.routes:mcpserver",
            "project": "provider",
            "with_fastmcp": True,
            "with_editable": True,
            "include_repo_editable": True,
            "pythonpath_paths": ["provider/src", "shared"],
            "package_specs": ["opamp-server"],
        },
        "clients": {
            "claude": {"enabled": False, "name": "OpAMP Server", "transport": "sse"},
            "codex": {"enabled": False, "name": "opamp-server", "transport": "stdio"},
            "vscode": {
                "enabled": False,
                "name": "opampServer",
                "config_path": str(tmp_path / "mcp.json"),
                "transport": "stdio",
            },
            "librechat": {
                "enabled": False,
                "name": "opampServer",
                "config_path": str(tmp_path / "librechat.yaml"),
                "transport": "stdio",
            },
            "gemini": {
                "enabled": False,
                "name": "opampServer",
                "config_path": str(tmp_path / "settings.json"),
                "transport": "stdio",
            },
        },
    }


def _write_config(tmp_path: Path, settings: dict) -> Path:
    config_path = tmp_path / "mcp-client-defaults.json"
    config_path.write_text(json.dumps(settings), encoding="utf-8")
    return config_path


def test_build_stdio_entry_supports_source_mode(tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)

    entry = tool.build_stdio_server_entry(settings)

    assert entry["command"] == "uv"
    assert "run" in entry["args"]
    assert "--project" in entry["args"]
    assert "--with-editable" in entry["args"]
    assert "fastmcp" in entry["args"]
    assert "OPAMP_MCP_SSE_URL" in entry["env"]
    assert "PYTHONPATH" in entry["env"]


def test_cli_dev_tool_spec_describes_cli_prompt_defaults(tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    settings["clients"]["claude"]["enabled"] = True
    settings["clients"]["codex"]["enabled"] = True
    settings["clients"]["vscode"]["enabled"] = False
    config_path = _write_config(tmp_path, settings)

    original_default_config_path = tool._default_config_path
    tool._default_config_path = lambda: config_path
    try:
        spec = tool.cli_dev_tool_spec()
    finally:
        tool._default_config_path = original_default_config_path

    assert spec["id"] == "mcp_client_config"
    assert spec["fixed_args"] == ["--yes"]
    arguments = {item["name"]: item for item in spec["arguments"]}
    assert arguments["clients"]["default"] == "claude,codex"
    assert arguments["server_host"]["default"] == "localhost"
    assert arguments["server_port"]["default"] == "8080"
    assert arguments["deployment_mode"]["default"] == "source"


def test_build_stdio_entry_supports_package_mode(tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    settings["deployment"]["mode"] = "package"
    settings["deployment"]["package_specs"] = [str(tmp_path / "opamp_server-0.4.0.whl")]

    entry = tool.build_stdio_server_entry(settings)

    assert entry["command"] == "uv"
    assert "--with-editable" not in entry["args"]
    assert str(tmp_path / "opamp_server-0.4.0.whl") in entry["args"]
    assert "opamp_provider.mcptool.routes:mcpserver" in entry["args"]


def test_vscode_target_writes_servers_config(tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    settings["clients"]["vscode"]["enabled"] = True

    results = tool._apply(settings, dry_run=False)
    payload = json.loads((tmp_path / "mcp.json").read_text(encoding="utf-8"))

    assert results[0].client == "vscode"
    assert "opampServer" in payload["servers"]
    assert payload["servers"]["opampServer"]["type"] == "stdio"


def test_gemini_target_writes_mcp_servers_config(tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    settings["clients"]["gemini"]["enabled"] = True

    tool._apply(settings, dry_run=False)
    payload = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))

    assert "opampServer" in payload["mcpServers"]
    assert payload["mcpServers"]["opampServer"]["command"] == "uv"


def test_librechat_target_can_create_new_yaml_without_pyyaml(tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    settings["clients"]["librechat"]["enabled"] = True

    tool._apply(settings, dry_run=False)
    text = (tmp_path / "librechat.yaml").read_text(encoding="utf-8")

    assert "mcpServers:" in text
    assert "opampServer:" in text
    assert "command:" in text


def test_cli_preview_prints_generated_config(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    settings["clients"]["vscode"]["enabled"] = True
    config_path = _write_config(tmp_path, settings)

    exit_code = tool.main(["--config", str(config_path), "--preview"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["clients"]["vscode"]["command"] == "uv"
    assert "Current MCP setup" in payload["summary"]


def test_cli_yes_dry_run_reports_actions_without_writing(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    tool = _load_module()
    settings = _base_settings(tmp_path)
    config_path = _write_config(tmp_path, settings)

    exit_code = tool.main(
        [
            "--config",
            str(config_path),
            "--yes",
            "--dry-run",
            "--clients",
            "vscode,gemini",
            "--server-host",
            "127.0.0.1",
            "--server-port",
            "9090",
            "--deployment-mode",
            "package",
            "--package-spec",
            "opamp-server",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "vscode: would update" in captured.out
    assert "gemini: would update" in captured.out
    assert not (tmp_path / "mcp.json").exists()
    assert not (tmp_path / "settings.json").exists()


def test_cli_unknown_client_fails(tmp_path: Path) -> None:
    tool = _load_module()
    config_path = _write_config(tmp_path, _base_settings(tmp_path))

    with pytest.raises(ValueError, match="unknown clients: nope"):
        tool.main(["--config", str(config_path), "--preview", "--clients", "nope"])


def test_cli_missing_config_fails(tmp_path: Path) -> None:
    tool = _load_module()

    with pytest.raises(FileNotFoundError, match="config file not found"):
        tool.main(["--config", str(tmp_path / "missing.json"), "--preview"])


def test_cli_invalid_deployment_mode_exits(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    tool = _load_module()
    config_path = _write_config(tmp_path, _base_settings(tmp_path))

    with pytest.raises(SystemExit) as exc_info:
        tool.main(["--config", str(config_path), "--deployment-mode", "bad"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "invalid choice: 'bad'" in captured.err
