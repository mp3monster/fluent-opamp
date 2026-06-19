from __future__ import annotations

from pathlib import Path

from opamp_dev_tools.config_sync import sync_config_service_json_assets


class _RuntimeStub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


def test_sync_config_service_json_assets_mirrors_src_trees(tmp_path: Path) -> None:
    repo_root = tmp_path
    config_service_root = repo_root / "config-service"
    src_definitions = config_service_root / "src" / "config_service" / "json-definitions"
    src_schemas = config_service_root / "src" / "config_service" / "json-schemas"
    root_definitions = config_service_root / "json-definitions"
    root_schemas = config_service_root / "json-schemas"

    (src_definitions / "nested").mkdir(parents=True)
    src_schemas.mkdir(parents=True)
    root_definitions.mkdir(parents=True)
    root_schemas.mkdir(parents=True)

    (src_definitions / "service.json").write_text('{"value": 1}\n', encoding="utf-8")
    (src_definitions / "nested" / "plugin.json").write_text('{"value": 2}\n', encoding="utf-8")
    (src_schemas / "schema.json").write_text('{"type": "object"}\n', encoding="utf-8")

    (root_definitions / "stale.json").write_text('{"stale": true}\n', encoding="utf-8")
    (root_schemas / "old.json").write_text('{"old": true}\n', encoding="utf-8")

    runtime = _RuntimeStub(repo_root)

    issues_found = sync_config_service_json_assets(runtime)

    assert issues_found is False
    assert (root_definitions / "service.json").read_text(encoding="utf-8") == '{"value": 1}\n'
    assert (root_definitions / "nested" / "plugin.json").read_text(encoding="utf-8") == '{"value": 2}\n'
    assert (root_schemas / "schema.json").read_text(encoding="utf-8") == '{"type": "object"}\n'
    assert not (root_definitions / "stale.json").exists()
    assert not (root_schemas / "old.json").exists()
    assert len(runtime.messages) == 2
