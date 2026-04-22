# ARIA Gateway Session Schema
#
# Pydantic models matching gateway_sessions table from sqlite_full.sql.
# Per blueprint §7.2 and sprint plan W1.2.I.
#
# Schema:
#   gateway_sessions (
#     id TEXT PRIMARY KEY,
#     channel TEXT NOT NULL,
#     external_user_id TEXT NOT NULL,
#     aria_session_id TEXT NOT NULL,
#     created_at INTEGER NOT NULL,
#     last_activity INTEGER NOT NULL,
#     locale TEXT DEFAULT 'it-IT',
#     state_json TEXT DEFAULT '{}'
#   )

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionRow(BaseModel):
    """Gateway session row matching gateway_sessions SQLite table.

    Per blueprint §7.2 schema definition.
    """

    id: str = Field(description="Primary key (UUID)")
    channel: str = Field(description="Channel identifier (telegram|slack|whatsapp|discord)")
    external_user_id: str = Field(description="External platform user ID")
    aria_session_id: str = Field(description="ARIA conductor session ID")
    created_at: int = Field(description="Creation timestamp (epoch seconds)")
    last_activity: int = Field(description="Last activity timestamp (epoch seconds)")
    locale: str = Field(default="it-IT", description="User locale")
    state_json: str = Field(default="{}", description="Serialized state dict")

    @property
    def state(self) -> dict[str, Any]:
        """Deserialize state_json to dict."""
        import json

        try:
            parsed = json.loads(self.state_json)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}

    def update_state(self, updates: dict[str, Any]) -> None:
        """Update state dict and serialize back to JSON."""
        import json

        current = self.state
        current.update(updates)
        self.state_json = json.dumps(current, ensure_ascii=False)

    def is_active(self, idle_seconds: int = 3600) -> bool:
        """Check if session is considered active.

        Args:
            idle_seconds: Max seconds since last_activity (default 1h).

        Returns:
            True if last_activity within idle threshold.
        """
        return (self.last_activity + idle_seconds) > int(datetime.now(tz=UTC).timestamp())

    class Config:
        # Allow field validation on assignment
        validate_assignment = True
