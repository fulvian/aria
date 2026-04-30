# ARIA Memory Wiki — WikiStore (CRUD)
#
# Per docs/plans/auto_persistence_echo.md §3.1 + §4.2.
#
# WikiStore manages wiki.db operations:
# - Page CRUD (create, read, update, append)
# - Revision audit trail
# - Schema fingerprint check for kilo.db
# - Watermark management (Phase B)
# - Tombstone management (P7 HITL)
#
# Usage:
#   from aria.memory.wiki.db import WikiStore
#   store = WikiStore(db_path)
#   await store.connect()
#   page = await store.create_page(patch)

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import aiosqlite

from aria.memory.wiki.migrations import WikiMigrationRunner
from aria.memory.wiki.schema import (
    Page,
    PageKind,
    PagePatch,
)

logger = logging.getLogger(__name__)

# === Slug Normalization ===

_SLUG_REPLACE_PATTERN = re.compile(r"[^a-z0-9]+")
_SLUG_STRIP_PATTERN = re.compile(r"^[-]+|[-]+$")


def slugify(text: str) -> str:
    """Convert text to kebab-case slug.

    Args:
        text: Raw text (e.g., "Don't Mock DB").

    Returns:
        Kebab-case slug (e.g., "dont-mock-db").
    """
    slug = text.lower().strip()
    slug = _SLUG_REPLACE_PATTERN.sub("-", slug)
    return _SLUG_STRIP_PATTERN.sub("", slug)


# === Schema Fingerprint ===

_KILO_DB_SCHEMA_TABLES = ["message", "part"]
_KILO_DB_FINGERPRINT_TABLES = "message,part"


async def compute_kilo_schema_fingerprint(kilo_db_path: Path) -> str | None:
    """Compute a fingerprint of kilo.db message/part schema.

    Per plan §4.2: on startup, verify kilo.db schema hasn't drifted.

    Args:
        kilo_db_path: Path to kilo.db.

    Returns:
        SHA256 fingerprint string, or None if kilo.db not found.
    """
    if not kilo_db_path.exists():  # noqa: ASYNC240
        return None

    schema_parts: list[str] = []
    try:
        async with aiosqlite.connect(kilo_db_path) as conn:
            for table in _KILO_DB_SCHEMA_TABLES:
                cursor = await conn.execute("PRAGMA table_info(?)", (table,))
                # PRAGMA doesn't support parameterized table names
                pass
            # Use raw SQL for PRAGMA (table names are safe constants)
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


# === WikiStore ===


