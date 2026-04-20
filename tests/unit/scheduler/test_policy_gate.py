# Tests for ARIA Policy Gate
#
# Per sprint plan W1.2.D.
#
# Tests:
# - Policy allow/ask/deny evaluation
# - Quiet hours logic
# - Policy override from payload

from __future__ import annotations

from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from aria.scheduler.policy_gate import PolicyDecision, PolicyGate, QuietHours
from aria.scheduler.schema import make_task


class MockOperationalConfig:
    """Mock operational configuration."""

    def __init__(
        self,
        quiet_hours_start: str = "22:00",
        quiet_hours_end: str = "07:00",
        timezone: str = "Europe/Rome",
    ) -> None:
        self.quiet_hours_start = quiet_hours_start
        self.quiet_hours_end = quiet_hours_end
        self.timezone = timezone


class MockConfig:
    """Mock configuration for testing."""

    def __init__(
        self,
        quiet_hours_start: str = "22:00",
        quiet_hours_end: str = "07:00",
        timezone: str = "Europe/Rome",
    ) -> None:
        self.operational = MockOperationalConfig(
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            timezone=timezone,
        )


# === QuietHours Tests ===


class TestQuietHours:
    """Tests for QuietHours class."""

    def test_quiet_hours_overnight(self) -> None:
        """Test quiet hours handling overnight (22:00-07:00)."""
        qh = QuietHours(start="22:00", end="07:00", timezone="Europe/Rome")

        # 23:00 should be in quiet hours
        import zoneinfo

        tz = zoneinfo.ZoneInfo("Europe/Rome")
        late_night = datetime(2026, 4, 20, 23, 0, 0, tzinfo=tz)
        assert qh.is_active(late_night) is True

        # 03:00 should be in quiet hours
        early_morning = datetime(2026, 4, 20, 3, 0, 0, tzinfo=tz)
        assert qh.is_active(early_morning) is True

        # 12:00 should NOT be in quiet hours
        midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)
        assert qh.is_active(midday) is False

    def test_quiet_hours_normal_range(self) -> None:
        """Test quiet hours with normal daytime range (e.g., 09:00-17:00)."""
        qh = QuietHours(start="09:00", end="17:00", timezone="UTC")

        # 10:00 should be in quiet hours
        morning = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
        assert qh.is_active(morning) is True

        # 20:00 should NOT be in quiet hours
        evening = datetime(2026, 4, 20, 20, 0, 0, tzinfo=UTC)
        assert qh.is_active(evening) is False

    def test_quiet_hours_end_time_same_day(self) -> None:
        """Test end_time for quiet hours ending same day."""
        qh = QuietHours(start="09:00", end="17:00", timezone="UTC")

        from datetime import datetime as dt2

        now = dt2(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
        end = qh.end_time(now)

        assert end.hour == 17
        assert end.minute == 0
        assert end.day == 20  # Same day

    def test_quiet_hours_end_time_overnight(self) -> None:
        """Test end_time for overnight quiet hours."""
        qh = QuietHours(start="22:00", end="07:00", timezone="UTC")

        from datetime import datetime as dt2

        # After midnight but before quiet hours end
        late_night = dt2(2026, 4, 20, 2, 0, 0, tzinfo=UTC)
        end = qh.end_time(late_night)

        # End should be 07:00 same day
        assert end.hour == 7
        assert end.day == 20

    def test_quiet_hours_end_time_before_end(self) -> None:
        """Test end_time when current time is before quiet hours end."""
        qh = QuietHours(start="22:00", end="07:00", timezone="UTC")

        from datetime import datetime as dt2

        # Evening before quiet hours
        evening = dt2(2026, 4, 20, 23, 30, 0, tzinfo=UTC)
        end = qh.end_time(evening)

        # End should be 07:00 next day
        assert end.hour == 7
        assert end.day == 21  # Next day


# === PolicyGate Tests ===


@pytest.fixture
def mock_config() -> MockConfig:
    """Create mock configuration."""
    return MockConfig(
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        timezone="Europe/Rome",
    )


@pytest.fixture
def policy_gate(mock_config: MockConfig) -> PolicyGate:
    """Create PolicyGate instance."""
    return PolicyGate(mock_config)


def test_policy_gate_policy_allow_always(
    policy_gate: PolicyGate,
) -> None:
    """Test policy=allow always returns ALLOW outside quiet hours."""
    # Outside quiet hours: 12:00 Europe/Rome
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Allow Task",
        category="search",
        trigger_type="cron",
        policy="allow",
    )

    decision = policy_gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.ALLOW


def test_policy_gate_policy_ask_triggers_hitl(
    policy_gate: PolicyGate,
) -> None:
    """Test policy=ask returns ASK (triggers HITL flow)."""
    # Outside quiet hours
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Ask Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )

    decision = policy_gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.ASK


def test_policy_gate_policy_deny_always(
    policy_gate: PolicyGate,
) -> None:
    """Test policy=deny always returns DENY."""
    # Any time
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Deny Task",
        category="search",
        trigger_type="cron",
        policy="deny",
    )

    decision = policy_gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.DENY


def test_policy_gate_quiet_hours_allow_readonly(
    policy_gate: PolicyGate,
) -> None:
    """Test read-only categories allowed during quiet hours."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    late_night = datetime(2026, 4, 20, 23, 0, 0, tzinfo=tz)

    # search is read-only
    task = make_task(
        name="Quiet Hours Search Task",
        category="search",
        trigger_type="cron",
        policy="allow",
    )

    decision = policy_gate.evaluate(task, now=late_night)
    assert decision == PolicyDecision.ALLOW


def test_policy_gate_quiet_hours_deny_write_category(
    policy_gate: PolicyGate,
) -> None:
    """Test write categories denied during quiet hours."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    late_night = datetime(2026, 4, 20, 23, 0, 0, tzinfo=tz)

    # workspace is NOT read-only
    task = make_task(
        name="Quiet Hours Workspace Task",
        category="workspace",
        trigger_type="cron",
        policy="allow",
    )

    decision = policy_gate.evaluate(task, now=late_night)
    assert decision == PolicyDecision.DENY


