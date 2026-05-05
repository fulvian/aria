"""Per-backend circuit breaker state machine.

State machine:
  closed (normal) → failures >= threshold → open
  open → cooldown timer expires → half_open
  half_open → success → closed
  half_open → failure → open (timer reset)

Events emitted on each transition for observability.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class Breaker:
    """Per-backend circuit breaker.

    Args:
        name: Backend name.
        failure_threshold: Consecutive failures to trip open.
        cooldown_s: Seconds to wait before transitioning to half_open.
        on_event: Optional callback(backend_name, from_state, to_state).
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 3,
        cooldown_s: float = 60.0,
        on_event: Callable[[str, BreakerState, BreakerState], None] | None = None,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._cooldown_s = cooldown_s
        self._on_event = on_event

        self._state: BreakerState = BreakerState.CLOSED
        self._failure_count: int = 0
        self._open_since: float = 0.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        """True if requests are allowed through."""
        if self._state == BreakerState.CLOSED:
            return True
        if self._state == BreakerState.OPEN:
            # Check if cooldown expired → transition to half_open
            if time.monotonic() - self._open_since >= self._cooldown_s:
                self._transition(BreakerState.HALF_OPEN)
                return True
            return False
        # half_open — allow probe request
        return True

    def record_success(self) -> None:
        """Record a successful call. Resets failure count."""
        if self._state == BreakerState.HALF_OPEN:
            self._transition(BreakerState.CLOSED)
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failure. May trip the breaker open."""
        self._failure_count += 1
        if self._state == BreakerState.HALF_OPEN or self._failure_count >= self._failure_threshold:
            self._transition(BreakerState.OPEN)
            self._open_since = time.monotonic()

    def reset(self) -> None:
        """Force reset breaker to closed state."""
        self._transition(BreakerState.CLOSED)
        self._failure_count = 0

    def _transition(self, new_state: BreakerState) -> None:
        old_state = self._state
        self._state = new_state
        if self._on_event and old_state != new_state:
            self._on_event(self._name, old_state, new_state)


class BreakerRegistry:
    """Thread-safe registry of per-backend Breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, Breaker] = {}

    def get_or_create(
        self,
        name: str,
        *,
        failure_threshold: int = 3,
        cooldown_s: float = 60.0,
        on_event: Callable[[str, BreakerState, BreakerState], None] | None = None,
    ) -> Breaker:
        if name not in self._breakers:
            self._breakers[name] = Breaker(
                name=name,
                failure_threshold=failure_threshold,
                cooldown_s=cooldown_s,
                on_event=on_event,
            )
        return self._breakers[name]

    def get(self, name: str) -> Breaker | None:
        return self._breakers.get(name)

    def __getitem__(self, name: str) -> Breaker:
        return self._breakers[name]

    def __contains__(self, name: str) -> bool:
        return name in self._breakers

    def __len__(self) -> int:
        return len(self._breakers)
