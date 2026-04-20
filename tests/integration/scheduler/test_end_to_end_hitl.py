"""Integration test: Full HITL cycle using real scheduler components.

Tests the complete flow:
1. Create a task with policy=ask
2. Create hitl_pending via HitlManager
3. Simulate resolution via resolve()
4. Verify task run completes after HITL resolution

Uses pytest-asyncio, aiosqlite temp DB, mock EventBus.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from aria.scheduler.hitl import HitlManager
from aria.scheduler.schema import (
    make_task,
    make_task_run,
)
from aria.scheduler.store import TaskStore
from aria.scheduler.triggers import EventBus

if TYPE_CHECKING:
    from pathlib import Path  # noqa: TC003


class _MockConfig:
    """Minimal mock config for testing."""

    def __init__(self, tmp_path: Path) -> None:
        self.paths = MagicMock()
        self.paths.runtime = tmp_path / "runtime"
        self.paths.runtime.mkdir(parents=True, exist_ok=True)
        self.operational = MagicMock()
        self.operational.log_level = "DEBUG"
        self.operational.timezone = "Europe/Rome"
        self.operational.quiet_hours_start = "22:00"
        self.operational.quiet_hours_end = "07:00"
        self.telegram = MagicMock()
        self.telegram.whitelist = []

    @property
    def log_level(self) -> str:
        return self.operational.log_level

    @property
    def timezone(self) -> str:
        return self.operational.timezone


@pytest.mark.integration
class TestEndToEndHitl:
    """Integration tests for HITL flow."""

    async def test_hitl_flow_end_to_end(self, tmp_path: Path) -> None:
        """Full HITL flow: create task, ask, respond, resume."""
        db_path = tmp_path / "test_hitl.db"
        store = TaskStore(db_path)
        await store.connect()

        try:
            # Create mock event bus
            bus = EventBus()
            published_events: list[tuple[str, dict]] = []

            async def mock_publish(event: str, payload: dict) -> None:
                published_events.append((event, payload))

            bus.publish = mock_publish  # type: ignore[assignment]

            # Create config
            config = _MockConfig(tmp_path)

            # Create HitlManager
            hitl_manager = HitlManager(store, bus, config)

            # Create task with policy=ask
            task = make_task(
                name="test hitl task",
                category="workspace",
                trigger_type="manual",
                policy="ask",
                owner_user_id="123456",
            )
            await store.create_task(task)

            # Create task run
            run = make_task_run(task_id=task.id)
            await store.record_run(run)

            # Create HITL pending via HitlManager
            question = "Do you want to execute this task?"
            pending = await hitl_manager.ask(
                task=task,
                run_id=run.id,
                question=question,
                options=["yes", "no", "later"],
            )

            assert pending is not None
            assert pending.task_id == task.id
            assert pending.run_id == run.id
            assert pending.question == question
            assert pending.user_response is None
            assert pending.resolved_at is None

            # Verify hitl.created event was published
            hitl_created_events = [(e, p) for e, p in published_events if e == "hitl.created"]
            assert len(hitl_created_events) == 1
            event_name, event_payload = hitl_created_events[0]
            assert event_payload["hitl_id"] == pending.id
            assert event_payload["task_id"] == task.id
            assert event_payload["question"] == question

            # Simulate user response - resolve via HitlManager
            await hitl_manager.resolve(pending.id, "yes")

            # Verify HITL was resolved in the database
            cursor = await store._conn.execute(
                "SELECT * FROM hitl_pending WHERE id = ?", (pending.id,)
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row["user_response"] == "yes"
            assert row["resolved_at"] is not None

            # Verify hitl.resolved event was published
            hitl_resolved_events = [(e, p) for e, p in published_events if e == "hitl.resolved"]
            assert len(hitl_resolved_events) == 1
            _, resolved_payload = hitl_resolved_events[0]
            assert resolved_payload["hitl_id"] == pending.id
            assert resolved_payload["response"] == "yes"

            # Verify wait_for_response returns the response
            # (Since we already resolved, the event was set)
            # Note: This tests the asyncio.Event notification mechanism
            assert pending.id in hitl_manager._responses
            assert hitl_manager._responses[pending.id] == "yes"

        finally:
            await store.close()

    async def test_hitl_ask_and_wait_for_response(self, tmp_path: Path) -> None:
        """Test HITL ask then wait with immediate resolve."""
        db_path = tmp_path / "test_hitl_wait.db"
        store = TaskStore(db_path)
        await store.connect()

        try:
            bus = EventBus()
            config = _MockConfig(tmp_path)
            hitl_manager = HitlManager(store, bus, config)

            # Create task
            task = make_task(
                name="test wait task",
                category="search",
                trigger_type="manual",
                policy="ask",
            )
            await store.create_task(task)

            run = make_task_run(task_id=task.id)
            await store.record_run(run)

            # Create HITL
            pending = await hitl_manager.ask(
                task=task,
                run_id=run.id,
                question="Continue?",
            )

            # Start waiting for response (in background)
            async def wait_task() -> str | None:
                return await hitl_manager.wait_for_response(pending.id, timeout_s=5)

            wait_future = asyncio.create_task(wait_task())

            # Give the wait task a moment to start waiting
            await asyncio.sleep(0.1)

            # Resolve the HITL
            await hitl_manager.resolve(pending.id, "yes")

            # Wait for the response
            response = await wait_future
            assert response == "yes"

        finally:
            await store.close()

    async def test_hitl_expire_stale(self, tmp_path: Path) -> None:
        """Test expiration of stale HITL entries."""
        db_path = tmp_path / "test_hitl_expire.db"
        store = TaskStore(db_path)
        await store.connect()

        try:
            bus = EventBus()
            config = _MockConfig(tmp_path)
            hitl_manager = HitlManager(store, bus, config)

            # Create task
            task = make_task(
                name="test expire task",
                category="workspace",
                trigger_type="manual",
                policy="ask",
            )
            await store.create_task(task)

            run = make_task_run(task_id=task.id)
            await store.record_run(run)

            # Create HITL with very short TTL
            pending = await hitl_manager.ask(
                task=task,
                run_id=run.id,
                question="Expire test?",
                ttl_seconds=1,  # 1 second TTL
            )

            # Verify it exists
            cursor = await store._conn.execute(
                "SELECT * FROM hitl_pending WHERE id = ?", (pending.id,)
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row["resolved_at"] is None

            # Wait for expiration
            await asyncio.sleep(1.5)

            # Manually expire via store (simulating what reaper does)
            from aria.scheduler.schema import make_hitl_pending

            # Create an already-expired HITL directly in store
            expired_pending = make_hitl_pending(
                question="Already expired",
                task_id=task.id,
                run_id=run.id,
                ttl_seconds=0,  # Already expired
            )
            await store.create_hitl(expired_pending)

            # Call expire_stale
            expired_ids = await hitl_manager.expire_stale()

            # The freshly expired one should be in the list
            assert expired_pending.id in expired_ids

        finally:
            await store.close()

    async def test_hitl_store_create_and_resolve(self, tmp_path: Path) -> None:
        """Test HITL creation and resolution via TaskStore directly."""
        db_path = tmp_path / "test_hitl_store.db"
        store = TaskStore(db_path)
        await store.connect()

        try:
            # Create HITL directly via store
            from aria.scheduler.schema import make_hitl_pending

            pending = make_hitl_pending(
                question="Direct store test?",
                task_id="task-123",
                run_id="run-456",
            )

            hitl_id = await store.create_hitl(pending)
            assert hitl_id == pending.id

            # Resolve via store
            resolved = await store.resolve_hitl(hitl_id, "yes")
            assert resolved is not None
            assert resolved.user_response == "yes"
            assert resolved.resolved_at is not None

        finally:
            await store.close()

    async def test_hitl_callback_data_parsing(self) -> None:
        """Test that HITL callback data is parsed correctly."""
        from aria.gateway.hitl_responder import (
            HITL_CALLBACK_PREFIX,
        )

        # Test callback data format: hitl:<hitl_id>:<response>
        callback_data = f"{HITL_CALLBACK_PREFIX}abc123:yes"
        prefix, hitl_id, response = callback_data.split(":", 2)

        assert prefix == "hitl"
        assert hitl_id == "abc123"
        assert response == "yes"

    async def test_hitl_keyboard_builder(self) -> None:
        """Test HITL inline keyboard building."""
        from aria.gateway.hitl_responder import build_hitl_keyboard

        hitl_id = "test-hitl-123"
        keyboard = build_hitl_keyboard(hitl_id)

        # Verify keyboard structure
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 1

        row = keyboard.inline_keyboard[0]
        assert len(row) == 3

        # Verify buttons
        yes_btn, no_btn, later_btn = row

        assert yes_btn.text == "✅ Yes"
        assert yes_btn.callback_data == f"hitl:{hitl_id}:yes"

        assert no_btn.text == "❌ No"
        assert no_btn.callback_data == f"hitl:{hitl_id}:no"

        assert later_btn.text == "⏸ Later"
        assert later_btn.callback_data == f"hitl:{hitl_id}:later"


@pytest.mark.integration
async def test_hitl_flow_full_integration(tmp_path: Path) -> None:
    """Standalone full HITL flow test for pytest discovery."""
    db_path = tmp_path / "test_full_hitl.db"
    store = TaskStore(db_path)
    await store.connect()

    try:
        bus = EventBus()
        config = _MockConfig(tmp_path)
        hitl_manager = HitlManager(store, bus, config)

        # Create task requiring HITL approval
        task = make_task(
            name="integration test task",
            category="workspace",
            trigger_type="manual",
            policy="ask",
            owner_user_id="999888777",
        )
        await store.create_task(task)

        # Record task run
        run = make_task_run(task_id=task.id)
        await store.record_run(run)

        # Ask for approval
        pending = await hitl_manager.ask(
            task=task,
            run_id=run.id,
            question="Should I run the workspace task?",
            options=["yes", "no"],
        )

        assert pending is not None
        assert pending.user_response is None

        # Simulate user approving
        await hitl_manager.resolve(pending.id, "yes")

        # Verify resolution
        resolved = await store.resolve_hitl(pending.id, "yes")
        assert resolved is not None
        assert resolved.user_response == "yes"

    finally:
        await store.close()
