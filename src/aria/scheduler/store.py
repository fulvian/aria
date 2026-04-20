# ARIA Task Store - SQLite persistence for scheduler
#
# Per blueprint §6.1 and sprint plan W1.2.A.
#
# Provides:
# - Task CRUD with lease-based concurrency (ADR-0005)
# - TaskRun tracking
# - DLQ management
# - HITL pending queue
#
# Usage:
#   from aria.scheduler.store import TaskStore
#   store = TaskStore(db_path)
#   await store.connect()

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import aiosqlite

    from aria.scheduler.schema import (
        DlqEntry,
        HitlPending,
        Task,
        TaskRun,
    )

logger = logging.getLogger(__name__)

# Default lease TTL in seconds
DEFAULT_LEASE_TTL = 300


# Worker ID format: scheduler-{pid}-{random_hex}
def _make_worker_id() -> str:
    return f"scheduler-{os.getpid()}-{uuid.uuid4().hex[:8]}"


# === SQLite Connection Setup ===

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL,
    trigger_type      TEXT NOT NULL,
    trigger_config    TEXT NOT NULL DEFAULT '{}',
    schedule_cron     TEXT,
    timezone          TEXT DEFAULT 'Europe/Rome',
    next_run_at       INTEGER,
    status            TEXT NOT NULL DEFAULT 'active',
    policy            TEXT NOT NULL DEFAULT 'allow',
    budget_tokens     INTEGER,
    budget_cost_eur   REAL,
    max_retries       INTEGER DEFAULT 3,
    retry_count       INTEGER DEFAULT 0,
    last_error        TEXT,
    owner_user_id     TEXT,
    payload           TEXT NOT NULL DEFAULT '{}',
    lease_owner       TEXT,
    lease_expires_at  INTEGER,
    created_at        INTEGER NOT NULL,
    updated_at        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_next_run ON tasks(next_run_at) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);
CREATE INDEX IF NOT EXISTS idx_tasks_lease ON tasks(lease_owner, lease_expires_at);

