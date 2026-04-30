from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003

import pytest

from aria.agents.coordination import (
    ContextEnvelope,
    WikiPageSnapshot,
    cleanup_expired_envelopes,
    create_envelope,
    load_envelope,
    save_envelope,
)


@pytest.fixture
def sample_snapshot() -> WikiPageSnapshot:
    return WikiPageSnapshot(
        title="Architecture Overview",
        content="ARIA uses a modular agent architecture.",
        path="/docs/architecture",
        section="design",
    )


@pytest.fixture
def sample_envelope(sample_snapshot: WikiPageSnapshot) -> ContextEnvelope:
    return create_envelope(
        trace_id="trace-100",
        session_id="session-abc",
        wiki_pages=[sample_snapshot],
        profile_snapshot="User: test",
    )


class TestWikiPageSnapshot:
    def test_creation(self) -> None:
        snap = WikiPageSnapshot(
            title="Test Page",
            content="Test content",
            path="/test",
        )
        assert snap.title == "Test Page"
        assert snap.content == "Test content"
        assert snap.path == "/test"
        assert snap.section == ""

    def test_creation_with_section(self) -> None:
        snap = WikiPageSnapshot(
            title="Test Page",
            content="Test content",
            path="/test",
            section="overview",
        )
        assert snap.section == "overview"


class TestContextEnvelopeCreation:
    def test_required_fields(self) -> None:
        env = ContextEnvelope(
            trace_id="trace-001",
            session_id="session-001",
        )
        assert env.trace_id == "trace-001"
        assert env.session_id == "session-001"
        assert env.wiki_pages == []
        assert env.profile_snapshot is None
        assert env.envelope_id is not None

    def test_expires_at_default_is_five_minutes(self) -> None:
        before = datetime.now(UTC)
        env = ContextEnvelope(
            trace_id="trace-002",
            session_id="session-002",
        )
        after = datetime.now(UTC)
        assert env.expires_at is not None
        assert before + timedelta(minutes=5) <= env.expires_at <= after + timedelta(minutes=5)

    def test_expires_at_custom(self) -> None:
        custom_expiry = datetime.now(UTC) + timedelta(hours=1)
        env = ContextEnvelope(
            trace_id="trace-003",
            session_id="session-003",
            expires_at=custom_expiry,
        )
        assert env.expires_at == custom_expiry

    def test_is_expired_false_when_not_expired(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        env = ContextEnvelope(
            trace_id="trace-004",
            session_id="session-004",
            expires_at=future,
        )
        assert env.is_expired is False

    def test_is_expired_true_when_expired(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=1)
        env = ContextEnvelope(
            trace_id="trace-005",
            session_id="session-005",
            expires_at=past,
        )
        assert env.is_expired is True

    def test_is_expired_false_when_expires_at_none(self) -> None:
        env = ContextEnvelope(
            trace_id="trace-006",
            session_id="session-006",
            expires_at=None,
        )
        assert env.is_expired is False


class TestCreateEnvelope:
    def test_factory_creates_envelope(self, sample_snapshot: WikiPageSnapshot) -> None:
        env = create_envelope(
            trace_id="trace-200",
            session_id="session-xyz",
            wiki_pages=[sample_snapshot],
            profile_snapshot="Profile data",
        )
        assert env.trace_id == "trace-200"
        assert env.session_id == "session-xyz"
        assert len(env.wiki_pages) == 1
        assert env.wiki_pages[0].title == "Architecture Overview"
        assert env.profile_snapshot == "Profile data"

    def test_factory_without_optional(self) -> None:
        env = create_envelope(
            trace_id="trace-201",
            session_id="session-xyz",
        )
        assert env.wiki_pages == []
        assert env.profile_snapshot is None


class TestEnvelopePersistence:
    def test_save_and_load_roundtrip(
        self, sample_envelope: ContextEnvelope, tmp_path: Path
    ) -> None:
        os.environ["ARIA_RUNTIME"] = str(tmp_path)
        try:
            saved_path = save_envelope(sample_envelope)
            assert saved_path.exists()
            with open(saved_path) as f:
                data = json.load(f)
            assert data["trace_id"] == "trace-100"
            assert data["session_id"] == "session-abc"

            loaded = load_envelope(sample_envelope.envelope_id)
            assert loaded is not None
            assert loaded.trace_id == sample_envelope.trace_id
            assert loaded.session_id == sample_envelope.session_id
            assert len(loaded.wiki_pages) == 1
            assert loaded.wiki_pages[0].title == "Architecture Overview"
        finally:
            os.environ.pop("ARIA_RUNTIME", None)

    def test_load_envelope_returns_none_for_missing(self, tmp_path: Path) -> None:
        os.environ["ARIA_RUNTIME"] = str(tmp_path)
        try:
            result = load_envelope("nonexistent-id")
            assert result is None
        finally:
            os.environ.pop("ARIA_RUNTIME", None)

    def test_cleanup_expired_envelopes(self, tmp_path: Path) -> None:
        os.environ["ARIA_RUNTIME"] = str(tmp_path)
        try:
            expired_env = ContextEnvelope(
                trace_id="trace-expired",
                session_id="session-expired",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
            save_envelope(expired_env)

            valid_env = ContextEnvelope(
                trace_id="trace-valid",
                session_id="session-valid",
            )
            save_envelope(valid_env)

            removed = cleanup_expired_envelopes()
            assert removed == 1

            expired_loaded = load_envelope(expired_env.envelope_id)
            assert expired_loaded is None

            valid_loaded = load_envelope(valid_env.envelope_id)
            assert valid_loaded is not None
        finally:
            os.environ.pop("ARIA_RUNTIME", None)

    def test_cleanup_with_no_envelopes_dir(self, tmp_path: Path) -> None:
        os.environ["ARIA_RUNTIME"] = str(tmp_path)
        try:
            env_dir = tmp_path / "envelopes"
            assert not env_dir.exists()
            removed = cleanup_expired_envelopes()
            assert removed == 0
        finally:
            os.environ.pop("ARIA_RUNTIME", None)
