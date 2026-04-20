from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import keyring.backends.fail
from keyring.errors import KeyringError
import pytest

from aria.credentials.keyring_store import KeyringStore


class _FakeBackend:
    pass


def test_service_name_prefix() -> None:
    store = KeyringStore(service_prefix="aria")
    assert store._service_name("google") == "aria.google"


def test_keyring_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    storage: dict[tuple[str, str], str] = {}

    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_keyring", lambda: _FakeBackend()
    )
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.set_password",
        lambda service, username, token: storage.__setitem__((service, username), token),
    )
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_password",
        lambda service, username: storage.get((service, username)),
    )
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.delete_password",
        lambda service, username: storage.pop((service, username), None),
    )

    store = KeyringStore()
    store.put_oauth("google_workspace", "primary", "token-value")
    assert store.get_oauth("google_workspace", "primary") == "token-value"
    assert store.delete_oauth("google_workspace", "primary")


def test_fallback_encrypted_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_keyring",
        lambda: keyring.backends.fail.Keyring(),
    )
    monkeypatch.setenv("ARIA_CREDENTIALS", str(tmp_path))

    key_file = tmp_path / "key.txt"
    key_file.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("ARIA_KEYRING_FALLBACK_KEY", str(key_file))

    store = KeyringStore()
    monkeypatch.setattr(store, "_encrypt_age", lambda data, _key: f"enc:{data}".encode("utf-8"))
    monkeypatch.setattr(
        store, "_decrypt_age", lambda data, _key: data.decode("utf-8").replace("enc:", "")
    )

    store.put_oauth("google_workspace", "primary", "refresh-token")
    assert store.get_oauth("google_workspace", "primary") == "refresh-token"
    assert "primary" in store.list_accounts("google_workspace")
    assert store.delete_oauth("google_workspace", "primary")


def test_missing_fallback_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_keyring",
        lambda: keyring.backends.fail.Keyring(),
    )
    monkeypatch.delenv("ARIA_KEYRING_FALLBACK_KEY", raising=False)
    store = KeyringStore()
    monkeypatch.setattr(store, "_get_fallback_key_path", lambda: None)

    with pytest.raises(RuntimeError):
        store.put_oauth("svc", "acc", "token")


def test_age_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_keyring", lambda: _FakeBackend()
    )
    store = KeyringStore()

    class _Result:
        def __init__(self, stdout: str | bytes):
            self.stdout = stdout

    def fake_run(args, **_kwargs):
        if args[0] == "age-keygen":
            return _Result("age1recipient")
        if "--decrypt" in args:
            return _Result(b"token")
        return _Result(b"encrypted")

    monkeypatch.setattr(subprocess, "run", fake_run)
    key_file = tmp_path / "age.txt"
    key_file.write_text("dummy", encoding="utf-8")

    assert store._age_recipient_from_key(key_file) == "age1recipient"
    encrypted = store._encrypt_age("token", key_file)
    assert encrypted == b"encrypted"
    assert store._decrypt_age(encrypted, key_file) == "token"


def test_keyring_main_list(monkeypatch: pytest.MonkeyPatch) -> None:
    from aria.credentials import keyring_store as ks

    monkeypatch.setattr(sys, "argv", ["ks", "list", "google_workspace"])
    monkeypatch.setattr(
        ks, "KeyringStore", lambda: type("S", (), {"list_accounts": lambda *_: []})()
    )
    assert ks.main() == 0


def test_backend_detection_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_cls = type("SecretCls", (), {})
    secret_cls.__module__ = "x.secret_service.backend"
    monkeypatch.setattr("aria.credentials.keyring_store.keyring.get_keyring", lambda: secret_cls())
    assert KeyringStore()._backend_name == "SecretService"

    gnome_cls = type("GnomeCls", (), {})
    gnome_cls.__module__ = "x.gnome.backend"
    monkeypatch.setattr("aria.credentials.keyring_store.keyring.get_keyring", lambda: gnome_cls())
    assert KeyringStore()._backend_name == "GNOME Keyring"

    kwallet_cls = type("KwalletCls", (), {})
    kwallet_cls.__module__ = "x.kwallet.backend"
    monkeypatch.setattr("aria.credentials.keyring_store.keyring.get_keyring", lambda: kwallet_cls())
    assert KeyringStore()._backend_name == "KDE Wallet"


def test_get_and_delete_error_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_keyring", lambda: _FakeBackend()
    )

    def raise_keyring(*_args, **_kwargs):
        raise KeyringError("boom")

    monkeypatch.setattr("aria.credentials.keyring_store.keyring.get_password", raise_keyring)
    monkeypatch.setattr("aria.credentials.keyring_store.keyring.delete_password", raise_keyring)

    store = KeyringStore()
    monkeypatch.setenv("ARIA_CREDENTIALS", str(tmp_path))
    assert store.get_oauth("svc", "acc") is None
    assert not store.delete_oauth("svc", "acc")


def test_put_oauth_keyring_error_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "aria.credentials.keyring_store.keyring.get_keyring", lambda: _FakeBackend()
    )

    def raise_keyring(*_args, **_kwargs):
        raise KeyringError("write failed")

    monkeypatch.setattr("aria.credentials.keyring_store.keyring.set_password", raise_keyring)
    monkeypatch.setenv("ARIA_CREDENTIALS", str(tmp_path))

    key_file = tmp_path / "key.txt"
    key_file.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("ARIA_KEYRING_FALLBACK_KEY", str(key_file))

    store = KeyringStore()
    monkeypatch.setattr(store, "_encrypt_age", lambda data, _key: f"enc:{data}".encode("utf-8"))
    store.put_oauth("svc", "acc", "token")
    assert (tmp_path / "keyring-fallback" / "svc-acc.age").exists()
