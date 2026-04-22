from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aria.agents.workspace.oauth_helper import GoogleOAuthHelper, OAuthSetupRequiredError


class _FakeKeyring:
    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self.deleted: list[tuple[str, str]] = []

    def get_oauth(self, _service: str, _account: str) -> str | None:
        return self.token

    def delete_oauth(self, service: str, account: str) -> bool:
        self.deleted.append((service, account))
        self.token = None
        return True


def _config_with_runtime(runtime: Path) -> Any:
    return SimpleNamespace(paths=SimpleNamespace(runtime=runtime))


def test_ensure_refresh_token_missing_raises(tmp_path: Path) -> None:
    helper = GoogleOAuthHelper(config=_config_with_runtime(tmp_path))
    helper._keyring = _FakeKeyring(token=None)  # type: ignore[attr-defined]

    with pytest.raises(OAuthSetupRequiredError):
        helper.ensure_refresh_token("primary")


def test_get_scopes_reads_runtime_file(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    scopes_dir = runtime / "credentials"
    scopes_dir.mkdir(parents=True)
    scopes_file = scopes_dir / "google_workspace_scopes_primary.json"
    scopes_file.write_text('{"scopes": ["a", "b"]}', encoding="utf-8")

    helper = GoogleOAuthHelper(config=_config_with_runtime(runtime))
    assert helper.get_scopes("primary") == ["a", "b"]


def test_revoke_clears_keyring_and_scopes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "runtime"
    scopes_dir = runtime / "credentials"
    scopes_dir.mkdir(parents=True)
    scopes_file = scopes_dir / "google_workspace_scopes_primary.json"
    scopes_file.write_text('{"scopes": ["a"]}', encoding="utf-8")
    runtime_creds_dir = scopes_dir / "google_workspace_mcp"
    runtime_creds_dir.mkdir(parents=True)
    runtime_creds_file = runtime_creds_dir / "user_example.com.json"
    runtime_creds_file.write_text('{"refresh_token": "rt"}', encoding="utf-8")

    helper = GoogleOAuthHelper(config=_config_with_runtime(runtime))
    fake_keyring = _FakeKeyring(token="refresh-token")
    helper._keyring = fake_keyring  # type: ignore[attr-defined]

    class _Resp:
        status_code = 200

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: _Resp())

    helper.revoke("primary")

    assert fake_keyring.deleted == [("google_workspace", "primary")]
    assert not scopes_file.exists()
    assert not runtime_creds_file.exists()
