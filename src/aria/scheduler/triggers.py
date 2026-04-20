# ARIA Trigger System
#
# Per blueprint §6.2 and sprint plan W1.2.B.
#
# Provides:
# - Trigger protocol and implementations
# - CronTrigger: cron expression with timezone support
# - OneshotTrigger: single execution
# - EventTrigger: event-driven
# - WebhookTrigger: HTTP callback
# - ManualTrigger: CLI/manual trigger
# - EventBus: in-process pub/sub
#
# Usage:
#   from aria.scheduler.triggers import CronTrigger, EventBus
#   trigger = CronTrigger("0 8 * * *", "Europe/Rome")
#   next_fire = trigger.next_fire(now, task)

from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.scheduler.schema import Task

logger = logging.getLogger(__name__)


# === Trigger Protocol ===


class Trigger(ABC):
    """Abstract base class for trigger implementations."""

    @abstractmethod
    def next_fire(self, now: datetime, task: Task) -> datetime | None:
        """Calculate the next fire time for a task.

        Args:
            now: Current time
            task: Task to evaluate

        Returns:
            Next fire datetime or None if trigger is exhausted/inactive
        """
        ...


# === Cron Trigger ===


class CronTrigger(Trigger):
    """Cron-based trigger with timezone support.

    Uses croniter library for accurate next-fire calculation
    respecting timezone and DST transitions.
    """

    # Cron expression validation (5 fields: min hour day month dow)
    CRON_PATTERN = re.compile(
        r"^(\*|[0-5]?\d)\s+(\*|[01]?\d|2[0-3])\s+(\*|[1-9]|[12]\d|3[01])\s+"
        r"(\*|[1-9]|1[0-2])\s+(\*|[0-6])$"
    )

    def __init__(self, expr: str, tz: str = "Europe/Rome") -> None:
        """Initialize CronTrigger.

        Args:
            expr: Cron expression (5 fields: min hour day month dow)
            tz: Timezone identifier (e.g., "Europe/Rome", "UTC")

        Raises:
            ValueError: If expression is invalid
        """
        if not self.CRON_PATTERN.match(expr):
            raise ValueError(f"Invalid cron expression: {expr}")

        self._expr = expr
        self._tz = tz

    @property
    def expression(self) -> str:
        """Get cron expression."""
        return self._expr

    @property
    def timezone(self) -> str:
        """Get timezone."""
        return self._tz

    def next_fire(self, now: datetime, task: Task) -> datetime | None:
        """Calculate next fire time for cron expression.

        Args:
            now: Current time
            task: Task with schedule information

        Returns:
            Next fire datetime
        """
        from croniter import croniter

        # Get timezone
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(self._tz)
        except Exception:
            logger.warning("Invalid timezone %s, falling back to UTC", self._tz)
            tz = UTC

        # Create croniter with current time
        current = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
        cron = croniter(self._expr, current, tz)

        # Get next fire time (after current time)
        return cron.get_next(datetime)


# === Oneshot Trigger ===


class OneshotTrigger(Trigger):
    """Single execution trigger.

    Fires once at the scheduled time, then marks task as completed.
    """

    def __init__(self, scheduled_at: datetime | None = None) -> None:
        """Initialize OneshotTrigger.

        Args:
            scheduled_at: Fixed execution time (if None, use task's next_run_at)
        """
        self._scheduled_at = scheduled_at

    def next_fire(self, now: datetime, task: Task) -> datetime | None:
        """Return the oneshot fire time.

        Args:
            now: Current time
            task: Task to evaluate

        Returns:
            Scheduled datetime or None if past
        """
        if self._scheduled_at:
            fire_time = self._scheduled_at
        elif task.next_run_at:
            fire_time = datetime.fromtimestamp(task.next_run_at / 1000, tz=UTC)
        else:
            return None

        # If scheduled time is in the future, return it
        if fire_time > now:
            return fire_time

        # Already fired - return None
        return None


# === Event Trigger ===


class EventTrigger(Trigger):
    """Event-driven trigger.

    Fires on event bus publication rather than schedule.
    next_fire returns None as it fires on-demand.
    """

    def __init__(self, event_name: str) -> None:
        """Initialize EventTrigger.

        Args:
            event_name: Name of event to listen for
        """
        self._event_name = event_name

    @property
    def event_name(self) -> str:
        """Get event name."""
        return self._event_name

    def next_fire(self, now: datetime, task: Task) -> None:
        """Event triggers fire on-demand, not on schedule.

        Args:
            now: Current time
            task: Task to evaluate

        Returns:
            None (fires on event bus publication)
        """
        return


