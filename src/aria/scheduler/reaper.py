"""Periodic maintenance task for the scheduler.

Cleans up expired leases, moves failed tasks to DLQ, and handles
orphaned task runs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import TaskStore

logger = logging.getLogger(__name__)


class Reaper:
    """Periodic maintenance tasks for the scheduler.

    Runs every 30 seconds and performs:
    - Releases expired leases (lease_owner reset)
    - Moves tasks to DLQ after max_retries exceeded
    - Forces outcome=timeout on stalled task runs
    - Expires stale hitl_pending entries
    - WAL checkpoint every 6 hours

    Args:
        store: TaskStore instance for database operations.
        interval_s: Interval between reaper runs in seconds.
    """

    def __init__(self, store: TaskStore, interval_s: int = 30) -> None:
        self._store = store
        self._interval_s = interval_s
        self._last_checkpoint_time = time.monotonic()
        self._checkpoint_interval_s = 6 * 3600  # 6 hours
        self._running = False

    async def run_once(self) -> int:
        """Execute one reaper cycle.

        Returns:
            Number of leases reclaimed in this cycle.
        """
        now_ms = int(time.time() * 1000)
        reclaimed = 0

        # 1. Release expired leases
        try:
            reclaimed = await self._store.reap_stale_leases(now_ms)
            if reclaimed > 0:
                logger.info("Reclaimed %d expired leases", reclaimed)
        except Exception as e:
            logger.error("Error releasing expired leases: %s", e)

        # 2. Move exhausted retries to DLQ
        try:
            moved = await self._move_exhausted_to_dlq()
            if moved > 0:
                logger.info("Moved %d tasks to DLQ", moved)
        except Exception as e:
            logger.error("Error moving tasks to DLQ: %s", e)

        # 3. Force timeout on stalled task runs
        try:
            timed_out = await self._mark_stalled_runs_timed_out()
            if timed_out > 0:
                logger.info("Marked %d task runs as timed out", timed_out)
        except Exception as e:
            logger.error("Error marking stalled runs: %s", e)

        # 4. Expire stale HITL pending entries
        try:
            expired = await self._store.expire_hitl(now_ms)
            if expired:
                logger.info("Expired %d HITL pending entries", len(expired))
        except Exception as e:
            logger.error("Error expiring HITL entries: %s", e)

        # 5. WAL checkpoint every 6 hours
        elapsed = time.monotonic() - self._last_checkpoint_time
        if elapsed >= self._checkpoint_interval_s:
            try:
                await self._checkpoint_wal()
                self._last_checkpoint_time = time.monotonic()
            except Exception as e:
                logger.error("Error checkpointing WAL: %s", e)

        return reclaimed

    async def run_forever(self) -> None:
        """Run reaper loop indefinitely until cancelled."""
        self._running = True
        try:
            while self._running:
                try:
                    await self.run_once()
                except Exception as e:
                    logger.exception("Reaper cycle failed: %s", e)
                await asyncio.sleep(self._interval_s)
        except asyncio.CancelledError:
            pass

    def stop(self) -> None:
        """Signal the reaper to stop after the current cycle."""
        self._running = False

    async def _move_exhausted_to_dlq(self) -> int:
        """Move tasks with retry_count >= max_retries to DLQ.

        Returns:
            Number of tasks moved to DLQ.
        """
        moved = 0
        tasks = await self._store.list_tasks(status=["active"])
        for task in tasks:
            if task.retry_count >= task.max_retries:
                try:
                    await self._store.move_to_dlq(
                        task_id=task.id,
                        reason=f"max_retries ({task.max_retries}) exceeded",
                        last_run_id=None,
                    )
                    moved += 1
                except Exception as e:
                    logger.error("Failed to move task %s to DLQ: %s", task.id, e)
        return moved

    async def _mark_stalled_runs_timed_out(self) -> int:
        """Mark task runs that started but never finished as timeout.

        Returns:
            Number of runs marked as timeout.
        """
        conn = self._store._conn
        if conn is None:
            return 0

        marked = 0
        cutoff_ms = int(time.time() * 1000) - 300_000  # 5 min timeout

        cursor = await conn.execute(
            """
            SELECT id, task_id, started_at
            FROM task_runs
            WHERE finished_at IS NULL
            AND started_at < ?
            """,
            (cutoff_ms,),
        )
        rows = await cursor.fetchall()

        for row in rows:
            run_id = row["id"]
            try:
                await self._store.update_run(
                    run_id,
                    finished_at=int(time.time() * 1000),
                    outcome="timeout",
                    result_summary="Task run timed out before completion",
                )
                marked += 1
            except Exception as e:
                logger.error("Failed to mark run %s as timeout: %s", run_id, e)

        return marked

    async def _checkpoint_wal(self) -> None:
        """Execute WAL checkpoint to truncate the WAL file."""
        conn = self._store._conn
        if conn is None:
            return

        await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info("WAL checkpoint completed")
