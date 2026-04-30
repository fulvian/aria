# Tests for wiki.kilo_reader — Kilo DB Reader

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest

from aria.memory.wiki.kilo_reader import KiloReader, KiloSessionInfo


def _create_kilo_db(db_path: Path, messages: list[dict] | None = None) -> None:
    """Create a minimal kilo.db with message table for testing."""
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

    if messages:
        for msg in messages:
            conn.execute(
                "INSERT INTO message (id, session_id, role, content, time_created) "
                "VALUES (?, ?, ?, ?, ?)",
                (msg["id"], msg["session_id"], msg["role"], msg.get("content", ""), msg["ts"]),
            )

    conn.commit()
    conn.close()


@pytest.fixture
async def kilo_db(tmp_path: Any) -> Path:
    """Create a temporary kilo.db with basic schema."""
    db_path = tmp_path / "kilo.db"
    _create_kilo_db(db_path)
    return db_path


@pytest.fixture
async def kilo_db_with_messages(tmp_path: Any) -> Path:
    """Create a kilo.db with sample conductor messages."""
    db_path = tmp_path / "kilo.db"
    now_ms = int(time.time() * 1000)
    _create_kilo_db(
        db_path,
        [
            {
                "id": "m1",
                "session_id": "sess1",
                "role": "user",
                "content": "hello",
                "ts": now_ms - 600000,
            },
            {
                "id": "m2",
                "session_id": "sess1",
                "role": "assistant",
                "content": "hi there",
                "ts": now_ms - 500000,
            },
            {
                "id": "m3",
                "session_id": "sess1",
                "role": "user",
                "content": "how are you",
                "ts": now_ms - 400000,
            },
            {
                "id": "m4",
                "session_id": "sess2",
                "role": "user",
                "content": "test",
                "ts": now_ms - 200000,
            },
            {
                "id": "m5",
                "session_id": "sess3",
                "role": "user",
                "content": "a",
                "ts": now_ms - 100000,
            },
            {
                "id": "m6",
                "session_id": "sess3",
                "role": "assistant",
                "content": "b",
                "ts": now_ms - 90000,
            },
            {
                "id": "m7",
                "session_id": "sess3",
                "role": "user",
                "content": "c",
                "ts": now_ms - 80000,
            },
        ],
    )
    return db_path


class TestKiloReaderConnect:
    """KiloReader connection tests."""

    async def test_connect_existing_db(self, kilo_db: Path) -> None:
        reader = KiloReader(kilo_db)
        await reader.connect()
        assert reader._conn is not None
        assert reader.schema_ok is True  # First run, no known fingerprint
        await reader.close()

    async def test_connect_missing_db(self, tmp_path: Any) -> None:
        reader = KiloReader(tmp_path / "nonexistent.db")
        await reader.connect()
        assert reader.schema_ok is False
        assert reader._conn is None

    async def test_close_idempotent(self, kilo_db: Path) -> None:
        reader = KiloReader(kilo_db)
        await reader.connect()
        await reader.close()
        await reader.close()  # Should not raise


class TestKiloReaderSchema:
    """Schema fingerprint tests."""

    async def test_fingerprint_computed(self, kilo_db: Path) -> None:
        reader = KiloReader(kilo_db)
        await reader.connect()
        assert reader.fingerprint is not None
        assert len(reader.fingerprint) == 64  # SHA256 hex
        await reader.close()

    async def test_fingerprint_changes_on_schema_change(self, tmp_path: Any) -> None:
        """Two DBs with different schemas should have different fingerprints."""
        db1 = tmp_path / "kilo1.db"
        db2 = tmp_path / "kilo2.db"

        conn1 = sqlite3.connect(str(db1))
        conn1.execute(
            "CREATE TABLE message (id TEXT, session_id TEXT, role TEXT, content TEXT, time_created INTEGER)"
        )
        conn1.execute("CREATE TABLE part (id TEXT, message_id TEXT, type TEXT, content TEXT)")
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(str(db2))
        conn2.execute(
            "CREATE TABLE message (id TEXT, session_id TEXT, role TEXT, content TEXT, time_created INTEGER, extra_col TEXT)"
        )
        conn2.execute("CREATE TABLE part (id TEXT, message_id TEXT, type TEXT, content TEXT)")
        conn2.commit()
        conn2.close()

        r1 = KiloReader(db1)
        await r1.connect()
        r2 = KiloReader(db2)
        await r2.connect()

        assert r1.fingerprint != r2.fingerprint

        await r1.close()
        await r2.close()


class TestKiloReaderSessions:
    """Session listing tests."""

    async def test_list_sessions_with_min_messages(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        sessions = await reader.list_conductor_sessions(min_messages=3)
        # sess1 has 3 messages, sess3 has 3 messages, sess2 has 1
        session_ids = {s.session_id for s in sessions}
        assert "sess1" in session_ids
        assert "sess3" in session_ids
        assert "sess2" not in session_ids

        await reader.close()

    async def test_list_sessions_empty_db(self, kilo_db: Path) -> None:
        reader = KiloReader(kilo_db)
        await reader.connect()

        sessions = await reader.list_conductor_sessions()
        assert sessions == []

        await reader.close()

    async def test_list_sessions_with_since_filter(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        now_ms = int(time.time() * 1000)
        # Only sessions with messages from the last 30 seconds (should find none)
        sessions = await reader.list_conductor_sessions(since_ts=now_ms - 30000)
        assert len(sessions) == 0

        await reader.close()


class TestKiloReaderMessages:
    """Message range query tests."""

    async def test_get_messages_range(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        messages = await reader.get_messages_range("sess1")
        assert len(messages) == 3
        assert messages[0].session_id == "sess1"
        assert messages[0].role == "user"
        assert messages[0].content == "hello"

        await reader.close()

    async def test_get_messages_range_with_after_ts(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        now_ms = int(time.time() * 1000)
        # Only messages after now (should find none)
        messages = await reader.get_messages_range("sess1", after_ts=now_ms)
        assert len(messages) == 0

        await reader.close()

    async def test_get_messages_range_limit(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        messages = await reader.get_messages_range("sess1", limit=2)
        assert len(messages) == 2

        await reader.close()

    async def test_get_messages_nonexistent_session(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        messages = await reader.get_messages_range("nonexistent")
        assert messages == []

        await reader.close()


class TestKiloReaderHealthCheck:
    """Health check tests."""

    async def test_health_check_connected(self, kilo_db: Path) -> None:
        reader = KiloReader(kilo_db)
        await reader.connect()

        health = await reader.health_check()
        assert health["kilo_db_exists"] is True
        assert health["schema_ok"] is True
        assert health["connected"] is True
        assert health["fingerprint"] is not None

        await reader.close()

    async def test_health_check_missing_db(self, tmp_path: Any) -> None:
        reader = KiloReader(tmp_path / "missing.db")
        await reader.connect()

        health = await reader.health_check()
        assert health["kilo_db_exists"] is False
        assert health["schema_ok"] is False

    async def test_get_session_last_ts(self, kilo_db_with_messages: Path) -> None:
        reader = KiloReader(kilo_db_with_messages)
        await reader.connect()

        ts = await reader.get_session_last_ts("sess1")
        assert ts is not None
        assert ts > 0

        await reader.close()

    async def test_get_session_last_ts_nonexistent(self, kilo_db: Path) -> None:
        reader = KiloReader(kilo_db)
        await reader.connect()

        ts = await reader.get_session_last_ts("nonexistent")
        assert ts is None

        await reader.close()
