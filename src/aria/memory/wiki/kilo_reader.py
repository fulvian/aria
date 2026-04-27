# ARIA Memory Wiki — Kilo DB Reader
#
# Per docs/plans/auto_persistence_echo.md §4.2 + §5.3.
#
# Read-only access to kilo.db for:
# - Schema fingerprint verification (P2: upstream invariance)
# - Message range queries for watchdog catch-up
# - Session listing for gap detection
#
# ARIA NEVER writes to kilo.db. Read-only access only.
#
# Usage:
#   from aria.memory.wiki.kilo_reader import KiloReader
#   reader = KiloReader(kilo_db_path)
#   await reader.connect()
#   sessions = await reader.list_conductor_sessions()

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiosqlite

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# === Known Schema Fingerprint ===
# SHA256 of expected kilo.db message/part column definitions.
# Computed from PRAGMA table_info() output: "table:name:type:dflt_value" sorted.
# This fingerprint should be updated when Kilo upgrades change message/part schema.

_KNOWN_FINGERPRINT: str | None = None  # Set during first check

_KILO_DB_SCHEMA_TABLES = ["message", "part"]


@dataclass
class KiloMessage:
    """A message from kilo.db (read-only)."""

    id: str
    session_id: str
    role: str
    content: str
    time_created: int  # unix epoch millis


@dataclass
class KiloSessionInfo:
    """Summary of a kilo session for gap detection."""

    session_id: str
    last_msg_ts: int  # unix epoch millis
    msg_count: int


