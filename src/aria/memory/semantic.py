# Semantic Store - FTS5 wrapper for Tier 1
#
# Thin wrapper around semantic_chunks table and FTS5 virtual table.
# Per blueprint §5.2 and sprint plan W1.1.K.
#
# Note: T2 (LanceDB embeddings) is stub-only in Sprint 1.1
# with NotImplementedError controlled by ARIA_MEMORY_T2=0.
#
# Usage:
#   from aria.memory.semantic import SemanticStore
#
#   store = SemanticStore(db_path)
#   chunks = await store.search("preferences", top_k=5)

# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from aria.memory.schema import Actor, SemanticChunk

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    import aiosqlite

    from aria.config import ARIAConfig

# === SemanticStore ===


class SemanticStore:
    """Tier 1 semantic memory store.

    Stores distilled semantic chunks derived from episodic T0 entries.
    Provides FTS5 search over semantic text and keywords.
    """

    # SQL statements
    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS semantic_chunks (
        id TEXT PRIMARY KEY,
        source_episodic_ids TEXT NOT NULL,
        actor TEXT NOT NULL CHECK (actor IN ('user_input', 'tool_output', 'agent_inference', 'system_event')),
        kind TEXT NOT NULL CHECK (kind IN ('fact', 'preference', 'decision', 'action_item', 'concept')),
        text TEXT NOT NULL,
        keywords TEXT DEFAULT '[]',
        confidence REAL DEFAULT 1.0,
        first_seen INTEGER NOT NULL,
        last_seen INTEGER NOT NULL,
        occurrences INTEGER DEFAULT 1,
        embedding_id TEXT,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
    )
    """

    CREATE_FTS = """
    CREATE VIRTUAL TABLE IF NOT EXISTS semantic USING fts5(
        id,
        source_episodic_ids,
        actor,
        kind,
        text,
        keywords,
        confidence,
        first_seen,
        last_seen,
        occurrences,
        embedding_id,
        content='semantic_chunks',
        content_rowid='rowid'
    )
    """

    CREATE_INDEXES = """
    CREATE INDEX IF NOT EXISTS idx_chunks_actor ON semantic_chunks(actor);
    CREATE INDEX IF NOT EXISTS idx_chunks_kind ON semantic_chunks(kind);
    CREATE INDEX IF NOT EXISTS idx_chunks_first_seen ON semantic_chunks(first_seen);
    """

    def __init__(self, db_path: Path, config: ARIAConfig) -> None:
        """Initialize semantic store.

        Args:
            db_path: Path to episodic.db (same as episodic store)
            config: AriaConfig instance
        """
        self._db_path = db_path.resolve()
        self._config = config
        self._conn: aiosqlite.Connection | None = None

    async def connect(self, conn: aiosqlite.Connection) -> None:
        """Set up semantic tables (called after episodic DB is set up).

        Args:
            conn: Open database connection
        """
        self._conn = conn

        # Create tables
        await conn.execute(self.CREATE_TABLE)
        await conn.execute(self.CREATE_FTS)
        await conn.executescript(self.CREATE_INDEXES)
        await conn.commit()

    async def insert(self, chunk: SemanticChunk) -> None:
        """Insert a semantic chunk.

        Args:
            chunk: SemanticChunk to insert
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        source_ids_json = json.dumps([str(id) for id in chunk.source_episodic_ids])
        keywords_json = json.dumps(chunk.keywords)
        first_seen_int = int(chunk.first_seen.timestamp())
        last_seen_int = int(chunk.last_seen.timestamp())

        await self._conn.execute(
            """
            INSERT INTO semantic_chunks (id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(chunk.id),
                source_ids_json,
                chunk.actor.value if isinstance(chunk.actor, Actor) else chunk.actor,
                chunk.kind,
                chunk.text,
                keywords_json,
                chunk.confidence,
                first_seen_int,
                last_seen_int,
                chunk.occurrences,
                str(chunk.embedding_id) if chunk.embedding_id else None,
            ),
        )
        await self._conn.commit()

    async def insert_many(self, chunks: list[SemanticChunk]) -> None:
        """Insert multiple semantic chunks.

        Args:
            chunks: List of SemanticChunk to insert
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        rows = []
        for chunk in chunks:
            source_ids_json = json.dumps([str(id) for id in chunk.source_episodic_ids])
            keywords_json = json.dumps(chunk.keywords)
            first_seen_int = int(chunk.first_seen.timestamp())
            last_seen_int = int(chunk.last_seen.timestamp())

            rows.append(
                (
                    str(chunk.id),
                    source_ids_json,
                    chunk.actor.value if isinstance(chunk.actor, Actor) else chunk.actor,
                    chunk.kind,
                    chunk.text,
                    keywords_json,
                    chunk.confidence,
                    first_seen_int,
                    last_seen_int,
                    chunk.occurrences,
                    str(chunk.embedding_id) if chunk.embedding_id else None,
                )
            )

        await self._conn.executemany(
            """
            INSERT INTO semantic_chunks (id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await self._conn.commit()

    async def get(self, id: UUID) -> SemanticChunk | None:
        """Get a chunk by ID.

        Args:
            id: Chunk UUID

        Returns:
            SemanticChunk or None
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        cursor = await self._conn.execute(
            "SELECT * FROM semantic_chunks WHERE id = ?",
            (str(id),),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_chunk(row)

    async def list_by_session(self, session_id: UUID, limit: int = 50) -> list[SemanticChunk]:
        """List chunks from a session's source episodic entries.

        Args:
            session_id: Session UUID
            limit: Max results

        Returns:
            List of SemanticChunk
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        # Find chunks that have source_episodic_ids containing entries from this session
        # This requires joining with episodic table
        cursor = await self._conn.execute(
            """
            SELECT DISTINCT c.* FROM semantic_chunks c
            JOIN episodic e ON e.id IN (SELECT value FROM json_each(c.source_episodic_ids))
            WHERE e.session_id = ?
            ORDER BY c.first_seen DESC
            LIMIT ?
            """,
            (str(session_id), limit),
        )
        rows = await cursor.fetchall()

        return [self._row_to_chunk(row) for row in rows]

    async def list_by_kind(
        self,
        kind: Literal["fact", "preference", "decision", "action_item", "concept"],
        limit: int = 50,
    ) -> list[SemanticChunk]:
        """List chunks by kind.

        Args:
            kind: Chunk type
            limit: Max results

        Returns:
            List of SemanticChunk
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        cursor = await self._conn.execute(
            "SELECT * FROM semantic_chunks WHERE kind = ? ORDER BY first_seen DESC LIMIT ?",
            (kind, limit),
        )
        rows = await cursor.fetchall()

        return [self._row_to_chunk(row) for row in rows]

    async def search(
        self,
        query: str,
        top_k: int = 10,
        kinds: list[str] | None = None,
    ) -> list[SemanticChunk]:
        """Full-text search over semantic chunks.

        Args:
            query: Search query
            top_k: Max results
            kinds: Optional filter by chunk kinds

        Returns:
            List of matching SemanticChunk
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        # Try FTS5 search first
        try:
            fts_query = query.replace('"', '""')

            kind_filter = ""
            params: tuple[str, ...] = (fts_query,)
            if kinds:
                kind_filter = f"AND kind IN ({','.join('?' * len(kinds))})"
                params = (fts_query, *kinds)

            cursor = await self._conn.execute(
                f"""
                SELECT c.* FROM semantic_chunks c
                JOIN semantic ON semantic.rowid = c.rowid
                WHERE semantic MATCH ? {kind_filter}
                ORDER BY rank
                LIMIT ?
                """,
                (*params, top_k),
            )
            rows = await cursor.fetchall()
            return [self._row_to_chunk(row) for row in rows]
        except Exception:
            # Fall back to LIKE search
            like_query = f"%{query}%"
            kind_filter = ""
            like_params: tuple[str, ...] = (like_query, like_query)
            if kinds:
                kind_filter = f"AND kind IN ({','.join('?' * len(kinds))})"
                like_params = (like_query, like_query, *kinds)

            cursor = await self._conn.execute(
                f"""
                SELECT * FROM semantic_chunks
                WHERE (text LIKE ? OR keywords LIKE ?) {kind_filter}
                ORDER BY confidence DESC, first_seen DESC
                LIMIT ?
                """,
                (*like_params, top_k),
            )
            rows = await cursor.fetchall()
            return [self._row_to_chunk(row) for row in rows]

    async def promote(self, id: UUID) -> bool:
        """Promote a chunk's confidence to 1.0 (HITL approved).

        Args:
            id: Chunk ID

        Returns:
            True if found and promoted
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        await self._conn.execute(
            "UPDATE semantic_chunks SET confidence = 1.0 WHERE id = ?",
            (str(id),),
        )
        await self._conn.commit()
        return True

    async def demote(self, id: UUID) -> bool:
        """Demote a chunk's confidence by 0.3 (error flagged).

        Args:
            id: Chunk ID

        Returns:
            True if found and demoted
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        await self._conn.execute(
            "UPDATE semantic_chunks SET confidence = MAX(0.0, confidence - 0.3) WHERE id = ?",
            (str(id),),
        )
        await self._conn.commit()
        return True

    async def delete(self, id: UUID) -> bool:
        """Delete a semantic chunk.

        Args:
            id: Chunk ID

        Returns:
            True if found and deleted
        """
        if self._conn is None:
            raise RuntimeError("SemanticStore not connected")

        cursor = await self._conn.execute(
            "DELETE FROM semantic_chunks WHERE id = ?",
            (str(id),),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    def _row_to_chunk(self, row: aiosqlite.Row) -> SemanticChunk:
        """Convert database row to SemanticChunk."""
        from uuid import UUID as _UUID

        source_ids = json.loads(row["source_episodic_ids"])
        keywords = json.loads(row["keywords"]) if row["keywords"] else []
        first_seen = datetime.fromtimestamp(row["first_seen"], tz=UTC)
        last_seen = datetime.fromtimestamp(row["last_seen"], tz=UTC)
        embedding_id = _UUID(row["embedding_id"]) if row["embedding_id"] else None

        return SemanticChunk(
            id=_UUID(row["id"]),
            source_episodic_ids=[_UUID(id_str) for id_str in source_ids],
            actor=Actor(row["actor"]),
            kind=row["kind"],
            text=row["text"],
            keywords=keywords,
            confidence=row["confidence"],
            first_seen=first_seen,
            last_seen=last_seen,
            occurrences=row["occurrences"],
            embedding_id=embedding_id,
        )


# === T2 Stub (LanceDB - not implemented in Sprint 1.1) ===


class T2Store:
    """Tier 2 embedding store (LanceDB) - stub.

    Per sprint plan: ARIA_MEMORY_T2=0 disables this.
    Only raises NotImplementedError if actually used.
    """

    def __init__(self, config: ARIAConfig) -> None:
        """Initialize T2 store.

        Raises:
            NotImplementedError: Always, in Sprint 1.1
        """
        if not config.memory.t2_enabled:
            raise NotImplementedError(
                "Tier 2 (LanceDB embeddings) not enabled. "
                "Set ARIA_MEMORY_T2=1 to enable (not recommended for Sprint 1.1)."
            )
        raise NotImplementedError("T2 embeddings not implemented in Sprint 1.1")
