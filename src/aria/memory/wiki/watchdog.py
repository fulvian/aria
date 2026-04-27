# ARIA Memory Wiki — Watchdog Task
#
# Per docs/plans/auto_persistence_echo.md §5.3 + Phase B.
#
# Scheduler task: detects skipped wiki_update calls and triggers
# catch-up curation from kilo.db.
#
# Mechanism:
# - Runs every 15 min (configurable via scheduler cron)
# - Queries kilo.db for sessions with conductor messages
# - Compares against wiki_watermark (last curated timestamp)
# - Gap > 5 min and ≥ 3 unprocessed messages → spawn catch-up
# - Catch-up: log the gap, mark for curator-only processing
#   (actual conductor spawn handled by runner)
#
# Usage:
#   from aria.memory.wiki.watchdog import run_watchdog_cycle
#   result = await run_watchdog_cycle(wiki_store, kilo_reader)

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.memory.wiki.db import WikiStore
    from aria.memory.wiki.kilo_reader import KiloReader, KiloSessionInfo

logger = logging.getLogger(__name__)

# === Constants ===

# Minimum gap (seconds) between last watermark and last message to trigger catch-up
GAP_THRESHOLD_SECONDS = 300  # 5 minutes

# Minimum unprocessed messages to trigger catch-up
MIN_MESSAGES_FOR_CATCHUP = 3

# Maximum sessions to process in a single watchdog cycle
MAX_SESSIONS_PER_CYCLE = 10


@dataclass
class WatchdogResult:
    """Result of a single watchdog cycle."""

    status: str  # "ok", "no_gap", "catchup_triggered", "error"
    sessions_checked: int = 0
    gaps_found: int = 0
    catchups_triggered: int = 0
    details: list[dict] = field(default_factory=list)


@dataclass
class SessionGap:
    """Detected gap in a session's wiki curation."""

    session_id: str
    last_watermark_ts: int  # millis
    last_msg_ts: int  # millis
    gap_seconds: float
    unprocessed_count: int


def _kilo_db_path() -> Path:
    """Resolve kilo.db path from environment or default."""
    aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
    # Kilo stores its DB in the isolated home
    kilo_home = aria_home / ".aria" / "kilo-home"
    return kilo_home / ".local" / "share" / "kilo" / "kilo.db"


async def run_watchdog_cycle(
    wiki_store: WikiStore,
    kilo_reader: KiloReader | None = None,
) -> WatchdogResult:
    """Run a single watchdog check cycle.

    Per plan §5.3:
    - Query kilo.db for sessions with unprocessed messages
    - Compare against wiki_watermark
    - Gap > 5 min and ≥ 3 messages → invoke catch-up

    Args:
        wiki_store: WikiStore for watermark queries.
        kilo_reader: Optional KiloReader (created from default path if None).

    Returns:
        WatchdogResult with cycle status.
    """
    result = WatchdogResult(status="ok")

    # Resolve kilo reader
    reader = kilo_reader
    reader_owned = False

    if reader is None:
        from aria.memory.wiki.kilo_reader import KiloReader

        kilo_path = _kilo_db_path()
        if not kilo_path.exists():  # noqa: ASYNC240
            logger.debug("kilo.db not found at %s — watchdog skipping", kilo_path)
            result.status = "error"
            result.details.append({"error": "kilo.db not found"})
            return result

        reader = KiloReader(kilo_path)
        await reader.connect()
        reader_owned = True

    try:
        if not reader.schema_ok:
            logger.warning("kilo.db schema check failed — watchdog skipping")
            result.status = "error"
            result.details.append({"error": "kilo.db schema mismatch"})
            return result

        # List sessions from kilo.db with sufficient messages
        # Only look at sessions from the last 24h to avoid scanning ancient history
        now_ms = int(time.time() * 1000)
        since_ts = now_ms - (24 * 3600 * 1000)  # 24h ago

        sessions = await reader.list_conductor_sessions(
            min_messages=MIN_MESSAGES_FOR_CATCHUP,
            since_ts=since_ts,
        )

        # Limit sessions per cycle
        sessions = sessions[:MAX_SESSIONS_PER_CYCLE]
        result.sessions_checked = len(sessions)

        if not sessions:
            logger.debug("No conductor sessions found for watchdog check")
            result.status = "no_gap"
            return result

        # Check each session for gaps
        gaps: list[SessionGap] = []
        for session in sessions:
            gap = await _check_session_gap(wiki_store, reader, session)
            if gap is not None:
                gaps.append(gap)

        result.gaps_found = len(gaps)

        if not gaps:
            result.status = "no_gap"
            return result

        # Process gaps: trigger catch-up for qualifying sessions
        for gap in gaps:
            catchup_result = await _trigger_catchup(wiki_store, reader, gap)
            result.details.append(catchup_result)
            if catchup_result.get("triggered", False):
                result.catchups_triggered += 1

        result.status = "catchup_triggered" if result.catchups_triggered > 0 else "no_gap"
        return result

    except Exception as exc:
        logger.error("Watchdog cycle failed: %s", exc)
        result.status = "error"
        result.details.append({"error": str(exc)})
        return result

    finally:
        if reader_owned:
            await reader.close()


