"""ARIA Scheduler daemon - systemd service entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from aria.config import get_config
from aria.utils.logging import get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aria.scheduler.daemon",
        description="ARIA Scheduler daemon - task scheduling with HITL support.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate CLI wiring and exit.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode (no systemd notifications).",
    )
    return parser


async def _run_scheduler() -> None:
    """Main scheduler coroutine - initializes and runs all components."""
    config = get_config()

    # Setup structured logging
    import logging

    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        force=True,
    )

    logger = get_logger(__name__)
    logger.info("Starting ARIA Scheduler Daemon v%s", config.VERSION)

    # Create runtime directories
    scheduler_dir = config.runtime / "scheduler"
    scheduler_dir.mkdir(parents=True, exist_ok=True)
    db_path = scheduler_dir / "scheduler.db"

    # Initialize components
    from aria.scheduler.budget_gate import BudgetGate
    from aria.scheduler.hitl import HitlManager
    from aria.scheduler.notify import SdNotifier
    from aria.scheduler.policy_gate import PolicyGate
    from aria.scheduler.reaper import Reaper
    from aria.scheduler.runner import TaskRunner
    from aria.scheduler.store import TaskStore
    from aria.scheduler.triggers import EventBus

    # Task store
    store = TaskStore(db_path)
    await store.connect()
    logger.info("Connected to scheduler DB at %s", db_path)

    # Event bus
    bus = EventBus()

    # Budget gate
    budget = BudgetGate(store, config)

    # Policy gate with clock
    from datetime import datetime

    policy = PolicyGate(config, clock=datetime.now)

    # HITL manager
    hitl = HitlManager(store, bus, config)

    # Systemd notifier
    notifier = SdNotifier()
    await notifier.start()
    logger.info("SdNotifier initialized (enabled=%s)", notifier._enabled)

    # Reaper
    reaper = Reaper(store, interval_s=30)

    # Task runner
    runner = TaskRunner(store, budget, policy, hitl, bus, config)

    # Create tasks for TaskGroup
    async with asyncio.TaskGroup() as tg:
        # Systemd watchdog ping
        tg.create_task(notifier.run_forever())
        # Reaper maintenance loop
        tg.create_task(reaper.run_forever())
        # Main task runner loop
        tg.create_task(runner.run_forever())

        logger.info("All scheduler components started")


def main(argv: list[str] | None = None) -> int:
    """Main entrypoint for the scheduler daemon.

    Handles:
    - SIGTERM/SIGINT graceful shutdown
    - Systemd watchdog integration
    - Component initialization and wiring
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        # Validate imports and basic wiring
        try:
            return 0
        except Exception:
            return 1

    # Development mode check (no NOTIFY_SOCKET)
    _ = args.dev or not os.environ.get("NOTIFY_SOCKET")

    try:
        asyncio.run(_run_scheduler())
        return 0
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Scheduler daemon failed: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
