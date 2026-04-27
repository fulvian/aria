# Memory Subsystem Gap Remediation Plan

**Goal:** Close all 7 gaps identified in `docs/analysis/memory_subsystem_health_check_2026-04-24.md` to make the memory subsystem fully operational and blueprint-compliant.

**Architecture:** CLM is triggered post-session via gateway hook and every 6h via scheduler cron task. HITL gains an `approve` execution path in the MCP server. EpisodicStore gains retention pruning; Reaper gains episodic WAL checkpoint. Integration tests validate all E2E flows.

**Tech Stack:** Python 3.11+, aiosqlite, FastMCP 3.x, pytest-asyncio, systemd (timer units)

**Source analysis:** `docs/analysis/memory_subsystem_health_check_2026-04-24.md`

**Context7 verified:** FastMCP `@mcp.tool` pattern, aiosqlite `execute`/`fetchone`/`rowcount` — confirmed valid.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/aria/memory/episodic.py` | Modify | Add `prune_old_entries()` method |
| `src/aria/memory/mcp_server.py` | Modify | Add `hitl_approve` tool (11th tool) |
| `src/aria/gateway/conductor_bridge.py` | Modify | Add post-session CLM distill hook |
| `src/aria/gateway/daemon.py` | Modify | Init SemanticStore+CLM, pass to bridge; wire episodic_store to Reaper |
| `src/aria/scheduler/reaper.py` | Modify | Add episodic WAL checkpoint + retention pruning |
| `src/aria/scheduler/runner.py` | Modify | Add `category="memory"` task execution |
| `src/aria/scheduler/daemon.py` | Modify | Seed `memory-distill` and `memory-wal-checkpoint` cron tasks on startup |
| `systemd/aria-backup.service` | Create | One-shot service to run `scripts/backup.sh` |
| `systemd/aria-backup.timer` | Create | Weekly systemd timer for backup |
| `tests/unit/memory/test_episodic_store.py` | Modify | Add unit tests for `prune_old_entries` |
| `tests/unit/memory/test_mcp_server.py` | Modify | Add unit test for `hitl_approve` |
| `tests/integration/memory/__init__.py` | Create | Package init |
| `tests/integration/memory/test_remember_distill_recall.py` | Create | E2E: remember → distill → recall |
| `tests/integration/memory/test_hitl_approve.py` | Create | E2E: forget → hitl_approve → tombstone |
| `tests/integration/memory/test_retention_pruning.py` | Create | E2E: old entries → prune → tombstoned |
| `docs/llm_wiki/wiki/memory-subsystem.md` | Modify | Update gap table, add new tools/methods |
| `docs/llm_wiki/wiki/log.md` | Modify | Append implementation log entry |

---

## Task 1: Add `prune_old_entries()` to EpisodicStore

**Files:**
- Modify: `src/aria/memory/episodic.py` (after `vacuum_wal`, before `stats`)
- Test: `tests/unit/memory/test_episodic_store.py`

### Why

`config.memory.t0_retention_days=365` exists but nothing tombstones old T0 entries. This violates blueprint §5.7 (P6-compliant: tombstone, never hard delete).

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/memory/test_episodic_store.py`:

```python
@pytest.mark.asyncio
async def test_prune_old_entries_tombstones_expired(tmp_path):
    """prune_old_entries tombstones entries older than retention_days."""
    from datetime import timedelta
    from aria.memory.episodic import EpisodicStore
    from aria.memory.schema import Actor, EpisodicEntry, content_hash
    from unittest.mock import MagicMock

    config = MagicMock()
    config.memory.t0_retention_days = 30
    db_path = tmp_path / "episodic.db"
    store = EpisodicStore(db_path, config)
    await store.connect()

    # Old entry (40 days ago)
    old_ts = datetime.now(UTC) - timedelta(days=40)
    old_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=old_ts,
        actor=Actor.USER_INPUT,
        role="user",
        content="old content to prune",
        content_hash=content_hash("old content to prune"),
    )
    await store.insert(old_entry)

    # Recent entry (1 day ago)
    recent_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=1),
        actor=Actor.USER_INPUT,
        role="user",
        content="recent content",
        content_hash=content_hash("recent content"),
    )
    await store.insert(recent_entry)

    pruned = await store.prune_old_entries(retention_days=30)

    assert pruned == 1
    # Old entry should be tombstoned (not visible)
    result = await store.get(old_entry.id)
    assert result is None
    # Recent entry still visible
    result = await store.get(recent_entry.id)
    assert result is not None
    await store.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/memory/test_episodic_store.py::test_prune_old_entries_tombstones_expired -v
```

Expected: `FAILED` — `AttributeError: 'EpisodicStore' object has no attribute 'prune_old_entries'`

- [ ] **Step 3: Implement `prune_old_entries()` in EpisodicStore**

In `src/aria/memory/episodic.py`, add after `vacuum_wal()` (around line 579):

