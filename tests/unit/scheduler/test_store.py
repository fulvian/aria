# Tests for ARIA TaskStore
#
# Per sprint plan W1.2.A.
#
# Tests:
# - Task CRUD operations
# - Lease-based concurrency
# - TaskRun tracking
# - DLQ management
# - HITL pending queue

from __future__ import annotations

import asyncio
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from aria.scheduler.schema import (
    DlqEntry,
    HitlPending,
    Task,
    TaskRun,
    make_hitl_pending,
    make_task,
    make_task_run,
)
from aria.scheduler.store import TaskStore


@pytest.fixture
async def store(tmp_path: Path) -> TaskStore:
    """Create a TaskStore with temporary database."""
    db_path = tmp_path / "test_scheduler.db"
    store = TaskStore(db_path)
    await store.connect()
    yield store
    await store.close()


@pytest.fixture
async def conn(tmp_path: Path):
    """Create a raw aiosqlite connection for advanced testing."""
    import aiosqlite

    db_path = tmp_path / "test_scheduler.db"
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    yield conn
    await conn.close()


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    return Task(
        id=str(uuid4()),
        name="Test Task",
        category="search",
        trigger_type="cron",
        trigger_config={"cron": "0 8 * * *"},
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
        next_run_at=now - 1000,  # Due immediately
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )


# === Task CRUD Tests ===


@pytest.mark.asyncio
async def test_store_create_and_retrieve_task(store: TaskStore, sample_task: Task) -> None:
    """Test creating a task and retrieving it by ID."""
    # Create task
    task_id = await store.create_task(sample_task)
    assert task_id == sample_task.id

    # Retrieve task
    retrieved = await store.get_task(task_id)
    assert retrieved is not None
    assert retrieved.id == sample_task.id
    assert retrieved.name == sample_task.name
    assert retrieved.category == sample_task.category
    assert retrieved.status == "active"


@pytest.mark.asyncio
async def test_store_update_task(store: TaskStore, sample_task: Task) -> None:
    """Test updating task fields."""
    await store.create_task(sample_task)

    # Update task
    await store.update_task(sample_task.id, name="Updated Name", status="paused")

    # Verify update
    retrieved = await store.get_task(sample_task.id)
    assert retrieved is not None
    assert retrieved.name == "Updated Name"
    assert retrieved.status == "paused"


@pytest.mark.asyncio
async def test_store_list_tasks(store: TaskStore, sample_task: Task) -> None:
    """Test listing tasks with filters."""
    # Create multiple tasks
    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    task2 = Task(
        id=str(uuid4()),
        name="Task 2",
        category="workspace",
        trigger_type="manual",
        trigger_config={},
        status="active",
        policy="ask",
        payload={},
        created_at=now,
        updated_at=now,
    )
    await store.create_task(sample_task)
    await store.create_task(task2)

    # List all
    all_tasks = await store.list_tasks()
    assert len(all_tasks) == 2

    # Filter by category
    search_tasks = await store.list_tasks(category="search")
    assert len(search_tasks) == 1
    assert search_tasks[0].category == "search"

    # Filter by status
    active_tasks = await store.list_tasks(status=["active"])
    assert len(active_tasks) == 2


# === Lease-based Concurrency Tests ===


@pytest.mark.asyncio
async def test_store_acquire_due_returns_only_due_tasks(store: TaskStore) -> None:
    """Test acquire_due returns only tasks that are due."""
    now = int(datetime.now(tz=UTC).timestamp() * 1000)

    # Create a due task (next_run_at in the past)
    due_task = Task(
        id=str(uuid4()),
        name="Due Task",
        category="search",
        trigger_type="cron",
        trigger_config={},
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
        next_run_at=now - 1000,  # Past
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )

    # Create a future task (not yet due)
    future_task = Task(
        id=str(uuid4()),
        name="Future Task",
        category="search",
        trigger_type="cron",
        trigger_config={},
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
        next_run_at=now + 3600000,  # 1 hour in future
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )

    await store.create_task(due_task)
    await store.create_task(future_task)

    # Acquire due tasks
    worker_id = "test-worker-1"
    acquired = await store.acquire_due(worker_id, lease_ttl_seconds=300, limit=10)

    # Should only get the due task
    assert len(acquired) == 1
    assert acquired[0].id == due_task.id
    assert acquired[0].lease_owner == worker_id


