# Scheduler Reaper — Background maintenance task
#
# Per blueprint §6 and memory gap remediation plan Task 5.
#
# Features:
# - Stale lease reaping
# - Expired HITL request handling
# - Episodic WAL checkpoint (every 6h)
# - T0 retention pruning (via episodic_store)
# - Periodic scheduler task cleanup
#
# Usage:
#   from aria.scheduler.reaper import Reaper
#
#   reaper = Reaper(store, interval_s=30, episodic_store=episodic_store)
#   await reaper.run_once()

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.memory.episodic import EpisodicStore
    from aria.scheduler.store import TaskStore

logger = logging.getLogger(__name__)


class Reaper:
    """Background maintenance task for scheduler.

    Runs periodic maintenance:
    1. Reap stale task leases
    2. Expire old HITL requests
    3. Checkpoint episodic.db WAL (every 6h)
    4. Prune old T0 entries (retention policy)
    """

    def __init__(
        self,
        store: TaskStore,
        interval_s: int = 30,
        episodic_store: EpisodicStore | None = None,
    ) -> None:
        """Initialize Reaper.

        Args:
            store: TaskStore instance
            interval_s: Interval between maintenance cycles
            episodic_store: Optional EpisodicStore for WAL checkpoint + retention pruning
        """
        self._store = store
        self._interval_s = interval_s
        self._last_checkpoint_time = time.monotonic()
        self._checkpoint_interval_s = 6 * 3600  # 6 hours
        self._running = False
        self._episodic_store = episodic_store

    async def run_once(self) -> None:
        """Run a single maintenance cycle."""
        elapsed = time.monotonic() - self._last_checkpoint_time

        # 1. Reap stale leases
        try:
            reaped = await self._store.reap_stale_leases(grace_s=60)
            if reaped > 0:
                logger.info("Reaped %d stale task leases", reaped)
        except Exception as e:
            logger.error("Error reaping stale leases: %s", e)

        # 2. Expire old HITL requests
        try:
            expired = await self._store.expire_hitl(older_than_hours=24)
            if expired:
                logger.info("Expired %d HITL requests", len(expired))
        except Exception as e:
            logger.error("Error expiring HITL requests: %s", e)

        # 3. List tasks (keep alive)
        try:
            tasks = await self._store.list_tasks()
            logger.debug("TaskStore has %d tasks", len(tasks))
        except Exception as e:
            logger.error("Error listing tasks: %s", e)

        # 4. Episodic WAL checkpoint + retention pruning (every 6h)
        if self._episodic_store is not None and elapsed >= self._checkpoint_interval_s:
            self._last_checkpoint_time = time.monotonic()

            try:
                await self._episodic_store.vacuum_wal()
                logger.info("Episodic WAL checkpoint completed")
            except Exception as e:
                logger.error("Error checkpointing episodic WAL: %s", e)

            try:
                from aria.config import get_config

                config = get_config()
                retention_days = config.memory.t0_retention_days
                pruned = await self._episodic_store.prune_old_entries(retention_days)
                if pruned > 0:
                    logger.info(
                        "Pruned %d T0 entries (retention=%dd)",
                        pruned,
                        retention_days,
                    )
            except Exception as e:
                logger.error("Error pruning old T0 entries: %s", e)

    async def run_forever(self) -> None:
        """Run maintenance loop until stopped."""
        self._running = True
        while self._running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error("Reaper cycle failed: %s", e)
            await asyncio.sleep(self._interval_s)

    def stop(self) -> None:
        """Stop the maintenance loop."""
        self._running = False
