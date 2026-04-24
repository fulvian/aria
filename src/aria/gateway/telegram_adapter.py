# Telegram Adapter — Telegram bot integration
#
# Stub implementation for Telegram adapter.
#
# Usage:
#   from aria.gateway.telegram_adapter import TelegramAdapter
#
#   adapter = TelegramAdapter(cm, auth, sessions, bus, config)
#   await adapter.start_polling()

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.config import ARIAConfig
    from aria.credentials import CredentialManager
    from aria.gateway.auth import AuthGuard
    from aria.gateway.session_manager import SessionManager
    from aria.scheduler.triggers import EventBus

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """Telegram bot adapter."""

    def __init__(
        self,
        cm: CredentialManager,
        auth: AuthGuard,
        sessions: SessionManager,
        bus: EventBus,
        config: ARIAConfig,
    ) -> None:
        """Initialize TelegramAdapter."""
        self._cm = cm
        self._auth = auth
        self._sessions = sessions
        self._bus = bus
        self._config = config
        self._running = False

    async def start_polling(self) -> None:
        """Start polling for Telegram updates."""
        self._running = True
        logger.info("Telegram adapter started (stub - would start polling)")

    async def stop_polling(self) -> None:
        """Stop polling."""
        self._running = False
        logger.info("Telegram adapter stopped")

    async def handle_gateway_reply(self, payload: dict) -> None:
        """Handle gateway reply event."""
        logger.debug("Would handle gateway reply: %s", payload)