# === Webhook Trigger ===


class WebhookTrigger(Trigger):
    """Webhook trigger for external HTTP callbacks.

    Validates HMAC signatures for security and fires on
    authenticated webhook calls.
    """

    def __init__(
        self,
        secret: str | None = None,
        allowed_sources: list[str] | None = None,
    ) -> None:
        """Initialize WebhookTrigger.

        Args:
            secret: HMAC secret for signature validation
            allowed_sources: List of allowed source IPs/CIDRs
        """
        self._secret = secret
        self._allowed_sources = allowed_sources or []

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature.

        Args:
            body: Request body bytes
            signature: Expected signature (hex-encoded)

        Returns:
            True if signature is valid
        """
        if not self._secret:
            return True

        if not signature:
            return False

        expected = hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()

        return hmac.compare_digest(expected, signature)

    def next_fire(self, now: datetime, task: Task) -> None:
        """Webhook triggers fire on HTTP callback, not on schedule.

        Args:
            now: Current time
            task: Task to evaluate

        Returns:
            None (fires on webhook request)
        """
        return


# === Manual Trigger ===


class ManualTrigger(Trigger):
    """Manual trigger for CLI/Telegram commands.

    Only fires via explicit trigger, not on schedule.
    """

    def next_fire(self, now: datetime, task: Task) -> None:
        """Manual triggers fire on explicit command, not on schedule.

        Args:
            now: Current time
            task: Task to evaluate

        Returns:
            None (fires on manual trigger)
        """
        return


# === Event Bus ===

Callback = Callable[[dict], Awaitable[None]]


class EventBus:
    """In-process publish/subscribe event bus.

    Provides lightweight event communication between components.
    Not persisted - events are transient.
    """

    def __init__(self) -> None:
        """Initialize EventBus."""
        self._subscribers: dict[str, list[Callback]] = {}
        self._logger = logging.getLogger(__name__ + ".EventBus")

    def subscribe(self, event: str, callback: Callback) -> None:
        """Subscribe to an event.

        Args:
            event: Event name
            callback: Async callback function
        """
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)
        self._logger.debug("Subscribed to event: %s", event)

    def unsubscribe(self, event: str, callback: Callback) -> None:
        """Unsubscribe from an event.

        Args:
            event: Event name
            callback: Callback to remove
        """
        if event in self._subscribers:
            with contextlib.suppress(ValueError):
                self._subscribers[event].remove(callback)

    async def publish(self, event: str, payload: dict) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event name
            payload: Event payload data
        """
        self._logger.debug("Publishing event: %s", event)

        if event not in self._subscribers:
            return

        for callback in self._subscribers[event]:
            try:
                await callback(payload)
            except Exception as e:
                self._logger.error("Error in event handler for %s: %s", event, e)

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._subscribers.clear()


# === Trigger Factory ===


def create_trigger(
    trigger_type: str,
    trigger_config: dict,
    task: Task | None = None,
) -> Trigger:
    """Create a trigger instance from configuration.

    Args:
        trigger_type: Type of trigger
        trigger_config: Trigger configuration dict
        task: Optional task for context

    Returns:
        Trigger instance

    Raises:
        ValueError: If trigger type is unknown
    """
    match trigger_type:
        case "cron":
            expr = trigger_config.get("cron", "* * * * *")
            tz = trigger_config.get("timezone", "Europe/Rome")
            return CronTrigger(expr, tz)

        case "oneshot":
            scheduled_at = None
            if "at" in trigger_config:
                scheduled_at = datetime.fromisoformat(trigger_config["at"])
            return OneshotTrigger(scheduled_at)

        case "event":
            event_name = trigger_config.get("event", "manual")
            return EventTrigger(event_name)

        case "webhook":
            secret = trigger_config.get("secret")
            allowed = trigger_config.get("allowed_sources", [])
            return WebhookTrigger(secret, allowed)

        case "manual":
            return ManualTrigger()

        case _:
            raise ValueError(f"Unknown trigger type: {trigger_type}")


# === Trigger Events ===


class TriggerEvents:
    """Standard event names for trigger system."""

    # Memory events
    SEMANTIC_THRESHOLD = "memory.semantic_threshold"

    # Task events
    DLQ_NEW = "task.dlq.new"

    # Credential events
    CREDENTIAL_ROTATION_NEEDED = "credential.rotation_needed"

    # Gateway events
    USER_MESSAGE = "gateway.user_message"

    # HITL events
    HITL_CREATED = "hitl.created"
    HITL_RESOLVED = "hitl.resolved"

    # System events
    SYSTEM_EVENT = "system_event"