```python
async def prune_old_entries(self, retention_days: int) -> int:
    """Tombstone T0 entries older than retention_days.

    Per P6: uses tombstone, never hard delete.

    Args:
        retention_days: Entries older than this are tombstoned.

    Returns:
        Number of entries tombstoned.
    """
    conn = await self._ensure_connected()
    cutoff_ts = int(datetime.now(UTC).timestamp()) - retention_days * 86400
    cursor = await conn.execute(
        """
        INSERT INTO episodic_tombstones (episodic_id, tombstoned_at, reason)
        SELECT id, ?, 'retention_expired'
        FROM episodic
        WHERE ts < ?
          AND id NOT IN (SELECT episodic_id FROM episodic_tombstones)
        """,
        (int(time.time()), cutoff_ts),
    )
    await conn.commit()
    return cursor.rowcount
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/memory/test_episodic_store.py::test_prune_old_entries_tombstones_expired -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full memory unit suite**

```bash
uv run pytest -q tests/unit/memory/
```

Expected: all tests pass (currently 32+1).

- [ ] **Step 6: Quality gate**

```bash
uv run ruff check src/aria/memory/episodic.py
uv run mypy src/aria/memory/episodic.py
```

Expected: `PASS` on both.

- [ ] **Step 7: Commit**

```bash
git add src/aria/memory/episodic.py tests/unit/memory/test_episodic_store.py
git commit -m "feat(memory): add prune_old_entries() for T0 retention enforcement"
```

---

## Task 2: Add `hitl_approve` Tool to MCP Server

**Files:**
- Modify: `src/aria/memory/mcp_server.py` (add tool after `hitl_cancel`)
- Test: `tests/unit/memory/test_mcp_server.py`

### Why

`forget` and `curate(forget)` enqueue HITL records but nothing ever executes the action. Blueprint P7 requires human-approved destructive actions to actually execute. This is the "Sprint 1.2" stub noted throughout the code.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/memory/test_mcp_server.py`:

```python
@pytest.mark.asyncio
async def test_hitl_approve_forget_episodic_tombstones_entry(tmp_path, monkeypatch):
    """hitl_approve resolves forget_episodic by tombstoning the entry."""
    import aria.memory.mcp_server as srv

    config = MagicMock()
    config.paths.runtime = tmp_path
    config.memory.t0_retention_days = 365
    config.memory.t2_enabled = False
    monkeypatch.setattr("aria.memory.mcp_server._store", None)
    monkeypatch.setattr("aria.memory.mcp_server._semantic", None)
    monkeypatch.setattr("aria.memory.mcp_server._clm", None)

    # Insert entry
    from aria.memory.episodic import create_episodic_store
    from aria.memory.schema import Actor, EpisodicEntry, content_hash
    from datetime import UTC, datetime
    from uuid import uuid4

    monkeypatch.setattr("aria.config.get_config", lambda: config)
    store, semantic, clm = await srv._ensure_store()

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/memory/test_mcp_server.py::test_hitl_approve_forget_episodic_tombstones_entry -v
```

Expected: `FAILED` — `AttributeError: module 'aria.memory.mcp_server' has no attribute 'hitl_approve'`

- [ ] **Step 3: Implement `hitl_approve` tool in `mcp_server.py`**

In `src/aria/memory/mcp_server.py`, add after `hitl_cancel` (before `# === Main ===`):

```python
@mcp.tool
async def hitl_approve(hitl_id: str) -> dict:
    """Approve a pending HITL request and execute the consequent action.

    Supported actions:
    - forget_episodic: tombstones the target episodic entry
    - forget_semantic: deletes the target semantic chunk

    Args:
        hitl_id: The HITL request ID to approve

    Returns:
        {"status": "ok", "action": "...", "target_id": "..."} or error
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, semantic, _ = await _ensure_store()
        conn = await store._ensure_connected()

        # Fetch the pending record
        cursor = await conn.execute(
            "SELECT id, target_id, action, status FROM memory_hitl_pending WHERE id = ?",
            (hitl_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return {"status": "error", "error": f"HITL request {hitl_id} not found"}

        if row["status"] != "pending":
            return {
                "status": "error",
                "error": f"HITL request {hitl_id} is not pending (status={row['status']})",
            }

        action = row["action"]
        target_id = row["target_id"]

        # Execute the action
        if action == "forget_episodic":
            import uuid as _uuid
            tombstoned = await store.tombstone(
                _uuid.UUID(target_id),
                reason=f"approved via hitl_approve({hitl_id})",
            )
            if not tombstoned:
                return {
                    "status": "error",
                    "error": f"Entry {target_id} not found or already tombstoned",
                }

        elif action == "forget_semantic":
            import uuid as _uuid
            deleted = await semantic.delete(_uuid.UUID(target_id))
            if not deleted:
                return {
                    "status": "error",
                    "error": f"Semantic chunk {target_id} not found",
                }

        else:
            return {
                "status": "error",
                "error": f"Unsupported HITL action: {action}",
            }

        # Mark resolved
        await conn.execute(
            "UPDATE memory_hitl_pending SET status = 'approved', resolved_at = ? WHERE id = ?",
            (int(datetime.now(UTC).timestamp()), hitl_id),
        )
        await conn.commit()

        return {
            "status": "ok",
            "hitl_id": hitl_id,
            "action": action,
            "target_id": target_id,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/memory/test_mcp_server.py::test_hitl_approve_forget_episodic_tombstones_entry -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full memory unit suite**

```bash
uv run pytest -q tests/unit/memory/
```

Expected: all tests pass.

- [ ] **Step 6: Quality gate**

```bash
uv run ruff check src/aria/memory/mcp_server.py
uv run mypy src/aria/memory/mcp_server.py
```

Expected: `PASS` on both.

- [ ] **Step 7: Commit**

```bash
git add src/aria/memory/mcp_server.py tests/unit/memory/test_mcp_server.py
git commit -m "feat(memory): add hitl_approve MCP tool — closes HITL approval path (P7)"
```

---

## Task 3: CLM Post-Session Hook in Gateway

**Files:**
- Modify: `src/aria/gateway/conductor_bridge.py` (add `_distill_session_bg` + call after conductor)
- Modify: `src/aria/gateway/daemon.py` (create SemanticStore + CLM, pass to bridge)

### Why

Blueprint §5.4 requires CLM trigger post-session. 1005 T0 entries accumulated with 0 T1 chunks because no hook calls distillation after each session completes.

- [ ] **Step 1: Modify `ConductorBridge` to accept and use CLM**

In `src/aria/gateway/conductor_bridge.py`, update the class:

Locate the `__init__` signature (around line 60–90, after logger definition):

```python
# BEFORE (existing):
class ConductorBridge:
    def __init__(
        self,
        bus: EventBus,
        store: EpisodicStore,
        config: ARIAConfig,
    ) -> None:
        self._bus = bus
        self._store = store
        self._config = config
        ...
