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
        trigger_type: Literal["cron", "event", "webhook", "oneshot", "manual"] = "manual",
        schedule_cron: str | None = None,
        timezone: str = "UTC",
        next_run_at: int | None = None,
        policy: Literal["allow", "ask", "deny"] = "allow",
        payload: dict | None = None,
        status: Literal["active", "paused", "completed", "failed"] = "active",
        created_at: int | None = None,
        updated_at: int | None = None,
        id: str | None = None,
    ) -> None:
        self.id = id or str(time.time_ns())
        self.name = name
        self.category = category
        self.trigger_type = trigger_type
        self.schedule_cron = schedule_cron
        self.timezone = timezone
        self.next_run_at = next_run_at or int(time.time() * 1000)
        self.policy = policy
        self.payload = payload or {}
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
            "schedule_cron": self.schedule_cron,
            "timezone": self.timezone,
            "next_run_at": self.next_run_at,
            "policy": self.policy,
            "payload": json.dumps(self.payload),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict) -> Task:
        """Create Task from database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            trigger_type=row["trigger_type"],
            schedule_cron=row["schedule_cron"],
            timezone=row["timezone"],
            next_run_at=row["next_run_at"],
            policy=row["policy"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class HitlRequest:
    """HITL pending request model."""

    def __init__(
        self,
        *,
        id: str,
        target_id: str,
        action: str,
        reason: str,
        trace_id: str | None,
        channel: str,
        status: Literal["pending", "approved", "cancelled", "rejected"] = "pending",
        created_at: int | None = None,
        resolved_at: int | None = None,
    ) -> None:
        self.id = id
        self.target_id = target_id
        self.action = action
        self.reason = reason
        self.trace_id = trace_id
        self.channel = channel
        self.status = status
        self.created_at = created_at or int(time.time() * 1000)
        self.resolved_at = resolved_at

    def to_row(self) -> dict:
        """Convert to dict for DB insertion."""
        return {
            "id": self.id,
            "target_id": self.target_id,
            "action": self.action,
            "reason": self.reason,
            "trace_id": self.trace_id,
            "channel": self.channel,
            "status": self.status,
            "created_at": self.created_at,
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
    CREATE TABLE IF NOT EXISTS scheduler_tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL DEFAULT 'default',
        trigger_type TEXT NOT NULL DEFAULT 'manual',
        schedule_cron TEXT,
        timezone TEXT NOT NULL DEFAULT 'UTC',
        next_run_at INTEGER,
        policy TEXT NOT NULL DEFAULT 'allow',
        payload TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'active',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS scheduler_hitl_pending (
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

    CREATE TABLE IF NOT EXISTS scheduler_runs (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        started_at INTEGER NOT NULL,
        finished_at INTEGER,
        outcome TEXT,
        result_summary TEXT,
        error TEXT,
        FOREIGN KEY (task_id) REFERENCES scheduler_tasks(id)
    );

    CREATE TABLE IF NOT EXISTS scheduler_leases (
        task_id TEXT PRIMARY KEY,
        leased_at INTEGER NOT NULL,
        lease_expires_at INTEGER NOT NULL,
        worker_id TEXT NOT NULL
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
        self._conn = aiosqlite.connect(self._db_path, timeout=30.0)
        self._conn.row_factory = aiosqlite.Row
        for pragma in self.PRAGMAS:
            await self._conn.execute(pragma)
        await self._conn.executescript(self.SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
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
            INSERT OR REPLACE INTO scheduler_tasks
            (id, name, category, trigger_type, schedule_cron, timezone, next_run_at, policy, payload, status, created_at, updated_at)
            VALUES (:id, :name, :category, :trigger_type, :schedule_cron, :timezone, :next_run_at, :policy, :payload, :status, :created_at, :updated_at)
            """,
            row,
        )
        await conn.commit()
        return task

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        conn = await self._ensure_connected()
        cursor = await conn.execute("SELECT * FROM scheduler_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return Task.from_row(dict(row)) if row else None

    async def list_tasks(
        self,
        status: list[str] | None = None,
        category: str | None = None,
    ) -> list[Task]:
        """List tasks, optionally filtered by status and category."""
        conn = await self._ensure_connected()
        query = "SELECT * FROM scheduler_tasks WHERE 1=1"
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
            UPDATE scheduler_tasks SET
                name=:name, category=:category, trigger_type=:trigger_type,
                schedule_cron=:schedule_cron, timezone=:timezone, next_run_at=:next_run_at,
                policy=:policy, payload=:payload, status=:status, updated_at=:updated_at
            WHERE id=:id
            """,
            row,
        )
        await conn.commit()
        return task

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        conn = await self._ensure_connected()
        cursor = await conn.execute("DELETE FROM scheduler_tasks WHERE id = ?", (task_id,))
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
    ) -> None:
        """Record a task run."""
        conn = await self._ensure_connected()
        await conn.execute(
            """
            INSERT INTO scheduler_runs (id, task_id, started_at, finished_at, outcome, result_summary, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, task_id, started_at, finished_at, outcome, result_summary, error),
        )
        await conn.commit()

    # === Lease Management ===

    async def acquire_lease(self, task_id: str, worker_id: str, lease_ttl_s: int = 300) -> bool:
        """Acquire a lease on a task. Returns True if acquired, False if already leased."""
        conn = await self._ensure_connected()
        now = int(time.time() * 1000)
        expires = now + lease_ttl_s * 1000
        try:
            await conn.execute(
                """
                INSERT INTO scheduler_leases (task_id, leased_at, lease_expires_at, worker_id)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, now, expires, worker_id),
            )
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            # Lease already exists, check if expired
            cursor = await conn.execute(
                "SELECT lease_expires_at FROM scheduler_leases WHERE task_id = ?",
                (task_id,),
            )
            row = await cursor.fetchone()
            if row and row["lease_expires_at"] < now:
                # Expired, update it
                await conn.execute(
                    "UPDATE scheduler_leases SET leased_at=?, lease_expires_at=?, worker_id=? WHERE task_id=?",
                    (now, expires, worker_id, task_id),
                )
                await conn.commit()
                return True
            return False

    async def release_lease(self, task_id: str, worker_id: str) -> None:
        """Release a lease on a task."""
        conn = await self._ensure_connected()
        await conn.execute(
            "DELETE FROM scheduler_leases WHERE task_id = ? AND worker_id = ?",
            (task_id, worker_id),
        )
        await conn.commit()

    async def reap_stale_leases(self, grace_s: int = 60) -> int:
        """Reap leases that have been stale for grace_s seconds. Returns count of reaped."""
        conn = await self._ensure_connected()
        now = int(time.time() * 1000)
        grace_ms = grace_s * 1000
        cursor = await conn.execute(
            "DELETE FROM scheduler_leases WHERE lease_expires_at < ?",
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
            INSERT INTO scheduler_hitl_pending (id, target_id, action, reason, trace_id, channel, status, created_at, resolved_at)
            VALUES (:id, :target_id, :action, :reason, :trace_id, :channel, :status, :created_at, :resolved_at)
            """,
            req.to_row(),
        )
        await conn.commit()
        return req

    async def list_hitl_pending(self, limit: int = 50) -> list[dict]:
        """List pending HITL requests."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            "SELECT * FROM scheduler_hitl_pending WHERE status = 'pending' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def resolve_hitl(self, hitl_id: str, status: str, resolved_at: int) -> bool:
        """Resolve a HITL request (approve/cancel/reject)."""
        conn = await self._ensure_connected()
        cursor = await conn.execute(
            "UPDATE scheduler_hitl_pending SET status = ?, resolved_at = ? WHERE id = ?",
            (status, resolved_at, hitl_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def expire_hitl(self, older_than_hours: int = 24) -> list[dict]:
        """Mark expired HITL requests as rejected. Returns list of expired requests."""
        conn = await self._ensure_connected()
        cutoff = int(time.time() * 1000) - older_than_hours * 3600 * 1000
        cursor = await conn.execute(
            """
            UPDATE scheduler_hitl_pending
            SET status = 'rejected', resolved_at = ?
            WHERE status = 'pending' AND created_at < ?
            """,
            (int(time.time() * 1000), cutoff),
        )
        await conn.commit()
        # Return the rejected requests
        cursor = await conn.execute(
            "SELECT * FROM scheduler_hitl_pending WHERE status = 'rejected' AND resolved_at >= ?",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
