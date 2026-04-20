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

    async def stats(self):
        class _Stats:
            t0_count = 1
            t1_count = 0
            sessions = 1
            last_session_ts = None
            avg_entry_size = 10.0
            storage_bytes = 100

        return _Stats()


class _FakeSemantic:
    async def search(self, _query, top_k=10, kinds=None):
        return []


class _FakeCLM:
    async def promote(self, _id):
        return None

    async def demote(self, _id):
        return None

    async def distill_session(self, _session_id):
        return []


@pytest.mark.asyncio
async def test_forget_and_curate_forget_enqueue_hitl(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store, _FakeSemantic(), _FakeCLM()

    monkeypatch.setattr(mcp_server, "_ensure_store", fake_ensure_store)

    entry_id = str(uuid.uuid4())
    result_forget = await mcp_server.forget(entry_id)
    assert result_forget["status"] == "pending_hitl"

    chunk_id = str(uuid.uuid4())
    result_curate = await mcp_server.curate(chunk_id, "forget")
    assert result_curate["status"] == "pending_hitl"

    assert len(fake_store.calls) == 2


@pytest.mark.asyncio
async def test_remember_recall_stats_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_store = _FakeStore()

    async def fake_ensure_store():
        return fake_store, _FakeSemantic(), _FakeCLM()

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


@pytest.mark.asyncio
async def test_ensure_store_initializes_globals(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(mcp_server, "_semantic", None)
    monkeypatch.setattr(mcp_server, "_clm", None)
    monkeypatch.setattr(mcp_server, "get_config", lambda: object())
    monkeypatch.setattr(mcp_server, "create_episodic_store", fake_create_store)
    monkeypatch.setattr(mcp_server, "SemanticStore", FakeSemanticCls)
    monkeypatch.setattr(mcp_server, "CLM", FakeClmCls)

    store, _semantic, _clm = await mcp_server._ensure_store()
    assert store is fake_store


@pytest.mark.asyncio
async def test_tool_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_main_transport_paths(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    monkeypatch.setenv("ARIA_MEMORY_MCP_TRANSPORT", "http")
    assert mcp_server.main() == 1

    monkeypatch.setenv("ARIA_MEMORY_MCP_TRANSPORT", "stdio")
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: None)
    assert mcp_server.main() == 0
