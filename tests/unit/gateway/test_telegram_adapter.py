from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.gateway.telegram_adapter import TelegramAdapter


def _make_adapter() -> tuple[TelegramAdapter, MagicMock, MagicMock, MagicMock, MagicMock]:
    cm = MagicMock()
    auth = MagicMock()
    sessions = MagicMock()
    bus = MagicMock()
    bus.publish = AsyncMock()
    config = SimpleNamespace(paths=SimpleNamespace(runtime=Path("/tmp/aria/runtime")))
    adapter = TelegramAdapter(cm=cm, auth=auth, sessions=sessions, bus=bus, config=config)
    return adapter, auth, sessions, bus, cm


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()
    user = SimpleNamespace(id=user_id, language_code="it-IT", first_name="Test")
    return SimpleNamespace(effective_user=user, message=message)


@pytest.mark.asyncio
async def test_handle_text_publishes_telegram_user_id() -> None:
    adapter, auth, sessions, bus, _cm = _make_adapter()
    auth.is_allowed_telegram_user.return_value = True

    session = SimpleNamespace(id="s1", locale="it-IT")
    sessions.get_or_create = AsyncMock(return_value=session)
    sessions.touch = AsyncMock()

    update = _make_update(user_id=123, text="ciao")
    context = MagicMock()

    await adapter._handle_text(update, context)

    bus.publish.assert_awaited_once()
    _event_name, payload = bus.publish.await_args.args
    assert payload["user_id"] == 123
    assert payload["telegram_user_id"] == "123"
    assert payload["text"] == "ciao"


@pytest.mark.asyncio
async def test_handle_gateway_reply_resolves_chat_id_from_session() -> None:
    adapter, _auth, sessions, _bus, _cm = _make_adapter()
    sessions.get_session = AsyncMock(
        return_value=SimpleNamespace(
            id="s1",
            external_user_id="987117252",
        )
    )

    bot = MagicMock()
    bot.send_message = AsyncMock()
    adapter._app = SimpleNamespace(bot=bot)

    await adapter.handle_gateway_reply({"session_id": "s1", "text": "risposta"})

    bot.send_message.assert_awaited_once_with(chat_id=987117252, text="risposta")


@pytest.mark.asyncio
async def test_handle_gateway_reply_falls_back_to_telegram_user_id() -> None:
    adapter, _auth, sessions, _bus, _cm = _make_adapter()
    sessions.get_session = AsyncMock(return_value=None)

    bot = MagicMock()
    bot.send_message = AsyncMock()
    adapter._app = SimpleNamespace(bot=bot)

    await adapter.handle_gateway_reply(
        {
            "session_id": "missing",
            "telegram_user_id": "987117252",
            "text": "fallback",
        }
    )

    bot.send_message.assert_awaited_once_with(chat_id=987117252, text="fallback")
