"""Unit tests for ARIA_SESSION_ID resolution in the memory MCP server."""

from __future__ import annotations

import os
import uuid

import pytest

from aria.memory import mcp_server


def _restore_env(name: str, original: str | None) -> None:
    if original is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = original


def test_get_session_id_uses_env_when_valid() -> None:
    original = os.environ.get("ARIA_SESSION_ID")
    sid = uuid.uuid4()
    os.environ["ARIA_SESSION_ID"] = str(sid)
    try:
        assert mcp_server._get_session_id() == sid
    finally:
        _restore_env("ARIA_SESSION_ID", original)


def test_get_session_id_raises_when_missing_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ARIA_SESSION_ID", raising=False)
    monkeypatch.setenv("ARIA_MEMORY_STRICT_SESSION", "1")
    with pytest.raises(RuntimeError, match="ARIA_SESSION_ID"):
        mcp_server._get_session_id()


def test_get_session_id_falls_back_to_random_when_lax(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ARIA_SESSION_ID", raising=False)
    monkeypatch.delenv("ARIA_MEMORY_STRICT_SESSION", raising=False)
    sid = mcp_server._get_session_id()
    assert isinstance(sid, uuid.UUID)
