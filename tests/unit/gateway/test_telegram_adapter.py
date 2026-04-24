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

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.await_args.kwargs
    assert call_kwargs["chat_id"] == 987117252
    assert "risposta" in call_kwargs["text"]
    assert call_kwargs["parse_mode"] is not None


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

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.await_args.kwargs
    assert call_kwargs["chat_id"] == 987117252
    assert "fallback" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_send_text_converts_markdown_to_html() -> None:
    """send_text should convert Markdown to Telegram HTML."""
    adapter, _auth, _sessions, _bus, _cm = _make_adapter()

    bot = MagicMock()
    bot.send_message = AsyncMock()
    adapter._app = SimpleNamespace(bot=bot)

    result = await adapter.send_text(chat_id=123, text="## Heading\n**bold**")

    assert result is True
    call_kwargs = bot.send_message.await_args.kwargs
    assert call_kwargs["chat_id"] == 123
    assert "<b>Heading</b>" in call_kwargs["text"]
    assert "<b>bold</b>" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_send_text_splits_long_messages() -> None:
    """send_text should split messages longer than 4096 chars into multiple calls."""
    adapter, _auth, _sessions, _bus, _cm = _make_adapter()

    bot = MagicMock()
    bot.send_message = AsyncMock()
    adapter._app = SimpleNamespace(bot=bot)

    long_text = "x" * 5000
    result = await adapter.send_text(chat_id=123, text=long_text)

    assert result is True
    assert bot.send_message.await_count >= 2


@pytest.mark.asyncio
async def test_send_text_returns_false_when_app_not_initialized() -> None:
    adapter, _auth, _sessions, _bus, _cm = _make_adapter()
    adapter._app = None
    result = await adapter.send_text(chat_id=123, text="hello")
    assert result is False


@pytest.mark.asyncio
async def test_send_text_returns_true_for_empty_text() -> None:
    adapter, _auth, _sessions, _bus, _cm = _make_adapter()
    result = await adapter.send_text(chat_id=123, text="   ")
    assert result is True