def test_policy_gate_quiet_hours_defer_ask(
    policy_gate: PolicyGate,
) -> None:
    """Test policy=ask during quiet hours returns DEFERRED."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    late_night = datetime(2026, 4, 20, 23, 0, 0, tzinfo=tz)

    task = make_task(
        name="Quiet Hours Ask Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )

    decision = policy_gate.evaluate(task, now=late_night)
    assert decision == PolicyDecision.DEFERRED


def test_policy_gate_quiet_hours_memory_readonly(
    policy_gate: PolicyGate,
) -> None:
    """Test memory category is read-only during quiet hours."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    late_night = datetime(2026, 4, 20, 23, 0, 0, tzinfo=tz)

    task = make_task(
        name="Quiet Hours Memory Task",
        category="memory",
        trigger_type="cron",
        policy="allow",
    )

    decision = policy_gate.evaluate(task, now=late_night)
    assert decision == PolicyDecision.ALLOW


def test_policy_gate_policy_override_allow(
    mock_config: MockConfig,
) -> None:
    """Test policy_override in payload takes precedence."""
    gate = PolicyGate(mock_config)

    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Override Task",
        category="workspace",
        trigger_type="cron",
        policy="deny",  # Base policy is deny
        payload={"policy_override": "allow"},  # But override says allow
    )

    decision = gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.ALLOW


def test_policy_gate_policy_override_deny(
    mock_config: MockConfig,
) -> None:
    """Test policy_override can force deny."""
    gate = PolicyGate(mock_config)

    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Override Task",
        category="search",
        trigger_type="cron",
        policy="allow",  # Base policy is allow
        payload={"policy_override": "deny"},  # But override says deny
    )

    decision = gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.DENY


def test_policy_gate_policy_override_ask(
    mock_config: MockConfig,
) -> None:
    """Test policy_override can force ask."""
    gate = PolicyGate(mock_config)

    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Override Task",
        category="search",
        trigger_type="cron",
        policy="allow",
        payload={"policy_override": "ask"},
    )

    decision = gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.ASK


def test_policy_gate_invalid_override_ignored(
    policy_gate: PolicyGate,
) -> None:
    """Test invalid policy_override values are ignored."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    midday = datetime(2026, 4, 20, 12, 0, 0, tzinfo=tz)

    task = make_task(
        name="Invalid Override Task",
        category="search",
        trigger_type="cron",
        policy="allow",
        payload={"policy_override": "invalid_value"},
    )

    # Should use base policy, not crash
    decision = policy_gate.evaluate(task, now=midday)
    assert decision == PolicyDecision.ALLOW


def test_policy_gate_get_deferred_time(
    policy_gate: PolicyGate,
) -> None:
    """Test get_deferred_time returns quiet hours end."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")
    late_night = datetime(2026, 4, 20, 23, 30, 0, tzinfo=tz)

    task = make_task(
        name="Deferred Task",
        category="workspace",
        trigger_type="cron",
        policy="ask",
    )

    deferred_time = policy_gate.get_deferred_time(task, now=late_night)

    # Should be 07:00 next day
    assert deferred_time.hour == 7
    assert deferred_time.minute == 0


def test_policy_gate_default_clock(
    mock_config: MockConfig,
) -> None:
    """Test PolicyGate uses default clock (datetime.now) when not provided."""
    gate = PolicyGate(mock_config)

    # Should not raise even with no clock provided
    task = make_task(
        name="Default Clock Task",
        category="search",
        trigger_type="cron",
        policy="allow",
    )

    decision = gate.evaluate(task)
    assert decision == PolicyDecision.ALLOW


# === PolicyDecision Enum Tests ===


def test_policy_decision_values() -> None:
    """Test PolicyDecision enum values."""
    assert PolicyDecision.ALLOW.value == "allow"
    assert PolicyDecision.ASK.value == "ask"
    assert PolicyDecision.DENY.value == "deny"
    assert PolicyDecision.DEFERRED.value == "deferred"


# === Integration Tests for Quiet Hours DST ===


def test_policy_gate_quiet_hours_dst_transition(
    mock_config: MockConfig,
) -> None:
    """Test policy evaluation across DST transition."""
    gate = PolicyGate(mock_config)

    import zoneinfo

    tz = zoneinfo.ZoneInfo("Europe/Rome")

    # March 30, 2026 - DST just started (clocks went forward March 29)
    # 23:00 local = 21:00 UTC (before DST was 22:00 UTC)
    during_dst = datetime(2026, 3, 30, 23, 0, 0, tzinfo=tz)

    task = make_task(
        name="DST Task",
        category="search",
        trigger_type="cron",
        policy="allow",
    )

    # Should be in quiet hours (23:00 local)
    decision = gate.evaluate(task, now=during_dst)
    assert decision == PolicyDecision.ALLOW  # search is read-only


def test_policy_gate_read_only_categories(
    mock_config: MockConfig,
) -> None:
    """Test that correct categories are marked as read-only."""
    gate = PolicyGate(mock_config)

    assert "search" in gate.READ_ONLY_CATEGORIES
    assert "memory" in gate.READ_ONLY_CATEGORIES
    assert "workspace" not in gate.READ_ONLY_CATEGORIES
    assert "custom" not in gate.READ_ONLY_CATEGORIES
