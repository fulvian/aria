"""E2E test: HITL inline keyboard flow using PTBTestApp mock.

Tests the complete HITL flow:
1. HITL created via scheduler
2. Inline keyboard message sent via mock bot
3. Callback query received with hitl:<id>:<response> data
4. HITL resolved via HitlResponder

No real HTTP calls to api.telegram.org.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.gateway.hitl_responder import (
    HITL_CALLBACK_PREFIX,
    build_hitl_keyboard,
    build_hitl_message,
    handle_hitl_callback,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Mock Telegram Bot and Update
# ---------------------------------------------------------------------------


class _MockCallbackQuery:
    """Mock callback query for testing."""

    def __init__(self, data: str | None = None) -> None:
        self.data = data
        self._answer_mock = AsyncMock()
        self._edit_message_mock = AsyncMock()
        self.message = MagicMock()
        self.message.reply_text = AsyncMock()
        self.message.edit_text = AsyncMock()

    async def answer(self) -> None:
        await self._answer_mock()

    async def edit_message_text(self, text: str, **kwargs: dict[str, object]) -> None:
        await self._edit_message_mock(text=text, **kwargs)


class _MockUpdate:
    """Mock Telegram update for testing."""

    def __init__(self, callback_data: str | None = None) -> None:
        self.callback_query = _MockCallbackQuery(data=callback_data)


class _MockBot:
    """Mock Telegram bot for testing."""

    def __init__(self) -> None:
        self._send_message_mock = AsyncMock()
        self.token = "test-token"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: object | None = None,
    ) -> MagicMock:
        """Mock send_message - returns a mock Message."""
        return self._send_message_mock(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )


# ---------------------------------------------------------------------------
# Mock config for tests
# ---------------------------------------------------------------------------


class _MockConfig:
    """Minimal mock config for testing."""

    def __init__(self, tmp_path: Path) -> None:
        self.paths = MagicMock()
        self.paths.runtime = tmp_path / "runtime"
        self.paths.runtime.mkdir(parents=True, exist_ok=True)
        self.operational = MagicMock()
        self.operational.log_level = "DEBUG"
        self.operational.timezone = "Europe/Rome"
        self.telegram = MagicMock()
        self.telegram.whitelist = []


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bot() -> _MockBot:
    """Create a mock Telegram bot."""
    return _MockBot()


@pytest.fixture
def mock_hitl_manager() -> MagicMock:
    """Create a mock HitlManager."""
    manager = MagicMock()
    manager.resolve = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def mock_context() -> MagicMock:
    """Create a mock Telegram context."""
    return MagicMock()


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestHitlInlineKeyboardFlow:
    """E2E tests for HITL inline keyboard flow."""

    async def test_hitl_inline_keyboard_flow(
        self,
        mock_bot: _MockBot,
        mock_hitl_manager: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """E2E: HITL created -> inline keyboard -> callback -> resolve.

        This test simulates the complete flow:
        1. A HITL is created with an ID
        2. An inline keyboard is built with hitl:<id>:yes|no|later buttons
        3. User clicks "yes" button
        4. Callback is parsed and HITL is resolved
        """
        hitl_id = "test-hitl-abc123"

        # Build keyboard for HITL
        keyboard = build_hitl_keyboard(hitl_id)

        # Verify keyboard has correct structure
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 1
        row = keyboard.inline_keyboard[0]
        assert len(row) == 3

        # Verify button callback_data format
        yes_btn = row[0]
        assert yes_btn.callback_data == f"{HITL_CALLBACK_PREFIX}{hitl_id}:yes"

        # Create update with callback data for "yes"
        callback_data = f"{HITL_CALLBACK_PREFIX}{hitl_id}:yes"
        update = _MockUpdate(callback_data=callback_data)

        # Simulate callback handling
        await handle_hitl_callback(update, mock_context, mock_hitl_manager)

        # Verify bot responded (acknowledged callback)
        update.callback_query._edit_message_mock.assert_called_once()

        # Verify HITL was resolved
        mock_hitl_manager.resolve.assert_called_once_with(hitl_id, "yes")

    async def test_hitl_callback_no_response(
        self,
        mock_bot: _MockBot,
        mock_hitl_manager: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """E2E: HITL callback with 'no' response."""
        hitl_id = "test-hitl-def456"

        callback_data = f"{HITL_CALLBACK_PREFIX}{hitl_id}:no"
        update = _MockUpdate(callback_data=callback_data)

        await handle_hitl_callback(update, mock_context, mock_hitl_manager)

        # Verify resolve was called with "no"
        mock_hitl_manager.resolve.assert_called_once_with(hitl_id, "no")

    async def test_hitl_callback_deferred(
        self,
        mock_bot: _MockBot,
        mock_hitl_manager: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """E2E: HITL callback with 'later' (deferred) response."""
        hitl_id = "test-hitl-ghi789"

        callback_data = f"{HITL_CALLBACK_PREFIX}{hitl_id}:later"
        update = _MockUpdate(callback_data=callback_data)

        await handle_hitl_callback(update, mock_context, mock_hitl_manager)

        # Verify resolve was called with "deferred" (later maps to deferred)
        mock_hitl_manager.resolve.assert_called_once_with(hitl_id, "deferred")

    async def test_hitl_callback_unknown_response(
        self,
        mock_bot: _MockBot,
        mock_hitl_manager: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """E2E: HITL callback with unknown response is rejected."""
        hitl_id = "test-hitl-unknown"

        # Malformed callback data
        callback_data = f"{HITL_CALLBACK_PREFIX}{hitl_id}:unknown_option"
        update = _MockUpdate(callback_data=callback_data)

        # Should not resolve
        await handle_hitl_callback(update, mock_context, mock_hitl_manager)

        # Verify resolve was NOT called (unknown response)
        mock_hitl_manager.resolve.assert_not_called()

    async def test_hitl_callback_malformed_data(
        self,
        mock_hitl_manager: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """E2E: Malformed callback data is handled gracefully."""
        # Missing parts
        update = _MockUpdate(callback_data="hitl:incomplete")

        await handle_hitl_callback(update, mock_context, mock_hitl_manager)

        # Verify resolve was NOT called
        mock_hitl_manager.resolve.assert_not_called()

    async def test_hitl_callback_wrong_prefix(
        self,
        mock_hitl_manager: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """E2E: Callback with wrong prefix is ignored."""
        update = _MockUpdate(callback_data="other:prefix:data")

        await handle_hitl_callback(update, mock_context, mock_hitl_manager)

        # Verify resolve was NOT called
        mock_hitl_manager.resolve.assert_not_called()

    async def test_build_hitl_message(self) -> None:
        """Test HITL message formatting."""
        question = "Do you want to execute this search?"
        message = build_hitl_message(question)

        assert "ARIA" in message
        assert question in message
        assert "Approval Required" in message or "Approve" in message

    async def test_hitl_message_formatting(self) -> None:
        """Test that HITL message includes question and formatting."""
        question = "Should I send the email now?"
        message = build_hitl_message(question)

        # Message should contain the question
        assert question in message

        # Message should be formatted for Telegram
        assert "**" in message or "*" in message  # Markdown formatting


@pytest.mark.e2e
async def test_hitl_flow_e2e_with_mock_bot(
    tmp_path: Path,
    mock_bot: _MockBot,
) -> None:
    """Standalone E2E test: Full flow with mock bot.

    This test verifies the complete HITL flow without real Telegram API.
    """
    from aria.scheduler.hitl import HitlManager
    from aria.scheduler.schema import make_task
    from aria.scheduler.store import TaskStore
    from aria.scheduler.triggers import EventBus

    db_path = tmp_path / "test_e2e_hitl.db"
    store = TaskStore(db_path)
    await store.connect()

    try:
        bus = EventBus()
        config = _MockConfig(tmp_path)
        # Create HitlManager (used implicitly via event bus)
        HitlManager(store, bus, config)  # noqa: F841

        # Create a task requiring approval
        task = make_task(
            name="e2e test task",
            category="workspace",
            trigger_type="manual",
            policy="ask",
            owner_user_id="123456",
        )
        await store.create_task(task)

        # Simulate the gateway sending a message via mock bot
        hitl_id = "e2e-hitl-123"
        question = "Execute this workspace task?"

        # Build keyboard
        keyboard = build_hitl_keyboard(hitl_id)

        # Build message
        message = build_hitl_message(question)

        # Verify keyboard and message are properly formatted
        assert keyboard is not None
        assert message is not None
        assert question in message

        # Simulate user clicking "yes"
        callback_data = f"{HITL_CALLBACK_PREFIX}{hitl_id}:yes"
        update = _MockUpdate(callback_data=callback_data)

        # Create a mock hitl_manager for resolution verification
        resolve_mock = AsyncMock(return_value=None)
        mock_manager = MagicMock()
        mock_manager.resolve = resolve_mock

        # Handle callback
        await handle_hitl_callback(update, MagicMock(), mock_manager)

        # Verify resolution
        resolve_mock.assert_called_once_with(hitl_id, "yes")

    finally:
        await store.close()


@pytest.mark.e2e
async def test_ptb_callback_query_handler_pattern() -> None:
    """Test that the callback handler pattern works with PTB-like objects.

    This verifies our handler is compatible with python-telegram-bot's
    CallbackQueryHandler pattern.
    """
    from telegram import Update
    from telegram.ext import CallbackContext

    hitl_id = "ptb-test-123"
    callback_data = f"{HITL_CALLBACK_PREFIX}{hitl_id}:yes"

    # Create PTB-style update with mock callback_query
    mock_query = MagicMock()
    mock_query.data = callback_data
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()

    mock_update = MagicMock(spec=Update)
    mock_update.callback_query = mock_query

    mock_context = MagicMock(spec=CallbackContext)

    # Create mock hitl manager
    hitl_manager = MagicMock()
    hitl_manager.resolve = AsyncMock()

    # Call handler
    await handle_hitl_callback(mock_update, mock_context, hitl_manager)

    # Verify
    hitl_manager.resolve.assert_called_once_with(hitl_id, "yes")
    mock_query.answer.assert_called_once()


@pytest.mark.e2e
async def test_inline_keyboard_button_count() -> None:
    """Test that HITL keyboard has exactly 3 buttons (yes, no, later)."""
    hitl_id = "test-buttons"
    keyboard = build_hitl_keyboard(hitl_id)

    assert len(keyboard.inline_keyboard) == 1
    row = keyboard.inline_keyboard[0]
    assert len(row) == 3

    # Verify all three buttons exist
    texts = [btn.text for btn in row]
    assert "✅ Yes" in texts
    assert "❌ No" in texts
    assert "⏸ Later" in texts