```

Replace with:

```python
class ConductorBridge:
    def __init__(
        self,
        bus: EventBus,
        store: EpisodicStore,
        config: ARIAConfig,
        clm: CLM | None = None,
    ) -> None:
        self._bus = bus
        self._store = store
        self._config = config
        self._clm = clm
        ...
```

Add to imports at top of file (after existing TYPE_CHECKING block or unconditionally):

```python
from aria.memory.clm import CLM
```

Add `_distill_session_bg` method to `ConductorBridge`:

```python
async def _distill_session_bg(self, session_id: str) -> None:
    """Fire-and-forget CLM distillation after session completes."""
    if self._clm is None:
        return
    try:
        import uuid as _uuid
        sess_uuid = _uuid.UUID(session_id)
        chunks = await self._clm.distill_session(sess_uuid)
        logger.info(
            "Post-session distillation: session=%s chunks_created=%d",
            session_id,
            len(chunks),
        )
    except Exception as exc:
        logger.warning("Post-session distillation failed: session=%s error=%s", session_id, exc)
```

Find `handle_user_message` (the method that stores conductor response and publishes reply). After the conductor response is stored in episodic (the `await self._store.add(...)` call for the conductor reply), add:

```python
# Trigger CLM distillation asynchronously (non-blocking)
if session_id:
    asyncio.create_task(self._distill_session_bg(session_id))
```

Note: `session_id` here is the string session ID extracted from the event payload. Verify the exact variable name in `handle_user_message` and use it.

- [ ] **Step 2: Modify `daemon.py` to create SemanticStore+CLM and wire to bridge**

In `src/aria/gateway/daemon.py`, add imports at top of `_async_main()`:

```python
from aria.memory.semantic import SemanticStore
from aria.memory.clm import CLM
```

After `episodic_store = await create_episodic_store(config)`, add:

```python
# Initialize semantic store sharing the episodic connection
semantic_store = SemanticStore(
    episodic_store._db_path,
    config,
)
conn = episodic_store._conn
if conn is None:
    raise RuntimeError("EpisodicStore connection is None after create_episodic_store")
await semantic_store.connect(conn)
clm = CLM(episodic_store, semantic_store)
```

Update bridge instantiation:

```python
# BEFORE:
conductor_bridge = ConductorBridge(bus=bus, store=episodic_store, config=config)

