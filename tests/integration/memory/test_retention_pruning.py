"""Integration test: T0 retention pruning on real SQLite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash


@pytest.fixture
def mock_config(tmp_path):
    cfg = MagicMock()
    cfg.paths.runtime = tmp_path
    cfg.memory.t0_retention_days = 30
    cfg.memory.t2_enabled = False
    return cfg


@pytest_asyncio.fixture
async def store(tmp_path, mock_config):
    db_path = tmp_path / "episodic.db"
    s = EpisodicStore(db_path, mock_config)
    await s.connect()
    yield s
    await s.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prune_old_entries_e2e(store):
    """Entries older than retention_days are tombstoned; recent ones survive."""
    # Old entry (40 days ago)
    old_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=40),
        actor=Actor.USER_INPUT,
        role="user",
        content="this is old",
        content_hash=content_hash("this is old"),
    )
    await store.insert(old_entry)

    # Recent entry
    recent_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=5),
        actor=Actor.USER_INPUT,
        role="user",
        content="this is recent",
        content_hash=content_hash("this is recent"),
    )
    await store.insert(recent_entry)

    pruned = await store.prune_old_entries(retention_days=30)
    assert pruned == 1

    assert await store.get(old_entry.id) is None
    assert await store.get(recent_entry.id) is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prune_idempotent(store):
    """Running prune twice does not double-tombstone entries."""
    old_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=40),
        actor=Actor.USER_INPUT,
        role="user",
        content="old idempotent",
        content_hash=content_hash("old idempotent"),
    )
    await store.insert(old_entry)

    first = await store.prune_old_entries(retention_days=30)
    second = await store.prune_old_entries(retention_days=30)

    assert first == 1
    assert second == 0  # already tombstoned, INSERT OR IGNORE / WHERE NOT IN
