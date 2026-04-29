"""Meeting-prep — calendar event-driven meeting briefings.

Orchestrates data from calendar events, email history, Drive attachments,
and wiki context to produce a one-page markdown meeting brief.

This module is designed to be invoked from the ``meeting-prep`` skill,
which handles the actual workspace-agent delegation (calendar/gmail/drive).
The data layer functions here provide structured models and rendering.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for workspace delegate callable
WorkspaceDelegate = Callable[..., Any]


@dataclass
class MeetingEvent:
    """Represents a calendar event."""

    id: str
    summary: str
    start_time: str
    description: str | None = None
    attendees: list[str] = field(default_factory=list)
    attachment_uris: list[str] = field(default_factory=list)


@dataclass
class Participant:
    """A meeting participant with communication history summary."""

    email: str
    name: str = ""
    history_summary: str = ""
    email_count: int = 0

    @property
    def summary(self) -> str:
        """Return the history summary (alias for backward compat)."""
        return self.history_summary


@dataclass
class MeetingBrief:
    """Structured meeting brief ready for markdown rendering."""

    event_id: str
    event_summary: str
    start_time: str
    participants: list[Participant]
    attachments: list[dict[str, str]]
    wiki_context: dict[str, Any]
    pending_decisions: list[str]


def parse_event_input(user_input: str) -> dict[str, Any] | None:
    """Parse user input to extract event query parameters.

    This is a lightweight extraction; the actual event lookup is done
    via workspace-agent's calendar.list_events. This function prepares
    the search context.

    Args:
        user_input: Raw user input string.

    Returns:
        Dict with ``raw`` (original input), ``keywords`` (extracted),
        or ``None`` if input is empty.
    """
    if not user_input or not user_input.strip():
        return None

    return {
        "raw": user_input.strip(),
        "keywords": user_input.strip(),
    }


def truncate_participants(
    participants: list[Participant],
    max_count: int = 5,
) -> list[Participant]:
    """Truncate participant list to top-N by email count.

    When there are more than ``max_count`` participants, keeps only
    the ones with highest email_count (most communication history).

    Args:
        participants: Full list of participants.
        max_count: Maximum number to keep (default 5).

    Returns:
        Truncated list.
    """
    if len(participants) <= max_count:
        return participants

    sorted_p = sorted(
        participants,
        key=lambda p: p.email_count,
        reverse=True,
    )
    return sorted_p[:max_count]


async def build_meeting_brief(
    event_query: dict[str, Any],
    workspace_delegate: WorkspaceDelegate,
    wiki_context: dict[str, Any],
) -> MeetingBrief:
    """Build a meeting brief by orchestrating workspace-agent calls.

    This function simulates the delegation flow:
    1. Calls workspace_delegate to find the calendar event
    2. Extracts participants and their email history
    3. Gathers Drive attachments
    4. Incorporates wiki context
    5. Returns structured MeetingBrief

    Args:
        event_query: Dict with ``raw`` and ``keywords`` from user input.
        workspace_delegate: Callable that proxies to workspace-agent.
        wiki_context: Wiki recall context dict.

    Returns:
        Structured :class:`MeetingBrief`.
    """
    # Step 1: Find event via calendar
    calendar_result = await workspace_delegate(
        "calendar.list_events",
        q=event_query.get("keywords", ""),
    )

    events = calendar_result.get("events", [])
    if not events:
        return MeetingBrief(
            event_id="",
            event_summary="No matching event found",
            start_time="",
            participants=[],
            attachments=[],
            wiki_context=wiki_context,
            pending_decisions=[],
        )

    event = events[0]
    event_id = event.get("id", "")
    event_summary = event.get("summary", "Unknown")
    start_time = event.get("start", {}).get("dateTime", "")
    description = event.get("description", "")

    # Step 2: Extract participants
    attendees = event.get("attendees", [])
    all_participants: list[Participant] = []
    for att in attendees:
        email = att.get("email", "")
        if not email or email == "fulvio@example.com" or "fulvio" in email:
            continue  # Skip self

        # Fetch email history for this participant
        try:
            gmail_result = await workspace_delegate(
                "gmail.search",
                query=f"from:{email} OR to:{email}",
            )
            messages = gmail_result.get("messages", [])
            history = _synthesize_email_history(messages)
            all_participants.append(
                Participant(
                    email=email,
                    name=att.get("displayName", email.split("@")[0]),
                    history_summary=history,
                    email_count=len(messages),
                )
            )
        except Exception as e:
            logger.warning("Failed to fetch email history for %s: %s", email, e)
            all_participants.append(
                Participant(
                    email=email,
                    name=att.get("displayName", email.split("@")[0]),
                    history_summary="Email history unavailable.",
                    email_count=0,
                )
            )

    # Step 3: Gather Drive attachments
    attachments: list[dict[str, str]] = []
    try:
        drive_result = await workspace_delegate(
            "drive.read",
            event_id=event_id,
        )
        for f in drive_result.get("files", []):
            attachments.append(
                {
                    "file_name": f.get("name", "Unknown"),
                    "summary": f"Drive file: {f.get('name', 'Unknown')}",
                    "mime_type": f.get("mimeType", ""),
                    "url": f.get("webViewLink", ""),
                }
            )
    except Exception as e:
        logger.warning("Failed to fetch Drive attachments: %s", e)

    # Step 4: Extract pending decisions from wiki context and description
    pending_decisions: list[str] = []
    wiki_pages = wiki_context.get("pages", [])
    for page in wiki_pages:
        body = page.get("body_md", "")
        for line in body.split("\n"):
            if "pending" in line.lower() or "decision" in line.lower():
                pending_decisions.append(line.strip())
    if description:
        for line in description.split("\n"):
            if "pending" in line.lower() or "decision" in line.lower():
                pending_decisions.append(line.strip())

    # Deduplicate
    pending_decisions = list(dict.fromkeys(pending_decisions))

    # Truncate participants if > 10
    participants = truncate_participants(all_participants, max_count=10)

    return MeetingBrief(
        event_id=event_id,
        event_summary=event_summary,
        start_time=start_time,
        participants=participants,
        attachments=attachments,
        wiki_context=wiki_context,
        pending_decisions=pending_decisions,
    )


def render_meeting_brief(brief: MeetingBrief) -> str:
    """Render a MeetingBrief to a one-page markdown string.

    Args:
        brief: The meeting brief to render.

    Returns:
        Markdown string (max ~800 words).
    """
    lines: list[str] = _init_brief_lines(brief)
    _add_event_info(lines, brief)
    _add_participants(lines, brief.participants)
    _add_attachments(lines, brief.attachments)
    _add_pending_decisions(lines, brief.pending_decisions)
    _add_wiki_context(lines, brief.wiki_context)
    return "\n".join(lines)


def _init_brief_lines(brief: MeetingBrief) -> list[str]:
    """Initialize the brief with header lines."""
    return [
        "# Meeting Brief",
        "",
        f"**{brief.event_summary}**",
        "",
        f"*Start: {brief.start_time}*" if brief.start_time else "",
        "",
        "---",
        "",
    ]


def _add_event_info(lines: list[str], brief: MeetingBrief) -> None:
    """Add event info section."""
    lines.append("## Event")
    lines.append("")
    lines.append(f"- **ID**: {brief.event_id}" if brief.event_id else "")
    lines.append(f"- **Summary**: {brief.event_summary}")
    if brief.start_time:
        _add_formatted_time(lines, brief.start_time)


def _add_formatted_time(lines: list[str], start_time: str) -> None:
    """Add formatted start time."""
    try:
        dt = datetime.datetime.fromisoformat(start_time)
        lines.append(f"- **Date**: {dt.strftime('%Y-%m-%d %H:%M')}")
    except (ValueError, TypeError):
        lines.append(f"- **Start**: {start_time}")
    lines.append("")


def _add_participants(lines: list[str], participants: list[Participant]) -> None:
    """Add participants section."""
    lines.append("## Participants")
    lines.append("")
    if not participants:
        lines.append("No external participants found.")
        lines.append("")
        return
    for p in participants:
        name_str = f" ({p.name})" if p.name else ""
        lines.append(f"### {p.email}{name_str}")
        if p.history_summary:
            lines.append("")
            lines.append(f"_{p.history_summary}_")
        if p.email_count > 0:
            lines.append(f"*{p.email_count} email(s) in last 90 days*")
        lines.append("")
    lines.append("")


def _add_attachments(lines: list[str], attachments: list[dict[str, str]]) -> None:
    """Add attachments section."""
    if not attachments:
        return
    lines.append("## Key Attachments")
    lines.append("")
    for att in attachments:
        lines.append(f"- **{att.get('file_name', 'Unknown')}**: {att.get('summary', '')}")
    lines.append("")


def _add_pending_decisions(lines: list[str], decisions: list[str]) -> None:
    """Add pending decisions section."""
    if not decisions:
        return
    lines.append("## Pending Decisions")
    lines.append("")
    for d in decisions:
        lines.append(f"- {d}")
    lines.append("")


def _add_wiki_context(lines: list[str], wiki_context: dict[str, Any]) -> None:
    """Add wiki context section."""
    wiki_pages = wiki_context.get("pages", [])
    if not wiki_pages:
        return
    lines.append("## Wiki Context")
    lines.append("")
    for page in wiki_pages:
        slug = page.get("slug", "unknown")
        body = page.get("body_md", "")
        preview = "\n".join(body.split("\n")[:3])
        lines.append(f"**{slug}**:")
        lines.append(f"> {preview}")
    lines.append("")


def _synthesize_email_history(messages: list[dict]) -> str:
    """Synthesize a short summary from email messages.

    Args:
        messages: List of message dicts from gmail.search.

    Returns:
        Short textual summary.
    """
    if not messages:
        return "No recent email history."

    subjects = [m.get("subject", "") for m in messages if m.get("subject")]

    # Extract key topics from subjects (deduplicate)
    unique_subjects = list(dict.fromkeys(subjects))
    topic_summary = "; ".join(unique_subjects[:5])

    if len(messages) == 1:
        return f"1 email found. Topics: {topic_summary}"
    else:
        return f"{len(messages)} emails found. Topics: {topic_summary}"
