"""Verify ConductorBridge persists user/assistant/tool turns via EpisodicStore.insert."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.gateway.conductor_bridge import ConductorBridge
from aria.memory.schema import Actor


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self.events.append((topic, payload))


@pytest.mark.asyncio
async def test_handle_user_message_inserts_user_then_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MagicMock()
    store.insert = AsyncMock()
    bus = _FakeBus()
    config = MagicMock()
    bridge = ConductorBridge(bus=bus, store=store, config=config, clm=None)

    valid_session = str(uuid.uuid4())

    async def _fake_spawn(
        *, input_text: str, session_id: str, trace_id: str
    ) -> dict[str, Any]:
        _ = (input_text, session_id, trace_id)
        return {
            "text": "ok",
            "child_session_id": "ses_x",
            "tokens_used": 0,
            "framed_tool_output": "<<TOOL_OUTPUT>>foo<</TOOL_OUTPUT>>",
        }

    monkeypatch.setattr(bridge, "_spawn_conductor", _fake_spawn)

    await bridge.handle_user_message(
        {
            "text": "hello",
            "session_id": valid_session,
            "telegram_user_id": "1",
            "trace_id": "t",
        },
    )

    assert store.insert.await_count == 3
    actors = [call.args[0].actor for call in store.insert.await_args_list]
    assert actors == [Actor.USER_INPUT, Actor.TOOL_OUTPUT, Actor.AGENT_INFERENCE]


@pytest.mark.asyncio
async def test_handle_user_message_reuses_child_session_for_follow_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MagicMock()
    store.insert = AsyncMock()
    bus = _FakeBus()
    config = MagicMock()
    bridge = ConductorBridge(bus=bus, store=store, config=config, clm=None)

    valid_session = str(uuid.uuid4())
    child_sessions: list[str] = []

    async def _fake_spawn(
        *, input_text: str, session_id: str, trace_id: str
    ) -> dict[str, Any]:
        _ = (input_text, trace_id)
        child_session_id = bridge._get_or_create_child_session_id(session_id)
        child_sessions.append(child_session_id)
        return {
            "text": "ok",
            "child_session_id": child_session_id,
            "tokens_used": 0,
        }

    monkeypatch.setattr(bridge, "_spawn_conductor", _fake_spawn)

    for text in ("cinema vicino", "continua"):
        await bridge.handle_user_message(
            {
                "text": text,
                "session_id": valid_session,
                "telegram_user_id": "1",
                "trace_id": f"trace-{text}",
            },
        )

    assert len(child_sessions) == 2
    assert child_sessions[0] == child_sessions[1]
