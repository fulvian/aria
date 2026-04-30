"""recall_episodic must support topic queries and exclude benchmark tags."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash


@pytest.mark.asyncio
async def test_list_by_time_range_excludes_tags(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    store = EpisodicStore(db_path, cfg)
    await store.connect()

    sid = uuid.uuid4()
    now = datetime.now(UTC)
    await store.insert(
        EpisodicEntry(
            session_id=sid,
            ts=now,
            actor=Actor.USER_INPUT,
            role="user",
            content="benchmark row",
            content_hash=content_hash("benchmark row"),
            tags=["benchmark"],
            meta={},
        )
    )
    await store.insert(
        EpisodicEntry(
            session_id=sid,
            ts=now,
            actor=Actor.USER_INPUT,
            role="user",
            content="real chat about barbecue",
            content_hash=content_hash("real chat about barbecue"),
            tags=["repl_message"],
            meta={},
        )
    )

    rows = await store.list_by_time_range(
        since=datetime.fromtimestamp(0, UTC),
        until=datetime.now(UTC),
        limit=10,
        exclude_tags=["benchmark"],
    )
    contents = [row.content for row in rows]
    assert "real chat about barbecue" in contents
    assert "benchmark row" not in contents

    matches = await store.search_text("barbecue", top_k=5)
    assert any("barbecue" in entry.content for entry in matches)
