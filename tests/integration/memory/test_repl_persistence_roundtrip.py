"""End-to-end test: a simulated REPL turn must survive write → distill → recall."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.memory.clm import CLM
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore


@pytest.mark.asyncio
async def test_barbecue_topic_recall_after_distillation(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    episodic = EpisodicStore(db_path, cfg)
    await episodic.connect()
    semantic = SemanticStore(db_path, cfg)
    conn = episodic._conn
    if conn is None:
        raise RuntimeError("Connection is None")
    await semantic.connect(conn)
    clm = CLM(episodic, semantic)

    sid = uuid.uuid4()
    now = datetime.now(UTC)

    user_msg = "Cerca informazioni sul barbecue di pesce siciliano"
    assistant_msg = (
        "Ecco una sintesi: ricette tradizionali, tecniche e tempi di cottura"
        " per il barbecue di pesce."
    )
    for actor, role, text in (
        (Actor.USER_INPUT, "user", user_msg),
        (Actor.AGENT_INFERENCE, "assistant", assistant_msg),
    ):
        await episodic.insert(
            EpisodicEntry(
                session_id=sid, ts=now, actor=actor, role=role,
                content=text, content_hash=content_hash(text),
                tags=["repl_message"],
            )
        )

    chunks = await clm.distill_session(sid)
    assert chunks, "distillation must produce at least one chunk"

    matches = await semantic.search("barbecue", top_k=10)
    assert matches, "semantic recall must surface the barbecue chunk"
    assert any("barbecue" in c.text.lower() for c in matches)

    fts = await episodic.search_text("barbecue", top_k=10)
    assert any("barbecue" in e.content.lower() for e in fts)
