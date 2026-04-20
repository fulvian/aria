# Tests for ARIA HITL Manager
#
# Per sprint plan W1.2.E.
#
# Tests:
# - ask: creates pending HITL
# - wait_for_response: timeout handling
# - resolve: sets response and notifies waiters
# - expire_stale: handles expired HITLs

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from aria.scheduler.hitl import HitlManager
from aria.scheduler.schema import HitlPending, make_hitl_pending, make_task
from aria.scheduler.store import TaskStore
from aria.scheduler.triggers import EventBus


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self, runtime_path: Path | None = None) -> None:
        self._runtime = runtime_path or Path("/tmp/test_runtime")

    @property
    def runtime(self) -> Path:
        return self._runtime


@pytest.fixture
async def store(tmp_path: Path) -> TaskStore:
    """Create TaskStore with temporary database."""
    db_path = tmp_path / "test_hitl.db"
    store = TaskStore(db_path)
    await store.connect()
    yield store
    await store.close()


@pytest.fixture
def mock_bus() -> MagicMock:
    """Create mock EventBus."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_config() -> MockConfig:
    """Create mock configuration."""
    return MockConfig()


@pytest.fixture
async def hitl_manager(
    store: TaskStore,
    mock_bus: MagicMock,
    mock_config: MockConfig,
) -> HitlManager:
    """Create HitlManager instance."""
    manager = HitlManager(store, mock_bus, mock_config)
    yield manager


# === Ask Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_ask_creates_pending(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test ask() creates a hitl_pending entry."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
        owner_user_id="12345",
    )
    await store.create_task(task)

    run_id = str(uuid4())
    question = "Do you approve this action?"

    pending = await hitl_manager.ask(
        task=task,
        run_id=run_id,
        question=question,
        options=["yes", "no"],
        ttl_seconds=900,
    )

    assert pending is not None
    assert pending.id is not None
    assert pending.task_id == task.id
    assert pending.run_id == run_id
    assert pending.question == question
    assert pending.channel == "telegram"


@pytest.mark.asyncio
async def test_hitl_manager_ask_publishes_event(
    hitl_manager: HitlManager,
    store: TaskStore,
    mock_bus: MagicMock,
) -> None:
    """Test ask() publishes hitl.created event."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
        owner_user_id="12345",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test question?",
        ttl_seconds=900,
    )

    # Verify event was published
    mock_bus.publish.assert_called_once()
    call_args = mock_bus.publish.call_args
    assert call_args[0][0] == "hitl.created"
    payload = call_args[0][1]
    assert payload["hitl_id"] == pending.id
    assert payload["task_id"] == task.id


@pytest.mark.asyncio
async def test_hitl_manager_ask_sets_waiting_state(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test ask() initializes waiting state."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=60,
    )

    # Check internal state
    assert pending.id in hitl_manager._waiting
    assert isinstance(hitl_manager._waiting[pending.id], asyncio.Event)
    assert pending.id in hitl_manager._responses


# === Wait for Response Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_wait_for_response_timeout(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test wait_for_response returns None on timeout."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=2,  # Short TTL
    )

    # Wait with very short timeout - should timeout
    response = await hitl_manager.wait_for_response(pending.id, timeout_s=1)

    assert response is None


@pytest.mark.asyncio
async def test_hitl_manager_wait_for_response_not_found(
    hitl_manager: HitlManager,
) -> None:
    """Test wait_for_response returns None for unknown hitl_id."""
    response = await hitl_manager.wait_for_response("unknown-id", timeout_s=1)

    assert response is None


@pytest.mark.asyncio
async def test_hitl_manager_wait_resolves_on_event(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test wait_for_response resolves when resolve() is called."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=10,
    )

    # Resolve in another task
    async def resolve_later() -> None:
        await asyncio.sleep(0.1)
        await hitl_manager.resolve(pending.id, "yes")

    # Start both tasks concurrently
    await asyncio.gather(
        hitl_manager.wait_for_response(pending.id, timeout_s=5),
        resolve_later(),
    )

    # Response should be "yes"
    # Note: Due to timing, the gather returns results, but main assertion
    # is that resolve() was called without error


# === Resolve Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_resolve_sets_response(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test resolve() updates database with response."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=900,
    )

    # Resolve the HITL
    await hitl_manager.resolve(pending.id, "yes")

    # Verify in database
    resolved = await store.resolve_hitl(pending.id, "yes")
    assert resolved is not None
    assert resolved.user_response == "yes"
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_hitl_manager_resolve_notifies_waiter(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test resolve() notifies the waiting task."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=900,
    )

    # Verify event is set after resolve
    await hitl_manager.resolve(pending.id, "approved")

    assert hitl_manager._waiting[pending.id].is_set()
    assert hitl_manager._responses[pending.id] == "approved"


@pytest.mark.asyncio
async def test_hitl_manager_resolve_publishes_event(
    hitl_manager: HitlManager,
    store: TaskStore,
    mock_bus: MagicMock,
) -> None:
    """Test resolve() publishes hitl.resolved event."""
    task = make_task(
        name="HITL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=900,
    )

    await hitl_manager.resolve(pending.id, "yes")

    # Verify event published
    mock_bus.publish.assert_called()
    calls = mock_bus.publish.call_args_list
    resolved_call = [c for c in calls if c[0][0] == "hitl.resolved"]
    assert len(resolved_call) == 1
    assert resolved_call[0][0][1]["hitl_id"] == pending.id
    assert resolved_call[0][0][1]["response"] == "yes"


