from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

import aria.memory.episodic as episodic_mod
from aria.config import ARIAConfig
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ARIAConfig:
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path / ".aria" / "runtime"))
    monkeypatch.setenv("ARIA_CREDENTIALS", str(tmp_path / ".aria" / "credentials"))
    monkeypatch.setattr(episodic_mod, "MIN_SQLITE_VERSION", (3, 0, 0))
    return ARIAConfig.from_env()


@pytest.mark.asyncio
async def test_insert_get_search_tombstone_and_hitl(tmp_path: Path, config: ARIAConfig) -> None:
    store = EpisodicStore(tmp_path / "episodic.db", config)
    await store.connect()
    try:
        session_id = uuid4()
        now = datetime.now(tz=UTC)
        entries = [
            EpisodicEntry(
                session_id=session_id,
                ts=now,
                actor=Actor.USER_INPUT,
                role="user",
                content="remember that I prefer strong espresso",
            ),
            EpisodicEntry(
                session_id=session_id,
                ts=now + timedelta(seconds=1),
                actor=Actor.USER_INPUT,
                role="user",
                content="ricordami di pagare la bolletta",
            ),
        ]
        await store.insert_many(entries)

        one = await store.get(entries[0].id)
        assert one is not None
        assert one.content_hash.startswith("sha256:")

        by_session = await store.list_by_session(session_id)
        assert len(by_session) == 2

        matches = await store.search_text("espresso", top_k=5)
        assert matches

        assert await store.tombstone(entries[0].id, reason="test")
        after_tombstone = await store.get(entries[0].id)
        assert after_tombstone is None

        hitl_id = await store.enqueue_hitl(entries[1].id, "forget_episodic", trace_id="abc")
        assert hitl_id
        pending = await store.list_hitl_pending()
        assert pending and pending[0]["id"] == hitl_id

        stats = await store.stats()
        assert stats.t0_count >= 1
    finally:
        await store.close()
