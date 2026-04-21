# Episodic Store - SQLite WAL + FTS5
#
# Tier 0 episodic memory store with FTS5 full-text search.
# Per blueprint §5.2, §6.1.1 and sprint plan W1.1.I.
#
# Features:
# - WAL mode for concurrent reads/writes
# - FTS5 virtual table for full-text search
# - Tombstone support for soft delete (no hard delete per P6)
# - PRAGMA settings for reliability
# - SQLite version check (>= 3.51.3)
#
# Usage:
#   from aria.memory.episodic import EpisodicStore
#
#   store = EpisodicStore(db_path, config)
#   await store.connect()
#   await store.insert(entry)
#   results = await store.search_text("hello world", top_k=10)

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, UUID, uuid5

import aiosqlite

from aria.memory.migrations import MigrationRunner
from aria.memory.schema import (
    Actor,
    EpisodicEntry,
    MemoryStats,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from uuid import UUID

    from aria.config import ARIAConfig

# === Version Check ===

MIN_SQLITE_VERSION = (3, 51, 3)


def version_tuple(version_str: str) -> tuple[int, int, int]:
    """Parse SQLite version string to tuple."""
    parts = version_str.split(".")
    values = [int(p) for p in parts[:3]]
    while len(values) < 3:
        values.append(0)
    return (values[0], values[1], values[2])


# === EpisodicStore ===


class EpisodicStore:
    """Tier 0 episodic memory store with FTS5 search.

    Per blueprint P6 - Verbatim Preservation:
    - NO UPDATE on content, content_hash, actor, role, session_id, ts
    - Only INSERT and tombstone operations
    """

    # PRAGMA settings per blueprint §6.1.1
    PRAGMAS = [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA foreign_keys=ON",
        "PRAGMA wal_autocheckpoint=1000",
        "PRAGMA busy_timeout=5000",
    ]

    def __init__(self, db_path: Path, config: ARIAConfig) -> None:
        """Initialize episodic store.

        Args:
            db_path: Path to episodic.db
            config: AriaConfig instance
        """
        self._db_path = db_path.resolve()
        self._config = config
        self._conn: aiosqlite.Connection | None = None
        self._migrations = MigrationRunner(self._db_path)

    async def connect(self) -> None:
        """Connect to database and apply migrations.

        Raises:
            MemoryError: if SQLite version < 3.51.3
            OSError: if database cannot be opened
        """
        # Ensure directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open connection
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        # Apply PRAGMAs
        for pragma in self.PRAGMAS:
            await self._conn.execute(pragma)

        # Check SQLite version
        cursor = await self._conn.execute("SELECT sqlite_version()")
        row = await cursor.fetchone()
        version = row[0] if row else "0"

        if version_tuple(version) < MIN_SQLITE_VERSION:
            await self._conn.close()
            self._conn = None
            raise MemoryError(f"SQLite {version} < 3.51.3 required (blueprint §6.1.1)")

        # Run migrations
        await self._migrations.run(self._conn)

        # Verify FTS5 is available
        cursor = await self._conn.execute("PRAGMA compile_options")
        options = [row[0] for row in await cursor.fetchall()]
        if "ENABLE_FTS5" not in options:
            logging.warning("FTS5 not compiled in SQLite - full-text search may not work")

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _ensure_connected(self) -> aiosqlite.Connection:
        """Ensure connection is open."""
        if self._conn is None:
            await self.connect()
        return self._conn  # type: ignore[return-value]

    # === Insert Operations ===

    async def insert(self, entry: EpisodicEntry) -> None:
        """Insert a single episodic entry.

        Per P6: Only INSERT, no UPDATE on content columns.

        Args:
            entry: EpisodicEntry to insert
        """
        conn = await self._ensure_connected()

        # Convert to storage format
        # Store ts as Unix timestamp (integer)
        ts_int = int(entry.ts.timestamp())

        # Serialize tags and meta as JSON
        tags_json = json.dumps(entry.tags)
        meta_json = json.dumps(entry.meta)

        await conn.execute(
            """
            INSERT INTO episodic (id, session_id, ts, actor, role, content, content_hash, tags, meta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(entry.id),
                str(entry.session_id),
                ts_int,
                entry.actor.value if isinstance(entry.actor, Actor) else entry.actor,
                entry.role,
                entry.content,
                entry.content_hash,
                tags_json,
                meta_json,
            ),
        )
        await conn.commit()

    async def insert_many(self, entries: Sequence[EpisodicEntry]) -> None:
        """Insert multiple episodic entries.

        Args:
            entries: Sequence of EpisodicEntry to insert
        """
        conn = await self._ensure_connected()

        # Use executemany for batch insert
        rows = []
        for entry in entries:
            ts_int = int(entry.ts.timestamp())
            tags_json = json.dumps(entry.tags)
            meta_json = json.dumps(entry.meta)

            rows.append(
                (
                    str(entry.id),
                    str(entry.session_id),
                    ts_int,
                    entry.actor.value if isinstance(entry.actor, Actor) else entry.actor,
                    entry.role,
                    entry.content,
                    entry.content_hash,
                    tags_json,
                    meta_json,
                )
            )

        await conn.executemany(
            """
            INSERT INTO episodic (id, session_id, ts, actor, role, content, content_hash, tags, meta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await conn.commit()

    async def add(
        self,
        *,
        session_id: str | UUID,
        actor: Actor,
        role: str,
        content: str,
        tags: list[str] | None = None,
        meta: dict[str, object] | None = None,
    ) -> EpisodicEntry:
        """Compatibility helper used by gateway and search modules.

        Accepts string session IDs and maps non-UUID values deterministically
        to UUIDv5 to preserve stable grouping.
        """
        if isinstance(session_id, UUID):
            session_uuid = session_id
        else:
            try:
                session_uuid = UUID(str(session_id))
            except ValueError:
                session_uuid = uuid5(NAMESPACE_URL, f"aria-session:{session_id}")

        role_value = role if role in {"user", "assistant", "system", "tool"} else "system"
        entry = EpisodicEntry(
            session_id=session_uuid,
            ts=datetime.now(UTC),
            actor=actor,
            role=role_value,
            content=content,
            tags=tags or [],
            meta=meta or {},
        )
        await self.insert(entry)
        return entry

    # === Query Operations ===

    async def get(self, id: UUID) -> EpisodicEntry | None:
        """Get a single entry by ID.

        Args:
            id: Entry UUID

        Returns:
            EpisodicEntry or None if not found
        """
        conn = await self._ensure_connected()

        cursor = await conn.execute(
            """
            SELECT e.* FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE e.id = ? AND t.episodic_id IS NULL
            """,
            (str(id),),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_entry(row)

    async def list_by_session(
        self,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EpisodicEntry]:
        """List entries for a session.

        Args:
            session_id: Session UUID
            limit: Max entries to return
            offset: Offset for pagination

        Returns:
            List of EpisodicEntry
        """
        conn = await self._ensure_connected()

        cursor = await conn.execute(
            """
            SELECT e.* FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE e.session_id = ? AND t.episodic_id IS NULL
            ORDER BY e.ts ASC
            LIMIT ? OFFSET ?
            """,
            (str(session_id), limit, offset),
        )
        rows = await cursor.fetchall()

        return [self._row_to_entry(row) for row in rows]

    async def list_by_time_range(
        self,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[EpisodicEntry]:
        """List entries in a time range.

        Args:
            since: Start time
            until: End time
            limit: Max entries to return

        Returns:
            List of EpisodicEntry
        """
        conn = await self._ensure_connected()

        since_int = int(since.timestamp())
        until_int = int(until.timestamp())

        cursor = await conn.execute(
            """
            SELECT e.* FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE e.ts >= ? AND e.ts <= ? AND t.episodic_id IS NULL
            ORDER BY e.ts ASC
            LIMIT ?
            """,
            (since_int, until_int, limit),
        )
        rows = await cursor.fetchall()

        return [self._row_to_entry(row) for row in rows]

    async def search_text(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[EpisodicEntry]:
        """Search entries using FTS5.

        Note: FTS5 searches the episodic content directly.
        For semantic search, use SemanticStore with CLM distillation.

        Args:
            query: Full-text search query
            top_k: Number of results to return

        Returns:
            List of matching EpisodicEntry
        """
        conn = await self._ensure_connected()

        # Use FTS5 MATCH for full-text search
        # Escape special characters
        fts_query = query.replace('"', '""')

        try:
            cursor = await conn.execute(
                """
                SELECT e.* FROM episodic e
                JOIN episodic_fts ON episodic_fts.rowid = e.rowid
                LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
                WHERE episodic_fts MATCH ? AND t.episodic_id IS NULL
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top_k),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        except Exception:
            # FTS5 table might not exist or query failed
            # Fall back to LIKE search
            cursor = await conn.execute(
                """
                SELECT e.* FROM episodic e
                LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
                WHERE e.content LIKE ? ESCAPE '\\' AND t.episodic_id IS NULL
                ORDER BY e.ts DESC
                LIMIT ?
                """,
                (f"%{query}%", top_k),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]

    async def search_by_tag(
        self,
        tag: str,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Search entries by tag.

        SQLite stores tags as JSON text; filtering is applied in Python for
        maximum compatibility with SQLite builds that may not include JSON1.
        """
        conn = await self._ensure_connected()

        lower_bound = int((since or datetime.fromtimestamp(0, tz=UTC)).timestamp())
        upper_bound = int((until or datetime.now(UTC)).timestamp())

        cursor = await conn.execute(
            """
            SELECT e.* FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE e.ts >= ? AND e.ts <= ? AND t.episodic_id IS NULL
            ORDER BY e.ts DESC
            LIMIT ?
            """,
            (lower_bound, upper_bound, max(limit * 5, limit)),
        )
        rows = await cursor.fetchall()

        results: list[dict[str, object]] = []
        for row in rows:
            entry = self._row_to_entry(row)
            if tag not in entry.tags:
                continue
            results.append(
                {
                    "id": str(entry.id),
                    "session_id": str(entry.session_id),
                    "ts": entry.ts.isoformat(),
                    "actor": entry.actor.value,
                    "role": entry.role,
                    "content": entry.content,
                    "tags": entry.tags,
                    "meta": entry.meta,
                }
            )
            if len(results) >= limit:
                break

        return results

    # === Soft Delete (Tombstone) ===

    async def tombstone(
        self,
        id: UUID,
        reason: str,
        actor_user_id: str | None = None,
    ) -> bool:
        """Soft delete an entry (tombstone).

        Per P6: NO hard delete. Tombstone records the deletion request.

        Args:
            id: Entry UUID to tombstone
            reason: Reason for deletion
            actor_user_id: Optional user ID who requested deletion

        Returns:
            True if entry was found and tombstoned, False otherwise
        """
        conn = await self._ensure_connected()

        # Check entry exists and not already tombstoned
        cursor = await conn.execute(
            "SELECT id FROM episodic WHERE id = ?",
            (str(id),),
        )
        row = await cursor.fetchone()

        if not row:
            return False

        # Insert tombstone record
        import time as _time

        await conn.execute(
            """
            INSERT OR REPLACE INTO episodic_tombstones (episodic_id, tombstoned_at, reason, actor_user_id)
            VALUES (?, ?, ?, ?)
            """,
            (str(id), int(_time.time()), reason, actor_user_id),
        )
        await conn.commit()

        return True

    async def enqueue_hitl(
        self,
        target_id: UUID,
        action: str,
        reason: str | None = None,
        trace_id: str | None = None,
        channel: str = "cli",
    ) -> str:
        """Create a HITL pending queue record.

        Returns the newly created hitl request ID.
        """
        conn = await self._ensure_connected()
        import uuid as _uuid

        hitl_id = str(_uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO memory_hitl_pending (id, target_id, action, reason, trace_id, channel, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                hitl_id,
                str(target_id),
                action,
                reason,
                trace_id,
                channel,
                int(time.time()),
            ),
        )
        await conn.commit()
        return hitl_id

    async def list_hitl_pending(self, limit: int = 100) -> list[dict[str, str | int | None]]:
        """List pending HITL records for memory operations."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            """
            SELECT id, target_id, action, reason, trace_id, channel, status, created_at, resolved_at
            FROM memory_hitl_pending
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "target_id": row["target_id"],
                "action": row["action"],
                "reason": row["reason"],
                "trace_id": row["trace_id"],
                "channel": row["channel"],
                "status": row["status"],
                "created_at": row["created_at"],
                "resolved_at": row["resolved_at"],
            }
            for row in rows
        ]

    # === Maintenance ===

    async def vacuum_wal(self) -> None:
        """Checkpoint and vacuum WAL.

        Per blueprint §6.1.1: manual checkpoint recommended every 6h.
        """
        conn = await self._ensure_connected()
        await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await conn.execute("VACUUM")

    async def stats(self) -> MemoryStats:
        """Get memory statistics.

        Returns:
            MemoryStats with current metrics
        """
        conn = await self._ensure_connected()

        # Count T0 entries
        cursor = await conn.execute(
            """
            SELECT COUNT(*) FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE t.episodic_id IS NULL
            """
        )
        row = await cursor.fetchone()
        t0_count = row[0] if row else 0

        # Count T1 (semantic chunks)
        cursor = await conn.execute("SELECT COUNT(*) FROM semantic_chunks")
        row = await cursor.fetchone()
        t1_count = row[0] if row else 0

        # Count unique sessions
        cursor = await conn.execute(
            """
            SELECT COUNT(DISTINCT session_id) FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE t.episodic_id IS NULL
            """
        )
        row = await cursor.fetchone()
        sessions = row[0] if row else 0

        # Last session timestamp
        cursor = await conn.execute(
            """
            SELECT MAX(ts) FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE t.episodic_id IS NULL
            """
        )
        row = await cursor.fetchone()
        last_ts = row[0] if row else None
        last_session_ts = datetime.fromtimestamp(last_ts, tz=UTC) if last_ts else None

        # Average entry size
        cursor = await conn.execute(
            """
            SELECT AVG(LENGTH(content)) FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE t.episodic_id IS NULL
            """
        )
        row = await cursor.fetchone()
        avg_entry_size = row[0] if row else 0.0

        # DB file size
        import os

        storage_bytes = os.path.getsize(self._db_path) if self._db_path.exists() else 0

        return MemoryStats(
            t0_count=t0_count,
            t1_count=t1_count,
            sessions=sessions,
            last_session_ts=last_session_ts,
            avg_entry_size=float(avg_entry_size),
            storage_bytes=storage_bytes,
        )

    def _row_to_entry(self, row: aiosqlite.Row) -> EpisodicEntry:
        """Convert database row to EpisodicEntry."""
        from uuid import UUID as _UUID

        ts_int = row["ts"]
        ts = datetime.fromtimestamp(ts_int, tz=UTC)

        tags = json.loads(row["tags"]) if row["tags"] else []
        meta = json.loads(row["meta"]) if row["meta"] else {}

        return EpisodicEntry(
            id=_UUID(row["id"]),
            session_id=_UUID(row["session_id"]),
            ts=ts,
            actor=Actor(row["actor"]),
            role=row["role"],
            content=row["content"],
            content_hash=row["content_hash"],
            tags=tags,
            meta=meta,
        )


# === Factory Function ===


async def create_episodic_store(config: ARIAConfig) -> EpisodicStore:
    """Create and connect an EpisodicStore.

    Args:
        config: AriaConfig instance

    Returns:
        Connected EpisodicStore
    """
    db_path = config.paths.runtime / "memory" / "episodic.db"
    store = EpisodicStore(db_path, config)
    await store.connect()
    return store
