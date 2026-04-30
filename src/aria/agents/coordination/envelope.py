# ARIA Agent Coordination — Context Envelope
#
# Per stabilization plan §F2.3:
# Shared context envelope passed between conductor and sub-agents.
#
# Models:
# - WikiPageSnapshot: Snapshot of a wiki page for context
# - ContextEnvelope: Full shared context envelope
#
# Functions:
# - create_envelope: Factory to build a new envelope
# - save_envelope: Persist envelope to .aria/runtime/envelopes/
# - load_envelope: Load envelope from disk by ID
# - cleanup_expired_envelopes: Remove expired envelopes
#
# Usage:
#   from aria.agents.coordination.envelope import (
#       ContextEnvelope, WikiPageSnapshot, create_envelope,
#       save_envelope, load_envelope, cleanup_expired_envelopes,
#   )

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ENVELOPES_SUBDIR = Path(".aria") / "runtime" / "envelopes"
_ENVELOPE_TTL_MINUTES = 5


# === Wiki Page Snapshot ===


class WikiPageSnapshot(BaseModel):
    """Snapshot of a single wiki page for context transfer.

    Conductor-level recall result; passed to sub-agents so they
    have relevant wiki context without direct DB access.
    """

    title: str
    content: str
    path: str
    section: str = ""

    model_config = {}


# === Context Envelope ===


class ContextEnvelope(BaseModel):
    """Shared context envelope for agent coordination.

    Carries wiki snapshots and profile data between conductor and
    sub-agents. Self-expiring — TTL of 5 minutes by default.
    """

    envelope_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    session_id: str
    wiki_pages: list[WikiPageSnapshot] = Field(default_factory=list)
    profile_snapshot: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    model_config = {}

    def __init__(self, **data: object) -> None:
        if "expires_at" not in data or data["expires_at"] is None:
            created = data.get("created_at", datetime.now(UTC))
            if not isinstance(created, datetime):
                created = datetime.now(UTC)
            data["expires_at"] = created + timedelta(minutes=_ENVELOPE_TTL_MINUTES)
        super().__init__(**data)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


# === Factory ===


def create_envelope(
    trace_id: str,
    session_id: str,
    wiki_pages: list[WikiPageSnapshot] | None = None,
    profile_snapshot: str | None = None,
) -> ContextEnvelope:
    """Build a new ContextEnvelope with defaults.

    Args:
        trace_id: Trace ID for request tracking.
        session_id: Session identifier.
        wiki_pages: Optional list of wiki page snapshots.
        profile_snapshot: Optional profile markdown string.

    Returns:
        A new ContextEnvelope instance.
    """
    return ContextEnvelope(
        envelope_id=str(uuid4()),
        trace_id=trace_id,
        session_id=session_id,
        wiki_pages=wiki_pages or [],
        profile_snapshot=profile_snapshot,
        created_at=datetime.now(UTC),
    )


# === Persistence Helpers ===


def _get_envelopes_dir() -> Path:
    """Resolve the envelopes storage directory.

    Uses ARIA_RUNTIME env var if set, otherwise defaults to
    <ARIA_HOME>/.aria/runtime/envelopes.
    """
    runtime_env = os.environ.get("ARIA_RUNTIME")
    if runtime_env:
        base = Path(runtime_env)
    else:
        aria_home = os.environ.get("ARIA_HOME", str(Path.home() / "coding" / "aria"))
        base = Path(aria_home) / ".aria" / "runtime"
    return base / "envelopes"


def save_envelope(envelope: ContextEnvelope) -> Path:
    """Persist an envelope to disk as JSON.

    Creates the envelopes directory if it does not exist.

    Args:
        envelope: The ContextEnvelope to save.

    Returns:
        Path to the saved JSON file.
    """
    env_dir = _get_envelopes_dir()
    env_dir.mkdir(parents=True, exist_ok=True)
    path = env_dir / f"{envelope.envelope_id}.json"
    data = envelope.model_dump(mode="json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.debug("Saved envelope %s to %s", envelope.envelope_id, path)
    return path


def load_envelope(envelope_id: str) -> ContextEnvelope | None:
    """Load an envelope from disk by its ID.

    Args:
        envelope_id: The UUID string of the envelope to load.

    Returns:
        The deserialized ContextEnvelope, or None if not found.
    """
    env_dir = _get_envelopes_dir()
    path = env_dir / f"{envelope_id}.json"
    if not path.exists():
        logger.debug("Envelope %s not found at %s", envelope_id, path)
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return ContextEnvelope.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to load envelope %s: %s", envelope_id, exc)
        return None


def cleanup_expired_envelopes() -> int:
    """Remove all expired envelope files from disk.

    Scans the envelopes directory and deletes files whose
    deserialized envelope has expired.

    Returns:
        Number of envelopes removed.
    """
    env_dir = _get_envelopes_dir()
    if not env_dir.exists():
        return 0

    removed = 0
    for path in env_dir.glob("*.json"):
        try:
            with open(path) as f:
                data = json.load(f)
            envelope = ContextEnvelope.model_validate(data)
            if envelope.is_expired:
                path.unlink()
                removed += 1
                logger.debug("Removed expired envelope %s", envelope.envelope_id)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.warning("Error processing envelope file %s: %s", path.name, exc)
            continue

    if removed:
        logger.info("Cleaned up %d expired envelope(s)", removed)
    return removed
