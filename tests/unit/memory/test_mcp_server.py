from __future__ import annotations

import uuid

import pytest

from aria.memory import mcp_server


class _FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.inserted = []
        self._db_path = "/tmp/fake"
        self._conn = object()

    async def enqueue_hitl(self, target_id, action, reason=None, trace_id=None, channel="cli"):
        self.calls.append((str(target_id), action))
        return "hitl-123"

    async def insert(self, entry):
        self.inserted.append(entry)

    async def search_text(self, _query, top_k=10):
        return self.inserted[:top_k]

    async def list_by_session(self, _session_id, limit=50):
        return self.inserted[:limit]

    async def list_by_time_range(self, _since, _until, limit=50):
        return self.inserted[:limit]

    async def list_hitl_pending(self, limit=100):
        return []

    async def stats(self):
        class _Stats:
            t0_count = 1
            t1_count = 0
            sessions = 1
            last_session_ts = None
            avg_entry_size = 10.0
            storage_bytes = 100

        return _Stats()


# DEPRECATED: remember, complete_turn, recall, recall_episodic, distill, curate
# removed in Phase D (2026-04-27). Tests kept as stub references.
# Phase E will remove these tests after 30 days stable.


@pytest.mark.skip(reason="removed in Phase D — see ADR-0005")
@pytest.mark.asyncio
async def test_remember_recall_stats_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEPRECATED: remember/recall tools removed."""
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    session_id = str(uuid.uuid4())
    remember_result = await mcp_server.remember(
        content="user wants coffee",
        actor="user_input",
        role="user",
        session_id=session_id,
        tags=["pref"],
    )
    assert remember_result["status"] == "ok"

    recall_result = await mcp_server.recall("coffee")
    assert isinstance(recall_result, list)

    episodic_result = await mcp_server.recall_episodic(session_id=session_id)
    assert isinstance(episodic_result, list)

    distill_result = await mcp_server.distill(session_id=session_id)
    assert isinstance(distill_result, list)

    stats_result = await mcp_server.stats()
    assert stats_result["t0_count"] == 1

    curated_promote = await mcp_server.curate(str(uuid.uuid4()), "promote")
    assert curated_promote["status"] == "ok"

    curated_demote = await mcp_server.curate(str(uuid.uuid4()), "demote")
    assert curated_demote["status"] == "ok"


@pytest.mark.skip(reason="removed in Phase D — see ADR-0005")
@pytest.mark.asyncio
async def test_tool_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEPRECATED: remember/recall/distill/curate tools removed."""
    async def broken_store():
        raise RuntimeError("boom")

    monkeypatch.setattr(mcp_server, "_ensure_store", broken_store)
    assert (await mcp_server.remember("x", "user_input", "user", str(uuid.uuid4())))[
        "status"
    ] == "error"
    assert "error" in (await mcp_server.recall("x"))[0]
    assert "error" in (await mcp_server.recall_episodic())[0]
    assert "error" in (await mcp_server.distill(str(uuid.uuid4())))[0]
    assert (await mcp_server.curate(str(uuid.uuid4()), "forget"))["status"] == "error"
    assert (await mcp_server.forget(str(uuid.uuid4())))["status"] == "error"
    assert "error" in (await mcp_server.stats())


@pytest.mark.skip(reason="removed in Phase D — see ADR-0005")
@pytest.mark.asyncio
async def test_ensure_store_initializes_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEPRECATED: _ensure_store signature changed."""
    fake_store = _FakeStore()

    class FakeSemanticCls:
        def __init__(self, _db_path, _config) -> None:
            pass

        async def connect(self, _conn):
            return None

    class FakeClmCls:
        def __init__(self, _store, _semantic):
            pass

    async def fake_create_store(_config):
        return fake_store

    monkeypatch.setattr(mcp_server, "_store", None)
    monkeypatch.setattr(mcp_server, "_config", None)
    monkeypatch.setattr(mcp_server, "get_config", lambda: object())
    monkeypatch.setattr(mcp_server, "create_episodic_store", fake_create_store)

    store = await mcp_server._ensure_store()
    assert store is fake_store


@pytest.mark.skip(reason="removed in Phase D — see ADR-0005")
@pytest.mark.asyncio
async def test_forget_and_curate_forget_enqueue_hitl(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEPRECATED: curate(forget) removed; forget still works."""
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    entry_id = str(uuid.uuid4())
    result_forget = await mcp_server.forget(entry_id)
    assert result_forget["status"] == "pending_hitl"

    # curate(forget) removed — skip test for that part
    assert len(fake_store.calls) == 1


