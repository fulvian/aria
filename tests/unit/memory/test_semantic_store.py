from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

import aria.memory.episodic as episodic_mod
from aria.config import ARIAConfig
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, SemanticChunk
from aria.memory.semantic import SemanticStore, T2Store


@pytest.mark.asyncio
async def test_semantic_store_crud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path / ".aria" / "runtime"))
    monkeypatch.setenv("ARIA_CREDENTIALS", str(tmp_path / ".aria" / "credentials"))
    monkeypatch.setattr(episodic_mod, "MIN_SQLITE_VERSION", (3, 0, 0))

    config = ARIAConfig.from_env()
    episodic = EpisodicStore(tmp_path / "db.sqlite", config)
    await episodic.connect()
    semantic = SemanticStore(tmp_path / "db.sqlite", config)
    conn = episodic._conn  # noqa: SLF001
    assert conn is not None
    await semantic.connect(conn)

    try:
        source = EpisodicEntry(
            session_id=uuid4(),
            ts=datetime.now(tz=UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content="I prefer tea in the morning",
        )
        await episodic.insert(source)

        chunk = SemanticChunk(
            source_episodic_ids=[source.id],
            actor=Actor.USER_INPUT,
            kind="preference",
            text="User prefers tea in the morning",
            keywords=["tea", "morning"],
            first_seen=datetime.now(tz=UTC),
            last_seen=datetime.now(tz=UTC),
        )
        await semantic.insert(chunk)
        await semantic.insert_many([chunk.model_copy(update={"id": uuid4()})])

        fetched = await semantic.get(chunk.id)
        assert fetched is not None
        assert fetched.kind == "preference"

        search = await semantic.search("tea", top_k=5)
        assert search

        by_kind = await semantic.list_by_kind("preference")
        assert by_kind

        by_session = await semantic.list_by_session(source.session_id)
        assert by_session

        await semantic.promote(chunk.id)
        await semantic.demote(chunk.id)
        assert await semantic.delete(chunk.id)

        with pytest.raises(NotImplementedError):
            T2Store(config)
    finally:
        await episodic.close()
