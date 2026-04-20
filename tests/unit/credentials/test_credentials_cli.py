from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aria.credentials import __main__ as cli


@dataclass
class _Config:
    home: Path


class _FakeManager:
    def __init__(self, _config) -> None:
        pass

    def status(self, provider=None):
        if provider:
            return {
                "provider": provider,
                "strategy": "least_used",
                "keys": [
                    {
                        "key_id": "k1",
                        "circuit_state": "closed",
                        "credits_remaining": 10,
                        "failure_count": 0,
                        "cooldown_until": None,
                        "last_used_at": None,
                    }
                ],
            }
        return {"tavily": self.status("tavily")}

    async def acquire(self, provider, strategy=None):
        if provider == "empty":
            return None

        class _K:
            key_id = "k1"

        return _K()

    def reload(self):
        return None


def test_status_and_reload_commands(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "CredentialManager", _FakeManager)
    monkeypatch.setattr(cli, "get_config", lambda: _Config(home=tmp_path))
    runner = CliRunner()

    result = runner.invoke(cli.app, ["status", "--provider", "tavily"])
    assert result.exit_code == 0

    list_result = runner.invoke(cli.app, ["list"])
    assert list_result.exit_code == 0

    rotate_result = runner.invoke(cli.app, ["rotate", "tavily"])
    assert rotate_result.exit_code == 0

    rotate_empty = runner.invoke(cli.app, ["rotate", "empty"])
    assert rotate_empty.exit_code == 1

    reload_result = runner.invoke(cli.app, ["reload"])
    assert reload_result.exit_code == 0


def test_audit_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "CredentialManager", _FakeManager)
    monkeypatch.setattr(cli, "get_config", lambda: _Config(home=tmp_path))

    log_dir = tmp_path / ".aria" / "runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"credentials-{datetime.now(tz=UTC).strftime('%Y-%m-%d')}.log"
    log_file.write_text(
        json.dumps(
            {
                "ts": "2026-01-01T00:00:00Z",
                "op": "acquire",
                "provider": "tavily",
                "key_id": "k1",
                "result": "ok",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli.app, ["audit", "--tail", "5"])
    assert result.exit_code == 0


def test_audit_without_file_and_helpers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "CredentialManager", _FakeManager)
    monkeypatch.setattr(cli, "get_config", lambda: _Config(home=tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli.app, ["audit", "--tail", "1"])
    assert result.exit_code == 0

    assert cli._format_datetime("not-a-date") == "not-a-date"
