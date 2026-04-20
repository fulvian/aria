# ARIA scheduler module
#
# Provides autonomous task scheduling with:
# - Cron, event, webhook, oneshot, manual triggers
# - Budget gate (tokens, cost per run/category)
# - Policy gate (allow, ask, deny with HITL)
# - Dead Letter Queue with retry logic
# - sd_notify watchdog integration
#
# Usage:
#   from aria.scheduler import SchedulerDaemon
#   daemon = SchedulerDaemon(db_path=path)

from __future__ import annotations

__all__ = ["SchedulerDaemon"]


class SchedulerDaemon:
    """Scheduler daemon stub - full implementation in Phase 1."""

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize scheduler daemon."""
        pass

    def add_task(self, name: str, **kwargs: object) -> dict:
        """Add a new task."""
        return {"id": "stub", "name": name}

    def list_tasks(self, **kwargs: object) -> list[dict]:
        """List all tasks."""
        return []

    def run_task(self, task_id: str) -> dict:
        """Run a specific task."""
        return {"id": task_id, "outcome": "stub"}
