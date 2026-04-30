from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

import aria.memory.episodic as episodic_mod
from aria.config import ARIAConfig
from aria.memory.clm import CLM
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry
from aria.memory.semantic import SemanticStore

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_clm_distill_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path / ".aria" / "runtime"))
    monkeypatch.setenv("ARIA_CREDENTIALS", str(tmp_path / ".aria" / "credentials"))
    monkeypatch.setattr(episodic_mod, "MIN_SQLITE_VERSION", (3, 0, 0))

    config = ARIAConfig.from_env()
    store = EpisodicStore(tmp_path / "memory.db", config)
    await store.connect()
    semantic = SemanticStore(tmp_path / "memory.db", config)
    conn = store._conn  # noqa: SLF001
    assert conn is not None
    await semantic.connect(conn)
    clm = CLM(store, semantic)

    try:
        session_id = uuid4()
        await store.insert(
            EpisodicEntry(
                session_id=session_id,
                ts=datetime.now(tz=UTC),
                actor=Actor.USER_INPUT,
                role="user",
                content="ricordami di chiamare il commercialista domani",
            )
        )
        await store.insert(
            EpisodicEntry(
                session_id=session_id,
                ts=datetime.now(tz=UTC),
                actor=Actor.TOOL_OUTPUT,
                role="tool",
                content="tool result should not be promoted as fact",
            )
        )

        chunks = await clm.distill_session(session_id)
        assert chunks
        assert all(chunk.actor == Actor.USER_INPUT for chunk in chunks)

        second = await clm.distill_session(session_id)
        assert second == []
    finally:
        await store.close()
        await asyncio.sleep(0)
