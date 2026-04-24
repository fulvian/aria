# Scheduler Store — SQLite-backed task store with WAL
#
# Per blueprint §6 and memory gap remediation plan Task 4.
#
# Features:
# - WAL mode for concurrent reads/writes
# - Tasks table with cron, event, webhook, oneshot, manual triggers
# - HITL pending table for human approval gates
# - Lease system for distributed task execution
#
# Usage:
#   from aria.scheduler.store import TaskStore, Task
#
#   store = TaskStore(db_path)
#   await store.connect()
#   tasks = await store.list_tasks(status=["active"])

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Literal

import aiosqlite

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# === Task Model ===


class Task:
    """Scheduler task model."""

    def __init__(
        self,
        *,
        name: str,
        category: str = "default",
        trigger_type: str = "manual",
        trigger_config: dict | None = None,
        schedule_cron: str | None = None,
        timezone: str = "Europe/Rome",
        next_run_at: int | None = None,
        policy: str = "allow",
        budget_tokens: int | None = None,
        budget_cost_eur: float | None = None,
        max_retries: int = 3,
        retry_count: int = 0,
        last_error: str | None = None,
        owner_user_id: str | None = None,
        payload: dict | None = None,
        lease_owner: str | None = None,
        lease_expires_at: int | None = None,
        status: str = "active",
        created_at: int | None = None,
        updated_at: int | None = None,
        id: str | None = None,
    ) -> None:
        self.id = id or str(time.time_ns())
        self.name = name
        self.category = category
        self.trigger_type = trigger_type
        self.trigger_config = trigger_config or {}
        self.schedule_cron = schedule_cron
        self.timezone = timezone
        self.next_run_at = next_run_at or int(time.time() * 1000)
        self.policy = policy
        self.budget_tokens = budget_tokens
        self.budget_cost_eur = budget_cost_eur
        self.max_retries = max_retries
        self.retry_count = retry_count
        self.last_error = last_error
        self.owner_user_id = owner_user_id
        self.payload = payload or {}
        self.lease_owner = lease_owner
        self.lease_expires_at = lease_expires_at
        self.status = status
        self.created_at = created_at or int(time.time() * 1000)
        self.updated_at = updated_at or int(time.time() * 1000)

    def to_row(self) -> dict:
        """Convert to dict for DB insertion."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "trigger_type": self.trigger_type,
            "trigger_config": json.dumps(self.trigger_config)
            if isinstance(self.trigger_config, dict)
            else self.trigger_config,
            "schedule_cron": self.schedule_cron,
            "timezone": self.timezone,
            "next_run_at": self.next_run_at,
            "policy": self.policy,
            "budget_tokens": self.budget_tokens,
            "budget_cost_eur": self.budget_cost_eur,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "owner_user_id": self.owner_user_id,
            "payload": json.dumps(self.payload),
            "lease_owner": self.lease_owner,
            "lease_expires_at": self.lease_expires_at,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict) -> Task:
        """Create Task from database row."""
        trigger_config = row.get("trigger_config", "{}")
        if isinstance(trigger_config, str):
            trigger_config = json.loads(trigger_config) if trigger_config else {}
        payload = row.get("payload", "{}")
        if isinstance(payload, str):
            payload = json.loads(payload) if payload else {}
        return cls(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            trigger_type=row["trigger_type"],
            trigger_config=trigger_config,
            schedule_cron=row.get("schedule_cron"),
            timezone=row.get("timezone", "Europe/Rome"),
            next_run_at=row.get("next_run_at"),
            policy=row.get("policy", "allow"),
            budget_tokens=row.get("budget_tokens"),
            budget_cost_eur=row.get("budget_cost_eur"),
            max_retries=row.get("max_retries", 3),
            retry_count=row.get("retry_count", 0),
            last_error=row.get("last_error"),
            owner_user_id=row.get("owner_user_id"),
            payload=payload,
            lease_owner=row.get("lease_owner"),
            lease_expires_at=row.get("lease_expires_at"),
            status=row.get("status", "active"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class HitlRequest:
    """HITL pending request model — aligned with existing hitl_pending schema."""

    def __init__(
        self,
        *,
        id: str,
        task_id: str,
        run_id: str | None = None,
        question: str,
        options_json: str | None = None,
        channel: str = "scheduler",
        user_response: str | None = None,
        created_at: int | None = None,
        expires_at: int | None = None,
        resolved_at: int | None = None,
    ) -> None:
        self.id = id
        self.task_id = task_id
        self.run_id = run_id
        self.question = question
        self.options_json = options_json
        self.channel = channel
        self.user_response = user_response
        self.created_at = created_at or int(time.time() * 1000)
        self.expires_at = expires_at
        self.resolved_at = resolved_at

    def to_row(self) -> dict:
        """Convert to dict for DB insertion."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "question": self.question,
            "options_json": self.options_json,
            "channel": self.channel,
            "user_response": self.user_response,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "resolved_at": self.resolved_at,
        }


