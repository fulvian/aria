"""Unit tests for the complete_turn MCP tool."""

from __future__ import annotations

import os
import uuid

import pytest

from aria.memory import mcp_server


@pytest.mark.asyncio
async def test_complete_turn_persists_assistant_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete_turn must insert an agent_inference entry."""
    sid = uuid.uuid4()
    monkeypatch.setenv("ARIA_SESSION_ID", str(sid))
    monkeypatch.delenv("ARIA_MEMORY_STRICT_SESSION", raising=False)

    # We test against the real function but need a store — use the existing
    # integration test infrastructure. For a pure unit test we mock the store.
    from unittest.mock import AsyncMock, MagicMock

    mock_store = MagicMock()
    mock_store.insert = AsyncMock()

    # Patch _ensure_store to return our mock
    async def _fake_ensure():
        return mock_store, MagicMock(), MagicMock()

    monkeypatch.setattr(mcp_server, "_ensure_store", _fake_ensure)

    result = await mcp_server.complete_turn(response_text="La risposta è 42")

    assert result["status"] == "ok"
    assert result["entries"] == 1
    mock_store.insert.assert_awaited_once()
    entry = mock_store.insert.await_args[0][0]
    assert entry.actor.value == "agent_inference"
    assert entry.role == "assistant"
    assert entry.content == "La risposta è 42"


@pytest.mark.asyncio
async def test_complete_turn_with_tool_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete_turn must insert both tool_output and agent_inference."""
    sid = uuid.uuid4()
    monkeypatch.setenv("ARIA_SESSION_ID", str(sid))
    monkeypatch.delenv("ARIA_MEMORY_STRICT_SESSION", raising=False)

    from unittest.mock import AsyncMock, MagicMock

    mock_store = MagicMock()
    mock_store.insert = AsyncMock()

    async def _fake_ensure():
        return mock_store, MagicMock(), MagicMock()

    monkeypatch.setattr(mcp_server, "_ensure_store", _fake_ensure)

    result = await mcp_server.complete_turn(
        response_text="Ecco i risultati",
        tool_output="web_search_result: ...",
    )

    assert result["status"] == "ok"
    assert result["entries"] == 2
    assert mock_store.insert.await_count == 2
    actors = [call.args[0].actor.value for call in mock_store.insert.await_args_list]
    assert actors == ["tool_output", "agent_inference"]
