"""Integration test: E2E flow remember → distill → recall on real SQLite."""

from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from aria.memory.clm import CLM
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def mock_config(tmp_path):
    cfg = MagicMock()
    cfg.paths.runtime = tmp_path
    cfg.memory.t0_retention_days = 365
    cfg.memory.t2_enabled = False
    return cfg


@pytest_asyncio.fixture(loop_scope="session")
async def stores(tmp_path, mock_config):
    db_path = tmp_path / "episodic.db"
    mock_config.paths.runtime = tmp_path
    store = EpisodicStore(db_path, mock_config)
    await store.connect()
    semantic = SemanticStore(db_path, mock_config)
    await semantic.connect(store._conn)
    clm = CLM(store, semantic)
    yield store, semantic, clm
    await store.close()
    await asyncio.sleep(0)


@pytest.mark.integration
async def test_remember_distill_recall_e2e(stores):
    """remember → distill_session → recall returns the distilled chunk."""
    store, semantic, clm = stores
    session_id = uuid4()

    # Insert a user entry with a preference keyword
    entry = EpisodicEntry(
        session_id=session_id,
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="Ricorda che preferisco Python rispetto a Java",
        content_hash=content_hash("Ricorda che preferisco Python rispetto a Java"),
    )
    await store.insert(entry)

    # Distill the session
    chunks = await clm.distill_session(session_id)
    assert len(chunks) >= 1, "CLM should extract at least one preference chunk"
    assert chunks[0].kind in ("preference", "decision")

    # Recall should now return the semantic chunk
    results = await semantic.search("preferisco Python", top_k=5)
    assert len(results) >= 1
    assert "Python" in results[0].text or "preferisco" in results[0].text


@pytest.mark.integration
async def test_distill_range_covers_multiple_sessions(stores):
    """distill_range processes entries from multiple sessions."""
    store, semantic, clm = stores

    # Insert entries in two sessions with preference keywords
    for i in range(2):
        session_id = uuid4()
        entry = EpisodicEntry(
            session_id=session_id,
            ts=datetime.now(UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content=f"Ricordami di fare la cosa {i} domani",
            content_hash=content_hash(f"Ricordami di fare la cosa {i} domani"),
        )
        await store.insert(entry)

    since = datetime.now(UTC) - timedelta(hours=1)
    until = datetime.now(UTC)
    chunks = await clm.distill_range(since, until)
    assert len(chunks) >= 2, "Two entries with action patterns should yield >=2 chunks"
