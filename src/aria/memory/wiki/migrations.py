# ARIA Memory Wiki — Schema Migrations
#
# Per docs/plans/auto_persistence_echo.md §3.1.
#
# Manages wiki.db schema creation and versioning.
# Tables: page, page_revision, page_fts, wiki_watermark, page_tombstone.
#
# Usage:
#   from aria.memory.wiki.migrations import WikiMigrationRunner
#   runner = WikiMigrationRunner(db_path)
#   await runner.run(conn)

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)

# === Wiki DB Schema DDL ===

WIKI_SCHEMA_DDL = """
-- ============================================================
-- wiki.db schema — Memory v3 (Per plan §3.1)
-- ============================================================

-- Core page table: one row per wiki page
CREATE TABLE IF NOT EXISTS page (
    id              TEXT PRIMARY KEY,
    slug            TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('profile','topic','lesson','entity','decision')),
    title           TEXT NOT NULL,
    body_md         TEXT NOT NULL DEFAULT '',
    confidence      REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    importance      TEXT NOT NULL DEFAULT 'med' CHECK (importance IN ('low','med','high')),
    source_kilo_msg_ids TEXT NOT NULL DEFAULT '[]',
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL,
    occurrences     INTEGER NOT NULL DEFAULT 1,
    UNIQUE(kind, slug)
);

CREATE INDEX IF NOT EXISTS idx_page_kind ON page(kind);
CREATE INDEX IF NOT EXISTS idx_page_last_seen ON page(last_seen DESC);

-- Audit trail: every body_md change
CREATE TABLE IF NOT EXISTS page_revision (
    id              TEXT PRIMARY KEY,
    page_id         TEXT NOT NULL REFERENCES page(id),
    body_md_before  TEXT,
    body_md_after   TEXT NOT NULL,
    diff_summary    TEXT,
    source_kilo_msg_ids TEXT NOT NULL DEFAULT '[]',
    ts              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revision_page ON page_revision(page_id, ts DESC);

-- FTS5 full-text index on title + body (standalone content, not content-sync)
CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(
    title, body_md, kind, slug
);

-- Triggers to keep FTS in sync with page table
CREATE TRIGGER IF NOT EXISTS page_ai AFTER INSERT ON page BEGIN
    INSERT INTO page_fts(title, body_md, kind, slug)
    VALUES (new.title, new.body_md, new.kind, new.slug);
END;

CREATE TRIGGER IF NOT EXISTS page_au AFTER UPDATE ON page BEGIN
    DELETE FROM page_fts WHERE slug = old.slug AND kind = old.kind;
    INSERT INTO page_fts(title, body_md, kind, slug)
    VALUES (new.title, new.body_md, new.kind, new.slug);
END;

CREATE TRIGGER IF NOT EXISTS page_ad AFTER DELETE ON page BEGIN
    DELETE FROM page_fts WHERE slug = old.slug AND kind = old.kind;
END;

-- Watchdog watermark per session (skip-recovery, Phase B)
CREATE TABLE IF NOT EXISTS wiki_watermark (
    kilo_session_id TEXT PRIMARY KEY,
    last_seen_msg_id TEXT NOT NULL,
    last_seen_ts INTEGER NOT NULL,
    last_curated_ts INTEGER NOT NULL
);

-- Tombstone (P7 HITL on hard delete)
CREATE TABLE IF NOT EXISTS page_tombstone (
    page_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    tombstoned_at INTEGER NOT NULL
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS wiki_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    checksum TEXT NOT NULL
);
"""


class WikiMigrationRunner:
    """Manages wiki.db schema migrations."""

    VERSION = 1
    CHECKSUM = hashlib.sha256(WIKI_SCHEMA_DDL.encode("utf-8")).hexdigest()

    async def run(self, conn: aiosqlite.Connection) -> int:
        """Run wiki.db migrations.

        Creates all tables if not exist. Idempotent.

        Args:
            conn: Open aiosqlite connection.

        Returns:
            Version applied (0 if already up-to-date).
        """
        # Check if already migrated (table may not exist yet)
        try:
            cursor = await conn.execute(
                "SELECT version, checksum FROM wiki_schema_migrations WHERE version = ?",
                (self.VERSION,),
            )
            row = await cursor.fetchone()
        except Exception:
            # Table doesn't exist yet — need to apply migration
            row = None

        if row:
            stored_checksum = row[1]
            if stored_checksum != self.CHECKSUM:
                logger.warning(
                    "wiki.db migration v%s checksum mismatch. "
                    "Schema may have been modified after initial application.",
                    self.VERSION,
                )
            return 0

        # Apply migration
        import time

        now = int(time.time())
        try:
            await conn.executescript(WIKI_SCHEMA_DDL)
            # The wiki_schema_migrations table is created inside the DDL,
            # so now insert the version record
            await conn.execute(
                "INSERT INTO wiki_schema_migrations (version, applied_at, checksum) "
                "VALUES (?, ?, ?)",
                (self.VERSION, now, self.CHECKSUM),
            )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

        logger.info("wiki.db schema v%s applied successfully", self.VERSION)
        return self.VERSION

    async def get_version(self, conn: aiosqlite.Connection) -> int:
        """Get current schema version."""
        try:
            cursor = await conn.execute("SELECT MAX(version) FROM wiki_schema_migrations")
            row = await cursor.fetchone()
            return row[0] if row and row[0] is not None else 0
        except Exception:
            return 0