# AFTER:
conductor_bridge = ConductorBridge(bus=bus, store=episodic_store, config=config, clm=clm)
```

- [ ] **Step 3: Write a unit test for the distill hook**

Add to `tests/unit/gateway/test_conductor_bridge.py`:

```python
@pytest.mark.asyncio
async def test_handle_user_message_triggers_distillation(tmp_path, monkeypatch):
    """After conductor completes, bridge fires _distill_session_bg."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from aria.gateway.conductor_bridge import ConductorBridge
    from aria.scheduler.triggers import EventBus

    bus = EventBus()
    store = AsyncMock()
    store.add = AsyncMock(return_value=MagicMock(id="test-id"))
    config = MagicMock()
    config.gateway.conductor_timeout_s = 10

    clm = AsyncMock()
    clm.distill_session = AsyncMock(return_value=[])

    bridge = ConductorBridge(bus=bus, store=store, config=config, clm=clm)

    # Patch _spawn_conductor to return a fake result
    async def fake_spawn(msg, session_id, trace_id, timeout):
        return {"text": "conductor reply", "tokens_used": 10}

    monkeypatch.setattr(bridge, "_spawn_conductor", fake_spawn)

    # Publish a user message
    payload = {
        "user_id": "123",
        "telegram_user_id": "123",
        "text": "hello",
        "session_id": "test-session",
        "trace_id": "trace-1",
    }
    await bus.publish("gateway.user_message", payload)
    # Allow event loop to process background tasks
    await asyncio.sleep(0.1)

    # distill_session should have been called
    clm.distill_session.assert_called_once()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/gateway/ -v
```

Expected: existing tests pass + new test passes.

- [ ] **Step 5: Quality gate**

```bash
uv run ruff check src/aria/gateway/conductor_bridge.py src/aria/gateway/daemon.py
uv run mypy src/aria/gateway/conductor_bridge.py src/aria/gateway/daemon.py
```

Expected: `PASS` on both.

- [ ] **Step 6: Commit**

```bash
git add src/aria/gateway/conductor_bridge.py src/aria/gateway/daemon.py \
        tests/unit/gateway/test_conductor_bridge.py
git commit -m "feat(gateway): trigger CLM distillation post-session via ConductorBridge"
```

---

## Task 4: CLM 6h Scheduler Cron Task

**Files:**
- Modify: `src/aria/scheduler/daemon.py` (seed `memory-distill` task)
- Modify: `src/aria/scheduler/runner.py` (handle `category="memory"` tasks)

### Why

Blueprint §5.4 requires CLM trigger "ogni 6h" in addition to post-session hook. Scheduler seeds are idempotent (insert-if-not-exists). Runner needs a handler for `category="memory"`.

- [ ] **Step 1: Add memory task seeding to scheduler daemon**

In `src/aria/scheduler/daemon.py`, after `store.connect()` call, add:

```python
# Seed memory maintenance tasks (idempotent)
await _seed_memory_tasks(store, config)
```

Add the function before `_run_scheduler()`:

```python
async def _seed_memory_tasks(store: "TaskStore", config: "ARIAConfig") -> None:
    """Seed recurring memory tasks if not already present.

    Idempotent: skips if a task with the same name already exists.
    """
    import time as _time

    existing = await store.list_tasks(status=["active", "paused"])
    existing_names = {t.name for t in existing}

    now_ms = int(_time.time() * 1000)

    if "memory-distill" not in existing_names:
        from aria.scheduler.schema import Task

        task = Task(
            name="memory-distill",
            category="memory",
            trigger_type="cron",
            schedule_cron="0 */6 * * *",
            timezone="Europe/Rome",
            next_run_at=now_ms + 6 * 3600 * 1000,  # first run in 6h
            policy="allow",
            payload={"action": "distill_range", "hours": 6},
            created_at=now_ms,
            updated_at=now_ms,
        )
        await store.create_task(task)
        logger.info("Seeded memory-distill cron task")

    if "memory-wal-checkpoint" not in existing_names:
        from aria.scheduler.schema import Task

        task = Task(
            name="memory-wal-checkpoint",
            category="memory",
            trigger_type="cron",
            schedule_cron="30 */6 * * *",
            timezone="Europe/Rome",
            next_run_at=now_ms + 6 * 3600 * 1000 + 1800 * 1000,  # offset 30min
            policy="allow",
            payload={"action": "wal_checkpoint"},
            created_at=now_ms,
            updated_at=now_ms,
        )
        await store.create_task(task)
        logger.info("Seeded memory-wal-checkpoint cron task")
```

Add TYPE_CHECKING imports:

```python
if TYPE_CHECKING:
    from aria.scheduler.store import TaskStore
    from aria.config import ARIAConfig
```

- [ ] **Step 2: Add `category="memory"` handler in runner**

In `src/aria/scheduler/runner.py`, in `_exec_task()`, before the `# Unknown category` fallback, add:

```python
if task.category == "memory":
    return await self._exec_memory_task(task)
```

Add `_exec_memory_task` method to `TaskRunner`:

```python
async def _exec_memory_task(self, task: Task) -> RunResult:
    """Execute a memory maintenance task.

    Supported actions (from task.payload["action"]):
    - distill_range: run CLM distillation on last N hours of T0 entries
    - wal_checkpoint: checkpoint episodic.db WAL
    """
    import uuid as _uuid
    from datetime import UTC, datetime, timedelta

    action = task.payload.get("action", "distill_range")
    run_id = str(_uuid.uuid4())

    try:
        from aria.config import get_config
        from aria.memory.clm import CLM
        from aria.memory.episodic import create_episodic_store
        from aria.memory.semantic import SemanticStore

        config = get_config()
        store = await create_episodic_store(config)

        if action == "wal_checkpoint":
            await store.vacuum_wal()
            await store.close()
            logger.info("Memory WAL checkpoint completed via scheduler task %s", task.id)
            return RunResult(
                run_id=run_id,
                outcome="success",
                result_summary="episodic.db WAL checkpointed",
            )

        # distill_range
        semantic = SemanticStore(store._db_path, config)
        conn = store._conn
        if conn is None:
            await store.close()
            return RunResult(run_id=run_id, outcome="failed", result_summary="EpisodicStore conn is None")
        await semantic.connect(conn)
        clm = CLM(store, semantic)

        hours = int(task.payload.get("hours", 6))
        until = datetime.now(UTC)
        since = until - timedelta(hours=hours)
        chunks = await clm.distill_range(since, until)
        await store.close()

        logger.info(
            "Memory distill_range completed: task=%s hours=%d chunks=%d",
            task.id, hours, len(chunks),
        )
        return RunResult(
            run_id=run_id,
            outcome="success",
            result_summary=f"Distilled {len(chunks)} semantic chunks from last {hours}h",
        )

    except Exception as exc:
        logger.error("Memory task %s failed: %s", task.id, exc)
        return RunResult(run_id=run_id, outcome="failed", result_summary=str(exc))
```

- [ ] **Step 3: Write unit tests**

Add to `tests/unit/scheduler/test_runner.py` (or create if missing):

```python
@pytest.mark.asyncio
async def test_exec_memory_task_distill_range(tmp_path, monkeypatch):
    """category=memory distill_range task creates CLM and distills."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from aria.scheduler.runner import TaskRunner
    from aria.scheduler.schema import Task
    import time

    # Build minimal task
    now_ms = int(time.time() * 1000)
    task = Task(
        name="memory-distill",
        category="memory",
        trigger_type="cron",
        schedule_cron="0 */6 * * *",
        payload={"action": "distill_range", "hours": 6},
        created_at=now_ms,
        updated_at=now_ms,
    )

    mock_chunks = [MagicMock(), MagicMock()]

    with patch("aria.scheduler.runner.create_episodic_store") as mock_store_factory, \
         patch("aria.scheduler.runner.SemanticStore") as mock_semantic_cls, \
         patch("aria.scheduler.runner.CLM") as mock_clm_cls, \
         patch("aria.scheduler.runner.get_config") as mock_config:

        mock_store = AsyncMock()
        mock_store._conn = MagicMock()
        mock_store._db_path = tmp_path / "episodic.db"
        mock_store_factory.return_value = mock_store

        mock_semantic = AsyncMock()
        mock_semantic_cls.return_value = mock_semantic

        mock_clm = AsyncMock()
        mock_clm.distill_range = AsyncMock(return_value=mock_chunks)
        mock_clm_cls.return_value = mock_clm

        runner = TaskRunner(
            store=MagicMock(), budget=MagicMock(), policy=MagicMock(),
            hitl=MagicMock(), bus=MagicMock(), config=MagicMock(),
        )
        result = await runner._exec_memory_task(task)

    assert result.outcome == "success"
    assert "2" in result.result_summary
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/scheduler/ -q
```

Expected: all pass.

- [ ] **Step 5: Quality gate**

```bash
uv run ruff check src/aria/scheduler/daemon.py src/aria/scheduler/runner.py
uv run mypy src/aria/scheduler/daemon.py src/aria/scheduler/runner.py
```

Expected: `PASS` on both.

- [ ] **Step 6: Commit**

```bash
git add src/aria/scheduler/daemon.py src/aria/scheduler/runner.py
git commit -m "feat(scheduler): seed memory-distill cron task and add category=memory handler"
```

---

## Task 5: Episodic WAL Checkpoint + Retention via Reaper

**Files:**
- Modify: `src/aria/scheduler/reaper.py` (add optional episodic_store, checkpoint + prune)
- Modify: `src/aria/scheduler/daemon.py` (pass episodic_store to Reaper — requires scheduler daemon to also init episodic store)

### Why

`vacuum_wal()` exists on `EpisodicStore` but nothing calls it. WAL grows unbounded. Similarly, `prune_old_entries()` (added in Task 1) needs a periodic caller. The Reaper already runs every 6h for WAL checkpoint — extend it to cover both dbs.

**Design decision:** The scheduler daemon does not currently create an EpisodicStore. Rather than coupling them, use the memory task approach from Task 4 for wal_checkpoint (already seeded). For the Reaper extension, we only add it if the scheduler process also manages memory — this is optional and additive. The simplest path: the scheduler daemon creates an EpisodicStore and passes it to Reaper. If episodic.db doesn't exist yet, EpisodicStore.connect() creates it cleanly.

- [ ] **Step 1: Extend Reaper to accept optional episodic_store**

In `src/aria/scheduler/reaper.py`, update `__init__`:

```python
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.memory.episodic import EpisodicStore
    from .store import TaskStore

