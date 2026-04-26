"""cleanup_benchmark_entries.py must tombstone only benchmark rows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from scripts.memory.cleanup_benchmark_entries import cleanup_benchmark_entries


@pytest.mark.asyncio
async def test_only_benchmark_rows_are_tombstoned(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    store = EpisodicStore(db_path, cfg)
    await store.connect()

    sid = uuid.uuid4()
    now = datetime.now(UTC)
    keep = EpisodicEntry(
        session_id=sid, ts=now, actor=Actor.USER_INPUT, role="user",
        content="real chat about barbecue", content_hash=content_hash("a"),
    )
    drop = EpisodicEntry(
        session_id=sid, ts=now, actor=Actor.USER_INPUT, role="user",
        content="test content entry 42 for memory recall benchmark",
        content_hash=content_hash("b"),
    )
    await store.insert(keep)
    await store.insert(drop)

    report = await cleanup_benchmark_entries(store, dry_run=False)
    assert report["tombstoned"] == 1
    assert report["scanned"] == 2

    survivors = await store.search_text("barbecue", top_k=5)
    assert any(e.id == keep.id for e in survivors)
