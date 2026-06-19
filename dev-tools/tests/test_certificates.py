from __future__ import annotations

import json
from pathlib import Path

from opamp_dev_tools.certificates import ensure_provider_tls_config


class _RuntimeStub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


def test_ensure_provider_tls_config_updates_json_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "opamp.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "provider": {
                    "tls": {
                        "enabled": True,
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    runtime = _RuntimeStub(tmp_path)

    issues_found = ensure_provider_tls_config(
        runtime,
        config_file="config/opamp.json",
        cert_file="certs/test-cert.pem",
        key_file="certs/test-key.pem",
        trust_anchor_mode="none",
    )

    assert issues_found is False
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["provider"]["tls"]["enabled"] is True
    assert payload["provider"]["tls"]["cert_file"] == str((tmp_path / "certs" / "test-cert.pem").resolve())
    assert payload["provider"]["tls"]["key_file"] == str((tmp_path / "certs" / "test-key.pem").resolve())
    assert payload["provider"]["tls"]["trust_anchor_mode"] == "none"
    assert runtime.messages[0].startswith("[OK] Updated provider TLS config")


def test_ensure_provider_tls_config_creates_missing_config_root(tmp_path: Path) -> None:
    runtime = _RuntimeStub(tmp_path)
    config_path = tmp_path / "new-config.json"

    issues_found = ensure_provider_tls_config(
        runtime,
        config_file=str(config_path),
        cert_file="/tmp/cert.pem",
        key_file="/tmp/key.pem",
        trust_anchor_mode="partial_chain",
    )

    assert issues_found is False
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["provider"]["tls"]["cert_file"] == "/tmp/cert.pem"
    assert payload["provider"]["tls"]["key_file"] == "/tmp/key.pem"
    assert payload["provider"]["tls"]["trust_anchor_mode"] == "partial_chain"