async def _check_session_gap(
    wiki_store: WikiStore,
    reader: KiloReader,
    session: KiloSessionInfo,
) -> SessionGap | None:
    """Check if a session has an unprocessed gap.

    Args:
        wiki_store: WikiStore for watermark lookup.
        reader: KiloReader for message queries.
        session: Session summary from kilo.db.

    Returns:
        SessionGap if gap detected, None otherwise.
    """
    # Get watermark for this session
    watermark = await wiki_store.get_watermark(session.session_id)

    last_curated_ts = watermark.get("last_seen_ts", 0) if watermark is not None else 0

    # Compute gap
    gap_ms = session.last_msg_ts - last_curated_ts
    gap_seconds = gap_ms / 1000.0

    # Skip if gap is too small (messages are recent, conductor may still be processing)
    if gap_seconds < GAP_THRESHOLD_SECONDS:
        return None

    # Count unprocessed messages
    after_ts = last_curated_ts if last_curated_ts > 0 else None
    messages = await reader.get_messages_range(
        session_id=session.session_id,
        after_ts=after_ts,
        limit=1000,  # Reasonable upper bound
    )
    unprocessed_count = len(messages)

    if unprocessed_count < MIN_MESSAGES_FOR_CATCHUP:
        return None

    logger.info(
        "Watchdog gap detected: session=%s gap=%.0fs unprocessed=%d",
        session.session_id,
        gap_seconds,
        unprocessed_count,
    )

    return SessionGap(
        session_id=session.session_id,
        last_watermark_ts=last_curated_ts,
        last_msg_ts=session.last_msg_ts,
        gap_seconds=gap_seconds,
        unprocessed_count=unprocessed_count,
    )


async def _trigger_catchup(
    wiki_store: WikiStore,
    reader: KiloReader,
    gap: SessionGap,
) -> dict:
    """Trigger catch-up curation for a session gap.

    Per plan §5.3: spawn aria-conductor w/ ARIA_MODE=curator-only.
    In this implementation, we log the gap and prepare catch-up context.
    The actual conductor spawn is handled by the scheduler runner.

    Args:
        wiki_store: WikiStore for watermark management.
        reader: KiloReader for message access.
        gap: The detected session gap.

    Returns:
        Dict with catch-up result.
    """
    logger.info(
        "Triggering catch-up: session=%s unprocessed=%d gap=%.0fs",
        gap.session_id,
        gap.unprocessed_count,
        gap.gap_seconds,
    )

    # Fetch the unprocessed messages for context
    after_ts = gap.last_watermark_ts if gap.last_watermark_ts > 0 else None
    messages = await reader.get_messages_range(
        session_id=gap.session_id,
        after_ts=after_ts,
        limit=50,  # Cap for catch-up
    )

    # Build catch-up context (what the curator will process)
    message_summaries = [
        {
            "id": m.id,
            "role": m.role,
            "ts": m.time_created,
            "content_len": len(m.content),
        }
        for m in messages
    ]

    # In production, the scheduler runner would spawn a conductor subprocess
    # with ARIA_MODE=curator-only and these messages as input.
    # For now, we return the context and mark it as a candidate for catch-up.
    return {
        "session_id": gap.session_id,
        "triggered": True,
        "unprocessed_count": gap.unprocessed_count,
        "gap_seconds": gap.gap_seconds,
        "messages": message_summaries,
        "note": "Catch-up context prepared. Runner should spawn curator-only conductor.",
    }
