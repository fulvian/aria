# Tests for wiki.watchdog — Watchdog gap detection and catch-up

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest

from aria.memory.wiki.db import WikiStore
from aria.memory.wiki.kilo_reader import KiloReader
from aria.memory.wiki.watchdog import (
    GAP_THRESHOLD_SECONDS,
    MIN_MESSAGES_FOR_CATCHUP,
    WatchdogResult,
    run_watchdog_cycle,
)


def _create_kilo_db_with_messages(
    db_path: Path,
    messages: list[dict],
) -> None:
    """Create a kilo.db with message table and sample data."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            time_created INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE part (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT
        )
    """)
    for msg in messages:
        conn.execute(
            "INSERT INTO message (id, session_id, role, content, time_created) "
            "VALUES (?, ?, ?, ?, ?)",
            (msg["id"], msg["session_id"], msg["role"], msg.get("content", ""), msg["ts"]),
        )
    conn.commit()
    conn.close()


@pytest.fixture
async def wiki_store(tmp_path: Any) -> WikiStore:
    """Create a WikiStore with a temporary database."""
    db_path = tmp_path / "wiki.db"
    s = WikiStore(db_path)
    await s.connect()
    yield s
    await s.close()


@pytest.fixture
async def kilo_reader(tmp_path: Any) -> KiloReader:
    """Create a KiloReader with a temporary kilo.db."""
    db_path = tmp_path / "kilo.db"
    _create_kilo_db_with_messages(db_path, [])
    reader = KiloReader(db_path)
    await reader.connect()
    yield reader
    await reader.close()


class TestWatchdogNoGap:
    """Watchdog with no gap detected."""

    async def test_no_kilo_db(self, wiki_store: WikiStore, tmp_path: Any) -> None:
        """Watchdog returns error when kilo.db not found."""
        result = await run_watchdog_cycle(
            wiki_store,
            kilo_reader=KiloReader(tmp_path / "missing.db"),
        )
        assert result.status == "error"

    async def test_empty_kilo_db(self, wiki_store: WikiStore, kilo_reader: KiloReader) -> None:
        """Watchdog returns no_gap when kilo.db has no messages."""
        result = await run_watchdog_cycle(wiki_store, kilo_reader)
        assert result.status == "no_gap"
        assert result.sessions_checked == 0


