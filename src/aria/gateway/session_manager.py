# ARIA Gateway Session Manager
#
# Async SQLite session management for multi-user gateway.
# Per blueprint §7.2 and sprint plan W1.2.I.
#
# Schema: gateway_sessions table (see schema.py)
# Operations:
#   - get_or_create(channel, external_user_id, locale="it-IT") -> SessionRow
#   - touch(session_id)
#   - set_state(session_id, state_dict)

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from aria.gateway.schema import SessionRow

logger = logging.getLogger(__name__)

# Default session DB path under ARIA_RUNTIME
DEFAULT_SESSIONS_DB = "gateway/sessions.db"


class SessionManager:
    """Async session manager for gateway_sessions table.

    Uses aiosqlite for all DB operations.
    Per blueprint §7.2 schema definition.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize session manager.

        Args:
            db_path: Optional path to sessions DB. Defaults to ARIA_RUNTIME/gateway/sessions.db.
        """
        if db_path is None:
            from aria.config import get_config

            config = get_config()
            db_path = config.paths.runtime / DEFAULT_SESSIONS_DB

        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    def _require_conn(self) -> aiosqlite.Connection:
        """Return active connection or raise runtime error."""
        if self._conn is None:
            raise RuntimeError("SessionManager not connected. Call connect() first.")
        return self._conn

    async def connect(self) -> None:
        """Initialize DB connection and ensure schema exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        # Create table if not exists
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS gateway_sessions (
                id                TEXT PRIMARY KEY,
                channel           TEXT NOT NULL CHECK (channel IN (
                    'telegram', 'slack', 'whatsapp', 'discord'
                )),
                external_user_id  TEXT NOT NULL,
                aria_session_id   TEXT NOT NULL,
                created_at        INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                last_activity     INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                locale            TEXT DEFAULT 'it-IT',
                state_json        TEXT DEFAULT '{}'
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_gateway_session
                ON gateway_sessions(channel, external_user_id);
            CREATE INDEX IF NOT EXISTS idx_gateway_external
                ON gateway_sessions(external_user_id);
            CREATE INDEX IF NOT EXISTS idx_gateway_activity
                ON gateway_sessions(last_activity);
            """
        )
        await self._conn.commit()
        logger.info("SessionManager connected to %s", self._db_path)

    async def close(self) -> None:
        """Close DB connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("SessionManager closed")

    async def get_or_create(
        self,
        channel: str,
        external_user_id: str,
        locale: str = "it-IT",
    ) -> SessionRow:
        """Get existing session or create new one.

        Args:
            channel: Channel name (e.g. "telegram").
            external_user_id: External platform user ID.
            locale: User locale (default "it-IT").

        Returns:
            SessionRow instance.
        """
        if not self._conn:
            await self.connect()
        conn = self._require_conn()

        now = int(datetime.now(tz=UTC).timestamp())
        session_id = str(uuid4())
        aria_session_id = str(uuid4())  # New ARIA conductor session

        # Try to get existing
        async with conn.execute(
            "SELECT * FROM gateway_sessions WHERE channel=? AND external_user_id=?",
            (channel, str(external_user_id)),
        ) as cursor:
            row = await cursor.fetchone()

        if row is not None:
            # Update last_activity
            await conn.execute(
                "UPDATE gateway_sessions SET last_activity=? WHERE id=?",
                (now, row["id"]),
            )
            await conn.commit()

            return SessionRow(
                id=row["id"],
                channel=row["channel"],
                external_user_id=row["external_user_id"],
                aria_session_id=row["aria_session_id"],
                created_at=row["created_at"],
                last_activity=now,
                locale=row["locale"],
                state_json=row["state_json"] or "{}",
            )

        # Create new session
        await conn.execute(
            """INSERT INTO gateway_sessions
               (id, channel, external_user_id, aria_session_id,
                created_at, last_activity, locale, state_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, '{}')""",
            (session_id, channel, str(external_user_id), aria_session_id, now, now, locale),
        )
        await conn.commit()

        return SessionRow(
            id=session_id,
            channel=channel,
            external_user_id=str(external_user_id),
            aria_session_id=aria_session_id,
            created_at=now,
            last_activity=now,
            locale=locale,
            state_json="{}",
        )

    async def touch(self, session_id: str) -> bool:
        """Update last_activity timestamp for a session.

        Args:
            session_id: Session ID.

        Returns:
            True if session found and updated, False otherwise.
        """
        if not self._conn:
            await self.connect()
        conn = self._require_conn()

        now = int(datetime.now(tz=UTC).timestamp())
        cursor = await conn.execute(
            "UPDATE gateway_sessions SET last_activity=? WHERE id=?",
            (now, session_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def set_state(self, session_id: str, state_dict: dict[str, Any]) -> bool:
        """Set session state from dict.

        Args:
            session_id: Session ID.
            state_dict: State dictionary to serialize.

        Returns:
            True if session found and updated, False otherwise.
        """
        if not self._conn:
            await self.connect()
        conn = self._require_conn()

        state_json = json.dumps(state_dict, ensure_ascii=False)
        cursor = await conn.execute(
            "UPDATE gateway_sessions SET state_json=? WHERE id=?",
            (state_json, session_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def get_session(self, session_id: str) -> SessionRow | None:
        """Get session by ID.

        Args:
            session_id: Session ID.

        Returns:
            SessionRow or None if not found.
        """
        if not self._conn:
            await self.connect()
        conn = self._require_conn()

        async with conn.execute(
            "SELECT * FROM gateway_sessions WHERE id=?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return SessionRow(
            id=row["id"],
            channel=row["channel"],
            external_user_id=row["external_user_id"],
            aria_session_id=row["aria_session_id"],
            created_at=row["created_at"],
            last_activity=row["last_activity"],
            locale=row["locale"],
            state_json=row["state_json"] or "{}",
        )

    async def list_active(self, idle_seconds: int = 3600) -> list[SessionRow]:
        """List sessions with activity within threshold.

        Args:
            idle_seconds: Max seconds since last_activity (default 1h).

        Returns:
            List of active SessionRow instances.
        """
        if not self._conn:
            await self.connect()
        conn = self._require_conn()

        now = int(datetime.now(tz=UTC).timestamp())
        threshold = now - idle_seconds

        rows: list[SessionRow] = []
        async with conn.execute(
            "SELECT * FROM gateway_sessions WHERE last_activity > ? ORDER BY last_activity DESC",
            (threshold,),
        ) as cursor:
            async for row in cursor:
                rows.append(
                    SessionRow(
                        id=row["id"],
                        channel=row["channel"],
                        external_user_id=row["external_user_id"],
                        aria_session_id=row["aria_session_id"],
                        created_at=row["created_at"],
                        last_activity=row["last_activity"],
                        locale=row["locale"],
                        state_json=row["state_json"] or "{}",
                    )
                )
        return rows