CREATE TABLE IF NOT EXISTS task_runs (
    id                TEXT PRIMARY KEY,
    task_id           TEXT NOT NULL REFERENCES tasks(id),
    started_at        INTEGER NOT NULL,
    finished_at       INTEGER,
    outcome           TEXT NOT NULL,
    tokens_used       INTEGER,
    cost_eur          REAL,
    result_summary    TEXT,
    logs_path         TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_task ON task_runs(task_id);

CREATE TABLE IF NOT EXISTS dlq (
    id                TEXT PRIMARY KEY,
    task_id           TEXT NOT NULL REFERENCES tasks(id),
    last_run_id       TEXT REFERENCES task_runs(id),
    moved_at          INTEGER NOT NULL,
    reason            TEXT NOT NULL,
    payload_snapshot  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dlq_task ON dlq(task_id);

CREATE TABLE IF NOT EXISTS hitl_pending (
    id                TEXT PRIMARY KEY,
    task_id           TEXT REFERENCES tasks(id),
    run_id            TEXT REFERENCES task_runs(id),
    created_at        INTEGER NOT NULL,
    expires_at        INTEGER NOT NULL,
    question          TEXT NOT NULL,
    options_json      TEXT,
    channel           TEXT NOT NULL DEFAULT 'telegram',
    user_response     TEXT,
    resolved_at       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_hitl_expires ON hitl_pending(expires_at);
CREATE INDEX IF NOT EXISTS idx_hitl_task ON hitl_pending(task_id);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    checksum TEXT NOT NULL
);
"""


# === TaskStore ===


class TaskStore:
    """SQLite-based task store with lease-based concurrency.

    Per ADR-0005: Uses lease_owner/lease_expires_at columns to enable
    safe concurrent scheduling across multiple scheduler instances.

    The acquire_due method uses a single UPDATE transaction to atomically
    claim multiple due tasks, preventing race conditions between workers.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize TaskStore.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = db_path.resolve()
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize database connection and run migrations."""
        import aiosqlite

        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrency
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")

        # Create schema
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

        logger.info("TaskStore connected to %s", self._db_path)

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    def _assert_connected(self) -> None:
        """Raise if not connected."""
        if self._conn is None:
            raise RuntimeError("TaskStore not connected. Call connect() first.")

    # === Task Operations ===

    async def create_task(self, task: Task) -> str:
        """Create a new task.

        Args:
            task: Task instance to create

        Returns:
            Task ID
        """
        self._assert_connected()

        trigger_config = json.dumps(task.trigger_config)
        payload = json.dumps(task.payload)

        await self._conn.execute(
            """
            INSERT INTO tasks (
                id, name, category, trigger_type, trigger_config,
                schedule_cron, timezone, next_run_at, status, policy,
                budget_tokens, budget_cost_eur, max_retries, retry_count,
                last_error, owner_user_id, payload, lease_owner, lease_expires_at,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                task.id,
                task.name,
                task.category,
                task.trigger_type,
                trigger_config,
                task.schedule_cron,
                task.timezone,
                task.next_run_at,
                task.status,
                task.policy,
                task.budget_tokens,
                task.budget_cost_eur,
                task.max_retries,
                task.retry_count,
                task.last_error,
                task.owner_user_id,
                payload,
                task.lease_owner,
                task.lease_expires_at,
                task.created_at,
                task.updated_at,
            ),
        )
        await self._conn.commit()
        logger.info("Created task %s: %s", task.id, task.name)
        return task.id

    async def update_task(self, task_id: str, **fields: object) -> None:
        """Update task fields.

        Args:
            task_id: Task ID to update
            **fields: Field names and new values
        """
        self._assert_connected()

        # Special handling for JSON fields
        json_fields = {"trigger_config", "payload"}

        set_clauses = []
        values = []

        for key, value in fields.items():
            if key in json_fields and isinstance(value, dict):
                set_clauses.append(f"{key} = ?")
                values.append(json.dumps(value))
            elif key == "updated_at":
                set_clauses.append("updated_at = ?")
                values.append(int(datetime.now(tz=UTC).timestamp() * 1000))
            else:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if not set_clauses:
            return

        values.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        await self._conn.execute(sql, values)
        await self._conn.commit()

    async def get_task(self, task_id: str) -> Task | None:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task instance or None if not found
        """
        self._assert_connected()

        cursor = await self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_task(row)

    async def list_tasks(
        self,
        status: list[str] | None = None,
        category: str | None = None,
    ) -> list[Task]:
        """List tasks with optional filtering.

        Args:
            status: Filter by status list
            category: Filter by category

        Returns:
            List of Task instances
        """
        self._assert_connected()

        conditions = []
        params: list[str] = []

        if status:
            placeholders = ",".join("?" * len(status))
            conditions.append(f"status IN ({placeholders})")
            params.extend(status)

        if category:
            conditions.append("category = ?")
            params.append(category)

        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        cursor = await self._conn.execute(
            f"SELECT * FROM tasks{where_clause} ORDER BY created_at DESC",
            params,
        )
        rows = await cursor.fetchall()

        return [self._row_to_task(row) for row in rows]

    async def acquire_due(
        self,
        worker_id: str,
        lease_ttl_seconds: int = DEFAULT_LEASE_TTL,
        limit: int = 10,
    ) -> list[Task]:
        """Acquire due tasks for processing.

        Uses atomic UPDATE to claim tasks, preventing race conditions.
        Per ADR-0005: Only tasks with no lease or expired lease are claimed.

        Args:
            worker_id: Unique worker identifier
            lease_ttl_seconds: How long to hold the lease
            limit: Maximum number of tasks to claim

        Returns:
            List of claimed Task instances
        """
        self._assert_connected()

        now_ms = int(time.time() * 1000)
        expiry_ms = now_ms + (lease_ttl_seconds * 1000)

        # Atomic claim: update tasks where next_run_at <= now
        # and (no lease or lease expired)
        await self._conn.execute(
            """
            UPDATE tasks
            SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
            WHERE id IN (
                SELECT id FROM tasks
                WHERE status = 'active'
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
                  AND (lease_owner IS NULL OR lease_expires_at < ?)
                ORDER BY next_run_at
                LIMIT ?
            )
            """,
            (worker_id, expiry_ms, now_ms, now_ms, now_ms, limit),
        )
        await self._conn.commit()

        # Fetch the claimed tasks
        cursor = await self._conn.execute(
            """
            SELECT * FROM tasks
            WHERE lease_owner = ? AND lease_expires_at = ?
            """,
            (worker_id, expiry_ms),
        )
        rows = await cursor.fetchall()

        tasks = [self._row_to_task(row) for row in rows]
        logger.debug("Worker %s acquired %d tasks", worker_id, len(tasks))
        return tasks

    async def release_lease(self, task_id: str, worker_id: str) -> None:
        """Release lease on a task.

        Only releases if the task is still owned by the given worker.

        Args:
            task_id: Task ID
            worker_id: Worker that owns the lease
        """
        self._assert_connected()

        now = int(datetime.now(tz=UTC).timestamp() * 1000)
        await self._conn.execute(
            """
            UPDATE tasks
            SET lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
            WHERE id = ? AND lease_owner = ?
            """,
            (now, task_id, worker_id),
        )
        await self._conn.commit()

    async def reap_stale_leases(self, now_ms: int | None = None) -> int:
        """Reap expired leases and return them to the pool.

        Args:
            now_ms: Current time in epoch ms (default: now)

        Returns:
            Number of leases reaped
        """
        self._assert_connected()

        if now_ms is None:
            now_ms = int(time.time() * 1000)

        cursor = await self._conn.execute(
            """
            UPDATE tasks
            SET lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
            WHERE lease_owner IS NOT NULL AND lease_expires_at < ?
            """,
            (now_ms, now_ms),
        )
        await self._conn.commit()

        count = cursor.rowcount
        if count > 0:
            logger.info("Reaped %d stale leases", count)
        return count

    # === TaskRun Operations ===

    async def record_run(self, run: TaskRun) -> str:
        """Record a new task run.

        Args:
            run: TaskRun instance to record

        Returns:
            Run ID
        """
        self._assert_connected()

        await self._conn.execute(
            """
            INSERT INTO task_runs (
                id, task_id, started_at, finished_at, outcome,
                tokens_used, cost_eur, result_summary, logs_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.task_id,
                run.started_at,
                run.finished_at,
                run.outcome,
                run.tokens_used,
                run.cost_eur,
                run.result_summary,
                run.logs_path,
            ),
        )
        await self._conn.commit()
        logger.info("Recorded run %s for task %s", run.id, run.task_id)
        return run.id

    async def update_run(self, run_id: str, **fields: object) -> None:
        """Update task run fields.

        Args:
            run_id: Run ID to update
            **fields: Field names and new values
        """
        self._assert_connected()

        set_clauses = []
        values = []

        for key, value in fields.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)

        if not set_clauses:
            return

        values.append(run_id)
        sql = f"UPDATE task_runs SET {', '.join(set_clauses)} WHERE id = ?"
        await self._conn.execute(sql, values)
        await self._conn.commit()

    # === DLQ Operations ===

    async def move_to_dlq(
        self,
        task_id: str,
        reason: str,
        last_run_id: str | None = None,
    ) -> str:
        """Move a failed task to the dead letter queue.

        Args:
            task_id: Task ID to move to DLQ
            reason: Reason for DLQ placement
            last_run_id: ID of the last failed run

        Returns:
            DLQ entry ID
        """
        self._assert_connected()

        now = int(datetime.now(tz=UTC).timestamp() * 1000)
        dlq_id = str(uuid.uuid4())

        # Get task payload snapshot
        task = await self.get_task(task_id)
        payload_snapshot = json.dumps(task.payload) if task else "{}"

        await self._conn.execute(
            """
            INSERT INTO dlq (id, task_id, last_run_id, moved_at, reason, payload_snapshot)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (dlq_id, task_id, last_run_id, now, reason, payload_snapshot),
        )

        # Update task status to dlq
        await self.update_task(task_id, status="dlq", last_error=reason)

        logger.info("Moved task %s to DLQ: %s", task_id, reason)
        return dlq_id

    async def list_dlq(self) -> list[DlqEntry]:
        """List all DLQ entries.

        Returns:
            List of DlqEntry instances
        """
        self._assert_connected()

        from aria.scheduler.schema import DlqEntry

        cursor = await self._conn.execute("SELECT * FROM dlq ORDER BY moved_at DESC")
        rows = await cursor.fetchall()

        entries = []
        for row in rows:
            entries.append(
                DlqEntry(
                    id=row["id"],
                    task_id=row["task_id"],
                    last_run_id=row["last_run_id"],
                    moved_at=row["moved_at"],
                    reason=row["reason"],
                    payload_snapshot=row["payload_snapshot"],
                )
            )
        return entries

    # === HITL Operations ===

    async def create_hitl(self, pending: HitlPending) -> str:
        """Create a new HITL pending request.

        Args:
            pending: HitlPending instance

        Returns:
            HITL ID
        """
        self._assert_connected()

        await self._conn.execute(
            """
            INSERT INTO hitl_pending (
                id, task_id, run_id, created_at, expires_at,
                question, options_json, channel, user_response, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pending.id,
                pending.task_id,
                pending.run_id,
                pending.created_at,
                pending.expires_at,
                pending.question,
                pending.options_json,
                pending.channel,
                pending.user_response,
                pending.resolved_at,
            ),
        )
        await self._conn.commit()
        logger.info("Created HITL %s: %s", pending.id, pending.question[:50])
        return pending.id

    async def resolve_hitl(self, hitl_id: str, response: str) -> HitlPending | None:
        """Resolve a HITL pending request.

        Args:
            hitl_id: HITL ID
            response: User response

        Returns:
            Updated HitlPending or None if not found
        """
        self._assert_connected()

        now = int(datetime.now(tz=UTC).timestamp() * 1000)

        # Get current entry
        cursor = await self._conn.execute("SELECT * FROM hitl_pending WHERE id = ?", (hitl_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        # Update with resolution
        await self._conn.execute(
            """
            UPDATE hitl_pending
            SET user_response = ?, resolved_at = ?
            WHERE id = ?
            """,
            (response, now, hitl_id),
        )
        await self._conn.commit()

        logger.info("Resolved HITL %s with response: %s", hitl_id, response)

        # Return updated entry
        return self._row_to_hitl(row, resolved_at=now, user_response=response)

    async def expire_hitl(self, now_ms: int | None = None) -> list[HitlPending]:
        """Find and expire stale HITL requests.

        Args:
            now_ms: Current time in epoch ms (default: now)

        Returns:
            List of expired HitlPending entries
        """
        self._assert_connected()

        if now_ms is None:
            now_ms = int(time.time() * 1000)

        cursor = await self._conn.execute(
            """
            SELECT * FROM hitl_pending
            WHERE expires_at < ? AND resolved_at IS NULL
            """,
            (now_ms,),
        )
        rows = await cursor.fetchall()

        expired = []
        for row in rows:
            expired.append(self._row_to_hitl(row))

        if expired:
            logger.info("Found %d expired HITL entries", len(expired))

        return expired

    # === Internal Helpers ===

    def _row_to_task(self, row: aiosqlite.Row) -> Task:
        """Convert database row to Task model."""
        from aria.scheduler.schema import Task

        return Task(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            trigger_type=row["trigger_type"],
            trigger_config=json.loads(row["trigger_config"]),
            schedule_cron=row["schedule_cron"],
            timezone=row["timezone"],
            next_run_at=row["next_run_at"],
            status=row["status"],
            policy=row["policy"],
            budget_tokens=row["budget_tokens"],
            budget_cost_eur=row["budget_cost_eur"],
            max_retries=row["max_retries"],
            retry_count=row["retry_count"],
            last_error=row["last_error"],
            owner_user_id=row["owner_user_id"],
            payload=json.loads(row["payload"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_hitl(
        self,
        row: aiosqlite.Row,
        resolved_at: int | None = None,
        user_response: str | None = None,
    ) -> HitlPending:
        """Convert database row to HitlPending model."""
        from aria.scheduler.schema import HitlPending

        return HitlPending(
            id=row["id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            question=row["question"],
            options_json=row["options_json"],
            channel=row["channel"],
            user_response=user_response or row["user_response"],
            resolved_at=resolved_at or row["resolved_at"],
        )
