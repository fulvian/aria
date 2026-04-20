# ARIA HITL Manager
#
# Per blueprint §6.4 and sprint plan W1.2.E.
#
# Responsibilities:
# - Create/resolve hitl_pending entries
# - Manage HITL timeouts
# - Publish hitl events to event bus
#
# Usage:
#   from aria.scheduler.hitl import HitlManager
#   hitl = HitlManager(store, bus, config)
#   pending = await hitl.ask(task, run_id, question, options)
#   response = await hitl.wait_for_response(pending.id, timeout_s=900)

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from aria.config import AriaConfig
    from aria.scheduler.schema import HitlPending, Task
    from aria.scheduler.store import TaskStore
    from aria.scheduler.triggers import EventBus

logger = logging.getLogger(__name__)


# === HITL Manager ===


class HitlManager:
    """Human-in-the-loop manager for task approval.

    Handles:
    - Creating hitl_pending entries
    - Publishing hitl.created events to event bus
    - Waiting for user responses
    - Resolving expired HITLs
    """

    DEFAULT_TTL_SECONDS = 900  # 15 minutes

    def __init__(
        self,
        store: TaskStore,
        bus: EventBus,
        config: AriaConfig,
    ) -> None:
        """Initialize HitlManager.

        Args:
            store: TaskStore for persistence
            bus: EventBus for publishing events
            config: ARIA configuration
        """
        self._store = store
        self._bus = bus
        self._config = config
        self._logger = logging.getLogger(__name__)

        # In-memory response waiting map
        self._waiting: dict[str, asyncio.Event] = {}
        self._responses: dict[str, str] = {}

    async def ask(
        self,
        task: Task,
        run_id: str,
        question: str,
        options: list[str] | None = None,
        channel: Literal["telegram", "cli"] = "telegram",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> HitlPending:
        """Create a HITL pending request.

        Args:
            task: Task requiring approval
            run_id: Current run ID
            question: Human-readable question
            options: Optional multiple choice options
            channel: Notification channel (telegram/cli)
            ttl_seconds: Time-to-live in seconds

        Returns:
            Created HitlPending entry
        """
        from aria.scheduler.schema import make_hitl_pending

        now_ms = int(time.time() * 1000)
        expires_ms = now_ms + (ttl_seconds * 1000)

        pending = make_hitl_pending(
            question=question,
            task_id=task.id,
            run_id=run_id,
            ttl_seconds=ttl_seconds,
            channel=channel,
            options=options,
        )

        # Persist to database
        await self._store.create_hitl(pending)

        # Publish event for gateway to consume
        await self._bus.publish(
            "hitl.created",
            {
                "hitl_id": pending.id,
                "task_id": task.id,
                "run_id": run_id,
                "question": question,
                "options": options or [],
                "channel": channel,
                "expires_at": expires_ms,
                "owner_user_id": task.owner_user_id,
            },
        )

        self._logger.info(
            "Created HITL %s for task %s: %s",
            pending.id,
            task.id,
            question[:50],
        )

        # Initialize waiting state
        self._waiting[pending.id] = asyncio.Event()
        self._responses[pending.id] = ""

        return pending

    async def wait_for_response(
        self,
        hitl_id: str,
        timeout_s: int = DEFAULT_TTL_SECONDS,
    ) -> str | None:
        """Wait for user response to HITL request.

        Uses asyncio.Event for efficient waiting.

        Args:
            hitl_id: HITL request ID
            timeout_s: Timeout in seconds

        Returns:
            User response string or None if timeout
        """
        if hitl_id not in self._waiting:
            # Check database for existing HITL
            self._logger.warning("HITL %s not in waiting map, checking store", hitl_id)
            return None

        event = self._waiting[hitl_id]

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_s)
        except TimeoutError:
            self._logger.info("HITL %s timed out waiting for response", hitl_id)
            return None

        response = self._responses.get(hitl_id, "")
        return response if response else None

    async def resolve(
        self,
        hitl_id: str,
        response: str,
    ) -> None:
        """Resolve a HITL request with user response.

        Updates database and notifies waiters.

        Args:
            hitl_id: HITL request ID
            response: User response (yes/no/later/custom)
        """
        now_ms = int(time.time() * 1000)

        # Update database
        updated = await self._store.resolve_hitl(hitl_id, response)

        if not updated:
            self._logger.warning("HITL %s not found for resolution", hitl_id)
            return

        # Notify waiters
        if hitl_id in self._waiting:
            self._responses[hitl_id] = response
            self._waiting[hitl_id].set()

        # Publish resolution event
        await self._bus.publish(
            "hitl.resolved",
            {
                "hitl_id": hitl_id,
                "response": response,
                "resolved_at": now_ms,
            },
        )

        self._logger.info("Resolved HITL %s with response: %s", hitl_id, response)

    async def expire_stale(self) -> list[str]:
        """Find and expire stale HITL requests.

        Returns:
            List of expired HITL IDs
        """
        now_ms = int(time.time() * 1000)

        # Get expired entries
        expired = await self._store.expire_hitl(now_ms)

        expired_ids = []
        for hitl in expired:
            expired_ids.append(hitl.id)

            # Notify waiters of timeout
            if hitl.id in self._waiting:
                self._responses[hitl.id] = ""  # Empty = timeout
                self._waiting[hitl.id].set()

        if expired_ids:
            self._logger.info("Expired %d stale HITL entries", len(expired_ids))

        return expired_ids

    def clear_completed(self, hitl_id: str) -> None:
        """Clear internal state for completed HITL.

        Called after response is processed.

        Args:
            hitl_id: HITL ID to clear
        """
        self._waiting.pop(hitl_id, None)
        self._responses.pop(hitl_id, None)


# === Import TaskStore ===
