"""Integration test: HITL full cycle forget → hitl_approve → tombstone."""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore


@pytest.fixture
def mock_config(tmp_path):
    cfg = MagicMock()
    cfg.paths.runtime = tmp_path
    cfg.memory.t0_retention_days = 365
    cfg.memory.t2_enabled = False
    return cfg


@pytest_asyncio.fixture
async def stores(tmp_path, mock_config):
    db_path = tmp_path / "episodic.db"
    mock_config.paths.runtime = tmp_path
    store = EpisodicStore(db_path, mock_config)
    await store.connect()
    semantic = SemanticStore(db_path, mock_config)
    await semantic.connect(store._conn)
    yield store, semantic
    await store.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forget_episodic_hitl_cycle(stores):
    """forget() → hitl list → hitl_approve() tombstones the entry."""
    store, semantic = stores

    # Insert entry
    entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="sensitive data to forget",
        content_hash=content_hash("sensitive data to forget"),
    )
    await store.insert(entry)

    # Enqueue HITL forget (simulating mcp_server.forget tool)
    hitl_id = await store.enqueue_hitl(
        target_id=entry.id,
        action="forget_episodic",
        reason="user requested",
        trace_id="trace-test",
        channel="test",
    )

    # Pending list should contain the request
    pending = await store.list_hitl_pending(limit=10)
    hitl_ids = [p["id"] for p in pending]
    assert hitl_id in hitl_ids

    # Entry is still visible (not yet approved)
    visible = await store.get(entry.id)
    assert visible is not None

    # Approve the HITL request — tombstone the entry
    tombstoned = await store.tombstone(entry.id, reason=f"approved via hitl_approve({hitl_id})")
    assert tombstoned is True

    # Mark resolved in HITL table
    conn = await store._ensure_connected()
    await conn.execute(
        "UPDATE memory_hitl_pending SET status = 'approved', resolved_at = ? WHERE id = ?",
        (int(datetime.now(UTC).timestamp()), hitl_id),
    )
    await conn.commit()

    # Entry no longer visible
    visible = await store.get(entry.id)
    assert visible is None

    # HITL record is resolved
    pending = await store.list_hitl_pending(limit=10)
    record = next((p for p in pending if p["id"] == hitl_id), None)
    assert record is not None
    assert record["status"] == "approved"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hitl_cancel_leaves_entry_intact(stores):
    """hitl_cancel() marks request cancelled, entry remains visible."""
    store, semantic = stores

    entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="entry that should survive",
        content_hash=content_hash("entry that should survive"),
    )
    await store.insert(entry)

    hitl_id = await store.enqueue_hitl(
        target_id=entry.id,
        action="forget_episodic",
        reason="test cancel",
        trace_id=None,
        channel="test",
    )

    # Cancel
    conn = await store._ensure_connected()
    cursor = await conn.execute(
        "UPDATE memory_hitl_pending SET status = 'cancelled', resolved_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (int(datetime.now(UTC).timestamp()), hitl_id),
    )
    await conn.commit()
    assert cursor.rowcount == 1

    # Entry still visible
    visible = await store.get(entry.id)
    assert visible is not None