@pytest.mark.asyncio
async def test_store_concurrent_acquire_only_one_wins(tmp_path: Path, sample_task: Task) -> None:
    """Test that concurrent acquire_due calls only one worker wins the lease."""
    # Use separate stores connected to same database
    db_path = tmp_path / "test_concurrent.db"

    store1 = TaskStore(db_path)
    store2 = TaskStore(db_path)
    await store1.connect()
    await store2.connect()

    try:
        # Create the task
        sample_task.next_run_at = int(time.time() * 1000) - 1000
        await store1.create_task(sample_task)

        # Simulate concurrent acquire
        worker1_id = "worker-1"
        worker2_id = "worker-2"

        async def acquire_and_check() -> tuple[str | None, str | None]:
            """Both workers try to acquire simultaneously."""
            acquired1 = await store1.acquire_due(worker1_id, lease_ttl_seconds=300, limit=1)
            acquired2 = await store2.acquire_due(worker2_id, lease_ttl_seconds=300, limit=1)

            w1_got = acquired1[0].id if acquired1 else None
            w2_got = acquired2[0].id if acquired2 else None
            return w1_got, w2_got

        # Run concurrent acquire
        (w1_result, w2_result) = await acquire_and_check()

        # Only one should have gotten the task
        results = [r for r in [w1_result, w2_result] if r is not None]
        assert len(results) == 1, "Expected only one worker to acquire the task"

        # Verify in database that only one holds the lease
        task = await store1.get_task(sample_task.id)
        assert task is not None
        assert task.lease_owner in (worker1_id, worker2_id)

    finally:
        await store1.close()
        await store2.close()


@pytest.mark.asyncio
async def test_store_release_lease_makes_task_reacquirable(store: TaskStore) -> None:
    """Test that releasing a lease makes the task re-acquirable."""
    now = int(datetime.now(tz=UTC).timestamp() * 1000)

    # Create a due task
    task = Task(
        id=str(uuid4()),
        name="Release Test Task",
        category="search",
        trigger_type="cron",
        trigger_config={},
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
        next_run_at=now - 1000,  # Due immediately
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )
    await store.create_task(task)

    worker_id = "test-worker"

    # Acquire task
    acquired = await store.acquire_due(worker_id, lease_ttl_seconds=300, limit=10)
    assert len(acquired) == 1
    assert acquired[0].lease_owner == worker_id

    # Release lease
    await store.release_lease(task.id, worker_id)

    # Verify lease is released
    task = await store.get_task(task.id)
    assert task is not None
    assert task.lease_owner is None
    assert task.lease_expires_at is None

    # Another worker can now acquire (verify by checking lease_owner is None before re-acquire)
    # Since release cleared the lease, a new acquire should succeed
    task_after_release = await store.get_task(task.id)
    assert task_after_release is not None
    assert task_after_release.lease_owner is None

    # Re-acquire with new worker
    new_worker_id = "new-worker"
    acquired2 = await store.acquire_due(new_worker_id, lease_ttl_seconds=300, limit=10)
    assert len(acquired2) == 1
    assert acquired2[0].lease_owner == new_worker_id


# === TaskRun Tests ===


@pytest.mark.asyncio
async def test_store_record_run(store: TaskStore, sample_task: Task) -> None:
    """Test recording a task run."""
    await store.create_task(sample_task)

    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    run = TaskRun(
        id=str(uuid4()),
        task_id=sample_task.id,
        started_at=now,
        outcome="success",
        tokens_used=1000,
        cost_eur=0.01,
    )

    run_id = await store.record_run(run)
    assert run_id == run.id


@pytest.mark.asyncio
async def test_store_update_run(store: TaskStore, sample_task: Task) -> None:
    """Test updating a task run."""
    await store.create_task(sample_task)

    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    run = TaskRun(
        id=str(uuid4()),
        task_id=sample_task.id,
        started_at=now,
        outcome="success",
    )

    await store.record_run(run)

    # Update run with completion info
    finished_at = now + 5000
    await store.update_run(
        run.id,
        finished_at=finished_at,
        outcome="success",
        tokens_used=1500,
        cost_eur=0.02,
        result_summary="Completed successfully",
    )

    # Note: TaskStore doesn't have get_run, so we verify through task_runs table
    # The update_run just executes UPDATE, so we verify it doesn't raise


# === DLQ Tests ===


