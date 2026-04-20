# ARIA Policy Gate
#
# Per blueprint §6.4 and sprint plan W1.2.D.
#
# Responsibilities:
# - Evaluate task policy (allow/ask/deny)
# - Handle quiet hours logic
# - Support payload.policy_override
#
# Usage:
#   from aria.scheduler.policy_gate import PolicyGate, PolicyDecision
#   gate = PolicyGate(config, clock=lambda: datetime.now())
#   decision = gate.evaluate(task)

from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from aria.config import AriaConfig
    from aria.scheduler.schema import Task

logger = logging.getLogger(__name__)


# === Policy Decision ===


class PolicyDecision(Enum):
    """Policy evaluation result."""

    ALLOW = "allow"  # Execute without asking
    ASK = "ask"  # -> HITL flow
    DENY = "deny"  # Never execute
    DEFERRED = "deferred"  # Quiet hours shift


# === Quiet Hours ===


class QuietHours:
    """Quiet hours configuration and helpers."""

    def __init__(
        self,
        start: str = "22:00",
        end: str = "07:00",
        timezone: str = "Europe/Rome",
    ) -> None:
        """Initialize QuietHours.

        Args:
            start: Start time (HH:MM)
            end: End time (HH:MM)
            timezone: Timezone for calculation
        """
        self._start = time.fromisoformat(start)
        self._end = time.fromisoformat(end)
        self._timezone = timezone

    def is_active(self, dt: datetime) -> bool:
        """Check if given datetime is within quiet hours.

        Args:
            dt: Datetime to check

        Returns:
            True if in quiet hours
        """
        # Get local time in configured timezone
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(self._timezone)
            local = dt.astimezone(tz)
            current_time = local.time()
        except Exception:
            # Fallback to UTC
            current_time = dt.astimezone().time()

        start = self._start
        end = self._end

        # Handle overnight (e.g., 22:00-07:00)
        if start <= end:
            return start <= current_time <= end
        else:
            return current_time >= start or current_time <= end

    def end_time(self, dt: datetime) -> datetime:
        """Get the end of quiet hours for a given day.

        Args:
            dt: Reference datetime

        Returns:
            Datetime when quiet hours end
        """
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(self._timezone)
            local = dt.astimezone(tz)
        except Exception:
            tz = UTC
            local = dt.astimezone(tz)

        # End time is same day if start > end (overnight)
        # Otherwise next day
        start = self._start
        end = self._end

        if start <= end:
            # Normal range: end is same day (e.g., 09:00-17:00)
            year, month, day = local.year, local.month, local.day
        # Overnight: end is next day (e.g., 22:00-07:00)
        elif local.time() >= start:
            # Past start, end is next day
            from datetime import timedelta

            next_day = local + timedelta(days=1)
            year, month, day = next_day.year, next_day.month, next_day.day
        else:
            # Before start, end is same day
            year, month, day = local.year, local.month, local.day

        from datetime import datetime as dt2

        return dt2(year, month, day, end.hour, end.minute, tzinfo=tz)


# === Policy Gate ===


class PolicyGate:
    """Policy evaluation gate for task execution.

    Implements the policy rules from blueprint §6.4:
    1. Task policy=allow in quiet hours -> ALLOW (read-only only)
    2. Task policy=ask in quiet hours -> DEFERRED (shift to quiet_hours_end)
    3. Task policy=deny -> DENY always
    4. payload.policy_override takes precedence

    Read-only categories during quiet hours: search, memory
    """

    # Categories considered read-only
    READ_ONLY_CATEGORIES = {"search", "memory"}

    def __init__(
        self,
        config: AriaConfig,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize PolicyGate.

        Args:
            config: ARIA configuration
            clock: Optional clock function (default: datetime.now)
        """
        self._config = config
        self._clock = clock or (datetime.now)

        # Initialize quiet hours from config
        op = config.operational
        self._quiet_hours = QuietHours(
            start=op.quiet_hours_start or "22:00",
            end=op.quiet_hours_end or "07:00",
            timezone=op.timezone,
        )

    def evaluate(self, task: Task, now: datetime | None = None) -> PolicyDecision:
        """Evaluate policy for a task.

        Args:
            task: Task to evaluate
            now: Optional datetime (default: use clock)

        Returns:
            PolicyDecision
        """
        if now is None:
            now = self._clock()

        # Check for explicit override in payload
        override = task.payload.get("policy_override")
        if override and override in ("allow", "ask", "deny"):
            logger.debug("Policy override for task %s: %s", task.id, override)
            return PolicyDecision(override)

        # Get base policy from task
        base_policy = task.policy

        # Deny always blocks
        if base_policy == "deny":
            return PolicyDecision.DENY

        # Check quiet hours
        decision = PolicyDecision.ALLOW
        if self._quiet_hours.is_active(now):
            # In quiet hours
            if base_policy == "allow" and task.category in self.READ_ONLY_CATEGORIES:
                # Allow read-only categories in quiet hours
                logger.info("Task %s allowed in quiet hours (read-only)", task.id)
            elif base_policy == "ask":
                # Defer until quiet hours end
                quiet_end = self._quiet_hours.end_time(now)
                logger.info(
                    "Task %s deferred from quiet hours until %s",
                    task.id,
                    quiet_end,
                )
                decision = PolicyDecision.DEFERRED
            else:
                # Write categories denied during quiet hours
                logger.info(
                    "Task %s denied in quiet hours (category=%s)",
                    task.id,
                    task.category,
                )
                decision = PolicyDecision.DENY
        elif base_policy == "ask":
            decision = PolicyDecision.ASK

        return decision

    def get_deferred_time(self, task: Task, now: datetime | None = None) -> datetime:
        """Get the deferred execution time for a DEFERRED decision.

        Args:
            task: Task that was deferred
            now: Optional datetime (default: use clock)

        Returns:
            Datetime when task should be re-evaluated
        """
        if now is None:
            now = self._clock()

        return self._quiet_hours.end_time(now)


# === Import AriaConfig ===
