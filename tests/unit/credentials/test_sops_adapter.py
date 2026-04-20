from __future__ import annotations

import subprocess
from pathlib import Path
import sys

import pytest

from aria.credentials.sops import SopsAdapter, SopsError


def test_decrypt_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    encrypted = tmp_path / "data.enc.yaml"
    encrypted.write_text("x", encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        class Result:
            stdout = "providers: {}\n"

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert adapter.decrypt(encrypted) == {"providers": {}}


def test_decrypt_missing_file_raises(tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    with pytest.raises(FileNotFoundError):
        adapter.decrypt(tmp_path / "missing.enc.yaml")


def test_encrypt_inplace_writes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    out = tmp_path / "x.enc.yaml"

    def fake_run(*_args, **_kwargs):
        class Result:
            stdout = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter.encrypt_inplace(out, {"a": 1})
    assert out.exists()


def test_edit_atomic_mutates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    target = tmp_path / "state.enc.yaml"
    target.write_text("x", encoding="utf-8")

    captured: dict[str, object] = {}

    monkeypatch.setattr(adapter, "decrypt", lambda _path: {"x": 1})

    def fake_encrypt(path: Path, data: dict[str, object]) -> None:
        captured["path"] = path
        captured["data"] = data

    monkeypatch.setattr(adapter, "encrypt_inplace", fake_encrypt)
    adapter.edit_atomic(target, lambda d: {**d, "y": 2})

    assert captured["path"] == target
    assert captured["data"] == {"x": 1, "y": 2}


def test_is_encrypted_detection(tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    encrypted = tmp_path / "e.enc.yaml"
    encrypted.write_text("sops:\n  kms: []\n", encoding="utf-8")
    plain = tmp_path / "plain.yaml"
    plain.write_text("a: 1\n", encoding="utf-8")

    assert adapter.is_encrypted(encrypted)
    assert not adapter.is_encrypted(plain)


def test_run_sops_maps_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=129, cmd=["sops"], stderr="no key")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SopsError) as exc:
        adapter._run_sops(["--decrypt", "x"], path=tmp_path / "x")
    assert "No age key found" in str(exc.value)


def test_run_sops_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["sops"], timeout=adapter.SUBPROCESS_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SopsError):
        adapter._run_sops(["--decrypt", "x"], path=tmp_path / "x")


def test_decrypt_yaml_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    encrypted = tmp_path / "data.enc.yaml"
    encrypted.write_text("x", encoding="utf-8")
    monkeypatch.setattr(adapter, "_run_sops", lambda *_args, **_kwargs: "[invalid")
    with pytest.raises(SopsError):
        adapter.decrypt(encrypted)


def test_sops_main_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aria.credentials import sops as sops_mod

    monkeypatch.setattr(sys, "argv", ["sops", "is-encrypted", str(tmp_path / "x")])
    monkeypatch.setattr(sops_mod.SopsAdapter, "is_encrypted", lambda self, path: False)
    assert sops_mod.main() == 0

    monkeypatch.setattr(sys, "argv", ["sops", "encrypt", str(tmp_path / "x")])
    assert sops_mod.main() == 1


def test_edit_atomic_lock_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    target = tmp_path / "state.enc.yaml"
    target.write_text("x", encoding="utf-8")

    monotonic_values = iter([0.0, 20.0])
    monkeypatch.setattr("aria.credentials.sops.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("aria.credentials.sops.time.sleep", lambda _x: None)

    def always_block(*_args, **_kwargs):
        raise BlockingIOError

    monkeypatch.setattr("aria.credentials.sops.fcntl.flock", always_block)
    with pytest.raises(SopsError):
        adapter.edit_atomic(target, lambda d: d)


def test_encrypt_inplace_cleanup_on_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = SopsAdapter(tmp_path / "age.txt")
    out = tmp_path / "bad.enc.yaml"

    def fail_run(*_args, **_kwargs):
        raise SopsError("boom")

    monkeypatch.setattr(adapter, "_run_sops", fail_run)
    with pytest.raises(SopsError):
        adapter.encrypt_inplace(out, {"x": 1})
    assert not any(tmp_path.glob(".sops_tmp_*.yaml"))