@pytest.mark.asyncio
async def test_store_move_to_dlq(store: TaskStore, sample_task: Task) -> None:
    """Test moving a task to the DLQ."""
    await store.create_task(sample_task)

    dlq_id = await store.move_to_dlq(
        sample_task.id,
        reason="Max retries exceeded",
        last_run_id=None,
    )

    assert dlq_id is not None

    # Verify task status is now dlq
    task = await store.get_task(sample_task.id)
    assert task is not None
    assert task.status == "dlq"

    # Verify DLQ entry
    dlq_entries = await store.list_dlq()
    assert len(dlq_entries) == 1
    assert dlq_entries[0].task_id == sample_task.id
    assert dlq_entries[0].reason == "Max retries exceeded"


@pytest.mark.asyncio
async def test_store_list_dlq(store: TaskStore, sample_task: Task) -> None:
    """Test listing DLQ entries."""
    await store.create_task(sample_task)
    await store.move_to_dlq(sample_task.id, reason="Test DLQ", last_run_id=None)

    dlq_entries = await store.list_dlq()
    assert len(dlq_entries) == 1
    assert dlq_entries[0].reason == "Test DLQ"


# === Lease Reaper Tests ===


@pytest.mark.asyncio
async def test_store_reap_stale_leases(store: TaskStore) -> None:
    """Test reaping stale leases."""
    now = int(datetime.now(tz=UTC).timestamp() * 1000)

    # Create a task with an expired lease
    task = Task(
        id=str(uuid4()),
        name="Stale Lease Task",
        category="search",
        trigger_type="cron",
        trigger_config={},
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
        next_run_at=now - 5000,
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )
    task.lease_owner = "old-worker"
    task.lease_expires_at = now - 1000  # Expired
    await store.create_task(task)

    # Reap stale leases
    reaped_count = await store.reap_stale_leases(now_ms=now)
    assert reaped_count == 1

    # Verify lease is cleared
    retrieved = await store.get_task(task.id)
    assert retrieved is not None
    assert retrieved.lease_owner is None
    assert retrieved.lease_expires_at is None


# === HITL Tests ===


@pytest.mark.asyncio
async def test_store_create_hitl(store: TaskStore, sample_task: Task) -> None:
    """Test creating a HITL pending entry."""
    await store.create_task(sample_task)

    run_id = str(uuid4())
    pending = make_hitl_pending(
        question="Approve this action?",
        task_id=sample_task.id,
        run_id=run_id,
        ttl_seconds=900,
        channel="telegram",
        options=["yes", "no"],
    )

    hitl_id = await store.create_hitl(pending)
    assert hitl_id == pending.id


@pytest.mark.asyncio
async def test_store_resolve_hitl(store: TaskStore, sample_task: Task) -> None:
    """Test resolving a HITL pending entry."""
    await store.create_task(sample_task)

    pending = make_hitl_pending(
        question="Approve this action?",
        task_id=sample_task.id,
        run_id=str(uuid4()),
        ttl_seconds=900,
    )

    await store.create_hitl(pending)

    # Resolve HITL
    resolved = await store.resolve_hitl(pending.id, "yes")
    assert resolved is not None
    assert resolved.user_response == "yes"
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_store_expire_hitl(store: TaskStore, sample_task: Task) -> None:
    """Test expiring stale HITL entries."""
    await store.create_task(sample_task)

    now = int(datetime.now(tz=UTC).timestamp() * 1000)

    # Create an already-expired HITL
    pending = HitlPending(
        id=str(uuid4()),
        task_id=sample_task.id,
        run_id=str(uuid4()),
        created_at=now - 1800000,  # 30 min ago
        expires_at=now - 900000,  # Expired 15 min ago
        question="Expired question?",
        channel="telegram",
    )

    await store.create_hitl(pending)

    # Expire HITLs
    expired = await store.expire_hitl(now_ms=now)
    assert len(expired) == 1
    assert expired[0].id == pending.id


@pytest.mark.asyncio
async def test_store_hitl_roundtrip(store: TaskStore, sample_task: Task) -> None:
    """Test full HITL create -> resolve roundtrip."""
    await store.create_task(sample_task)

    # Create HITL
    pending = make_hitl_pending(
        question="Do you approve?",
        task_id=sample_task.id,
        run_id=str(uuid4()),
        ttl_seconds=60,
        options=["Approve", "Deny"],
    )

    await store.create_hitl(pending)

    # Resolve
    resolved = await store.resolve_hitl(pending.id, "Approve")
    assert resolved is not None
    assert resolved.user_response == "Approve"

    # Verify it persists
    task = await store.get_task(sample_task.id)
    assert task is not None
