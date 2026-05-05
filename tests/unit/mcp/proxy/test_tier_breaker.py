"""Unit tests for the circuit breaker state machine."""

from __future__ import annotations

import time

from aria.mcp.proxy.tier.breaker import Breaker, BreakerRegistry, BreakerState


class TestBreaker:
    def test_initial_state_is_closed(self) -> None:
        b = Breaker("test", failure_threshold=3, cooldown_s=60)
        assert b.state == BreakerState.CLOSED
        assert b.is_closed is True
        assert b.failure_count == 0

    def test_closed_to_open_after_threshold_failures(self) -> None:
        b = Breaker("test", failure_threshold=3, cooldown_s=60)
        assert b.state == BreakerState.CLOSED

        b.record_failure()
        assert b.state == BreakerState.CLOSED
        assert b.failure_count == 1

        b.record_failure()
        assert b.state == BreakerState.CLOSED
        assert b.failure_count == 2

        b.record_failure()
        assert b.state == BreakerState.OPEN
        assert b.failure_count == 3
        assert b.is_closed is False

    def test_open_blocks_requests(self) -> None:
        b = Breaker("test", failure_threshold=1, cooldown_s=60)
        b.record_failure()
        assert b.state == BreakerState.OPEN
        assert b.is_closed is False

    def test_open_to_half_open_after_cooldown(self) -> None:
        b = Breaker("test", failure_threshold=1, cooldown_s=0.01)
        b.record_failure()
        assert b.state == BreakerState.OPEN

        # Wait for cooldown — is_closed triggers transition
        time.sleep(0.02)
        assert b.is_closed is True  # transitions to half_open
        assert b.state == BreakerState.HALF_OPEN

    def test_half_open_success_closes(self) -> None:
        b = Breaker("test", failure_threshold=1, cooldown_s=0.01)
        b.record_failure()
        time.sleep(0.02)
        # Trigger half_open transition via is_closed check
        assert b.is_closed is True
        assert b.state == BreakerState.HALF_OPEN

        b.record_success()
        assert b.state == BreakerState.CLOSED
        assert b.failure_count == 0

    def test_half_open_failure_reopens(self) -> None:
        b = Breaker("test", failure_threshold=1, cooldown_s=0.01)
        b.record_failure()
        time.sleep(0.02)
        # Trigger half_open transition via is_closed check
        _ = b.is_closed
        assert b.state == BreakerState.HALF_OPEN

        b.record_failure()
        assert b.state == BreakerState.OPEN

    def test_success_resets_failure_count(self) -> None:
        b = Breaker("test", failure_threshold=5, cooldown_s=60)
        b.record_failure()
        b.record_failure()
        assert b.failure_count == 2

        b.record_success()
        assert b.failure_count == 0
        assert b.state == BreakerState.CLOSED

    def test_on_event_callback(self) -> None:
        events: list[tuple[str, BreakerState, BreakerState]] = []

        def on_event(name: str, old: BreakerState, new: BreakerState) -> None:
            events.append((name, old, new))

        b = Breaker("test", failure_threshold=1, cooldown_s=0.01, on_event=on_event)
        b.record_failure()
        assert len(events) == 1
        assert events[0] == ("test", BreakerState.CLOSED, BreakerState.OPEN)

        assert b.state == BreakerState.OPEN

        time.sleep(0.02)
        _ = b.is_closed  # trigger half_open transition
        assert len(events) == 2
        assert events[1] == ("test", BreakerState.OPEN, BreakerState.HALF_OPEN)
        assert b.state == BreakerState.HALF_OPEN

        b.record_success()
        assert len(events) == 3
        assert events[2] == ("test", BreakerState.HALF_OPEN, BreakerState.CLOSED)

    def test_reset_force_closes(self) -> None:
        b = Breaker("test", failure_threshold=1, cooldown_s=60)
        b.record_failure()
        assert b.state == BreakerState.OPEN

        b.reset()
        assert b.state == BreakerState.CLOSED
        assert b.failure_count == 0


class TestBreakerRegistry:
    def test_get_or_create_creates_new(self) -> None:
        r = BreakerRegistry()
        b = r.get_or_create("test-backend", failure_threshold=3, cooldown_s=60)
        assert b.name == "test-backend"
        assert b.state == BreakerState.CLOSED

    def test_get_or_create_returns_existing(self) -> None:
        r = BreakerRegistry()
        b1 = r.get_or_create("test", failure_threshold=3, cooldown_s=60)
        b2 = r.get_or_create("test", failure_threshold=5, cooldown_s=30)
        assert b1 is b2  # same instance
        # First-call args win (get_or_create only creates if missing)
        assert b1.failure_count == 0

    def test_contains(self) -> None:
        r = BreakerRegistry()
        assert "x" not in r
        r.get_or_create("x")
        assert "x" in r

    def test_getitem(self) -> None:
        r = BreakerRegistry()
        r.get_or_create("test")
        assert r["test"].name == "test"

    def test_len(self) -> None:
        r = BreakerRegistry()
        assert len(r) == 0
        r.get_or_create("a")
        r.get_or_create("b")
        assert len(r) == 2
