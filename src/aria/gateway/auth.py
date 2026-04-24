# AuthGuard — Authentication guard for Telegram
#
# Stub implementation for authentication.
#
# Usage:
#   from aria.gateway.auth import AuthGuard
#
#   auth = AuthGuard(whitelist=[123456])
#   auth.authorize(user_id)  # raises if unauthorized

from __future__ import annotations


class AuthGuard:
    """Authentication guard for gateway."""

    def __init__(self, whitelist: list[int] | None = None) -> None:
        """Initialize AuthGuard.

        Args:
            whitelist: List of authorized user IDs
        """
        self._whitelist = set(whitelist or [])

    def authorize(self, user_id: int | str) -> bool:
        """Authorize a user.

        Args:
            user_id: The user ID to authorize

        Returns:
            True if authorized

        Raises:
            PermissionError: if user is not in whitelist
        """
        uid = int(user_id)
        if self._whitelist and uid not in self._whitelist:
            raise PermissionError(f"User {uid} not authorized")
        return True

    def add_to_whitelist(self, user_id: int) -> None:
        """Add a user to the whitelist."""
        self._whitelist.add(user_id)

    def remove_from_whitelist(self, user_id: int) -> None:
        """Remove a user from the whitelist."""
        self._whitelist.discard(user_id)
