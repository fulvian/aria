from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from aria.memory.migrations import MigrationRunner


@pytest.mark.asyncio
async def test_migration_runner_bootstraps_migrations_table(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    conn = await aiosqlite.connect(db_path)
    try:
        runner = MigrationRunner(db_path)
        applied = await runner.run(conn)

        assert applied == [1, 2, 3]

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        assert await cursor.fetchone() is not None

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='semantic_chunks'"
        )
        assert await cursor.fetchone() is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_runner_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    conn = await aiosqlite.connect(db_path)
    try:
        runner = MigrationRunner(db_path)
        await runner.run(conn)
        applied_second = await runner.run(conn)

        assert applied_second == []

        cursor = await conn.execute("SELECT COUNT(*) FROM schema_migrations")
        row = await cursor.fetchone()
        assert row is not None
        count = row[0]
        assert count == 3
    finally:
        await conn.close()
