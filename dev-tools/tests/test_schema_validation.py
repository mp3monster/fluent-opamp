from __future__ import annotations

import sys
from pathlib import Path

from opamp_dev_tools.schema_validation import validate_config_service_schemas


class _RuntimeStub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.issues: list[dict[str, object]] = []
        self.messages: list[str] = []

    def record_issue(self, message: str, **kwargs: object) -> None:
        self.issues.append({"message": message, **kwargs})

    def info(self, message: str) -> None:
        self.messages.append(message)


def test_validate_schemas_uses_master_src_copy(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    _write_json_artifacts_module(repo_root)

    packaged_defs = repo_root / "config-service" / "json-definitions"
    packaged_defs.mkdir(parents=True)
    (packaged_defs / "broken.json").write_text("{ invalid }\n", encoding="utf-8")

    master_defs = repo_root / "config-service" / "src" / "config_service" / "json-definitions"
    master_defs.mkdir(parents=True, exist_ok=True)
    (master_defs / "valid.json").write_text('{"ok": true}\n', encoding="utf-8")

    runtime = _RuntimeStub(repo_root)
    _clear_config_service_imports(monkeypatch)

    issues_found = validate_config_service_schemas(runtime)

    assert issues_found is False
    assert runtime.issues == []
    assert runtime.messages == ["Schema validation completed without issues."]


def test_validate_schemas_reports_master_src_errors(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    _write_json_artifacts_module(repo_root)

    master_defs = repo_root / "config-service" / "src" / "config_service" / "json-definitions"
    master_defs.mkdir(parents=True, exist_ok=True)
    broken_path = master_defs / "broken.json"
    broken_path.write_text("{ invalid }\n", encoding="utf-8")

    runtime = _RuntimeStub(repo_root)
    _clear_config_service_imports(monkeypatch)

    issues_found = validate_config_service_schemas(runtime)

    assert issues_found is True
    assert len(runtime.issues) == 1
    assert runtime.issues[0]["path"] == broken_path
    assert "validation failed" in str(runtime.issues[0]["message"])


def _write_json_artifacts_module(repo_root: Path) -> None:
    package_root = repo_root / "config-service" / "src" / "config_service"
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "json_artifacts.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import json",
                "from pathlib import Path",
                "",
                "def load_json_artifact(path: Path):",
                "    return json.loads(path.read_text(encoding='utf-8'))",
                "",
                "def load_json_schema_artifact(path: Path):",
                "    return json.loads(path.read_text(encoding='utf-8'))",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _clear_config_service_imports(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for name in list(sys.modules):
        if name == "config_service" or name.startswith("config_service."):
            monkeypatch.delitem(sys.modules, name, raising=False)