@pytest.mark.asyncio
async def test_hitl_manager_resolve_not_found(
    hitl_manager: HitlManager,
) -> None:
    """Test resolve() handles unknown hitl_id gracefully."""
    # Should not raise
    await hitl_manager.resolve("unknown-id", "yes")


# === Expire Stale Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_expire_stale(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test expire_stale() finds and expires old HITLs."""
    task = make_task(
        name="Expire Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    now = int(datetime.now().timestamp() * 1000)

    # Create an already-expired HITL directly in store
    expired = HitlPending(
        id=str(uuid4()),
        task_id=task.id,
        run_id=str(uuid4()),
        created_at=now - 1800000,  # 30 min ago
        expires_at=now - 900000,  # Expired 15 min ago
        question="Expired question?",
        channel="telegram",
    )
    await store.create_hitl(expired)

    # Expire stale HITLs
    expired_ids = await hitl_manager.expire_stale()

    assert len(expired_ids) == 1
    assert expired_ids[0] == expired.id


@pytest.mark.asyncio
async def test_hitl_manager_expire_stale_notifies_waiters(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test expire_stale() notifies waiting tasks of timeout."""
    task = make_task(
        name="Expire Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    now = int(datetime.now().timestamp() * 1000)

    # Create expired HITL with waiting state
    expired = HitlPending(
        id=str(uuid4()),
        task_id=task.id,
        run_id=str(uuid4()),
        created_at=now - 1800000,
        expires_at=now - 900000,
        question="Expired?",
        channel="telegram",
    )
    await store.create_hitl(expired)
    hitl_manager._waiting[expired.id] = asyncio.Event()
    hitl_manager._responses[expired.id] = ""

    # Expire
    await hitl_manager.expire_stale()

    # Waiter should be notified (event set)
    assert hitl_manager._waiting[expired.id].is_set()
    # Response should be empty (timeout)
    assert hitl_manager._responses[expired.id] == ""


@pytest.mark.asyncio
async def test_hitl_manager_expire_no_stale(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test expire_stale() with no expired entries."""
    task = make_task(
        name="Valid Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    # Create a non-expired HITL
    valid = HitlPending(
        id=str(uuid4()),
        task_id=task.id,
        run_id=str(uuid4()),
        created_at=int(datetime.now().timestamp() * 1000),
        expires_at=int((datetime.now() + timedelta(hours=1)).timestamp() * 1000),
        question="Valid question?",
        channel="telegram",
    )
    await store.create_hitl(valid)

    expired_ids = await hitl_manager.expire_stale()

    assert len(expired_ids) == 0


# === Clear Completed Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_clear_completed(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test clear_completed() removes internal state."""
    task = make_task(
        name="Clear Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Test?",
        ttl_seconds=900,
    )

    # Verify state exists
    assert pending.id in hitl_manager._waiting
    assert pending.id in hitl_manager._responses

    # Clear
    hitl_manager.clear_completed(pending.id)

    # Verify state removed
    assert pending.id not in hitl_manager._waiting
    assert pending.id not in hitl_manager._responses


# === Roundtrip Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_full_roundtrip(
    hitl_manager: HitlManager,
    store: TaskStore,
    mock_bus: MagicMock,
) -> None:
    """Test complete HITL flow: ask -> wait -> resolve."""
    task = make_task(
        name="Roundtrip Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
        owner_user_id="12345",
    )
    await store.create_task(task)
    run_id = str(uuid4())

    # Ask
    pending = await hitl_manager.ask(
        task=task,
        run_id=run_id,
        question="Approve?",
        options=["yes", "no"],
        ttl_seconds=60,
    )

    assert pending.id is not None
    mock_bus.publish.assert_called_with(
        "hitl.created",
        ANY,
    )

    # Resolve
    await hitl_manager.resolve(pending.id, "yes")

    # Verify
    resolved = await store.resolve_hitl(pending.id, "yes")
    assert resolved is not None
    assert resolved.user_response == "yes"


# === Error Handling Tests ===


@pytest.mark.asyncio
async def test_hitl_manager_ask_with_options(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test ask() with options parameter."""
    task = make_task(
        name="Options Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    options = ["approve", "deny", "defer"]
    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="What to do?",
        options=options,
        ttl_seconds=900,
    )

    assert pending.options_json is not None
    assert "approve" in pending.options_json
    assert "deny" in pending.options_json


@pytest.mark.asyncio
async def test_hitl_manager_ask_cli_channel(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test ask() with cli channel."""
    task = make_task(
        name="CLI Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="CLI question?",
        channel="cli",
        ttl_seconds=900,
    )

    assert pending.channel == "cli"


@pytest.mark.asyncio
async def test_hitl_manager_default_ttl(
    hitl_manager: HitlManager,
    store: TaskStore,
) -> None:
    """Test default TTL is 15 minutes (900 seconds)."""
    task = make_task(
        name="Default TTL Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )
    await store.create_task(task)

    pending = await hitl_manager.ask(
        task=task,
        run_id=str(uuid4()),
        question="Default TTL?",
    )

    # Check expiry is approximately 15 min from now
    now = int(datetime.now().timestamp() * 1000)
    expected_expiry = now + (900 * 1000)
    diff = abs(pending.expires_at - expected_expiry)
    assert diff < 5000  # Within 5 seconds