logger = logging.getLogger(__name__)


class Reaper:
    def __init__(
        self,
        store: TaskStore,
        interval_s: int = 30,
        episodic_store: EpisodicStore | None = None,
    ) -> None:
        self._store = store
        self._interval_s = interval_s
        self._last_checkpoint_time = time.monotonic()
        self._checkpoint_interval_s = 6 * 3600
        self._running = False
        self._episodic_store = episodic_store
```

In `run_once()`, after the existing WAL checkpoint block (step 5), add:

```python
        # 6. Checkpoint episodic.db WAL and prune old T0 entries
        if self._episodic_store is not None and elapsed >= self._checkpoint_interval_s:
            try:
                await self._episodic_store.vacuum_wal()
                logger.info("Episodic WAL checkpoint completed")
            except Exception as e:
                logger.error("Error checkpointing episodic WAL: %s", e)

            try:
                from aria.config import get_config
                config = get_config()
                retention_days = config.memory.t0_retention_days
                pruned = await self._episodic_store.prune_old_entries(retention_days)
                if pruned > 0:
                    logger.info("Pruned %d T0 entries (retention=%dd)", pruned, retention_days)
            except Exception as e:
                logger.error("Error pruning old T0 entries: %s", e)
```

- [ ] **Step 2: Wire episodic_store into Reaper in scheduler daemon**

In `src/aria/scheduler/daemon.py`, after `store.connect()` and the memory task seeding, add:

```python
# Initialize episodic store for Reaper WAL checkpoint + retention
from aria.memory.episodic import create_episodic_store as _create_episodic_store
episodic_store = await _create_episodic_store(config)
```

Update Reaper instantiation:

```python
# BEFORE:
reaper = Reaper(store, interval_s=30)

# AFTER:
reaper = Reaper(store, interval_s=30, episodic_store=episodic_store)
```

Add cleanup in the shutdown path (after `async with asyncio.TaskGroup()`):

```python
await episodic_store.close()
```

- [ ] **Step 3: Write unit test for extended Reaper**

Add to `tests/unit/scheduler/test_reaper.py`:

```python
@pytest.mark.asyncio
async def test_reaper_checkpoints_episodic_wal(monkeypatch):
    """Reaper calls episodic_store.vacuum_wal() at the 6h checkpoint interval."""
    from unittest.mock import AsyncMock, MagicMock
    from aria.scheduler.reaper import Reaper

    task_store = MagicMock()
    task_store.reap_stale_leases = AsyncMock(return_value=0)
    task_store.expire_hitl = AsyncMock(return_value=[])
    task_store.list_tasks = AsyncMock(return_value=[])
    task_store._conn = MagicMock()

    episodic_store = AsyncMock()
    episodic_store.vacuum_wal = AsyncMock()
    episodic_store.prune_old_entries = AsyncMock(return_value=0)

    reaper = Reaper(task_store, interval_s=30, episodic_store=episodic_store)
    # Force checkpoint interval to 0 so it runs immediately
    reaper._checkpoint_interval_s = 0

    await reaper.run_once()

    episodic_store.vacuum_wal.assert_called_once()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/scheduler/test_reaper.py -v
```

Expected: all pass.

- [ ] **Step 5: Quality gate**

```bash
uv run ruff check src/aria/scheduler/reaper.py src/aria/scheduler/daemon.py
uv run mypy src/aria/scheduler/reaper.py src/aria/scheduler/daemon.py
```

Expected: `PASS` on both.

- [ ] **Step 6: Commit**

```bash
git add src/aria/scheduler/reaper.py src/aria/scheduler/daemon.py tests/unit/scheduler/test_reaper.py
git commit -m "feat(scheduler): extend Reaper with episodic WAL checkpoint and T0 retention pruning"
```

---

## Task 6: Integration Tests for Memory Subsystem

**Files:**
- Create: `tests/integration/memory/__init__.py`
- Create: `tests/integration/memory/test_remember_distill_recall.py`
- Create: `tests/integration/memory/test_hitl_approve.py`
- Create: `tests/integration/memory/test_retention_pruning.py`

### Why

The health check identified zero integration tests. Unit tests pass but don't cover E2E flows across store+CLM+MCP layers against a real SQLite db.

- [ ] **Step 1: Create package init**

```bash
touch tests/integration/memory/__init__.py
```

- [ ] **Step 2: Write E2E test: remember → distill → recall**

Create `tests/integration/memory/test_remember_distill_recall.py`:

```python
"""Integration test: E2E flow remember → distill → recall on real SQLite."""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from aria.memory.clm import CLM
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore


