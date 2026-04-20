# ARIA Scheduler Schema - Pydantic Models
#
# Per blueprint §6.1 and sprint plan W1.2.A.
#
# Models:
# - TaskStatus, TaskCategory, TriggerType, TaskPolicy (Literals)
# - Task: scheduled task with lease columns
# - TaskRun: task execution record
# - DlqEntry: dead letter queue entry
# - HitlPending: human-in-the-loop pending request
#
# Usage:
#   from aria.scheduler.schema import Task, TaskRun, DlqEntry, HitlPending

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

# === Task Literals ===

TaskStatus = Literal["active", "paused", "dlq", "completed", "failed"]
TaskCategory = Literal["search", "workspace", "memory", "custom", "system"]
TriggerType = Literal["cron", "event", "webhook", "oneshot", "manual"]
TaskPolicy = Literal["allow", "ask", "deny"]
RunOutcome = Literal[
    "success", "failed", "blocked_budget", "blocked_policy", "timeout", "not_implemented"
]


# === Task Model ===


class Task(BaseModel):
    """Scheduled task with lease-based concurrency control.

    Per ADR-0005: lease_owner/lease_expires_at enable safe concurrent
    scheduling across multiple scheduler instances.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    category: TaskCategory
    trigger_type: TriggerType
    trigger_config: dict = Field(default_factory=dict)
    schedule_cron: str | None = None
    timezone: str = "Europe/Rome"
    next_run_at: int | None = None  # epoch ms
    status: TaskStatus = "active"
    policy: TaskPolicy = "allow"
    budget_tokens: int | None = None
    budget_cost_eur: float | None = None
    max_retries: int = 3
    retry_count: int = 0
    last_error: str | None = None
    owner_user_id: str | None = None
    payload: dict = Field(default_factory=dict)
    # Lease columns (ADR-0005)
    lease_owner: str | None = None
    lease_expires_at: int | None = None  # epoch ms
    created_at: int
    updated_at: int

    model_config = {
        "use_enum_values": False,
    }


# === TaskRun Model ===


class TaskRun(BaseModel):
    """Task execution record."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    started_at: int  # epoch ms
    finished_at: int | None = None
    outcome: RunOutcome
    tokens_used: int | None = None
    cost_eur: float | None = None
    result_summary: str | None = None
    logs_path: str | None = None

    model_config = {
        "use_enum_values": False,
    }


# === DLQ Entry ===


class DlqEntry(BaseModel):
    """Dead letter queue entry for failed tasks."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    last_run_id: str | None = None
    moved_at: int  # epoch ms
    reason: str
    payload_snapshot: str  # JSON

    model_config = {
        "use_enum_values": False,
    }


# === HITL Pending ===


class HitlPending(BaseModel):
    """Human-in-the-loop pending approval."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str | None = None
    run_id: str | None = None
    created_at: int  # epoch ms
    expires_at: int  # epoch ms
    question: str
    options_json: str | None = None  # JSON array of options
    channel: Literal["telegram", "cli"] = "telegram"
    user_response: str | None = None
    resolved_at: int | None = None

    model_config = {
        "use_enum_values": False,
    }


# === Convenience Factories ===


def make_task(
    name: str,
    category: TaskCategory,
    trigger_type: TriggerType,
    payload: dict | None = None,
    schedule_cron: str | None = None,
    policy: TaskPolicy = "allow",
    timezone: str = "Europe/Rome",
    budget_tokens: int | None = None,
    budget_cost_eur: float | None = None,
    max_retries: int = 3,
    owner_user_id: str | None = None,
    trigger_config: dict | None = None,
) -> Task:
    """Create a new Task with auto-generated timestamps.

    Args:
        name: Task name
        category: Task category
        trigger_type: Type of trigger
        payload: Task payload dict
        schedule_cron: Cron expression (for cron trigger)
        policy: Policy (allow/ask/deny)
        timezone: Timezone for scheduling
        budget_tokens: Max tokens per run
        budget_cost_eur: Max cost per run in EUR
        max_retries: Maximum retry attempts
        owner_user_id: Telegram user ID
        trigger_config: Additional trigger configuration

    Returns:
        Populated Task instance
    """
    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    return Task(
        name=name,
        category=category,
        trigger_type=trigger_type,
        payload=payload or {},
        schedule_cron=schedule_cron,
        policy=policy,
        timezone=timezone,
        budget_tokens=budget_tokens,
        budget_cost_eur=budget_cost_eur,
        max_retries=max_retries,
        owner_user_id=owner_user_id,
        trigger_config=trigger_config or {},
        created_at=now,
        updated_at=now,
    )


def make_task_run(task_id: str, started_at: int | None = None) -> TaskRun:
    """Create a new TaskRun.

    Args:
        task_id: Associated task ID
        started_at: Start time in epoch ms (default: now)

    Returns:
        Populated TaskRun instance
    """
    return TaskRun(
        task_id=task_id,
        started_at=started_at or int(datetime.now(tz=UTC).timestamp() * 1000),
        outcome="success",  # default, updated on completion
    )


def make_hitl_pending(
    question: str,
    task_id: str | None = None,
    run_id: str | None = None,
    ttl_seconds: int = 900,
    channel: Literal["telegram", "cli"] = "telegram",
    options: list[str] | None = None,
) -> HitlPending:
    """Create a new HITL pending request.

    Args:
        question: Human-readable question
        task_id: Associated task ID
        run_id: Associated task run ID
        ttl_seconds: Time-to-live in seconds
        channel: Notification channel
        options: Optional multiple choice options

    Returns:
        Populated HitlPending instance
    """
    import json

    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    return HitlPending(
        task_id=task_id,
        run_id=run_id,
        created_at=now,
        expires_at=now + (ttl_seconds * 1000),
        question=question,
        options_json=json.dumps(options) if options else None,
        channel=channel,
    )
