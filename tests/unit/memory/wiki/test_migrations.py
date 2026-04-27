# Tests for wiki.migrations — Schema creation and versioning

from __future__ import annotations

import pytest

from aria.memory.wiki.migrations import WIKI_SCHEMA_DDL, WikiMigrationRunner


@pytest.fixture
async def conn(tmp_path: Any):
    """Create an in-memory database connection."""
    import aiosqlite

    db = await aiosqlite.connect(":memory:")
    yield db
    await db.close()


class TestWikiMigrationRunner:
    """WikiMigrationRunner tests."""

    async def test_run_creates_tables(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        version = await runner.run(conn)
        assert version == 1

        # Verify tables exist
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert "page" in tables
        assert "page_revision" in tables
        assert "page_tombstone" in tables
        assert "wiki_watermark" in tables
        assert "wiki_schema_migrations" in tables

    async def test_run_creates_fts5_index(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        await runner.run(conn)

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='page_fts'"
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_run_idempotent(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        v1 = await runner.run(conn)
        v2 = await runner.run(conn)

        assert v1 == 1  # First run applies
        assert v2 == 0  # Second run is no-op

    async def test_get_version_initial(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        # Before migration, version should be 0
        # (table doesn't exist yet, should handle gracefully)
        version = await runner.get_version(conn)
        assert version == 0

    async def test_get_version_after_migration(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        await runner.run(conn)
        version = await runner.get_version(conn)
        assert version == 1

    async def test_page_unique_constraint(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        await runner.run(conn)

        # Insert first page
        await conn.execute(
            "INSERT INTO page (id, slug, kind, title, body_md, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("id-1", "test", "topic", "Test", "content", 1000, 1000),
        )
        await conn.commit()

        # Insert duplicate (kind, slug) should fail
        with pytest.raises(Exception, match="UNIQUE"):
            await conn.execute(
                "INSERT INTO page (id, slug, kind, title, body_md, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("id-2", "test", "topic", "Test 2", "content", 1000, 1000),
            )

    async def test_page_kind_check_constraint(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        await runner.run(conn)

        with pytest.raises(Exception, match="CHECK"):
            await conn.execute(
                "INSERT INTO page (id, slug, kind, title, body_md, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("id-1", "test", "invalid_kind", "Test", "content", 1000, 1000),
            )

    async def test_page_confidence_range(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        await runner.run(conn)

        with pytest.raises(Exception, match="CHECK"):
            await conn.execute(
                "INSERT INTO page (id, slug, kind, title, body_md, confidence, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("id-1", "test", "topic", "Test", "content", 2.0, 1000, 1000),
            )

    async def test_page_importance_check(self, conn: Any) -> None:
        runner = WikiMigrationRunner()
        await runner.run(conn)

        with pytest.raises(Exception, match="CHECK"):
            await conn.execute(
                "INSERT INTO page (id, slug, kind, title, body_md, importance, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("id-1", "test", "topic", "Test", "content", "critical", 1000, 1000),
            )


class TestWikiSchemaDDL:
    """Test the DDL string itself."""

    def test_ddl_is_not_empty(self) -> None:
        assert len(WIKI_SCHEMA_DDL) > 100

    def test_ddl_contains_all_tables(self) -> None:
        assert "CREATE TABLE IF NOT EXISTS page" in WIKI_SCHEMA_DDL
        assert "CREATE TABLE IF NOT EXISTS page_revision" in WIKI_SCHEMA_DDL
        assert "CREATE TABLE IF NOT EXISTS page_tombstone" in WIKI_SCHEMA_DDL
        assert "CREATE TABLE IF NOT EXISTS wiki_watermark" in WIKI_SCHEMA_DDL
        assert "CREATE VIRTUAL TABLE IF NOT EXISTS page_fts" in WIKI_SCHEMA_DDL

    def test_ddl_contains_triggers(self) -> None:
        assert "CREATE TRIGGER IF NOT EXISTS page_ai" in WIKI_SCHEMA_DDL
        assert "CREATE TRIGGER IF NOT EXISTS page_au" in WIKI_SCHEMA_DDL
        assert "CREATE TRIGGER IF NOT EXISTS page_ad" in WIKI_SCHEMA_DDL

    def test_ddl_contains_indexes(self) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_page_kind" in WIKI_SCHEMA_DDL
        assert "CREATE INDEX IF NOT EXISTS idx_page_last_seen" in WIKI_SCHEMA_DDL
        assert "CREATE INDEX IF NOT EXISTS idx_revision_page" in WIKI_SCHEMA_DDL