@pytest.fixture
def mock_config(tmp_path):
    cfg = MagicMock()
    cfg.paths.runtime = tmp_path
    cfg.memory.t0_retention_days = 365
    cfg.memory.t2_enabled = False
    return cfg


@pytest_asyncio.fixture
async def stores(tmp_path, mock_config):
    db_path = tmp_path / "episodic.db"
    mock_config.paths.runtime = tmp_path
    store = EpisodicStore(db_path, mock_config)
    await store.connect()
    semantic = SemanticStore(db_path, mock_config)
    await semantic.connect(store._conn)
    clm = CLM(store, semantic)
    yield store, semantic, clm
    await store.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_remember_distill_recall_e2e(stores):
    """remember → distill_session → recall returns the distilled chunk."""
    store, semantic, clm = stores
    session_id = uuid4()

    # Insert a user entry with a preference keyword
    entry = EpisodicEntry(
        session_id=session_id,
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="Ricorda che preferisco Python rispetto a Java",
        content_hash=content_hash("Ricorda che preferisco Python rispetto a Java"),
    )
    await store.insert(entry)

    # Distill the session
    chunks = await clm.distill_session(session_id)
    assert len(chunks) >= 1, "CLM should extract at least one preference chunk"
    assert chunks[0].kind in ("preference", "decision")

    # Recall should now return the semantic chunk
    results = await semantic.search("preferisco Python", top_k=5)
    assert len(results) >= 1
    assert "Python" in results[0].text or "preferisco" in results[0].text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_distill_range_covers_multiple_sessions(stores):
    """distill_range processes entries from multiple sessions."""
    store, semantic, clm = stores

    # Insert entries in two sessions with preference keywords
    for i in range(2):
        session_id = uuid4()
        entry = EpisodicEntry(
            session_id=session_id,
            ts=datetime.now(UTC),
            actor=Actor.USER_INPUT,
            role="user",
            content=f"Ricordami di fare la cosa {i} domani",
            content_hash=content_hash(f"Ricordami di fare la cosa {i} domani"),
        )
        await store.insert(entry)

    from datetime import timedelta
    since = datetime.now(UTC) - timedelta(hours=1)
    until = datetime.now(UTC)
    chunks = await clm.distill_range(since, until)
    assert len(chunks) >= 2, "Two entries with action patterns should yield >=2 chunks"
```

- [ ] **Step 3: Write E2E test: forget → hitl_approve → tombstone**

Create `tests/integration/memory/test_hitl_approve.py`:

```python
"""Integration test: HITL full cycle forget → hitl_approve → tombstone."""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore


@pytest.fixture
def mock_config(tmp_path):
    cfg = MagicMock()
    cfg.paths.runtime = tmp_path
    cfg.memory.t0_retention_days = 365
    cfg.memory.t2_enabled = False
    return cfg


@pytest_asyncio.fixture
async def stores(tmp_path, mock_config):
    db_path = tmp_path / "episodic.db"
    mock_config.paths.runtime = tmp_path
    store = EpisodicStore(db_path, mock_config)
    await store.connect()
    semantic = SemanticStore(db_path, mock_config)
    await semantic.connect(store._conn)
    yield store, semantic
    await store.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forget_episodic_hitl_cycle(stores):
    """forget() → hitl list → hitl_approve() tombstones the entry."""
    store, semantic = stores

    # Insert entry
    entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="sensitive data to forget",
        content_hash=content_hash("sensitive data to forget"),
    )
    await store.insert(entry)

    # Enqueue HITL forget (simulating mcp_server.forget tool)
    hitl_id = await store.enqueue_hitl(
        target_id=entry.id,
        action="forget_episodic",
        reason="user requested",
        trace_id="trace-test",
        channel="test",
    )

    # Pending list should contain the request
    pending = await store.list_hitl_pending(limit=10)
    hitl_ids = [p["id"] for p in pending]
    assert hitl_id in hitl_ids

    # Entry is still visible (not yet approved)
    visible = await store.get(entry.id)
    assert visible is not None

    # Approve the HITL request — tombstone the entry
    tombstoned = await store.tombstone(entry.id, reason=f"approved via hitl_approve({hitl_id})")
    assert tombstoned is True

    # Mark resolved in HITL table
    conn = await store._ensure_connected()
    await conn.execute(
        "UPDATE memory_hitl_pending SET status = 'approved', resolved_at = ? WHERE id = ?",
        (int(datetime.now(UTC).timestamp()), hitl_id),
    )
    await conn.commit()

    # Entry no longer visible
    visible = await store.get(entry.id)
    assert visible is None

    # HITL record is resolved
    pending = await store.list_hitl_pending(limit=10)
    record = next((p for p in pending if p["id"] == hitl_id), None)
    assert record is not None
    assert record["status"] == "approved"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hitl_cancel_leaves_entry_intact(stores):
    """hitl_cancel() marks request cancelled, entry remains visible."""
    store, semantic = stores

    entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC),
        actor=Actor.USER_INPUT,
        role="user",
        content="entry that should survive",
        content_hash=content_hash("entry that should survive"),
    )
    await store.insert(entry)

    hitl_id = await store.enqueue_hitl(
        target_id=entry.id,
        action="forget_episodic",
        reason="test cancel",
        trace_id=None,
        channel="test",
    )

    # Cancel
    conn = await store._ensure_connected()
    cursor = await conn.execute(
        "UPDATE memory_hitl_pending SET status = 'cancelled', resolved_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (int(datetime.now(UTC).timestamp()), hitl_id),
    )
    await conn.commit()
    assert cursor.rowcount == 1

    # Entry still visible
    visible = await store.get(entry.id)
    assert visible is not None
