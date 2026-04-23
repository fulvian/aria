"""Task runner for the scheduler daemon.

Manages the main scheduling loop: acquiring due tasks, evaluating policies,
checking budgets, executing tasks (stub), and reporting results.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from .schema import TaskRun

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config import AriaConfig
    from .budget_gate import BudgetGate
    from .hitl import HitlManager
    from .policy_gate import PolicyGate
    from .store import Task, TaskStore
    from .triggers import EventBus


WorkspaceExecutor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class RunResult:
    """Result of a task execution."""

    run_id: str
    outcome: Literal[
        "success",
        "failed",
        "blocked_budget",
        "blocked_policy",
        "timeout",
        "not_implemented",
    ]
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
        workspace_executor: WorkspaceExecutor | None = None,
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
        self._workspace_executor = workspace_executor or self._execute_workspace_via_kilocode

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

        # Execute the task
        result = await self._exec_task(task)

        # Report the run
        await self._report_run(
            task,
            outcome=result.outcome,
            result_summary=result.result_summary,
            tokens_used=result.tokens_used,
            cost_eur=result.cost_eur,
        )

        # Release lease
        await self._store.release_lease(task.id, self._worker_id)

    async def _exec_task(self, task: Task) -> RunResult:
        """Execute a task based on category.

        Task execution:
        - category=system → success stub (placeholder for system task plugin)
        - category=workspace → execute via profiled workspace sub-agent
        - others → not_implemented

        Args:
            task: The task to execute.

        Returns:
            RunResult with outcome and metadata.
        """
        if task.category == "system":
            outcome: Literal[
                "success",
                "failed",
                "blocked_budget",
                "blocked_policy",
                "timeout",
                "not_implemented",
            ] = "success"
            summary = "System task completed successfully (stub)"
            logger.info(
                "Executed system task %s → outcome=%s",
                task.id,
                outcome,
            )
            return RunResult(
                run_id=str(uuid.uuid4()),
                outcome=outcome,
                result_summary=summary,
            )

        if task.category == "workspace":
            return await self._exec_workspace_task(task)

        # Unknown category
        outcome = "not_implemented"
        summary = f"Task category '{task.category}' not implemented"
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

    async def _exec_workspace_task(self, task: Task) -> RunResult:
        """Execute a workspace category task.

        Workspace tasks carry payload with:
        - sub_agent: target agent (e.g., "workspace-agent")
        - skill: skill to invoke (e.g., "triage-email", "gmail-composer-pro")
        - trace_prefix: optional prefix for logging

        Execution flow:
        1. Validate payload has required fields
        2. Map skill to workspace profile (read vs write)
        3. Enforce HITL policy for destructive operations
        4. Execute skill via configured workspace executor
        5. Emit structured telemetry
        6. Return result

        Write skills (gmail-composer-pro, docs-editor-pro, sheets-editor-pro,
        slides-editor-pro) are allowed without HITL by default. HITL is only
        required for destructive/irreversible operations when write intent is
        not explicit in the originating user request.

        Args:
            task: The workspace task to execute.

        Returns:
            RunResult with outcome and metadata.
        """
        payload = task.payload or {}
        requested_sub_agent = payload.get("sub_agent", "workspace-agent")
        skill = payload.get("skill", "")
        trace_prefix = payload.get("trace_prefix", task.name)

        # Validate required payload
        if not skill:
            logger.warning(
                "Workspace task %s missing skill in payload",
                task.id,
            )
            return RunResult(
                run_id=str(uuid.uuid4()),
                outcome="failed",
                result_summary="Missing skill in task payload",
            )

        # Map skill to execution metadata
        skill_metadata = self._get_workspace_skill_metadata(skill)
        expected_sub_agent = self._select_workspace_profile(skill)
        sub_agent = expected_sub_agent or requested_sub_agent

        # Enforce HITL only for destructive workspace operations.
        explicit_user_write = self._is_explicit_user_write_authorized(payload)
        destructive_operation = self._is_destructive_workspace_operation(skill, payload)
        if (
            destructive_operation
            and not skill_metadata["is_read"]
            and task.policy != "ask"
            and not explicit_user_write
        ):
            summary = (
                f"Destructive workspace operation for skill '{skill}' requires policy=ask or "
                f"explicit user write intent; "
                f"task policy is '{task.policy}'"
            )
            self._log_workspace_telemetry(
                trace_id=trace_prefix,
                profile=sub_agent,
                skill=skill,
                tool="workspace_skill_execution",
                latency_ms=0,
                retries=0,
                outcome="failed",
                error_type="policy",
                error_detail=summary,
            )
            return RunResult(
                run_id=str(uuid.uuid4()),
                outcome="blocked_policy",
                result_summary=summary,
            )

        if expected_sub_agent and requested_sub_agent != expected_sub_agent:
            logger.info(
                "[%s] Overriding sub_agent '%s' -> '%s' for skill '%s'",
                trace_prefix,
                requested_sub_agent,
                expected_sub_agent,
                skill,
            )

        logger.info(
            "[%s] Executing workspace task %s: agent=%s, skill=%s (read=%s, hitl=%s)",
            trace_prefix,
            task.id,
            sub_agent,
            skill,
            skill_metadata["is_read"],
            skill_metadata["requires_hitl"],
        )

        execution_request = {
            "task_id": task.id,
            "task_name": task.name,
            "skill": skill,
            "sub_agent": sub_agent,
            "payload": payload,
            "trace_id": trace_prefix,
        }

        start = time.perf_counter()
        retries = int(payload.get("retry_count", 0) or 0)
        try:
            exec_result = await self._workspace_executor(execution_request)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            error_detail = str(exc)
            error_type = self._classify_workspace_error(error_detail)
            self._log_workspace_telemetry(
                trace_id=trace_prefix,
                profile=sub_agent,
                skill=skill,
                tool="workspace_skill_execution",
                latency_ms=latency_ms,
                retries=retries,
                outcome="error",
                error_type=error_type,
                error_detail=error_detail,
            )
            return RunResult(
                run_id=str(uuid.uuid4()),
                outcome="failed",
                result_summary=f"Workspace execution failed: {error_detail}",
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        success = bool(exec_result.get("success", False))
        summary = str(
            exec_result.get("summary")
            or f"Workspace task executed: skill={skill}, agent={sub_agent}"
        )
        tokens_used = exec_result.get("tokens_used")
        cost_eur = exec_result.get("cost_eur")
        exec_error_detail = str(exec_result.get("error_detail", "")) if not success else None
        exec_error_type = str(
            exec_result.get("error_type") or self._classify_workspace_error(exec_error_detail or "")
        )

        self._log_workspace_telemetry(
            trace_id=trace_prefix,
            profile=sub_agent,
            skill=skill,
            tool="workspace_skill_execution",
            latency_ms=latency_ms,
            retries=retries,
            outcome="success" if success else "failed",
            error_type=None if success else exec_error_type,
            error_detail=None if success else exec_error_detail,
        )

        outcome: Literal[
            "success", "failed", "blocked_budget", "blocked_policy", "timeout", "not_implemented"
        ] = "success" if success else "failed"

        logger.info(
            "[%s] Completed workspace task %s → outcome=%s",
            trace_prefix,
            task.id,
            outcome,
        )

        return RunResult(
            run_id=str(uuid.uuid4()),
            outcome=outcome,
            result_summary=summary,
            tokens_used=tokens_used if isinstance(tokens_used, int) else None,
            cost_eur=cost_eur if isinstance(cost_eur, (int, float)) else None,
        )

    async def _execute_workspace_via_kilocode(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute workspace task by invoking KiloCode sub-agent.

        The scheduler delegates workspace execution to the configured sub-agent
        via `kilo run --agent <sub_agent> --input <prompt>`.
        """
        kilo_executable = shutil.which("kilo")
        if kilo_executable is None:
            raise RuntimeError("kilo executable not found in PATH")

        input_prompt = json.dumps(
            {
                "task_id": request.get("task_id"),
                "task_name": request.get("task_name"),
                "skill": request.get("skill"),
                "payload": request.get("payload", {}),
                "trace_id": request.get("trace_id"),
            },
            ensure_ascii=True,
        )

        env = os.environ.copy()
        env.update(
            {
                "KILOCODE_CONFIG_DIR": str(self._config.paths.kilocode_config),
                "KILOCODE_STATE_DIR": str(self._config.paths.kilocode_state),
                "ARIA_HOME": str(self._config.paths.home),
                "ARIA_RUNTIME": str(self._config.paths.runtime),
            }
        )

        cmd = [
            kilo_executable,
            "run",
            "--session",
            str(uuid.uuid4()),
            "--agent",
            str(request.get("sub_agent", "workspace-agent")),
            "--input",
            input_prompt,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            cwd=str(self._config.paths.home),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            close_fds=True,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            return {
                "success": False,
                "summary": "Workspace sub-agent execution failed",
                "error_type": self._classify_workspace_error(stderr_text),
                "error_detail": stderr_text or stdout_text,
            }

        parsed_json: dict[str, Any] | None = None
        for line in reversed(stdout_text.splitlines()):
            cleaned = line.strip()
            if not cleaned:
                continue
            try:
                maybe_obj = json.loads(cleaned)
            except json.JSONDecodeError:
                continue
            if isinstance(maybe_obj, dict):
                parsed_json = maybe_obj
                break

        if isinstance(parsed_json, dict):
            # MCP Python SDK semantics: tool responses can use isError=true
            if parsed_json.get("isError") is True:
                error_detail = str(parsed_json.get("content") or stdout_text)
                return {
                    "success": False,
                    "summary": "Workspace tool returned error",
                    "error_type": self._classify_workspace_error(error_detail),
                    "error_detail": error_detail,
                }

            return {
                "success": True,
                "summary": str(parsed_json.get("result") or "Workspace task executed"),
                "tokens_used": parsed_json.get("tokens_used"),
                "cost_eur": parsed_json.get("cost_eur"),
            }

        if stderr_text:
            return {
                "success": False,
                "summary": "Workspace sub-agent execution produced stderr",
                "error_type": self._classify_workspace_error(stderr_text),
                "error_detail": stderr_text,
            }

        return {
            "success": True,
            "summary": stdout_text[:500] if stdout_text else "Workspace task executed",
        }

    def _select_workspace_profile(self, skill: str) -> str | None:
        """Map workspace skill to deterministic profile agent name."""
        profile_map = {
            # Read skills
            "triage-email": "workspace-mail-read",
            "gmail-thread-intelligence": "workspace-mail-read",
            "calendar-orchestration": "workspace-calendar-read",
            "docs-structure-reader": "workspace-docs-read",
            "sheets-analytics-reader": "workspace-sheets-read",
            "slides-content-auditor": "workspace-slides-read",
            # Write skills
            "doc-draft": "workspace-docs-write",
            "gmail-composer-pro": "workspace-mail-write",
            "docs-editor-pro": "workspace-docs-write",
            "sheets-editor-pro": "workspace-sheets-write",
            "slides-editor-pro": "workspace-slides-write",
        }
        return profile_map.get(skill)

    def _classify_workspace_error(self, detail: str) -> str:
        """Classify workspace error type for telemetry and retries."""
        normalized = detail.lower()
        if "401" in normalized or "403" in normalized or "unauthorized" in normalized:
            return "auth"
        if "429" in normalized or "quota" in normalized or "rate" in normalized:
            return "quota"
        if "timeout" in normalized or "connection" in normalized or "network" in normalized:
            return "network"
        if "policy" in normalized or "hitl" in normalized:
            return "policy"
        return "tool_error"

    def _log_workspace_telemetry(
        self,
        *,
        trace_id: str,
        profile: str,
        skill: str,
        tool: str,
        latency_ms: int,
        retries: int,
        outcome: Literal["success", "failed", "error"],
        error_type: str | None,
        error_detail: str | None,
    ) -> None:
        """Emit structured telemetry event for workspace execution."""
        logger.info(
            "workspace_tool_invocation",
            extra={
                "event": "workspace_tool_invocation",
                "trace_id": trace_id,
                "timestamp": int(time.time() * 1000),
                "profile": profile,
                "skill": skill,
                "tool": tool,
                "latency_ms": latency_ms,
                "retries": retries,
                "outcome": outcome,
                "error_type": error_type,
                "error_detail": error_detail,
            },
        )

    def _get_workspace_skill_metadata(self, skill: str) -> dict:
        """Get metadata for a workspace skill.

        Args:
            skill: Skill name (e.g., "triage-email", "gmail-composer-pro")

        Returns:
            Dict with keys: is_read (bool), requires_hitl (bool), description (str)
        """
        # Read skills (no write operations, no HITL required for execution)
        read_skills = {
            "triage-email": {
                "is_read": True,
                "requires_hitl": False,
                "description": "Email inbox triage",
            },
            "gmail-thread-intelligence": {
                "is_read": True,
                "requires_hitl": False,
                "description": "Gmail thread analysis",
            },
            "docs-structure-reader": {
                "is_read": True,
                "requires_hitl": False,
                "description": "Docs structure extraction",
            },
            "sheets-analytics-reader": {
                "is_read": True,
                "requires_hitl": False,
                "description": "Sheets analytics",
            },
            "slides-content-auditor": {
                "is_read": True,
                "requires_hitl": False,
                "description": "Slides content audit",
            },
            "calendar-orchestration": {
                "is_read": True,
                "requires_hitl": False,
                "description": "Calendar management",
            },
            "doc-draft": {
                "is_read": False,
                "requires_hitl": False,
                "description": "Document drafting",
            },  # read-only skill
        }

        # Write skills (HITL only for destructive actions)
        write_skills = {
            "gmail-composer-pro": {
                "is_read": False,
                "requires_hitl": False,
                "description": "Gmail compose and send",
            },
            "docs-editor-pro": {
                "is_read": False,
                "requires_hitl": False,
                "description": "Docs editing",
            },
            "sheets-editor-pro": {
                "is_read": False,
                "requires_hitl": False,
                "description": "Sheets editing",
            },
            "slides-editor-pro": {
                "is_read": False,
                "requires_hitl": False,
                "description": "Slides editing",
            },
        }

        if skill in read_skills:
            return read_skills[skill]
        if skill in write_skills:
            return write_skills[skill]

        # Unknown skill - assume write, require HITL only if destructive flags are present.
        return {"is_read": False, "requires_hitl": True, "description": f"Unknown skill: {skill}"}

    def _is_destructive_workspace_operation(self, skill: str, payload: dict[str, Any]) -> bool:
        """Return True when workspace operation is destructive/irreversible.

        The policy is intentionally pragmatic:
        - read and non-destructive writes are allowed without HITL,
        - destructive operations require HITL unless explicitly authorized.
        """
        if bool(payload.get("destructive")):
            return True

        destructive_tokens = {
            "delete",
            "remove",
            "erase",
            "destroy",
            "purge",
            "revoke",
            "overwrite",
            "truncate",
        }

        operation_mode = str(payload.get("operation_mode", "")).strip().lower()
        if operation_mode in destructive_tokens:
            return True

        write_operation = str(payload.get("write_operation", "")).strip().lower()
        if any(token in write_operation for token in destructive_tokens):
            return True

        skill_lower = skill.strip().lower()
        return any(token in skill_lower for token in destructive_tokens)

    def _is_explicit_user_write_authorized(self, payload: dict[str, Any]) -> bool:
        """Return True when user has explicitly requested the write action."""
        if bool(payload.get("user_explicit_request")):
            return True
        if bool(payload.get("explicit_write_intent")):
            return True

        source = str(payload.get("request_origin", "")).strip().lower()
        return source in {"interactive_user", "user_prompt"} and bool(
            payload.get("write_requested")
        )

    async def _report_run(
        self,
        task: Task,
        outcome: Literal[
            "success",
            "failed",
            "blocked_budget",
            "blocked_policy",
            "timeout",
            "not_implemented",
        ],
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
