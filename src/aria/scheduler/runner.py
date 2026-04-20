"""Task runner for the scheduler daemon.

Manages the main scheduling loop: acquiring due tasks, evaluating policies,
checking budgets, executing tasks (stub), and reporting results.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .schema import TaskRun

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config import AriaConfig
    from .budget_gate import BudgetGate
    from .hitl import HitlManager
    from .policy_gate import PolicyGate
    from .store import Task, TaskStore
    from .triggers import EventBus


@dataclass
class RunResult:
    """Result of a task execution."""

    run_id: str
    outcome: str
    tokens_used: int | None = None
    cost_eur: float | None = None
    result_summary: str | None = None


class TaskRunner:
    """Main task execution loop for the scheduler.

    Acquires due tasks, evaluates policy/budget gates, handles HITL flows,
    executes tasks (stub in Sprint 1.2), and reports results.

    Args:
        store: TaskStore for task persistence.
        budget: BudgetGate for token/cost budgeting.
        policy: PolicyGate for policy evaluation.
        hitl: HitlManager for human-in-the-loop requests.
        bus: EventBus for internal event publishing.
        config: AriaConfig for runtime configuration.
    """

    def __init__(
        self,
        store: TaskStore,
        budget: BudgetGate,
        policy: PolicyGate,
        hitl: HitlManager,
        bus: EventBus,
        config: AriaConfig,
    ) -> None:
        self._store = store
        self._budget = budget
        self._policy = policy
        self._hitl = hitl
        self._bus = bus
        self._config = config
        self._worker_id = f"scheduler-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._running = False
        self._loop_interval_s = 5

    async def run_forever(self) -> None:
        """Run the main scheduling loop indefinitely.

        Every loop iteration:
        1. Acquires due tasks (lease_ttl=300, limit=5)
        2. Evaluates policy gate for each task
        3. Checks budget gate pre-check
        4. For ask policy: creates HITL pending and waits for response
        5. Executes the task (stub in Sprint 1.2)
        6. Reports the run result
        """
        self._running = True
        logger.info("TaskRunner started with worker_id=%s", self._worker_id)

        try:
            while self._running:
                try:
                    await self._run_cycle()
                except Exception as e:
                    logger.exception("TaskRunner cycle failed: %s", e)
                await asyncio.sleep(self._loop_interval_s)
        except asyncio.CancelledError:
            pass

        logger.info("TaskRunner stopped")

    def stop(self) -> None:
        """Signal the runner to stop after the current cycle."""
        self._running = False

    async def _run_cycle(self) -> None:
        """Execute one scheduling cycle."""
        tasks = await self._store.acquire_due(
            worker_id=self._worker_id,
            lease_ttl_seconds=300,
            limit=5,
        )

        if not tasks:
            return

        logger.debug("Acquired %d due tasks", len(tasks))

        for task in tasks:
            try:
                await self._process_task(task)
            except Exception as e:
                logger.exception("Failed to process task %s: %s", task.id, e)

    async def _process_task(self, task: Task) -> None:
        """Process a single task through policy, budget, HITL, and execution.

        Args:
            task: The task to process.
        """
        from .policy_gate import PolicyDecision

        # Evaluate policy gate
        policy_decision = self._policy.evaluate(task)

        if policy_decision == PolicyDecision.DENY:
            logger.info("Task %s denied by policy", task.id)
            await self._report_run(
                task,
                outcome="blocked_policy",
                result_summary="Task denied by policy gate",
            )
            await self._store.release_lease(task.id, self._worker_id)
            return

        if policy_decision == PolicyDecision.DEFERRED:
            logger.info("Task %s deferred to quiet hours end", task.id)
            deferred_at_ms = int(self._policy.get_deferred_time(task).timestamp() * 1000)
            await self._store.update_task(
                task.id,
                next_run_at=deferred_at_ms,
            )
            await self._store.release_lease(task.id, self._worker_id)
            return

        # Budget pre-check
        budget_decision = await self._budget.pre_check(task)
        if not budget_decision.allowed:
            logger.info("Task %s blocked by budget: %s", task.id, budget_decision.reason)
            await self._report_run(
                task,
                outcome="blocked_budget",
                result_summary=budget_decision.reason or "Budget limit exceeded",
            )
            await self._store.release_lease(task.id, self._worker_id)
            return

        # Handle ask policy (HITL)
        response: str | None = None
        if policy_decision == PolicyDecision.ASK:
            try:
                question = self._build_hitl_question(task)
                pending = await self._hitl.ask(
                    task=task,
                    run_id=str(uuid.uuid4()),
                    question=question,
                    options=["yes", "no", "later"],
                    channel="telegram",
                    ttl_seconds=900,
                )
                logger.info(
                    "HITL pending created for task %s, hitl_id=%s",
                    task.id,
                    pending.id,
                )
                response = await self._hitl.wait_for_response(pending.id, timeout_s=900)
                if response is None or response == "no":
                    logger.info(
                        "HITL response for task %s was '%s', aborting",
                        task.id,
                        response,
                    )
                    await self._report_run(
                        task,
                        outcome="blocked_policy",
                        result_summary="Human denied the task",
                    )
                    await self._store.release_lease(task.id, self._worker_id)
                    return
                if response == "later":
                    deferred_at_ms = int(self._policy.get_deferred_time(task).timestamp() * 1000)
                    await self._store.update_task(
                        task.id,
                        next_run_at=deferred_at_ms,
                    )
                    await self._store.release_lease(task.id, self._worker_id)
                    return
                # response == "yes" - continue execution
            except Exception as e:
                logger.error("HITL error for task %s: %s", task.id, e)
                await self._report_run(
                    task,
                    outcome="failed",
                    result_summary=f"HITL error: {e}",
                )
                await self._store.release_lease(task.id, self._worker_id)
                return

        # Execute the task (stub for Sprint 1.2)
        result = await self._exec_task(task)

        # Report the run
        await self._report_run(task, outcome=result.outcome, result_summary=result.result_summary)

        # Release lease
        await self._store.release_lease(task.id, self._worker_id)

    async def _exec_task(self, task: Task) -> RunResult:
        """Execute a task (stub implementation for Sprint 1.2).

        Sprint 1.2 stub:
        - category=system → outcome=success
        - all others → outcome=not_implemented

        Args:
            task: The task to execute.

        Returns:
            RunResult with outcome and metadata.
        """
        if task.category == "system":
            outcome = "success"
            summary = "System task completed successfully (stub)"
        else:
            outcome = "not_implemented"
            summary = f"Task category '{task.category}' not implemented in Sprint 1.2 (stub)"

        logger.info(
            "Executed task %s (category=%s) → outcome=%s",
            task.id,
            task.category,
            outcome,
        )

        return RunResult(
            run_id=str(uuid.uuid4()),
            outcome=outcome,
            result_summary=summary,
        )

    async def _report_run(
        self,
        task: Task,
        outcome: str,
        result_summary: str | None = None,
        tokens_used: int | None = None,
        cost_eur: float | None = None,
    ) -> None:
        """Record a task run result.

        Args:
            task: The task that was executed.
            outcome: The outcome string.
            result_summary: Human-readable summary.
            tokens_used: Token count if available.
            cost_eur: Cost in EUR if available.
        """
        now_ms = int(time.time() * 1000)

        run_id = str(uuid.uuid4())
        run = TaskRun(
            id=run_id,
            task_id=task.id,
            started_at=now_ms - 1000,  # Approximate
            finished_at=now_ms,
            outcome=outcome,
            tokens_used=tokens_used,
            cost_eur=cost_eur,
            result_summary=result_summary,
        )

        try:
            await self._store.record_run(run)
            logger.debug("Recorded run %s for task %s", run.id, task.id)
        except Exception as e:
            logger.error("Failed to record run for task %s: %s", task.id, e)

    def _build_hitl_question(self, task: Task) -> str:
        """Build the HITL approval question for a task.

        Args:
            task: The task to build a question for.

        Returns:
            The question string to ask the human.
        """
        return (
            f"Approve task '{task.name}'?\n"
            f"Category: {task.category}\n"
            f"Policy: {task.policy}\n"
            f"Retry: {task.retry_count}/{task.max_retries}"
        )

    def _get_quiet_hours_end_timestamp(self) -> int:
        """Get the timestamp when quiet hours end.

        Returns:
            Unix timestamp in seconds when quiet hours end.
        """
        from datetime import datetime
        from datetime import time as dt_time
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(self._config.operational.timezone)
        now = datetime.now(tz=tz)

        end_str = self._config.operational.quiet_hours_end or "07:00"
        hour, minute = map(int, end_str.split(":"))
        dt_time(hour=hour, minute=minute)

        # If we're past end time today, it's tomorrow
        end_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= end_today:
            from datetime import timedelta

            end_dt = end_today + timedelta(days=1)
        else:
            end_dt = end_today

        return int(end_dt.timestamp())
