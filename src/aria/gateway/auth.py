# ARIA Gateway — Auth Guard
#
# Whitelist enforcement + HMAC webhook verification.
# Per blueprint §7.3 and sprint plan W1.2.I.
#
# Security invariants:
# - Whitelist check BEFORE any download
# - HMAC uses hmac.compare_digest (timing-safe)
# - Log and silently discard non-whitelisted users

from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


class AuthGuard:
    """Telegram user whitelist + HMAC webhook verification."""

    def __init__(self, whitelist: list[int]) -> None:
        """Initialize auth guard with Telegram user ID whitelist.

        Args:
            whitelist: List of allowed Telegram user IDs.
        """
        self._whitelist: set[int] = set(whitelist)
        logger.info("AuthGuard initialized with %d whitelisted users", len(self._whitelist))

    def is_allowed_telegram_user(self, user_id: int) -> bool:
        """Check if a Telegram user is whitelisted.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if user is whitelisted, False otherwise.
        """
        allowed = user_id in self._whitelist
        if not allowed:
            logger.warning(
                "Unauthorized Telegram user attempted access: user_id=%d",
                user_id,
            )
        return allowed

    def verify_webhook_hmac(
        self,
        body: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify HMAC-SHA256 signature of webhook payload.

        Uses timing-safe comparison to prevent timing attacks.

        Args:
            body: Raw request body bytes.
            signature: Expected HMAC signature (hex-encoded).
            secret: Webhook secret string.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not body or not signature or not secret:
            logger.warning("HMAC verification called with missing parameters")
            return False

        # Compute expected HMAC
        expected = hmac.new(
            key=secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        normalized_signature = signature.strip().lower()
        if normalized_signature.startswith("sha256="):
            normalized_signature = normalized_signature.split("=", 1)[1]

        # Timing-safe comparison
        valid = hmac.compare_digest(expected, normalized_signature)

        if not valid:
            logger.warning(
                "HMAC verification failed: provided signature length=%d",
                len(signature),
            )

        return valid
