# Scheduler Triggers — Event system for scheduler
#
# Per blueprint §6 and memory gap remediation plan.
#
# Provides:
# - EventBus: simple pub/sub for scheduler events
# - Event types for task lifecycle
#
# Usage:
#   from aria.scheduler.triggers import EventBus
#
#   bus = EventBus()
#   bus.subscribe("task.completed", handler)

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Simple async event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], Any]]] = {}

    def subscribe(
        self,
        event: str,
        handler: Callable[[dict[str, Any]], Any],
    ) -> None:
        """Subscribe to an event.

        Args:
            event: Event name (e.g., "task.completed", "hitl.created")
            handler: Async function that handles the event payload
        """
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(handler)
        logger.debug("Subscribed handler to event: %s", event)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event."""
        if event in self._subscribers:
            self._subscribers[event] = [h for h in self._subscribers[event] if h != handler]

    async def publish(self, event: str, payload: dict[str, Any]) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event name
            payload: Event payload data
        """
        if event not in self._subscribers:
            logger.debug("No subscribers for event: %s", event)
            return

        logger.debug("Publishing event: %s with payload: %s", event, payload)
        for handler in self._subscribers[event]:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Error in event handler for %s: %s", event, e)

    # === Common Event Types ===

    async def task_completed(self, task_id: str, result: str) -> None:
        """Publish task completed event."""
        await self.publish("task.completed", {"task_id": task_id, "result": result})

    async def task_failed(self, task_id: str, error: str) -> None:
        """Publish task failed event."""
        await self.publish("task.failed", {"task_id": task_id, "error": error})

    async def hitl_created(self, hitl_id: str, target_id: str, action: str) -> None:
        """Publish HITL created event."""
        await self.publish(
            "hitl.created",
            {
                "hitl_id": hitl_id,
                "target_id": target_id,
                "action": action,
            },
        )

    async def hitl_resolved(self, hitl_id: str, response: str) -> None:
        """Publish HITL resolved event."""
        await self.publish("hitl.resolved", {"hitl_id": hitl_id, "response": response})
