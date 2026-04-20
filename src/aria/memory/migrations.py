# Memory Migrations
#
# Manages SQLite schema migrations for the memory subsystem.
# Per sprint plan W1.1.M.
#
# Pattern:
# - Table schema_migrations (version, applied_at, checksum)
# - Migration files in src/aria/memory/migrations/NNNN__<slug>.sql
# - Idempotent: check checksum before applying
#
# Usage:
#   from aria.memory.migrations import MigrationRunner
#   runner = MigrationRunner(db_path)
#   await runner.run()

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

# === Migration Directory ===

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATIONS_DIR.mkdir(exist_ok=True)


# === SQL Migration Files ===

INIT_MIGRATION = """
-- Migration 0001: Initialize memory schema
-- Creates base episodic and semantic tables
-- Note: PRAGMAs are applied in connect() before migrations run,
-- so they are NOT included here to avoid transaction conflicts.

-- Tier 0: Raw episodic memory (verbatim preservation)
CREATE TABLE IF NOT EXISTS episodic (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('user_input', 'tool_output', 'agent_inference', 'system_event')),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    meta TEXT DEFAULT '{}',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic(session_id);
CREATE INDEX IF NOT EXISTS idx_episodic_ts ON episodic(ts);
CREATE INDEX IF NOT EXISTS idx_episodic_actor ON episodic(actor);

-- Tier 1 semantic chunks + FTS5 index table
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
);

CREATE INDEX IF NOT EXISTS idx_chunks_actor ON semantic_chunks(actor);
CREATE INDEX IF NOT EXISTS idx_chunks_kind ON semantic_chunks(kind);
CREATE INDEX IF NOT EXISTS idx_chunks_first_seen ON semantic_chunks(first_seen);

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
);

CREATE TRIGGER IF NOT EXISTS semantic_fts_insert AFTER INSERT ON semantic_chunks BEGIN
    INSERT INTO semantic(rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES (NEW.rowid, NEW.id, NEW.source_episodic_ids, NEW.actor, NEW.kind, NEW.text, NEW.keywords, NEW.confidence, NEW.first_seen, NEW.last_seen, NEW.occurrences, NEW.embedding_id);
END;

CREATE TRIGGER IF NOT EXISTS semantic_fts_delete AFTER DELETE ON semantic_chunks BEGIN
    INSERT INTO semantic(semantic, rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES ('delete', OLD.rowid, OLD.id, OLD.source_episodic_ids, OLD.actor, OLD.kind, OLD.text, OLD.keywords, OLD.confidence, OLD.first_seen, OLD.last_seen, OLD.occurrences, OLD.embedding_id);
END;

CREATE TRIGGER IF NOT EXISTS semantic_fts_update AFTER UPDATE ON semantic_chunks BEGIN
    INSERT INTO semantic(semantic, rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES ('delete', OLD.rowid, OLD.id, OLD.source_episodic_ids, OLD.actor, OLD.kind, OLD.text, OLD.keywords, OLD.confidence, OLD.first_seen, OLD.last_seen, OLD.occurrences, OLD.embedding_id);
    INSERT INTO semantic(rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES (NEW.rowid, NEW.id, NEW.source_episodic_ids, NEW.actor, NEW.kind, NEW.text, NEW.keywords, NEW.confidence, NEW.first_seen, NEW.last_seen, NEW.occurrences, NEW.embedding_id);
END;

-- FTS5 virtual table for full-text search on episodic content
CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
    content,
    actor,
    session_id,
    content='episodic',
    content_rowid='rowid'
);

-- Triggers to keep episodic_fts in sync with episodic table
-- (Note: These require SQLite 3.51.3+ per MIN_SQLITE_VERSION)
CREATE TRIGGER IF NOT EXISTS episodic_fts_insert AFTER INSERT ON episodic BEGIN
    INSERT INTO episodic_fts(rowid, content, actor, session_id)
    VALUES (NEW.rowid, NEW.content, NEW.actor, NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS episodic_fts_delete AFTER DELETE ON episodic BEGIN
    INSERT INTO episodic_fts(episodic_fts, rowid, content, actor, session_id)
    VALUES ('delete', OLD.rowid, OLD.content, OLD.actor, OLD.session_id);
END;

CREATE TRIGGER IF NOT EXISTS episodic_fts_update AFTER UPDATE ON episodic BEGIN
    INSERT INTO episodic_fts(episodic_fts, rowid, content, actor, session_id)
    VALUES ('delete', OLD.rowid, OLD.content, OLD.actor, OLD.session_id);
    INSERT INTO episodic_fts(rowid, content, actor, session_id)
    VALUES (NEW.rowid, NEW.content, NEW.actor, NEW.session_id);
END;

-- Schema migrations tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    checksum TEXT NOT NULL
);
"""

