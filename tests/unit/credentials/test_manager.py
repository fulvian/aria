from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import SecretStr

from aria.credentials.manager import CredentialManager
from aria.credentials.rotator import CircuitState, KeyInfo
from aria.credentials.sops import SopsError


@dataclass
class _Paths:
    runtime: Path
    credentials: Path


@dataclass
class _Sops:
    age_key_file: Path


@dataclass
class _Config:
    paths: _Paths
    sops: _Sops
    home: Path


class _FakeRotator:
    def __init__(self, *_args, **_kwargs) -> None:
        self.synced: dict[str, list[dict]] = {}
        self.success_calls: list[tuple[str, str, int]] = []
        self.failure_calls: list[tuple[str, str, str]] = []

    def sync_provider_keys(self, provider: str, keys: list[dict]) -> None:
        self.synced[provider] = keys

    async def acquire(self, provider: str, _strategy=None):
        if provider in {"missing", "nokey"}:
            key_id = "missing-key"
            return KeyInfo(
                provider=provider,
                key_id=key_id,
                key=SecretStr(""),
                credits_remaining=100,
                circuit_state=CircuitState.CLOSED,
            )
        if provider not in self.synced or not self.synced[provider]:
            return None
        key_id = str(self.synced[provider][0]["key_id"])
        return KeyInfo(
            provider=provider,
            key_id=key_id,
            key=SecretStr(""),
            credits_remaining=100,
            circuit_state=CircuitState.CLOSED,
        )

    async def report_success(self, provider: str, key_id: str, credits_used: int = 1) -> None:
        self.success_calls.append((provider, key_id, credits_used))

    async def report_failure(
        self, provider: str, key_id: str, reason: str, _retry_after=None
    ) -> None:
        self.failure_calls.append((provider, key_id, reason))

    def status(self, provider: str | None = None) -> dict:
        return {"provider": provider or "all", "keys": []}

    async def flush(self) -> None:
        return None


class _FakeKeyring:
    def __init__(self) -> None:
        self.tokens: dict[tuple[str, str], str] = {}

    def put_oauth(self, service: str, account: str, refresh_token: str) -> None:
        self.tokens[(service, account)] = refresh_token

    def get_oauth(self, service: str, account: str) -> str | None:
        return self.tokens.get((service, account))

    def delete_oauth(self, service: str, account: str) -> bool:
        return self.tokens.pop((service, account), None) is not None


class _FakeAudit:
    def __init__(self) -> None:
        self.ops: list[tuple[str, str]] = []

    def record_acquire(self, **_kwargs) -> None:
        self.ops.append(("acquire", "ok"))

    def record_no_key(self, *_args, **_kwargs) -> None:
        self.ops.append(("acquire", "no_key"))

    def record_success(self, *_args, **_kwargs) -> None:
        self.ops.append(("success", "ok"))

    def record_failure(self, *_args, **_kwargs) -> None:
        self.ops.append(("failure", "ok"))

    def record(self, **_kwargs) -> None:
        self.ops.append(("oauth", "ok"))


@pytest.fixture
def manager_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fake_audit = _FakeAudit()
    fake_sops_payload = {
        "providers": {
            "tavily": {
                "keys": [
                    {"key_id": "tvly-1", "key": "tvly-secret", "credits_total": 1000},
                ]
            }
        }
    }

    class _FakeSops:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def decrypt(self, _path: Path):
            return fake_sops_payload

    monkeypatch.setattr("aria.credentials.manager.SopsAdapter", _FakeSops)
    monkeypatch.setattr("aria.credentials.manager.Rotator", _FakeRotator)
    monkeypatch.setattr("aria.credentials.manager.KeyringStore", _FakeKeyring)
    monkeypatch.setattr("aria.credentials.manager.get_audit_logger", lambda: fake_audit)

    config = _Config(
        paths=_Paths(runtime=tmp_path / "runtime", credentials=tmp_path / "credentials"),
        sops=_Sops(age_key_file=tmp_path / "age.txt"),
        home=tmp_path,
    )
    (config.paths.credentials / "secrets").mkdir(parents=True, exist_ok=True)
    (config.paths.credentials / "secrets" / "api-keys.enc.yaml").write_text("x", encoding="utf-8")
    return lambda: (CredentialManager(config=cast("Any", config)), fake_audit)


@pytest.mark.asyncio
async def test_acquire_and_report(manager_factory) -> None:
    manager, _audit = manager_factory()
    key = await manager.acquire("tavily")
    assert key is not None
    assert key.key_id == "tvly-1"
    assert key.key.get_secret_value() == "tvly-secret"

    await manager.report_success("tavily", "tvly-1", credits_used=3)
    await manager.report_failure("tavily", "tvly-1", reason="rate_limit")


@pytest.mark.asyncio
async def test_acquire_no_key_and_status(manager_factory) -> None:
    manager, _audit = manager_factory()
    missing = await manager.acquire("missing")
    assert missing is None
    assert manager.status("tavily")["provider"] == "tavily"


def test_oauth_roundtrip(manager_factory) -> None:
    manager, _audit = manager_factory()
    manager.put_oauth("google_workspace", "primary", "refresh")
    bundle = manager.get_oauth("google_workspace", "primary")
    assert bundle is not None
    assert bundle.refresh_token == "refresh"
    manager.revoke_oauth("google_workspace", "primary")
    assert manager.get_oauth("google_workspace", "primary") is None