class TestWatchdogGapDetection:
    """Watchdog gap detection tests."""

    async def test_detects_gap_in_session(self, wiki_store: WikiStore, tmp_path: Any) -> None:
        """Watchdog detects a session with unprocessed messages."""
        now_ms = int(time.time() * 1000)

        # Create kilo.db with a session that has many messages
        kilo_path = tmp_path / "kilo.db"
        messages = []
        for i in range(5):
            messages.append(
                {
                    "id": f"msg_{i}",
                    "session_id": "sess_gap",
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i}",
                    "ts": now_ms - (600000 - i * 60000),  # Staggered over 10 min
                }
            )
        _create_kilo_db_with_messages(kilo_path, messages)

        reader = KiloReader(kilo_path)
        await reader.connect()

        # No watermark exists for this session → last_curated_ts = 0
        # Gap is huge (from epoch to now), should be detected
        result = await run_watchdog_cycle(wiki_store, reader)

        assert result.status == "catchup_triggered"
        assert result.sessions_checked >= 1
        assert result.gaps_found >= 1
        assert result.catchups_triggered >= 1

        await reader.close()

    async def test_no_gap_when_watermark_is_recent(
        self, wiki_store: WikiStore, tmp_path: Any
    ) -> None:
        """Watchdog does not trigger when watermark is recent."""
        now_ms = int(time.time() * 1000)

        # Create kilo.db with recent messages
        kilo_path = tmp_path / "kilo.db"
        messages = [
            {
                "id": "m1",
                "session_id": "sess_recent",
                "role": "user",
                "content": "hi",
                "ts": now_ms - 1000,
            },
            {
                "id": "m2",
                "session_id": "sess_recent",
                "role": "assistant",
                "content": "hello",
                "ts": now_ms - 500,
            },
            {
                "id": "m3",
                "session_id": "sess_recent",
                "role": "user",
                "content": "test",
                "ts": now_ms,
            },
        ]
        _create_kilo_db_with_messages(kilo_path, messages)

        reader = KiloReader(kilo_path)
        await reader.connect()

        # Set a very recent watermark (within gap threshold)
        await wiki_store.set_watermark("sess_recent", "m3", now_ms)

        result = await run_watchdog_cycle(wiki_store, reader)

        # Gap should be tiny (< 5 min), no catch-up triggered
        assert result.gaps_found == 0

        await reader.close()

    async def test_gap_with_old_watermark(self, wiki_store: WikiStore, tmp_path: Any) -> None:
        """Watchdog detects gap when watermark is old."""
        now_ms = int(time.time() * 1000)
        old_ts = now_ms - 3600000  # 1 hour ago

        # Create kilo.db with messages spread over time
        kilo_path = tmp_path / "kilo.db"
        messages = [
            # Old messages (already curated via watermark)
            {"id": "m1", "session_id": "sess_old", "role": "user", "content": "a", "ts": old_ts},
            {
                "id": "m2",
                "session_id": "sess_old",
                "role": "assistant",
                "content": "b",
                "ts": old_ts + 1000,
            },
            {
                "id": "m3",
                "session_id": "sess_old",
                "role": "user",
                "content": "c",
                "ts": old_ts + 2000,
            },
            # New unprocessed messages (> 5 min after watermark, >= 3 msgs)
            {
                "id": "m4",
                "session_id": "sess_old",
                "role": "user",
                "content": "d",
                "ts": now_ms - 600000,
            },
            {
                "id": "m5",
                "session_id": "sess_old",
                "role": "assistant",
                "content": "e",
                "ts": now_ms - 500000,
            },
            {
                "id": "m6",
                "session_id": "sess_old",
                "role": "user",
                "content": "f",
                "ts": now_ms - 400000,
            },
        ]
        _create_kilo_db_with_messages(kilo_path, messages)

        reader = KiloReader(kilo_path)
        await reader.connect()

        # Set old watermark at m3 (1 hour ago)
        await wiki_store.set_watermark("sess_old", "m3", old_ts + 2000)

        result = await run_watchdog_cycle(wiki_store, reader)

        # Should detect gap (old watermark, 3+ new messages > 5 min gap)
        assert result.gaps_found >= 1

        await reader.close()

    async def test_too_few_messages_no_catchup(self, wiki_store: WikiStore, tmp_path: Any) -> None:
        """Watchdog does not trigger for sessions with too few messages."""
        now_ms = int(time.time() * 1000)

        kilo_path = tmp_path / "kilo.db"
        # Only 2 messages (below MIN_MESSAGES_FOR_CATCHUP=3)
        messages = [
            {
                "id": "m1",
                "session_id": "sess_small",
                "role": "user",
                "content": "a",
                "ts": now_ms - 600000,
            },
            {
                "id": "m2",
                "session_id": "sess_small",
                "role": "assistant",
                "content": "b",
                "ts": now_ms - 590000,
            },
        ]
        _create_kilo_db_with_messages(kilo_path, messages)

        reader = KiloReader(kilo_path)
        await reader.connect()

        result = await run_watchdog_cycle(wiki_store, reader)

        # sess_small has only 2 messages → filtered out by min_messages=3
        assert result.gaps_found == 0

        await reader.close()


class TestWatchdogResultFormat:
    """WatchdogResult data format tests."""

    def test_result_defaults(self) -> None:
        result = WatchdogResult(status="ok")
        assert result.sessions_checked == 0
        assert result.gaps_found == 0
        assert result.catchups_triggered == 0
        assert result.details == []

    def test_result_with_values(self) -> None:
        result = WatchdogResult(
            status="catchup_triggered",
            sessions_checked=5,
            gaps_found=2,
            catchups_triggered=1,
            details=[{"session_id": "s1"}],
        )
        assert result.status == "catchup_triggered"
        assert result.sessions_checked == 5
        assert result.gaps_found == 2


class TestWatchdogConstants:
    """Verify watchdog configuration constants."""

    def test_gap_threshold(self) -> None:
        assert GAP_THRESHOLD_SECONDS == 300  # 5 minutes

    def test_min_messages(self) -> None:
        assert MIN_MESSAGES_FOR_CATCHUP == 3