class WikiStore:
    """Manages wiki.db CRUD operations.

    Per plan §3: wiki.db is the canonical knowledge store.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize WikiStore.

        Args:
            db_path: Path to wiki.db file.
        """
        self._db_path = db_path.resolve()
        self._conn: aiosqlite.Connection | None = None
        self._migration_runner = WikiMigrationRunner()

    @property
    def db_path(self) -> Path:
        """Return the database path."""
        return self._db_path

    async def connect(self) -> None:
        """Open connection and run migrations."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for concurrent read/write
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        # Run migrations
        await self._migration_runner.run(self._conn)
        logger.info("WikiStore connected to %s", self._db_path)

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
            raise RuntimeError("Failed to establish wiki.db connection")
        return self._conn

    # === Page CRUD ===

    async def create_page(self, patch: PagePatch) -> Page:
        """Create a new wiki page from a patch.

        Args:
            patch: The page patch with create operation.

        Returns:
            The created Page.

        Raises:
            ValueError: If op is not "create" or title missing.
            RuntimeError: If page already exists (kind, slug conflict).
        """
        conn = await self._ensure_connected()

        if patch.op != "create":
            raise ValueError(f"create_page requires op='create', got {patch.op!r}")

        # Auto-extract title from body_md if not explicitly provided (P2)
        title = patch.title
        if not title and patch.body_md:
            heading_match = re.search(r"^#+\s+(.+)$", patch.body_md, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1).strip()
                logger.info(
                    "Auto-extracted title from body_md heading: %r (slug=%s)",
                    title,
                    patch.slug,
                )

        if not title:
            raise ValueError(
                "title is required for create operation. "
                "Provide 'title' in the patch, or start body_md with a Markdown "
                "heading (e.g., '# My Title')."
            )

        now = int(time.time())
        page = Page(
            slug=patch.slug,
            kind=patch.kind,
            title=title,
            body_md=patch.body_md,
            confidence=patch.confidence,
            importance=patch.importance,
            source_kilo_msg_ids=patch.source_kilo_msg_ids,
            first_seen=now,
            last_seen=now,
            occurrences=1,
        )

        try:
            await conn.execute(
                """INSERT INTO page (id, slug, kind, title, body_md, confidence,
                   importance, source_kilo_msg_ids, first_seen, last_seen, occurrences)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    page.id,
                    page.slug,
                    page.kind.value,
                    page.title,
                    page.body_md,
                    page.confidence,
                    page.importance,
                    json.dumps(page.source_kilo_msg_ids),
                    page.first_seen,
                    page.last_seen,
                    page.occurrences,
                ),
            )
            await conn.commit()
        except Exception as exc:
            await conn.rollback()
            if "UNIQUE constraint failed" in str(exc):
                raise RuntimeError(
                    f"Page already exists: kind={patch.kind.value}, slug={patch.slug}"
                ) from exc
            raise

        # Record creation in revision audit
        await self._record_revision(
            conn, page.id, None, page.body_md, patch.diff_summary, patch.source_kilo_msg_ids
        )

        logger.info("Created wiki page: kind=%s slug=%s", page.kind.value, page.slug)
        return page

    async def update_page(self, patch: PagePatch) -> Page:
        """Update an existing wiki page (full body rewrite).

        Args:
            patch: The page patch with update operation.

        Returns:
            The updated Page.

        Raises:
            LookupError: If page not found.
            ValueError: If page is a decision (immutable).
        """
        conn = await self._ensure_connected()

        if patch.op != "update":
            raise ValueError(f"update_page requires op='update', got {patch.op!r}")

        # Fetch existing
        existing = await self.get_page(patch.kind, patch.slug)
        if existing is None:
            raise LookupError(f"Page not found: kind={patch.kind.value}, slug={patch.slug}")

        # Enforce immutability for decisions
        if existing.kind == PageKind.DECISION:
            raise ValueError(f"Decision pages are immutable: kind=decision, slug={patch.slug}")

        old_body = existing.body_md
        new_title = patch.title or existing.title
        now = int(time.time())

        await conn.execute(
            """UPDATE page
               SET title = ?, body_md = ?, confidence = ?, importance = ?,
                   source_kilo_msg_ids = ?, last_seen = ?, occurrences = occurrences + 1
               WHERE kind = ? AND slug = ?""",
            (
                new_title,
                patch.body_md,
                patch.confidence,
                patch.importance,
                json.dumps(patch.source_kilo_msg_ids),
                now,
                patch.kind.value,
                patch.slug,
            ),
        )
        await conn.commit()

        await self._record_revision(
            conn,
            existing.id,
            old_body,
            patch.body_md,
            patch.diff_summary,
            patch.source_kilo_msg_ids,
        )

        logger.info("Updated wiki page: kind=%s slug=%s", patch.kind.value, patch.slug)

        # Return updated page
        updated = await self.get_page(patch.kind, patch.slug)
        if updated is None:
            raise RuntimeError("Page vanished after update")
        return updated

    async def append_page(self, patch: PagePatch) -> Page:
        """Append content to an existing wiki page.

        Args:
            patch: The page patch with append operation.

        Returns:
            The updated Page with appended content.

        Raises:
            LookupError: If page not found.
            ValueError: If page is a decision (immutable).
        """
        conn = await self._ensure_connected()

        if patch.op != "append":
            raise ValueError(f"append_page requires op='append', got {patch.op!r}")

        existing = await self.get_page(patch.kind, patch.slug)
        if existing is None:
            raise LookupError(f"Page not found: kind={patch.kind.value}, slug={patch.slug}")

        # Enforce immutability for decisions
        if existing.kind == PageKind.DECISION:
            raise ValueError(f"Decision pages are immutable: kind=decision, slug={patch.slug}")

        old_body = existing.body_md
        new_body = old_body + "\n\n" + patch.body_md
        now = int(time.time())

        await conn.execute(
            """UPDATE page
               SET body_md = ?, confidence = ?, source_kilo_msg_ids = ?,
                   last_seen = ?, occurrences = occurrences + 1
               WHERE kind = ? AND slug = ?""",
            (
                new_body,
                patch.confidence,
                json.dumps(patch.source_kilo_msg_ids),
                now,
                patch.kind.value,
                patch.slug,
            ),
        )
        await conn.commit()

        await self._record_revision(
            conn,
            existing.id,
            old_body,
            new_body,
            patch.diff_summary,
            patch.source_kilo_msg_ids,
        )

        logger.info("Appended to wiki page: kind=%s slug=%s", patch.kind.value, patch.slug)

        updated = await self.get_page(patch.kind, patch.slug)
        if updated is None:
            raise RuntimeError("Page vanished after append")
        return updated

    async def get_page(self, kind: PageKind, slug: str) -> Page | None:
        """Get a page by kind and slug.

        Args:
            kind: Page kind.
            slug: Page slug.

        Returns:
            Page if found, None otherwise.
        """
        conn = await self._ensure_connected()

        cursor = await conn.execute(
            "SELECT * FROM page WHERE kind = ? AND slug = ?",
            (kind.value, slug),
        )
        row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_page(row)

    async def get_page_by_id(self, page_id: str) -> Page | None:
        """Get a page by its ID.

        Args:
            page_id: UUID string.

        Returns:
            Page if found, None otherwise.
        """
        conn = await self._ensure_connected()

        cursor = await conn.execute(
            "SELECT * FROM page WHERE id = ?",
            (page_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_page(row)

    async def list_pages(
        self,
        kind: PageKind | None = None,
        limit: int = 50,
    ) -> list[Page]:
        """List pages, optionally filtered by kind.

        Args:
            kind: Optional kind filter.
            limit: Maximum pages to return.

        Returns:
            List of Page objects ordered by last_seen DESC.
        """
        conn = await self._ensure_connected()

        if kind:
            cursor = await conn.execute(
                "SELECT * FROM page WHERE kind = ? ORDER BY last_seen DESC LIMIT ?",
                (kind.value, limit),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM page ORDER BY last_seen DESC LIMIT ?",
                (limit,),
            )

        rows = await cursor.fetchall()
        return [self._row_to_page(row) for row in rows]

    async def apply_patch(self, patch: PagePatch) -> Page:
        """Apply a patch, dispatching to create/update/append.

        Args:
            patch: The page patch to apply.

        Returns:
            The resulting Page.
        """
        if patch.op == "create":
            return await self.create_page(patch)
        elif patch.op == "update":
            return await self.update_page(patch)
        elif patch.op == "append":
            return await self.append_page(patch)
        else:
            raise ValueError(f"Unknown patch op: {patch.op!r}")

    # === Tombstone (P7 HITL) ===

    async def tombstone_page(self, page_id: str, reason: str) -> bool:
        """Tombstone a page (soft delete).

        Per P7: requires HITL approval before calling this.

        Args:
            page_id: UUID of the page.
            reason: Reason for deletion.

        Returns:
            True if tombstoned, False if not found.
        """
        conn = await self._ensure_connected()

        page = await self.get_page_by_id(page_id)
        if page is None:
            return False

        now = int(time.time())

        # Delete revisions first (FK constraint), then page
        await conn.execute("DELETE FROM page_revision WHERE page_id = ?", (page_id,))
        # Delete from page (cascade to FTS via trigger)
        await conn.execute("DELETE FROM page WHERE id = ?", (page_id,))
        # Insert tombstone
        await conn.execute(
            "INSERT INTO page_tombstone (page_id, reason, tombstoned_at) VALUES (?, ?, ?)",
            (page_id, reason, now),
        )
        await conn.commit()

        logger.info("Tombstoned wiki page: id=%s slug=%s", page_id, page.slug)
        return True

    async def is_tombstoned(self, page_id: str) -> bool:
        """Check if a page is tombstoned."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            "SELECT 1 FROM page_tombstone WHERE page_id = ?",
            (page_id,),
        )
        row = await cursor.fetchone()
        return row is not None

    # === Watermark (Phase B) ===

    async def get_watermark(self, kilo_session_id: str) -> dict[str, Any] | None:
        """Get watermark for a session."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            "SELECT * FROM wiki_watermark WHERE kilo_session_id = ?",
            (kilo_session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "kilo_session_id": row["kilo_session_id"],
            "last_seen_msg_id": row["last_seen_msg_id"],
            "last_seen_ts": row["last_seen_ts"],
            "last_curated_ts": row["last_curated_ts"],
        }

    async def set_watermark(
        self,
        kilo_session_id: str,
        last_seen_msg_id: str,
        last_seen_ts: int,
    ) -> None:
        """Set or update watermark for a session."""
        conn = await self._ensure_connected()
        now = int(time.time())
        await conn.execute(
            """INSERT INTO wiki_watermark
               (kilo_session_id, last_seen_msg_id, last_seen_ts, last_curated_ts)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(kilo_session_id) DO UPDATE SET
                   last_seen_msg_id = excluded.last_seen_msg_id,
                   last_seen_ts = excluded.last_seen_ts,
                   last_curated_ts = excluded.last_curated_ts""",
            (kilo_session_id, last_seen_msg_id, last_seen_ts, now),
        )
        await conn.commit()

    # === Stats ===

    async def stats(self) -> dict[str, Any]:
        """Get wiki stats."""
        conn = await self._ensure_connected()

        # Page counts by kind
        cursor = await conn.execute("SELECT kind, COUNT(*) as cnt FROM page GROUP BY kind")
        kind_counts = {row["kind"]: row["cnt"] for row in await cursor.fetchall()}

        # Total pages
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM page")
        total_row = await cursor.fetchone()
        total = total_row["cnt"] if total_row else 0

        # Revisions count
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM page_revision")
        rev_row = await cursor.fetchone()
        revisions = rev_row["cnt"] if rev_row else 0

        # Tombstones count
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM page_tombstone")
        tomb_row = await cursor.fetchone()
        tombstones = tomb_row["cnt"] if tomb_row else 0

        # Last curated
        cursor = await conn.execute("SELECT MAX(last_curated_ts) as ts FROM wiki_watermark")
        row = await cursor.fetchone()
        last_curated = row["ts"] if row and row["ts"] else None

        return {
            "total_pages": total,
            "total_revisions": revisions,
            "total_tombstones": tombstones,
            "last_curated_ts": last_curated,
            "kind_counts": kind_counts,
        }

    # === Internal ===

    async def _record_revision(
        self,
        conn: aiosqlite.Connection,
        page_id: str,
        body_before: str | None,
        body_after: str,
        diff_summary: str | None,
        source_kilo_msg_ids: list[str],
    ) -> None:
        """Record a page revision in the audit trail."""
        from uuid import uuid4

        rev_id = str(uuid4())
        now = int(time.time())
        await conn.execute(
            """INSERT INTO page_revision (id, page_id, body_md_before, body_md_after,
               diff_summary, source_kilo_msg_ids, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                rev_id,
                page_id,
                body_before,
                body_after,
                diff_summary,
                json.dumps(source_kilo_msg_ids),
                now,
            ),
        )
        await conn.commit()

    @staticmethod
    def _row_to_page(row: aiosqlite.Row) -> Page:
        """Convert a database row to a Page model."""
        source_ids_raw = row["source_kilo_msg_ids"]
        if isinstance(source_ids_raw, str):
            try:
                source_ids = json.loads(source_ids_raw)
            except (json.JSONDecodeError, TypeError):
                source_ids = []
        elif isinstance(source_ids_raw, list):
            source_ids = source_ids_raw
        else:
            source_ids = []

        return Page(
            id=row["id"],
            slug=row["slug"],
            kind=PageKind(row["kind"]),
            title=row["title"],
            body_md=row["body_md"],
            confidence=row["confidence"],
            importance=row["importance"],
            source_kilo_msg_ids=source_ids,
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            occurrences=row["occurrences"],
        )
