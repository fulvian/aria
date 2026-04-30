# ARIA Scheduler Daemon
#
# Entry point for the Scheduler service that handles autonomous task scheduling.
# Per blueprint §6 and memory gap remediation plan Tasks 4 & 5.
#
# Features:
# - Cron, event, webhook, oneshot, manual triggers
# - Budget gate (tokens, cost per run/category)
# - Policy gate (allow, ask, deny with HITL)
# - Dead Letter Queue with retry logic
# - sd_notify watchdog integration
# - Memory maintenance tasks (distill, WAL checkpoint)
#
# Usage:
#   python -m aria.scheduler.daemon
#   python -m aria.scheduler.daemon --check

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import time as _time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.config import ARIAConfig
    from aria.scheduler.store import TaskStore

logger = logging.getLogger(__name__)


async def _seed_memory_tasks(store: TaskStore, config: ARIAConfig) -> None:
    """Seed recurring memory tasks if not already present.

    Idempotent: skips if a task with the same name already exists.
    """
    from aria.scheduler.store import Task

    existing = await store.list_tasks(status=["active", "paused"])
    existing_names = {t.name for t in existing}

    now_ms = int(_time.time() * 1000)

    if "memory-wal-checkpoint" not in existing_names:
        task = Task(
            name="memory-wal-checkpoint",
            category="memory",
            trigger_type="cron",
            schedule_cron="30 */6 * * *",
            timezone="Europe/Rome",
            next_run_at=now_ms + 6 * 3600 * 1000 + 1800 * 1000,  # offset 30min
            policy="allow",
            payload={"action": "wal_checkpoint"},
            created_at=now_ms,
            updated_at=now_ms,
        )
        await store.create_task(task)
        logger.info("Seeded memory-wal-checkpoint cron task")

    # Wiki watchdog: detects skipped wiki_update calls (plan §5.3 Phase B)
    if "memory-watchdog" not in existing_names:
        task = Task(
            name="memory-watchdog",
            category="memory",
            trigger_type="cron",
            schedule_cron="*/15 * * * *",
            timezone="Europe/Rome",
            next_run_at=now_ms + 15 * 60 * 1000,  # first run in 15 min
            policy="allow",
            payload={"action": "wiki_watchdog"},
            created_at=now_ms,
            updated_at=now_ms,
        )
        await store.create_task(task)
        logger.info("Seeded memory-watchdog cron task")


async def _async_main() -> int:  # noqa: PLR0915
    """Async main entry point for scheduler daemon."""
    from aria.config import get_config
    from aria.memory.episodic import create_episodic_store
    from aria.scheduler.reaper import Reaper
    from aria.scheduler.runner import BudgetGate, EventBus, HitlManager, PolicyGate, TaskRunner
    from aria.scheduler.store import TaskStore

    config = get_config()
    logger.info("Starting ARIA Scheduler daemon...")

    # Initialize components
    scheduler_db = config.paths.runtime / "scheduler" / "scheduler.db"
    task_store = TaskStore(scheduler_db)
    await task_store.connect()

    # Seed memory maintenance tasks (idempotent)
    await _seed_memory_tasks(task_store, config)

    # Initialize episodic store for Reaper WAL checkpoint + retention pruning
    episodic_store = await create_episodic_store(config)

    # Initialize event bus and gates
    bus = EventBus()
    budget = BudgetGate()
    policy = PolicyGate()
    hitl = HitlManager(task_store, bus, config)

    # Initialize task runner
    runner = TaskRunner(
        store=task_store,
        budget=budget,
        policy=policy,
        hitl=hitl,
        bus=bus,
        config=config,
    )

    # Initialize reaper with episodic store for WAL checkpoint + retention
    reaper = Reaper(task_store, interval_s=30, episodic_store=episodic_store)

    logger.info("ARIA Scheduler daemon started successfully")

    # Run until shutdown
    stop_event = asyncio.Event()

    def handle_signal(sig: int) -> None:
        logger.info("Received signal %d, shutting down...", sig)
        stop_event.set()

    # Set up signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(
            sig,
            lambda s=sig: handle_signal(s),  # type: ignore[misc]
        )

    try:
        # Run reaper in background task
        reaper_task = asyncio.create_task(reaper.run_forever())

        # Main loop - process due tasks
        while not stop_event.is_set():
            try:
                # Check for due tasks and execute them
                tasks = await task_store.list_tasks(status=["active"])
                now_ms = int(_time.time() * 1000)

                for task in tasks:
                    if task.next_run_at and task.next_run_at <= now_ms:
                        # Task is due - try to acquire lease and execute
                        if await task_store.acquire_lease(task.id, runner._worker_id):
                            try:
                                result = await runner.execute_task(task.id)
                                logger.info(
                                    "Task %s completed: outcome=%s summary=%s",
                                    task.name,
                                    result.outcome,
                                    result.result_summary,
                                )
                            finally:
                                await task_store.release_lease(task.id, runner._worker_id)
                        else:
                            logger.debug("Task %s is leased by another worker", task.name)

                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)
                await asyncio.sleep(10)

    finally:
        # Clean shutdown
        logger.info("Shutting down ARIA Scheduler daemon...")
        reaper.stop()
        try:
            reaper_task.cancel()
            await reaper_task
        except asyncio.CancelledError:
            pass

        await episodic_store.close()
        await task_store.close()
        logger.info("ARIA Scheduler daemon stopped")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for scheduler daemon."""
    parser = argparse.ArgumentParser(
        prog="python -m aria.scheduler.daemon",
        description="ARIA Scheduler daemon.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate CLI wiring and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for scheduler daemon."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        # Validate that we can import all required modules
        try:
            from aria.config import get_config
            from aria.scheduler.reaper import Reaper
            from aria.scheduler.runner import TaskRunner
            from aria.scheduler.store import TaskStore

            _ = (get_config, Reaper, TaskRunner, TaskStore)
            return 0
        except ImportError as e:
            print(f"Import error: {e}", file=__import__("sys").stderr)
            return 1

    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        return asyncio.run(_async_main())
    except KeyboardInterrupt:
        logger.info("Scheduler daemon interrupted")
        return 0
    except Exception as e:
        logger.exception("Scheduler daemon failed: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
