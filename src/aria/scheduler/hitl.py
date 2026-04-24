# Scheduler HITL — Human-In-The-Loop integration
#
# Per blueprint §6 and memory gap remediation plan.
#
# Provides HITL management for tasks requiring human approval.
#
# Usage:
#   from aria.scheduler.hitl import HitlManager
#
#   hitl = HitlManager(task_store, bus, config)
#   await hitl.resolve(hitl_id, response)

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aria.scheduler.store import HitlRequest

if TYPE_CHECKING:
    from aria.config import ARIAConfig
    from aria.scheduler.store import TaskStore
    from aria.scheduler.triggers import EventBus

logger = logging.getLogger(__name__)


class HitlManager:
    """Human-In-The-Loop manager for task approval."""

    def __init__(
        self,
        store: TaskStore,
        bus: EventBus,
        config: ARIAConfig,
    ) -> None:
        """Initialize HitlManager.

        Args:
            store: TaskStore instance
            bus: EventBus for publishing events
            config: AriaConfig instance
        """
        self._store = store
        self._bus = bus
        self._config = config

    async def enqueue(self, task_id: str, reason: str, trace_id: str | None = None) -> HitlRequest:
        """Enqueue a task for HITL approval."""
        import uuid

        req = HitlRequest(
            id=str(uuid.uuid4()),
            target_id=task_id,
            action="approve_task",
            reason=reason,
            trace_id=trace_id,
            channel="scheduler",
        )
        await self._store.create_hitl_request(req)
        await self._bus.hitl_created(req.id, task_id, req.action)
        logger.info("HITL request enqueued: %s for task %s", req.id, task_id)
        return req

    async def resolve(self, hitl_id: str, response: str) -> bool:
        """Resolve a HITL request.

        Args:
            hitl_id: The HITL request ID
            response: The user's response

        Returns:
            True if resolved successfully
        """
        import time

        now = int(time.time() * 1000)
        status = "approved" if response.lower() in ("approve", "yes", "allow") else "rejected"
        result = await self._store.resolve_hitl(hitl_id, status, now)
        if result:
            await self._bus.hitl_resolved(hitl_id, response)
            logger.info("HITL request %s resolved: %s", hitl_id, status)
        return result

    async def list_pending(self, limit: int = 50) -> list[dict]:
        """List pending HITL requests."""
        return await self._store.list_hitl_pending(limit)