# === TaskStore ===


class TaskStore:
    """SQLite-backed task store with WAL mode."""

    PRAGMAS = [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA foreign_keys=ON",
        "PRAGMA busy_timeout=5000",
    ]

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'default',
        trigger_type TEXT NOT NULL DEFAULT 'manual',
        trigger_config TEXT NOT NULL DEFAULT '{}',
        schedule_cron TEXT,
        timezone TEXT NOT NULL DEFAULT 'Europe/Rome',
        next_run_at INTEGER,
        policy TEXT NOT NULL DEFAULT 'allow',
        budget_tokens INTEGER,
        budget_cost_eur REAL,
        max_retries INTEGER DEFAULT 3,
        retry_count INTEGER DEFAULT 0,
        last_error TEXT,
        owner_user_id TEXT,
        payload TEXT NOT NULL DEFAULT '{}',
        lease_owner TEXT,
        lease_expires_at INTEGER,
        status TEXT NOT NULL DEFAULT 'active',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS task_runs (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        started_at INTEGER NOT NULL,
        finished_at INTEGER,
        outcome TEXT NOT NULL,
        result_summary TEXT,
        tokens_used INTEGER,
        cost_eur REAL,
        logs_path TEXT,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS dlq (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        error TEXT NOT NULL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS hitl_pending (
        id TEXT PRIMARY KEY,
        target_id TEXT NOT NULL,
        action TEXT NOT NULL,
        reason TEXT NOT NULL,
        trace_id TEXT,
        channel TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at INTEGER NOT NULL,
        resolved_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at INTEGER NOT NULL
    );
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize task store.

        Args:
            db_path: Path to scheduler.db
        """
        self._db_path = db_path.resolve()
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database and create schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_conn = aiosqlite.connect(self._db_path, timeout=30.0)
        self._conn = await raw_conn.__aenter__()
        self._conn.row_factory = aiosqlite.Row
        for pragma in self.PRAGMAS:
            await self._conn.execute(pragma)
        await self._conn.executescript(self.SCHEMA)
        # Migrate task_runs: add tokens_used, cost_eur, logs_path if missing
        for col, col_type in [
            ("tokens_used", "INTEGER"),
            ("cost_eur", "REAL"),
            ("logs_path", "TEXT"),
        ]:
            try:
                await self._conn.execute(f"ALTER TABLE task_runs ADD COLUMN {col} {col_type}")
            except Exception:
                pass  # Column already exists
        await self._conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.__aexit__(None, None, None)
            self._conn = None

    async def _ensure_connected(self) -> aiosqlite.Connection:
        """Ensure connection is established."""
        if self._conn is None:
            raise RuntimeError("TaskStore not connected. Call connect() first.")
        return self._conn

    # === Task CRUD ===

    async def create_task(self, task: Task) -> Task:
        """Create a new task (idempotent - upsert by name)."""
        conn = await self._ensure_connected()
        row = task.to_row()
        await conn.execute(
            """
            INSERT OR REPLACE INTO tasks
            (id, name, category, trigger_type, trigger_config, schedule_cron, timezone, next_run_at, policy, budget_tokens, budget_cost_eur, max_retries, retry_count, last_error, owner_user_id, payload, lease_owner, lease_expires_at, status, created_at, updated_at)
            VALUES (:id, :name, :category, :trigger_type, :trigger_config, :schedule_cron, :timezone, :next_run_at, :policy, :budget_tokens, :budget_cost_eur, :max_retries, :retry_count, :last_error, :owner_user_id, :payload, :lease_owner, :lease_expires_at, :status, :created_at, :updated_at)
            """,
            row,
        )
        await conn.commit()
        return task

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        conn = await self._ensure_connected()
        cursor = await conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return Task.from_row(dict(row)) if row else None

    async def list_tasks(
        self,
        status: list[str] | None = None,
        category: str | None = None,
    ) -> list[Task]:
        """List tasks, optionally filtered by status and category."""
        conn = await self._ensure_connected()
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if status:
            placeholders = ",".join("?" * len(status))
            query += f" AND status IN ({placeholders})"
            params.extend(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [Task.from_row(dict(row)) for row in rows]

    async def update_task(self, task: Task) -> Task:
        """Update an existing task."""
        conn = await self._ensure_connected()
        task.updated_at = int(time.time() * 1000)
        row = task.to_row()
        await conn.execute(
            """
            UPDATE tasks SET
                name=:name, category=:category, trigger_type=:trigger_type,
                trigger_config=:trigger_config, schedule_cron=:schedule_cron, timezone=:timezone,
                next_run_at=:next_run_at, policy=:policy, budget_tokens=:budget_tokens,
                budget_cost_eur=:budget_cost_eur, max_retries=:max_retries, retry_count=:retry_count,
                last_error=:last_error, owner_user_id=:owner_user_id, payload=:payload,
                lease_owner=:lease_owner, lease_expires_at=:lease_expires_at,
                status=:status, updated_at=:updated_at
            WHERE id=:id
            """,
            row,
        )
        await conn.commit()
        return task

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        conn = await self._ensure_connected()
        cursor = await conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await conn.commit()
        return cursor.rowcount > 0

    # === Run Tracking ===

    async def record_run(
        self,
        run_id: str,
        task_id: str,
        started_at: int,
        finished_at: int | None = None,
        outcome: str | None = None,
        result_summary: str | None = None,
        error: str | None = None,
        tokens_used: int | None = None,
        cost_eur: float | None = None,
        logs_path: str | None = None,
    ) -> None:
        """Record a task run."""
        conn = await self._ensure_connected()
        await conn.execute(
            """
            INSERT INTO task_runs (id, task_id, started_at, finished_at, outcome, result_summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, task_id, started_at, finished_at, outcome, result_summary),
        )
        await conn.commit()

    # === Lease Management (using task.lease_owner/lease_expires_at columns) ===

    async def acquire_lease(self, task_id: str, worker_id: str, lease_ttl_s: int = 300) -> bool:
        """Acquire a lease on a task. Returns True if acquired, False if already leased."""
        conn = await self._ensure_connected()
        now = int(time.time() * 1000)
        expires = now + lease_ttl_s * 1000
        # Check if task has existing valid lease
        cursor = await conn.execute(
            "SELECT lease_owner, lease_expires_at FROM tasks WHERE id = ?",
            (task_id,),
        )
        row = await cursor.fetchone()
        if row and row["lease_owner"] and row["lease_expires_at"]:
            if row["lease_expires_at"] > now:
                # Lease is valid and not expired
                return False
        # Acquire lease
        await conn.execute(
            "UPDATE tasks SET lease_owner=?, lease_expires_at=? WHERE id=?",
            (worker_id, expires, task_id),
        )
        await conn.commit()
        return True

    async def release_lease(self, task_id: str, worker_id: str) -> None:
        """Release a lease on a task."""
        conn = await self._ensure_connected()
        await conn.execute(
            "UPDATE tasks SET lease_owner=NULL, lease_expires_at=NULL WHERE id=? AND lease_owner=?",
            (task_id, worker_id),
        )
        await conn.commit()

    async def reap_stale_leases(self, grace_s: int = 60) -> int:
        """Reap leases that have been stale for grace_s seconds. Returns count of reaped."""
        conn = await self._ensure_connected()
        now = int(time.time() * 1000)
        grace_ms = grace_s * 1000
        # First delete task_runs for stale tasks, then delete the tasks
        await conn.execute(
            "DELETE FROM task_runs WHERE task_id IN (SELECT id FROM tasks WHERE lease_expires_at IS NOT NULL AND lease_expires_at < ?)",
            (now - grace_ms,),
        )
        cursor = await conn.execute(
            "DELETE FROM tasks WHERE lease_expires_at IS NOT NULL AND lease_expires_at < ?",
            (now - grace_ms,),
        )
        await conn.commit()
        return cursor.rowcount

    # === HITL Pending ===

    async def create_hitl_request(self, req: HitlRequest) -> HitlRequest:
        """Create a new HITL request."""
        conn = await self._ensure_connected()
        await conn.execute(
            """
            INSERT INTO hitl_pending (id, task_id, run_id, question, options_json, channel, user_response, created_at, expires_at, resolved_at)
            VALUES (:id, :task_id, :run_id, :question, :options_json, :channel, :user_response, :created_at, :expires_at, :resolved_at)
            """,
            req.to_row(),
        )
        await conn.commit()
        return req

    async def list_hitl_pending(self, limit: int = 50) -> list[dict]:
        """List pending HITL requests (resolved_at IS NULL means pending)."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            "SELECT * FROM hitl_pending WHERE resolved_at IS NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def resolve_hitl(self, hitl_id: str, user_response: str, resolved_at: int) -> bool:
        """Resolve a HITL request by setting user_response and resolved_at."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            "UPDATE hitl_pending SET user_response = ?, resolved_at = ? WHERE id = ? AND resolved_at IS NULL",
            (user_response, resolved_at, hitl_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def expire_hitl(self, older_than_hours: int = 24) -> list[dict]:
        """Mark expired HITL requests as rejected (set user_response='expired')."""
        conn = await self._ensure_connected()
        cutoff = int(time.time() * 1000) - older_than_hours * 3600 * 1000
        # First get expired IDs to return
        cursor = await conn.execute(
            "SELECT * FROM hitl_pending WHERE resolved_at IS NULL AND created_at < ?",
            (cutoff,),
        )
        expired_rows = [dict(row) for row in await cursor.fetchall()]
        # Mark them as expired
        cursor = await conn.execute(
            "UPDATE hitl_pending SET user_response = 'expired', resolved_at = ? WHERE resolved_at IS NULL AND created_at < ?",
            (int(time.time() * 1000), cutoff),
        )
        await conn.commit()
        return expired_rows