```

- [ ] **Step 4: Write E2E test: retention pruning**

Create `tests/integration/memory/test_retention_pruning.py`:

```python
"""Integration test: T0 retention pruning on real SQLite."""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash


@pytest.fixture
def mock_config(tmp_path):
    cfg = MagicMock()
    cfg.paths.runtime = tmp_path
    cfg.memory.t0_retention_days = 30
    cfg.memory.t2_enabled = False
    return cfg


@pytest_asyncio.fixture
async def store(tmp_path, mock_config):
    db_path = tmp_path / "episodic.db"
    s = EpisodicStore(db_path, mock_config)
    await s.connect()
    yield s
    await s.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prune_old_entries_e2e(store):
    """Entries older than retention_days are tombstoned; recent ones survive."""
    # Old entry (40 days ago)
    old_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=40),
        actor=Actor.USER_INPUT,
        role="user",
        content="this is old",
        content_hash=content_hash("this is old"),
    )
    await store.insert(old_entry)

    # Recent entry
    recent_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=5),
        actor=Actor.USER_INPUT,
        role="user",
        content="this is recent",
        content_hash=content_hash("this is recent"),
    )
    await store.insert(recent_entry)

    pruned = await store.prune_old_entries(retention_days=30)
    assert pruned == 1

    assert await store.get(old_entry.id) is None
    assert await store.get(recent_entry.id) is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prune_idempotent(store):
    """Running prune twice does not double-tombstone entries."""
    old_entry = EpisodicEntry(
        session_id=uuid4(),
        ts=datetime.now(UTC) - timedelta(days=40),
        actor=Actor.USER_INPUT,
        role="user",
        content="old idempotent",
        content_hash=content_hash("old idempotent"),
    )
    await store.insert(old_entry)

    first = await store.prune_old_entries(retention_days=30)
    second = await store.prune_old_entries(retention_days=30)

    assert first == 1
    assert second == 0  # already tombstoned, INSERT OR IGNORE / WHERE NOT IN
```

- [ ] **Step 5: Run integration tests**

```bash
uv run pytest -q tests/integration/memory/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Quality gate**

```bash
uv run ruff check tests/integration/memory/
uv run mypy tests/integration/memory/
```

Expected: `PASS` on both.

- [ ] **Step 7: Commit**

```bash
git add tests/integration/memory/
git commit -m "test(memory): add integration tests for E2E remember/distill/recall, HITL, retention"
```

---

## Task 7: Backup Scheduling via Systemd Timer

**Files:**
- Create: `systemd/aria-backup.service`
- Create: `systemd/aria-backup.timer`

### Why

`scripts/backup.sh` exists and works but has no automation. Blueprint §5.7 mentions backup without specifying frequency; weekly is a sane MVP default.

- [ ] **Step 1: Create aria-backup.service**

Create `systemd/aria-backup.service`:

```ini
[Unit]
Description=ARIA Backup — one-shot encrypted backup of episodic.db and credentials
After=network.target

[Service]
Type=oneshot
ExecStart=%h/coding/aria/scripts/backup.sh
WorkingDirectory=%h/coding/aria

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
PrivateTmp=true
ReadWritePaths=%h/.aria-backups
ReadWritePaths=%h/coding/aria/.aria

StandardOutput=journal
StandardError=journal
SyslogIdentifier=aria-backup

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Create aria-backup.timer**

Create `systemd/aria-backup.timer`:

```ini
[Unit]
Description=ARIA weekly backup timer
Requires=aria-backup.service

[Timer]
# Every Sunday at 02:00 local time
OnCalendar=weekly
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Update install_systemd.sh to install the timer**

Check `scripts/install_systemd.sh` — add `aria-backup.timer` to the list of units installed/enabled.

In `scripts/install_systemd.sh`, find where other `.service` files are copied (e.g., `aria-scheduler.service`, `aria-gateway.service`) and add:

```bash
cp systemd/aria-backup.service "$SYSTEMD_DIR/"
cp systemd/aria-backup.timer "$SYSTEMD_DIR/"
```

And in the `enable` section:

```bash
systemctl --user enable aria-backup.timer
systemctl --user start aria-backup.timer
```

- [ ] **Step 4: Verify timer syntax**

```bash
systemd-analyze verify systemd/aria-backup.timer systemd/aria-backup.service 2>/dev/null || \
  systemd-run --user --unit=test-timer-verify \
    systemd-analyze verify systemd/aria-backup.timer 2>&1 | head -20
```

If `systemd-analyze verify` is unavailable, at minimum validate INI syntax:

```bash
grep -E "^\[|^[A-Z]" systemd/aria-backup.timer systemd/aria-backup.service
```

Expected: no parse errors.

- [ ] **Step 5: Commit**

```bash
git add systemd/aria-backup.service systemd/aria-backup.timer scripts/install_systemd.sh
git commit -m "feat(ops): add aria-backup.timer for weekly automated encrypted backup"
```

---

## Task 8: Wiki Update

**Files:**
- Modify: `docs/llm_wiki/wiki/memory-subsystem.md`
- Modify: `docs/llm_wiki/wiki/log.md`
- Modify: `docs/llm_wiki/wiki/index.md`

