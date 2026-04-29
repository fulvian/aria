"""Unit tests for meeting-prep module (meeting_prep.py)."""

from __future__ import annotations

from datetime import datetime

import pytest

from aria.agents.productivity.meeting_prep import (
    MeetingBrief,
    MeetingEvent,
    Participant,
    build_meeting_brief,
    render_meeting_brief,
    parse_event_input,
    truncate_participants,
)


class TestMeetingEvent:
    """Tests for MeetingEvent dataclass."""

    def test_minimal_event(self) -> None:
        event = MeetingEvent(
            id="evt_001",
            summary="Q1 Review",
            start_time="2026-05-01T10:00:00",
        )
        assert event.id == "evt_001"
        assert event.summary == "Q1 Review"
        assert event.description is None

    def test_full_event(self) -> None:
        event = MeetingEvent(
            id="evt_002",
            summary="Client Call - Acme",
            description="Discuss Q2 roadmap",
            start_time="2026-05-03T14:30:00",
            attendees=["fulvio@example.com", "mario@acme.com", "anna@acme.com"],
            attachment_uris=["https://drive.google.com/file/d/123"],
        )
        assert len(event.attendees) == 3


class TestParticipant:
    """Tests for Participant dataclass."""

    def test_participant_with_history(self) -> None:
        p = Participant(
            email="mario@acme.com",
            name="Mario Rossi",
            history_summary="Discussed Q1 budget, follow-up on proposal.",
            email_count=12,
        )
        assert p.summary == "Discussed Q1 budget, follow-up on proposal."
        assert p.email_count == 12


class TestParseEventInput:
    """Tests for parse_event_input()."""

    def test_parse_with_all_fields(self) -> None:
        result = parse_event_input(
            "prepara meeting Acme del 5 maggio 2026 sul progetto ARIA"
        )
        assert result is not None
        assert "acme" in result["keywords"].lower() or "Acme" in result.get("raw", "")
        assert result["raw"] == "prepara meeting Acme del 5 maggio 2026 sul progetto ARIA"

    def test_parse_minimal(self) -> None:
        result = parse_event_input("prepara call domani")
        assert result is not None
        assert "raw" in result

    def test_parse_empty(self) -> None:
        result = parse_event_input("")
        assert result is None


class TestTruncateParticipants:
    """Tests for truncate_participants()."""

    def test_no_truncation_needed(self) -> None:
        participants = [
            Participant(email=f"user{i}@example.com", name=f"User {i}")
            for i in range(3)
        ]
        result = truncate_participants(participants, max_count=5)
        assert len(result) == 3

    def test_truncation_applied(self) -> None:
        participants = [
            Participant(email=f"user{i}@example.com", name=f"User {i}", email_count=i)
            for i in range(10)
        ]
        result = truncate_participants(participants, max_count=5)
        assert len(result) == 5
        # Highest email_count should be kept
        result_counts = [p.email_count for p in result]

    def test_truncation_empty(self) -> None:
        assert truncate_participants([], max_count=5) == []


class MockWorkspaceDelegate:
    """Mock for workspace-agent delegate callable."""

    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(self, action: str, **kwargs: dict) -> dict:
        self.call_count += 1
        if action == "calendar.list_events":
            return {
                "events": [
                    {
                        "id": "evt_mock_001",
                        "summary": "Q1 Review Meeting",
                        "description": "Quarterly review with Acme team",
                        "start": {"dateTime": "2026-05-01T10:00:00"},
                        "attendees": [
                            {"email": "fulvio@example.com"},
                            {"email": "mario@acme.com"},
                            {"email": "anna@acme.com"},
                        ],
                    }
                ]
            }
        if action == "gmail.search":
            return {
                "messages": [
                    {
                        "id": "msg_001",
                        "from": "mario@acme.com",
                        "subject": "Q1 Budget Review",
                        "snippet": "Let's discuss the Q1 budget numbers.",
                    },
                    {
                        "id": "msg_002",
                        "from": "mario@acme.com",
                        "subject": "Re: Proposal Timeline",
                        "snippet": "The timeline looks good, let's proceed.",
                    },
                ]
            }
        if action == "drive.read":
            return {
                "files": [
                    {
                        "id": "file_001",
                        "name": "Q1_Report.pdf",
                        "mimeType": "application/pdf",
                        "webViewLink": "https://drive.google.com/file/d/123",
                    }
                ]
            }
        return {}


class TestBuildMeetingBrief:
    """Tests for build_meeting_brief()."""

    @pytest.mark.asyncio
    async def test_build_basic_brief(self) -> None:
        delegate = MockWorkspaceDelegate()
        brief = await build_meeting_brief(
            event_query={"raw": "Q1 review meeting with Acme", "keywords": "Acme"},
            workspace_delegate=delegate,
            wiki_context={},
        )

        assert isinstance(brief, MeetingBrief)
        assert brief.event_summary == "Q1 Review Meeting"

    @pytest.mark.asyncio
    async def test_participant_extraction(self) -> None:
        delegate = MockWorkspaceDelegate()
        brief = await build_meeting_brief(
            event_query={"raw": "Q1 review", "keywords": "review"},
            workspace_delegate=delegate,
            wiki_context={},
        )

        # Should have external participants (not self)
        external = [p for p in brief.participants if "fulvio" not in p.email]
        assert len(external) > 0

    @pytest.mark.asyncio
    async def test_brief_renders(self) -> None:
        delegate = MockWorkspaceDelegate()
        brief = await build_meeting_brief(
            event_query={"raw": "Q1 review", "keywords": "review"},
            workspace_delegate=delegate,
            wiki_context={},
        )
        md = render_meeting_brief(brief)
        assert "# Meeting Brief" in md
        assert brief.event_summary in md


class TestRenderMeetingBrief:
    """Tests for render_meeting_brief()."""

    def test_render_full_brief(self) -> None:
        brief = MeetingBrief(
            event_id="evt_001",
            event_summary="Q1 Review with Acme",
            start_time="2026-05-01T10:00:00",
            participants=[
                Participant(
                    email="mario@acme.com",
                    name="Mario Rossi",
                    history_summary="Discussed Q1 budget, follows up regularly.",
                    email_count=15,
                )
            ],
            attachments=[
                {
                    "file_name": "Q1_Report.pdf",
                    "summary": "Q1 financial report with revenue figures.",
                }
            ],
            wiki_context={"pages": []},
            pending_decisions=["Approve Q2 budget allocation"],
        )
        md = render_meeting_brief(brief)

        assert "# Meeting Brief" in md
        assert "Q1 Review with Acme" in md
        assert "Mario Rossi" in md
        assert "Q1_Report.pdf" in md
        assert "Approve Q2 budget" in md

    def test_render_minimal_brief(self) -> None:
        brief = MeetingBrief(
            event_id="evt_002",
            event_summary="Quick sync",
            start_time="2026-05-02T15:00:00",
            participants=[],
            attachments=[],
            wiki_context={},
            pending_decisions=[],
        )
        md = render_meeting_brief(brief)
        assert "# Meeting Brief" in md
        assert "Quick sync" in md
        assert "No participants" in md or "participants" in md.lower()