TOMBSTONES_MIGRATION = """
-- Migration 0002: Add episodic_tombstones table
-- Per blueprint P6 - soft delete for verbatim preservation

CREATE TABLE IF NOT EXISTS episodic_tombstones (
    episodic_id TEXT PRIMARY KEY,
    tombstoned_at INTEGER NOT NULL,
    reason TEXT NOT NULL,
    actor_user_id TEXT
);
"""

HITL_PENDING_MIGRATION = """
-- Migration 0003: Add memory HITL pending queue

CREATE TABLE IF NOT EXISTS memory_hitl_pending (
    id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    trace_id TEXT,
    channel TEXT NOT NULL DEFAULT 'cli',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    resolved_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_memory_hitl_pending_status ON memory_hitl_pending(status);
CREATE INDEX IF NOT EXISTS idx_memory_hitl_pending_created ON memory_hitl_pending(created_at);
"""

# === Migration Runner ===


class MigrationRunner:
    """Manages database migrations with checksum verification."""

    # Migration versions applied by this runner
    MIGRATIONS: list[tuple[int, str, str]] = [
        (1, "0001__init.sql", INIT_MIGRATION),
        (2, "0002__tombstones.sql", TOMBSTONES_MIGRATION),
        (3, "0003__hitl_pending.sql", HITL_PENDING_MIGRATION),
    ]

    def __init__(self, db_path: Path) -> None:
        """Initialize migration runner.

        Args:
            db_path: Path to SQLite database
        """
        self._db_path = db_path.resolve()

    def _file_checksum(self, content: str) -> str:
        """Compute checksum for migration content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def _ensure_migrations_table(self, conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL,
                checksum TEXT NOT NULL
            )
            """
        )
        await conn.commit()

    async def run(self, conn: aiosqlite.Connection) -> list[int]:
        """Run pending migrations.

        Args:
            conn: Open database connection

        Returns:
            List of applied migration versions
        """
        applied: list[int] = []
        await self._ensure_migrations_table(conn)

        for version, _filename, sql in self.MIGRATIONS:
            # Check if already applied
            cursor = await conn.execute(
                "SELECT checksum FROM schema_migrations WHERE version = ?",
                (version,),
            )
            row = await cursor.fetchone()

            if row:
                # Already applied - verify checksum
                stored_checksum = row[0]
                expected_checksum = self._file_checksum(sql)

                if stored_checksum != expected_checksum:
                    # File modified after application - warn but don't fail
                    import logging

                    logging.warning(
                        f"Migration {version} checksum mismatch. "
                        f"File may have been modified after application."
                    )
                continue

            checksum = self._file_checksum(sql)
            now = int(__import__("time").time())
            try:
                await conn.execute("BEGIN")
                await conn.executescript(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at, checksum) VALUES (?, ?, ?)",
                    (version, now, checksum),
                )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

            applied.append(version)

        return applied

    async def get_applied_versions(self, conn: aiosqlite.Connection) -> list[int]:
        """Get list of applied migration versions."""
        cursor = await conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


# === Migration File Export ===


def ensure_migration_files() -> None:
    """Write migration SQL files to disk for reference/debugging.

    Called during module import to ensure files exist.
    """
    for _version, filename, sql in MigrationRunner.MIGRATIONS:
        filepath = MIGRATIONS_DIR / filename
        rendered = sql.strip() + "\n"
        if not filepath.exists() or filepath.read_text(encoding="utf-8") != rendered:
            filepath.write_text(rendered, encoding="utf-8")


# Export migration files on import
ensure_migration_files()
