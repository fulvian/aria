"""Integration tests: ContextEnvelope propagation — conductor → sub-agent, persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from aria.agents.coordination.envelope import (
    ContextEnvelope,
    WikiPageSnapshot,
    create_envelope,
    load_envelope,
    save_envelope,
)


@pytest.fixture
def envelope_fixture(tmp_path: Path) -> ContextEnvelope:
    """Create a sample envelope as the conductor would."""
    wiki = WikiPageSnapshot(
        title="ARIA Architecture",
        content="ARIA uses a modular agent architecture.",
        path="/docs/architecture",
        section="Overview",
    )
    return create_envelope(
        trace_id="trace-123",
        session_id="ses-test-integration",
        wiki_pages=[wiki],
        profile_snapshot="User prefers Python.",
    )


class TestEnvelopePropagation:
    """Envelope created by conductor must be loadable by a sub-agent."""

    def test_envelope_created_by_conductor_readable_by_subagent(
        self,
        envelope_fixture: ContextEnvelope,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        conductor_envelope = envelope_fixture
        monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path))
        path = save_envelope(conductor_envelope)

        assert path.exists()
        assert path.name == f"{conductor_envelope.envelope_id}.json"

        sub_agent_loaded = load_envelope(conductor_envelope.envelope_id)
        assert sub_agent_loaded is not None
        assert sub_agent_loaded.trace_id == "trace-123"
        assert sub_agent_loaded.session_id == "ses-test-integration"
        assert len(sub_agent_loaded.wiki_pages) == 1
        assert sub_agent_loaded.wiki_pages[0].title == "ARIA Architecture"
        assert sub_agent_loaded.profile_snapshot == "User prefers Python."

    def test_envelope_file_persistence(
        self,
        envelope_fixture: ContextEnvelope,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path))
        env = envelope_fixture
        saved_path = save_envelope(env)

        assert saved_path.is_file()
        content = saved_path.read_text(encoding="utf-8")
        assert env.envelope_id in content
        assert "trace-123" in content
        assert "ARIA Architecture" in content

        loaded = load_envelope(env.envelope_id)
        assert loaded is not None
        assert loaded.model_dump(mode="json") == env.model_dump(mode="json")

    def test_load_nonexistent_envelope_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path))
        result = load_envelope("nonexistent-id")
        assert result is None

    def test_envelope_expires(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ARIA_RUNTIME", str(tmp_path))
        from datetime import UTC, datetime, timedelta

        old = datetime.now(UTC) - timedelta(minutes=10)
        env = ContextEnvelope(
            trace_id="trace-expired",
            session_id="ses-expired",
            created_at=old,
            expires_at=old,
        )
        assert env.is_expired is True

        save_envelope(env)
        from aria.agents.coordination.envelope import cleanup_expired_envelopes

        removed = cleanup_expired_envelopes()
        assert removed >= 1

        loaded = load_envelope(env.envelope_id)
        assert loaded is None