# === Retry logic tests ===


class _FlakySops:
    """Fake SOPS adapter that fails N times before succeeding."""

    def __init__(self, fail_count: int = 1, payload: dict | None = None) -> None:
        self._fail_count = fail_count
        self._payload = payload or {
            "providers": {
                "tavily": {
                    "keys": [
                        {"key_id": "tvly-retry", "key": "tvly-secret", "credits_total": 500},
                    ]
                }
            }
        }
        self._attempts = 0
        self.age_key_file = Path("/tmp/fake-age-key")

    def decrypt(self, _path: Path) -> dict:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            raise SopsError("Decryption failed", exit_code=128)
        return self._payload


def _make_manager_with_flaky_sops(
    fail_count: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[CredentialManager, _FlakySops]:
    """Create a CredentialManager with a flaky SOPS adapter."""
    fake_sops = _FlakySops(fail_count=fail_count)
    fake_audit = _FakeAudit()

    monkeypatch.setattr("aria.credentials.manager.SopsAdapter", lambda *_a, **_kw: fake_sops)
    monkeypatch.setattr("aria.credentials.manager.Rotator", _FakeRotator)
    monkeypatch.setattr("aria.credentials.manager.KeyringStore", _FakeKeyring)
    monkeypatch.setattr("aria.credentials.manager.get_audit_logger", lambda: fake_audit)

    config = _Config(
        paths=_Paths(runtime=tmp_path / "runtime", credentials=tmp_path / "credentials"),
        sops=_Sops(age_key_file=tmp_path / "age.txt"),
        home=tmp_path,
    )
    (config.paths.credentials / "secrets").mkdir(parents=True, exist_ok=True)
    (config.paths.credentials / "secrets" / "api-keys.enc.yaml").write_text("x", encoding="utf-8")

    cm = CredentialManager(config=cast("Any", config))
    return cm, fake_sops


def test_load_api_keys_retries_on_first_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SOPS decryption fails once, retries, succeeds on second attempt."""
    cm, flaky_sops = _make_manager_with_flaky_sops(
        fail_count=1, monkeypatch=monkeypatch, tmp_path=tmp_path
    )

    # Manager should have loaded keys after retry
    assert "tavily" in cm._api_keys
    assert cm._api_keys["tavily"][0]["key_id"] == "tvly-retry"
    assert flaky_sops._attempts == 2


def test_load_api_keys_retries_and_fails_both(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SOPS decryption fails twice, manager continues with empty keys."""
    cm, flaky_sops = _make_manager_with_flaky_sops(
        fail_count=2, monkeypatch=monkeypatch, tmp_path=tmp_path
    )

    # Should have empty keys after both attempts fail
    assert cm._api_keys == {}
    assert flaky_sops._attempts == 2


def test_load_api_keys_logs_warning_on_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warning is logged when first SOPS attempt fails."""
    with caplog.at_level(logging.WARNING, logger="aria.credentials.manager"):
        cm, _ = _make_manager_with_flaky_sops(
            fail_count=1, monkeypatch=monkeypatch, tmp_path=tmp_path
        )

    assert any("retrying" in r.message.lower() for r in caplog.records)
    assert "tavily" in cm._api_keys


def test_load_api_keys_logs_error_on_final_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Error is logged when both SOPS attempts fail."""
    with caplog.at_level(logging.ERROR, logger="aria.credentials.manager"):
        cm, _ = _make_manager_with_flaky_sops(
            fail_count=2, monkeypatch=monkeypatch, tmp_path=tmp_path
        )

    assert any("failed after 2 attempts" in r.message for r in caplog.records)
    assert cm._api_keys == {}


def test_parse_providers_handles_canonical_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_parse_providers correctly processes canonical format with keys list."""
    cm, _ = _make_manager_with_flaky_sops(fail_count=0, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert "tavily" in cm._api_keys
    assert cm._api_keys["tavily"][0]["key_id"] == "tvly-retry"


def test_parse_providers_handles_legacy_list_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_parse_providers correctly handles legacy list-style format."""
    payload = {
        "providers": {
            "exa": [
                {"id": "exa-legacy", "key": "exa-secret", "credits_total": 200},
            ]
        }
    }
    fake_sops = _FlakySops(fail_count=0, payload=payload)
    fake_audit = _FakeAudit()

    monkeypatch.setattr("aria.credentials.manager.SopsAdapter", lambda *_a, **_kw: fake_sops)
    monkeypatch.setattr("aria.credentials.manager.Rotator", _FakeRotator)
    monkeypatch.setattr("aria.credentials.manager.KeyringStore", _FakeKeyring)
    monkeypatch.setattr("aria.credentials.manager.get_audit_logger", lambda: fake_audit)

    config = _Config(
        paths=_Paths(runtime=tmp_path / "runtime", credentials=tmp_path / "credentials"),
        sops=_Sops(age_key_file=tmp_path / "age.txt"),
        home=tmp_path,
    )
    (config.paths.credentials / "secrets").mkdir(parents=True, exist_ok=True)
    (config.paths.credentials / "secrets" / "api-keys.enc.yaml").write_text("x", encoding="utf-8")

    cm = CredentialManager(config=cast("Any", config))
    assert "exa" in cm._api_keys
    assert cm._api_keys["exa"][0]["key_id"] == "exa-legacy"