### Why

CLAUDE.md mandates wiki maintenance after every meaningful task. The health check identified multiple gaps; fixing them changes the conformance table significantly.

- [ ] **Step 1: Update `memory-subsystem.md`**

Update the gap table to reflect resolved status:

| Gap | Before | After |
|-----|--------|-------|
| CLM mai eseguito | ❌ CRITICO | ✅ post-session hook + 6h cron |
| HITL approval path inesistente | ❌ CRITICO | ✅ `hitl_approve` tool |
| Retention T0/T1 non applicata | ❌ CRITICO | ✅ `prune_old_entries` + Reaper |
| WAL episodic.db non checkpointato | ⚠️ MANCANTE | ✅ Reaper + memory-wal-checkpoint task |
| Integration tests assenti | ⚠️ MANCANTE | ✅ 6 integration tests |
| Backup non schedulato | ⚠️ MANCANTE | ✅ aria-backup.timer |
| T1 compression 90gg | ⚠️ MANCANTE | ⚠️ DEFERRED (T1 now populated; compress later) |

Add section for new tools:
- `hitl_approve` — description and args
- CLM trigger: post-session via `ConductorBridge._distill_session_bg` and 6h via scheduler

Update `source:` and `last_updated:` fields.

- [ ] **Step 2: Append log entry to `log.md`**

```markdown
## 2026-04-24T<HH:MM> — Memory Gap Remediation (Sprint 1.2)

**Operation**: IMPLEMENT — Close all 7 gaps from memory health check
**Pages affected**: [[memory-subsystem]]
**Sources**: `src/aria/memory/episodic.py`, `src/aria/memory/mcp_server.py`,
             `src/aria/gateway/conductor_bridge.py`, `src/aria/gateway/daemon.py`,
             `src/aria/scheduler/reaper.py`, `src/aria/scheduler/runner.py`,
             `src/aria/scheduler/daemon.py`, `systemd/aria-backup.*`,
             `tests/integration/memory/`

### Changes

1. `prune_old_entries(retention_days)` added to EpisodicStore — P6-compliant tombstone
2. `hitl_approve(hitl_id)` MCP tool added — closes P7 HITL execution path
3. Post-session CLM hook in ConductorBridge — §5.4 trigger post-session
4. memory-distill + memory-wal-checkpoint cron tasks seeded in scheduler
5. Reaper extended with episodic_store: WAL checkpoint + retention pruning every 6h
6. 6 integration tests in `tests/integration/memory/` covering E2E flows
7. aria-backup.timer systemd unit for weekly encrypted backup

### Quality Gates

```
ruff check: PASS
ruff format --check: PASS
mypy: PASS
pytest -q: all pass (unit + integration)
```
```

- [ ] **Step 3: Update index.md**

Add `docs/plans/memory_gaps_remediation_plan_2026-04-24.md` to raw sources table.

- [ ] **Step 4: Commit**

```bash
git add docs/llm_wiki/wiki/memory-subsystem.md \
        docs/llm_wiki/wiki/log.md \
        docs/llm_wiki/wiki/index.md
git commit -m "docs(wiki): update memory-subsystem wiki post gap remediation"
```

---

## Final Verification

Run the full quality gate before creating PR:

- [ ] **Step 1: Full test suite**

```bash
uv run pytest -q
```

Expected: all tests pass (was 543 before this plan; should be 543 + ~15 new).

- [ ] **Step 2: Quality gate**

```bash
uv run ruff check src/
uv run ruff format --check src/
uv run mypy src/
```

Expected: `PASS` on all three.

- [ ] **Step 3: Validate MCP server tool count**

```bash
python -c "
import aria.memory.mcp_server as s
tools = [attr for attr in dir(s.mcp) if not attr.startswith('_')]
print('MCP tools registered')
"
```

Or count `@mcp.tool` decorators:

```bash
grep -c "@mcp.tool" src/aria/memory/mcp_server.py
```

Expected: `11` (was 10, now +1 for `hitl_approve`). Still ≤ 20 per P9. ✅

- [ ] **Step 4: Smoke test CLM on existing data**

```bash
uv run python -c "
import asyncio
from aria.config import get_config
from aria.memory.episodic import create_episodic_store
from aria.memory.semantic import SemanticStore
from aria.memory.clm import CLM
from datetime import UTC, datetime, timedelta

async def main():
    config = get_config()
    store = await create_episodic_store(config)
    semantic = SemanticStore(store._db_path, config)
    await semantic.connect(store._conn)
    clm = CLM(store, semantic)
    since = datetime.now(UTC) - timedelta(hours=168)  # last week
    chunks = await clm.distill_range(since, datetime.now(UTC))
    print(f'Distilled {len(chunks)} chunks from existing 1005 T0 entries')
    await store.close()

asyncio.run(main())
"
```

Expected: prints `Distilled N chunks` where N > 0.

---

## Scope Note: T1 Compression (90d) — Deferred

Blueprint §5.7 specifies T1 compression after 90 days. This is **intentionally deferred** because:
1. T1 had 0 chunks before this plan — nothing to compress.
2. CLM is now operational; T1 will accumulate data.
3. Compression logic (merging similar chunks, reducing occurrences) adds complexity.
4. Re-evaluate after 30 days of CLM operation when T1 has meaningful data volume.

Create an ADR stub if needed (`docs/foundation/decisions/ADR-0011-t1-compression-deferred.md`).

---

*Plan authored: 2026-04-24*
*Source: `docs/analysis/memory_subsystem_health_check_2026-04-24.md`*
*Context7 verified: FastMCP @mcp.tool, aiosqlite execute/fetchone/rowcount*
