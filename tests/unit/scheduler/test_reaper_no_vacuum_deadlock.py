"""Reaper must skip VACUUM gracefully when the DB is busy."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from aria.memory.episodic import EpisodicStore


@pytest.mark.asyncio
async def test_vacuum_wal_skips_on_busy(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    store = EpisodicStore(db_path, cfg)
    await store.connect()

    # Hold a read transaction on a SECOND connection so VACUUM cannot run.
    other = await aiosqlite.connect(db_path)
    await other.execute("BEGIN")
    await other.execute("SELECT 1 FROM sqlite_master")

    try:
        # Must not raise; should checkpoint then return.
        await store.vacuum_wal()
    finally:
        await other.execute("ROLLBACK")
        await other.close()
        await store.close()
