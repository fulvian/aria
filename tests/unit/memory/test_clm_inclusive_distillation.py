"""CLM must produce chunks for general topics and assistant turns."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from aria.memory.clm import CLM
from aria.memory.schema import Actor, EpisodicEntry, content_hash


class _StubSemantic:
    def __init__(self) -> None:
        self.chunks: list = []

    async def list_by_session(self, *_a, **_kw):  # noqa: D401
        return []

    async def insert_many(self, chunks):
        self.chunks.extend(chunks)


@pytest.fixture
def make_entry():
    def _factory(actor: Actor, role: str, content: str) -> EpisodicEntry:
        return EpisodicEntry(
            session_id=uuid.uuid4(),
            ts=datetime.now(UTC),
            actor=actor,
            role=role,
            content=content,
            content_hash=content_hash(content),
        )

    return _factory


def test_topic_fallback_chunk_for_user_input(make_entry):
    clm = CLM(store=None, semantic=_StubSemantic())  # type: ignore[arg-type]
    entries = [make_entry(Actor.USER_INPUT, "user", "Cerca una guida sul barbecue di pesce")]
    chunks = clm._distill_entries(entries)
    assert chunks, "expected at least one fallback topic chunk"
    assert any("barbecue" in c.text.lower() for c in chunks)


def test_assistant_turn_yields_concept_chunk(make_entry):
    clm = CLM(store=None, semantic=_StubSemantic())  # type: ignore[arg-type]
    entries = [
        make_entry(
            Actor.AGENT_INFERENCE,
            "assistant",
            "Riassunto della ricerca sul barbecue: tre tecniche di affumicatura.",
        )
    ]
    chunks = clm._distill_entries(entries)
    assert chunks
    assert any(c.kind == "concept" for c in chunks)
