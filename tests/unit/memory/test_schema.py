# Unit tests for aria.memory.schema
# Per sprint plan W1.1.H acceptance criteria

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aria.memory.schema import (
    Actor,
    EpisodicEntry,
    MemoryStats,
    SemanticChunk,
    content_hash,
    make_episodic_entry,
    make_semantic_chunk,
)


class TestActor:
    """Test Actor enum."""

    def test_actor_values(self) -> None:
        """Actor enum has correct values."""
        assert Actor.USER_INPUT.value == "user_input"
        assert Actor.TOOL_OUTPUT.value == "tool_output"
        assert Actor.AGENT_INFERENCE.value == "agent_inference"
        assert Actor.SYSTEM_EVENT.value == "system_event"

    def test_actor_is_string_enum(self) -> None:
        """Actor is a string enum."""
        assert isinstance(Actor.USER_INPUT, str)
        assert Actor.USER_INPUT == "user_input"


class TestContentHash:
    """Test content_hash function."""

    def test_content_hash_format(self) -> None:
        """content_hash returns 'sha256:<hex>' format."""
        result = content_hash("test content")
        assert result.startswith("sha256:")
        assert len(result) == len("sha256:") + 64  # SHA256 hex is 64 chars

    def test_content_hash_deterministic(self) -> None:
        """Same content produces same hash."""
        h1 = content_hash("test")
        h2 = content_hash("test")
        assert h1 == h2

    def test_content_hash_different_for_different_content(self) -> None:
        """Different content produces different hashes."""
        h1 = content_hash("test1")
        h2 = content_hash("test2")
        assert h1 != h2


class TestEpisodicEntry:
    """Test EpisodicEntry model."""

    def test_create_with_required_fields(self) -> None:
        """Can create entry with required fields."""
        now = datetime.now(tz=UTC)
        session = uuid4()

        entry = EpisodicEntry(
            session_id=session,
            ts=now,
            actor=Actor.USER_INPUT,
            role="user",
            content="Hello world",
        )

        assert entry.session_id == session
        assert entry.ts == now
        assert entry.actor == Actor.USER_INPUT
        assert entry.role == "user"
        assert entry.content == "Hello world"
        assert entry.tags == []
        assert entry.meta == {}

    def test_auto_generates_content_hash(self) -> None:
        """content_hash is auto-generated if not provided."""
        entry = EpisodicEntry(
            session_id=uuid4(),
            ts=datetime.now(tz=UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content="Test content",
        )

        assert entry.content_hash.startswith("sha256:")
        expected = f"sha256:{hashlib.sha256(b'Test content').hexdigest()}"
        assert entry.content_hash == expected

    def test_uuid_auto_generated(self) -> None:
        """id is auto-generated if not provided."""
        entry = EpisodicEntry(
            session_id=uuid4(),
            ts=datetime.now(tz=UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content="Test",
        )

        assert entry.id is not None

    def test_tags_default_empty_list(self) -> None:
        """tags defaults to empty list."""
        entry = EpisodicEntry(
            session_id=uuid4(),
            ts=datetime.now(tz=UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content="Test",
        )

        assert entry.tags == []

    def test_meta_default_empty_dict(self) -> None:
        """meta defaults to empty dict."""
        entry = EpisodicEntry(
            session_id=uuid4(),
            ts=datetime.now(tz=UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content="Test",
        )

        assert entry.meta == {}

    def test_all_actor_types_valid(self) -> None:
        """All Actor types are valid for entry."""
        for actor in Actor:
            entry = EpisodicEntry(
                session_id=uuid4(),
                ts=datetime.now(tz=UTC),
                actor=actor,
                role="user",
                content="Test",
            )
            assert entry.actor == actor

    def test_all_role_types_valid(self) -> None:
        """All role types are valid."""
        for role in ["user", "assistant", "system", "tool"]:
            entry = EpisodicEntry(
                session_id=uuid4(),
                ts=datetime.now(tz=UTC),
                actor=Actor.USER_INPUT,
                role=role,
                content="Test",
            )
            assert entry.role == role


class TestSemanticChunk:
    """Test SemanticChunk model."""

    def test_create_with_required_fields(self) -> None:
        """Can create chunk with required fields."""
        now = datetime.now(tz=UTC)
        source_ids = [uuid4(), uuid4()]

        chunk = SemanticChunk(
            source_episodic_ids=source_ids,
            actor=Actor.USER_INPUT,
            kind="fact",
            text="The sky is blue",
            first_seen=now,
            last_seen=now,
        )

        assert chunk.source_episodic_ids == source_ids
        assert chunk.actor == Actor.USER_INPUT
        assert chunk.kind == "fact"
        assert chunk.text == "The sky is blue"
        assert chunk.confidence == 1.0
        assert chunk.occurrences == 1

    def test_all_kinds_valid(self) -> None:
        """All kind types are valid."""
        now = datetime.now(tz=UTC)
        for kind in ["fact", "preference", "decision", "action_item", "concept"]:
            chunk = SemanticChunk(
                source_episodic_ids=[uuid4()],
                actor=Actor.USER_INPUT,
                kind=kind,  # type: ignore
                text="Test",
                first_seen=now,
                last_seen=now,
            )
            assert chunk.kind == kind


class TestMakeHelpers:
    """Test helper functions."""

    def test_make_episodic_entry(self) -> None:
        """make_episodic_entry creates valid entry."""
        session = uuid4()
        entry = make_episodic_entry(
            session_id=session,
            content="Remember that I prefer Italian food",
            actor=Actor.USER_INPUT,
            role="user",
        )

        assert entry.session_id == session
        assert entry.content == "Remember that I prefer Italian food"
        assert entry.actor == Actor.USER_INPUT

    def test_make_semantic_chunk(self) -> None:
        """make_semantic_chunk creates valid chunk."""
        source_id = uuid4()
        chunk = make_semantic_chunk(
            source_episodic_ids=[source_id],
            actor=Actor.USER_INPUT,
            kind="preference",
            text="User prefers Italian food",
        )

        assert chunk.source_episodic_ids == [source_id]
        assert chunk.kind == "preference"
        assert chunk.text == "User prefers Italian food"
        assert chunk.confidence == 1.0


class TestMemoryStats:
    """Test MemoryStats model."""

    def test_create_with_defaults(self) -> None:
        """Can create MemoryStats with defaults."""
        stats = MemoryStats()

        assert stats.t0_count == 0
        assert stats.t1_count == 0
        assert stats.sessions == 0
        assert stats.last_session_ts is None
        assert stats.avg_entry_size == 0.0
        assert stats.storage_bytes == 0

    def test_create_with_values(self) -> None:
        """Can create MemoryStats with values."""
        now = datetime.now(tz=UTC)
        stats = MemoryStats(
            t0_count=100,
            t1_count=50,
            sessions=10,
            last_session_ts=now,
            avg_entry_size=512.5,
            storage_bytes=1024000,
        )

        assert stats.t0_count == 100
        assert stats.t1_count == 50
        assert stats.sessions == 10
        assert stats.last_session_ts == now
        assert stats.avg_entry_size == 512.5
        assert stats.storage_bytes == 1024000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
