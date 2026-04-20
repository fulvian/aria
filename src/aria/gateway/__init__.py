# ARIA gateway module
#
# External channel adapter for human interaction:
# - Telegram (python-telegram-bot v22 async)
# - Session management (multi-user, isolated)
# - Auth/whitelist + HMAC for webhooks
# - Multimodal handlers (OCR, STT)
#
# Usage:
#   from aria.gateway import GatewayDaemon
#   gateway = GatewayDaemon(token=token)

from __future__ import annotations

__all__ = ["GatewayDaemon"]


class GatewayDaemon:
    """Gateway daemon stub - full implementation in Phase 1."""

    def __init__(self, token: str | None = None) -> None:
        """Initialize gateway daemon."""
        pass

    def start(self) -> None:
        """Start the gateway."""
        pass

    def stop(self) -> None:
        """Stop the gateway."""
        pass
