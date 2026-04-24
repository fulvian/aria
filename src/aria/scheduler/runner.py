# Scheduler Runner — Task execution engine
#
# Per blueprint §6 and memory gap remediation plan Task 4.
#
# Features:
# - Task execution with budget and policy gates
# - HITL integration for destructive actions
# - Memory maintenance task handler (category="memory")
# - Run result tracking
#
# Usage:
#   from aria.scheduler.runner import TaskRunner, RunResult
#
#   runner = TaskRunner(store=store, budget=budget, policy=policy, hitl=hitl, bus=bus)
#   result = await runner.execute_task(task_id)

from __future__ import annotations

import logging
import time
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from aria.scheduler.store import HitlRequest

if TYPE_CHECKING:
    from aria.config import ARIAConfig
    from aria.scheduler.store import Task, TaskStore

logger = logging.getLogger(__name__)


class RunResult:
    """Result of a task execution."""

    def __init__(
        self,
        *,
        run_id: str,
        outcome: Literal["success", "failed", "skipped", "hitl_required"],
        result_summary: str,
        error: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.outcome = outcome
        self.result_summary = result_summary
        self.error = error


class TaskRunner:
    """Task execution runner with budget/policy gates and HITL support."""

    def __init__(
        self,
        store: TaskStore,
        budget: BudgetGate | None,
        policy: PolicyGate | None,
        hitl: HitlManager | None,
        bus: EventBus | None,
        config: ARIAConfig,
    ) -> None:
        self._store = store
        self._budget = budget
        self._policy = policy
        self._hitl = hitl
        self._bus = bus
        self._config = config
        self._worker_id = str(_uuid.uuid4())

    async def execute_task(self, task_id: str) -> RunResult:
        """Execute a task by ID.

        Args:
            task_id: The task ID to execute

        Returns:
            RunResult with outcome
        """
        task = await self._store.get_task(task_id)
        if not task:
            return RunResult(
                run_id=str(_uuid.uuid4()),
                outcome="failed",
                result_summary=f"Task {task_id} not found",
            )
        return await self._exec_task(task)

    async def _exec_task(self, task: Task) -> RunResult:
        """Execute a task with budget/policy gates."""
        run_id = str(_uuid.uuid4())
        started_at = int(time.time() * 1000)

        # Budget gate
        if self._budget and not self._budget.can_run(task.category, task.payload):
            await self._store.record_run(
                run_id,
                task.id,
                started_at,
                int(time.time() * 1000),
                outcome="skipped",
                result_summary="Budget gate denied",
            )
            return RunResult(
                run_id=run_id,
                outcome="skipped",
                result_summary=f"Task {task.name} skipped: budget exceeded",
            )

        # Policy gate - check HITL requirement
        if self._policy and task.policy == "ask":
            hitl_req = await self._hitl.enqueue(task) if self._hitl else None
            if hitl_req:
                await self._store.record_run(
                    run_id,
                    task.id,
                    started_at,
                    int(time.time() * 1000),
                    outcome="hitl_required",
                    result_summary=f"HITL enqueued: {hitl_req.id}",
                )
                return RunResult(
                    run_id=run_id,
                    outcome="hitl_required",
                    result_summary=f"Task {task.name} requires HITL approval",
                )

        # Execute based on category
        try:
            if task.category == "memory":
                result = await self._exec_memory_task(task)
            elif task.category == "web_search":
                result = await self._exec_web_search_task(task)
            elif task.category == "workspace":
                result = await self._exec_workspace_task(task)
            else:
                result = await self._exec_default_task(task)

            # Record success
            await self._store.record_run(
                run_id,
                task.id,
                started_at,
                int(time.time() * 1000),
                outcome=result.outcome,
                result_summary=result.result_summary,
                error=result.error,
            )

            # Update task next_run_at for cron tasks
            if task.trigger_type == "cron" and result.outcome == "success" and task.schedule_cron:
                from croniter import croniter

                if task.timezone and task.timezone != "UTC":
                    import zoneinfo

                    tz: datetime.tzinfo = zoneinfo.ZoneInfo(task.timezone)
                else:

                    tz: datetime.tzinfo = UTC
                cron = croniter(task.schedule_cron, datetime.now(tz))
                task.next_run_at = int(cron.get_next(datetime).timestamp() * 1000)
                await self._store.update_task(task)

            return result

        except Exception as exc:
            logger.error("Task %s failed: %s", task.id, exc)
            await self._store.record_run(
                run_id,
                task.id,
                started_at,
                int(time.time() * 1000),
                outcome="failed",
                result_summary=str(exc),
                error=str(exc),
            )
            return RunResult(
                run_id=run_id,
                outcome="failed",
                result_summary=f"Task {task.name} failed: {exc}",
                error=str(exc),
            )

    async def _exec_memory_task(self, task: Task) -> RunResult:
        """Execute a memory maintenance task.

        Supported actions (from task.payload["action"]):
        - distill_range: run CLM distillation on last N hours of T0 entries
        - wal_checkpoint: checkpoint episodic.db WAL
        """
        action = task.payload.get("action", "distill_range")
        run_id = str(_uuid.uuid4())

        try:
            from aria.config import get_config
            from aria.memory.episodic import create_episodic_store

            config = get_config()
            store = await create_episodic_store(config)

            if action == "wal_checkpoint":
                await store.vacuum_wal()
                await store.close()
                logger.info(
                    "Memory WAL checkpoint completed via scheduler task %s",
                    task.id,
                )
                return RunResult(
                    run_id=run_id,
                    outcome="success",
                    result_summary="episodic.db WAL checkpointed",
                )

            # distill_range
            from aria.memory.clm import CLM
            from aria.memory.semantic import SemanticStore

            semantic = SemanticStore(store._db_path, config)
            conn = store._conn
            if conn is None:
                await store.close()
                return RunResult(
                    run_id=run_id,
                    outcome="failed",
                    result_summary="EpisodicStore conn is None",
                )
            await semantic.connect(conn)
            clm = CLM(store, semantic)

            hours = int(task.payload.get("hours", 6))
            until = datetime.now(UTC)
            since = until - timedelta(hours=hours)
            chunks = await clm.distill_range(since, until)
            await store.close()

            logger.info(
                "Memory distill_range completed: task=%s hours=%d chunks=%d",
                task.id,
                hours,
                len(chunks),
            )
            return RunResult(
                run_id=run_id,
                outcome="success",
                result_summary=f"Distilled {len(chunks)} semantic chunks from last {hours}h",
            )

        except Exception as exc:
            logger.error("Memory task %s failed: %s", task.id, exc)
            return RunResult(
                run_id=run_id,
                outcome="failed",
                result_summary=str(exc),
                error=str(exc),
            )

    async def _exec_web_search_task(self, task: Task) -> RunResult:
        """Execute a web search task (stub for future implementation)."""
        return RunResult(
            run_id=str(_uuid.uuid4()),
            outcome="success",
            result_summary=f"Web search task {task.name} executed (stub)",
        )

    async def _exec_workspace_task(self, task: Task) -> RunResult:
        """Execute a workspace task (stub for future implementation)."""
        return RunResult(
            run_id=str(_uuid.uuid4()),
            outcome="success",
            result_summary=f"Workspace task {task.name} executed (stub)",
        )

    async def _exec_default_task(self, task: Task) -> RunResult:
        """Execute a generic task (stub for future implementation)."""
        return RunResult(
            run_id=str(_uuid.uuid4()),
            outcome="success",
            result_summary=f"Task {task.name} executed (default handler)",
        )


class BudgetGate:
    """Budget gate for task execution."""

    def __init__(
        self,
        *,
        hourly_limit: int = 100,
        daily_limit: int = 1000,
    ) -> None:
        self._hourly_limit = hourly_limit
        self._daily_limit = daily_limit
        self._hourly_count: dict[str, int] = {}
        self._daily_count: dict[str, int] = {}

    def can_run(self, category: str, payload: dict) -> bool:
        """Check if task can run within budget."""
        return True  # Stub - always allow


class PolicyGate:
    """Policy gate for task execution with HITL."""

    def requires_approval(self, task: Task) -> bool:
        """Check if task requires HITL approval."""
        return task.policy == "ask"


class HitlManager:
    """HITL manager for human-in-the-loop approval."""

    def __init__(self, store: TaskStore, bus: EventBus, config: ARIAConfig) -> None:
        self._store = store
        self._bus = bus
        self._config = config

    async def enqueue(self, task: Task) -> HitlRequest | None:
        """Enqueue a task for HITL approval."""
        req = HitlRequest(
            id=str(_uuid.uuid4()),
            target_id=task.id,
            action="approve_task",
            reason=f"Task {task.name} requires human approval",
            trace_id=None,
            channel="scheduler",
        )
        return await self._store.create_hitl_request(req)


class EventBus:
    """Simple event bus for publishing events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list] = {}

    def subscribe(self, event: str, handler) -> None:
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(handler)

    async def publish(self, event: str, payload: dict) -> None:
        if event in self._subscribers:
            for handler in self._subscribers[event]:
                await handler(payload)
