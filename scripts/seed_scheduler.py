#!/usr/bin/env python3
"""
ARIA Scheduler Seed Script

Seeds the scheduler with default tasks for Sprint 1.4:
- daily-email-triage (08:00 daily)
- weekly-backup (03:00 Sunday)
- blueprint-review (10:00 Sunday, deny policy)

Per sprint plan W1.4.H.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to path for imports
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from croniter import croniter

from aria.config import get_config
from aria.scheduler.schema import make_task
from aria.scheduler.store import TaskStore


# === Seed Data ===

SEED_TASKS = [
    {
        "id": "seed-daily-email-triage",
        "name": "daily-email-triage",
        "category": "workspace",
        "trigger_type": "cron",
        "trigger_config": {"cron": "0 8 * * *", "timezone": "Europe/Rome"},
        "schedule_cron": "0 8 * * *",
        "timezone": "Europe/Rome",
        "status": "active",
        "policy": "allow",
        "budget_tokens": 30000,
        "budget_cost_eur": 0.05,
        "max_retries": 3,
        "payload": {
            "sub_agent": "workspace-agent",
            "skill": "triage-email",
            "trace_prefix": "daily-triage",
        },
    },
    {
        "id": "seed-weekly-backup",
        "name": "weekly-backup",
        "category": "system",
        "trigger_type": "cron",
        "trigger_config": {"cron": "0 3 * * 0", "timezone": "Europe/Rome"},
        "schedule_cron": "0 3 * * 0",
        "timezone": "Europe/Rome",
        "status": "active",
        "policy": "allow",
        "budget_tokens": 5000,
        "budget_cost_eur": 0.01,
        "max_retries": 3,
        "payload": {"command": "scripts/backup.sh"},
    },
    {
        "id": "seed-blueprint-review",
        "name": "blueprint-review",
        "category": "system",
        "trigger_type": "cron",
        "trigger_config": {"cron": "0 10 * * 0", "timezone": "Europe/Rome"},
        "schedule_cron": "0 10 * * 0",
        "timezone": "Europe/Rome",
        "status": "active",
        "policy": "deny",  # Stub only, not active until Phase 2
        "budget_tokens": 20000,
        "budget_cost_eur": 0.02,
        "max_retries": 1,
        "payload": {"sub_agent": "blueprint-keeper"},
    },
]


async def seed_tasks() -> int:
    """Seed the scheduler with default tasks."""
    config = get_config()
    db_path = config.paths.runtime / "scheduler" / "scheduler.db"

    store = TaskStore(db_path)
    await store.connect()

    try:
        seeded = 0
        for task_data in SEED_TASKS:
            # Calculate next run time
            cron = task_data["schedule_cron"]
            now = datetime.now(tz=UTC)
            next_run_dt = croniter(cron, now).get_next(datetime)
            next_run_at = int(next_run_dt.timestamp() * 1000)

            # Check if task already exists
            existing = await store.get_task(task_data["id"])
            if existing:
                print(f"Task '{task_data['name']}' already exists, skipping")
                continue

            # Create task
            task = make_task(
                name=task_data["name"],
                category=task_data["category"],
                trigger_type=task_data["trigger_type"],
                payload=task_data["payload"],
                schedule_cron=task_data["schedule_cron"],
                policy=task_data["policy"],
                timezone=task_data["timezone"],
                trigger_config=task_data["trigger_config"],
            )
            task.id = task_data["id"]
            task.next_run_at = next_run_at
            task.budget_tokens = task_data["budget_tokens"]
            task.budget_cost_eur = task_data["budget_cost_eur"]
            task.max_retries = task_data["max_retries"]
            task.status = task_data["status"]

            await store.create_task(task)
            seeded += 1
            print(
                f"Seeded: {task_data['name']} (next run: {next_run_dt.strftime('%Y-%m-%d %H:%M')})"
            )

        print(f"\nSeeded {seeded} new task(s)")
        return 0

    finally:
        await store.close()


def main() -> int:
    """Main entry point."""
    try:
        return asyncio.run(seed_tasks())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
