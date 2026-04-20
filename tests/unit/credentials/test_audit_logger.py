from __future__ import annotations

import json
from pathlib import Path

import pytest

from aria.credentials.audit import AuditLogger


def test_audit_logger_writes_json_lines(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)
    logger.record(
        provider="tavily",
        op="acquire",
        key_id="tvly-1",
        result="ok",
        credits_remaining=50,
    )

    files = list(tmp_path.glob("credentials-*.log"))
    assert files
    payload = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert payload["provider"] == "tavily"
    assert payload["key_id"] == "tvly-1"
    assert "key" not in payload


def test_audit_convenience_methods(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)
    logger.record_acquire("tavily", "k1", "ok", credits_remaining=10)
    logger.record_success("tavily", "k1", credits_used=1)
    logger.record_failure("tavily", "k1", error="rate_limit")
    logger.record_no_key("tavily", "depleted")

    lines = []
    for file_path in tmp_path.glob("credentials-*.log"):
        lines.extend(file_path.read_text(encoding="utf-8").splitlines())
    assert len(lines) == 4


def test_audit_fallback_on_write_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)

    def broken_write(_entry):
        raise OSError("boom")

    monkeypatch.setattr(logger, "_write_line", broken_write)
    logger.record(provider="tavily", op="acquire", key_id="k1", result="ok")