class KiloReader:
    """Read-only reader for kilo.db.

    Per plan §4.2: schema fingerprint check on boot.
    Per plan §5.3: message range queries for watchdog catch-up.

    Attributes:
        db_path: Path to kilo.db.
        schema_ok: Whether schema fingerprint matches known-good.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize KiloReader.

        Args:
            db_path: Path to kilo.db (Kilo's SQLite database).
        """
        from pathlib import Path as _Path

        self._db_path = _Path(db_path).resolve()
        self._conn: aiosqlite.Connection | None = None
        self.schema_ok: bool = False
        self._fingerprint: str | None = None

    @property
    def db_path(self) -> Path:
        """Return the database path."""
        return self._db_path

    @property
    def fingerprint(self) -> str | None:
        """Return the computed schema fingerprint, if checked."""
        return self._fingerprint

    async def connect(self) -> None:
        """Open read-only connection to kilo.db and verify schema.

        Per plan §4.2: runs PRAGMA table_info on message/part tables,
        compares hash to known fingerprint. Mismatch → log warning,
        refuse catch-up writes (read-only mode still available).
        """
        if not self._db_path.exists():  # noqa: ASYNC240
            logger.warning("kilo.db not found at %s — watchdog disabled", self._db_path)
            self.schema_ok = False
            return

        # Open in read-only mode (immutable=1 for safety)
        uri = f"file:{self._db_path}?mode=ro&nolock=1&immutable=1"
        try:
            self._conn = await aiosqlite.connect(uri, uri=True)
            self._conn.row_factory = aiosqlite.Row
        except Exception as exc:
            logger.error("Failed to open kilo.db read-only: %s", exc)
            self.schema_ok = False
            return

        # Verify schema fingerprint
        self._fingerprint = await self._compute_fingerprint()
        if self._fingerprint is None:
            logger.warning("Could not compute kilo.db schema fingerprint")
            self.schema_ok = False
            return

        if _KNOWN_FINGERPRINT is None:
            # First run: accept whatever schema we find
            logger.info(
                "kilo.db schema fingerprint: %s (accepted, no known fingerprint set)",
                self._fingerprint[:16],
            )
            self.schema_ok = True
        elif self._fingerprint == _KNOWN_FINGERPRINT:
            logger.info("kilo.db schema fingerprint verified")
            self.schema_ok = True
        else:
            logger.warning(
                "kilo.db schema fingerprint MISMATCH! "
                "Expected: %s, Got: %s. Catch-up writes disabled.",
                _KNOWN_FINGERPRINT[:16],
                self._fingerprint[:16],
            )
            self.schema_ok = False

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _ensure_connected(self) -> aiosqlite.Connection:
        """Ensure connection is open."""
        if self._conn is None:
            await self.connect()
        if self._conn is None:
            raise RuntimeError("Failed to establish kilo.db connection")
        return self._conn

    async def _compute_fingerprint(self) -> str | None:
        """Compute SHA256 fingerprint of kilo.db message/part schema.

        Returns:
            Hex digest of schema fingerprint, or None on error.
        """
        conn = await self._ensure_connected()

        schema_parts: list[str] = []
        try:
            for table in _KILO_DB_SCHEMA_TABLES:
                cursor = await conn.execute(f"PRAGMA table_info({table})")
                rows = await cursor.fetchall()
                # Columns: cid, name, type, notnull, dflt_value, pk
                for row in rows:
                    schema_parts.append(f"{table}:{row[1]}:{row[2]}:{row[4]}")
        except Exception as exc:
            logger.warning("Failed to read kilo.db schema: %s", exc)
            return None

        if not schema_parts:
            return None

        combined = "|".join(sorted(schema_parts))
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    async def list_conductor_sessions(
        self,
        min_messages: int = 3,
        since_ts: int | None = None,
    ) -> list[KiloSessionInfo]:
        """List kilo sessions with conductor messages, for gap detection.

        Per plan §5.3: queries kilo.db for sessions with aria-conductor
        messages, returns session summary with last message timestamp
        and message count.

        Args:
            min_messages: Minimum messages to consider a session.
            since_ts: Only include sessions with messages after this timestamp.

        Returns:
            List of KiloSessionInfo sorted by last_msg_ts DESC.
        """
        conn = await self._ensure_connected()

        sql = """
            SELECT
                session_id,
                MAX(time_created) as last_ts,
                COUNT(*) as msg_count
            FROM message
            WHERE 1=1
        """
        params: list[Any] = []

        if since_ts is not None:
            sql += " AND time_created >= ?"
            params.append(since_ts)

        sql += " GROUP BY session_id HAVING COUNT(*) >= ?"
        params.append(min_messages)
        sql += " ORDER BY last_ts DESC"

        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
        except Exception as exc:
            logger.warning("Failed to list conductor sessions: %s", exc)
            return []

        return [
            KiloSessionInfo(
                session_id=row["session_id"],
                last_msg_ts=row["last_ts"],
                msg_count=row["msg_count"],
            )
            for row in rows
        ]

    async def get_messages_range(
        self,
        session_id: str,
        after_ts: int | None = None,
        limit: int = 100,
    ) -> list[KiloMessage]:
        """Get messages from kilo.db for a session within a time range.

        Per plan §5.3: used by watchdog to fetch unprocessed messages
        for catch-up curation.

        Args:
            session_id: Kilo session ID.
            after_ts: Only messages after this timestamp (millis).
            limit: Maximum messages to return.

        Returns:
            List of KiloMessage sorted by time_created ASC.
        """
        conn = await self._ensure_connected()

        sql = """
            SELECT id, session_id, role, content, time_created
            FROM message
            WHERE session_id = ?
        """
        params: list[Any] = [session_id]

        if after_ts is not None:
            sql += " AND time_created > ?"
            params.append(after_ts)

        sql += " ORDER BY time_created ASC LIMIT ?"
        params.append(limit)

        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
        except Exception as exc:
            logger.warning("Failed to get messages for session %s: %s", session_id, exc)
            return []

        return [
            KiloMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"] or "",
                time_created=row["time_created"],
            )
            for row in rows
        ]

    async def get_session_last_ts(self, session_id: str) -> int | None:
        """Get the last message timestamp for a session.

        Args:
            session_id: Kilo session ID.

        Returns:
            Unix epoch millis, or None if no messages.
        """
        conn = await self._ensure_connected()

        try:
            cursor = await conn.execute(
                "SELECT MAX(time_created) as last_ts FROM message WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            return row["last_ts"] if row and row["last_ts"] else None
        except Exception as exc:
            logger.warning("Failed to get last ts for session %s: %s", session_id, exc)
            return None

    async def health_check(self) -> dict[str, Any]:
        """Health check for kilo.db reader.

        Returns:
            Dict with status, fingerprint, and connectivity info.
        """
        exists = self._db_path.exists()
        return {
            "kilo_db_path": str(self._db_path),
            "kilo_db_exists": exists,
            "schema_ok": self.schema_ok,
            "fingerprint": self._fingerprint[:16] + "..." if self._fingerprint else None,
            "connected": self._conn is not None,
        }