@pytest.mark.skip(reason="removed in Phase D — see ADR-0005")
def test_main_transport_paths(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """DEPRECATED: transport check still valid but tool names changed."""
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    monkeypatch.setenv("ARIA_MEMORY_MCP_TRANSPORT", "http")
    assert mcp_server.main() == 1

    monkeypatch.setenv("ARIA_MEMORY_MCP_TRANSPORT", "stdio")
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: None)
    assert mcp_server.main() == 0


@pytest.mark.asyncio
async def test_forget_enqueues_hitl(monkeypatch: pytest.MonkeyPatch) -> None:
    """forget tool still works — queues HITL request."""
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    entry_id = str(uuid.uuid4())
    result = await mcp_server.forget(entry_id)
    assert result["status"] == "pending_hitl"
    assert len(fake_store.calls) == 1


@pytest.mark.asyncio
async def test_stats_returns_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """stats tool still works — returns episodic store stats."""
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    result = await mcp_server.stats()
    assert result["t0_count"] == 1
    assert result["sessions"] == 1


@pytest.mark.asyncio
async def test_hitl_ask_enqueues_hitl(monkeypatch: pytest.MonkeyPatch) -> None:
    """hitl_ask still works."""
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    result = await mcp_server.hitl_ask("forget_episodic", str(uuid.uuid4()), "test")
    assert result["status"] == "pending_hitl"


@pytest.mark.asyncio
async def test_hitl_list_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """hitl_list_pending still works."""
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    result = await mcp_server.hitl_list_pending()
    assert result == []


@pytest.mark.asyncio
async def test_hitl_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    """hitl_cancel still works — validates signature."""
    async def fake_ensure_store():
        raise RuntimeError("boom")

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    result = await mcp_server.hitl_cancel("123")
    assert "error" in result  # because broken store raises


@pytest.mark.asyncio
async def test_hitl_approve_forget_episodic_tombstones_entry(tmp_path, monkeypatch) -> None:
    """hitl_approve resolves forget_episodic by tombstoning the entry."""
    import aria.memory.mcp_server as srv
    from aria.memory.episodic import create_episodic_store
    from aria.memory.schema import Actor, EpisodicEntry, content_hash

    from datetime import UTC, datetime
    from uuid import uuid4
    from unittest.mock import MagicMock

    config = MagicMock()
    config.paths.runtime = tmp_path
    config.memory.t0_retention_days = 365
    config.memory.t2_enabled = False
    monkeypatch.setattr("aria.memory.mcp_server._store", None)
    monkeypatch.setattr("aria.memory.mcp_server._config", None)
    monkeypatch.setattr("aria.memory.mcp_server.get_config", lambda: config)

    store = await srv._ensure_store()

    entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="entry to forget",
        content_hash=content_hash("entry to forget"),
    )
    await store.insert(entry)

    # Enqueue HITL forget
    hitl_id = await store.enqueue_hitl(
        target_id=entry.id,
        action="forget_episodic",
        reason="test",
        trace_id="test-trace",
        channel="test",
    )

    # Approve
    result = await srv.hitl_approve(hitl_id)

    assert result["status"] == "ok"
    assert result["action"] == "forget_episodic"
    # Entry should now be tombstoned
    visible = await store.get(entry.id)
    assert visible is None
    await store.close()
