# SessionManager — Gateway session management
#
# Stub implementation for session management.
#
# Usage:
#   from aria.gateway.session_manager import SessionManager
#
#   sessions = SessionManager(db_path)
#   session = await sessions.get_or_create(user_id)

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class SessionManager:
    """Manages gateway sessions."""

    def __init__(self, db_path: Path) -> None:
        """Initialize SessionManager.

        Args:
            db_path: Path to sessions.db
        """
        self._db_path = db_path
        self._sessions: dict[str, dict] = {}

    async def get_or_create(self, user_id: str) -> dict[str, Any]:
        """Get or create a session for a user."""
        if user_id not in self._sessions:
            self._sessions[user_id] = {
                "user_id": user_id,
                "created_at": int(time.time() * 1000),
                "last_active": int(time.time() * 1000),
            }
        else:
            self._sessions[user_id]["last_active"] = int(time.time() * 1000)
        return self._sessions[user_id]

    async def update(self, user_id: str, data: dict[str, Any]) -> None:
        """Update session data."""
        if user_id in self._sessions:
            self._sessions[user_id].update(data)

    async def close(self) -> None:
        """Close session manager."""
        pass  # Stub - no cleanup needed
