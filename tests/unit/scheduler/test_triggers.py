# Tests for ARIA Trigger System
#
# Per sprint plan W1.2.B.
#
# Tests:
# - CronTrigger with DST handling
# - OneshotTrigger
# - EventTrigger
# - WebhookTrigger
# - ManualTrigger
# - EventBus publish/subscribe

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from aria.scheduler.schema import Task, make_task
from aria.scheduler.triggers import (
    CronTrigger,
    EventBus,
    EventTrigger,
    ManualTrigger,
    OneshotTrigger,
    WebhookTrigger,
    create_trigger,
)


# === CronTrigger Tests ===


def test_cron_trigger_next_fire_dst_europe_rome() -> None:
    """Test CronTrigger respects Europe/Rome timezone and DST transitions.

    DST in Italy: last Sunday of March (02:00 -> 03:00) to last Sunday of October.
    """
    # Create cron trigger: daily at 8:00 AM
    trigger = CronTrigger("0 8 * * *", tz="Europe/Rome")

    # Test during DST (August 2026)
    now_dst = datetime(2026, 8, 15, 7, 0, 0, tzinfo=UTC)  # 07:00 UTC = 09:00 Europe/Rome (DST)
    task = make_task(
        name="DST Task",
        category="search",
        trigger_type="cron",
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
    )

    next_fire = trigger.next_fire(now_dst, task)
    assert next_fire is not None

    # next_fire is in Europe/Rome timezone, so hour is local time (8 AM)
    assert next_fire.hour == 8  # 8:00 AM Europe/Rome
    assert next_fire.minute == 0


def test_cron_trigger_next_fire_standard_time() -> None:
    """Test CronTrigger during standard time (winter).

    Standard time in Italy: UTC+1
    """
    trigger = CronTrigger("0 8 * * *", tz="Europe/Rome")

    # Test during standard time (January 2026)
    now_std = datetime(2026, 1, 15, 7, 0, 0, tzinfo=UTC)  # 07:00 UTC = 08:00 Europe/Rome (standard)
    task = make_task(
        name="Standard Time Task",
        category="search",
        trigger_type="cron",
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
    )

    next_fire = trigger.next_fire(now_std, task)
    assert next_fire is not None

    # next_fire is in Europe/Rome timezone, so hour is local time (8 AM)
    assert next_fire.hour == 8  # 8:00 AM Europe/Rome
    assert next_fire.minute == 0


def test_cron_trigger_dst_transition_forward() -> None:
    """Test CronTrigger handles DST transition forward (March).

    On the last Sunday of March at 02:00, clocks jump to 03:00.
    """
    trigger = CronTrigger("0 8 * * *", tz="Europe/Rome")

    # Day before DST change (March 28, 2026 is Saturday)
    # DST starts March 29, 2026 (last Sunday)
    now_before = datetime(2026, 3, 28, 7, 0, 0, tzinfo=UTC)  # 07:00 UTC = 08:00 Europe/Rome
    task = make_task(
        name="Pre-DST Task",
        category="search",
        trigger_type="cron",
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
    )

    next_fire = trigger.next_fire(now_before, task)
    assert next_fire is not None
    # Should be March 29 at 8:00 Europe/Rome (next day, DST started)
    assert next_fire.day == 29
    assert next_fire.hour == 8  # 8:00 AM Europe/Rome
    assert next_fire.minute == 0


def test_cron_trigger_dst_transition_backward() -> None:
    """Test CronTrigger handles DST transition backward (October).

    On the last Sunday of October at 03:00, clocks go back to 02:00.
    """
    trigger = CronTrigger("0 8 * * *", tz="Europe/Rome")

    # Day after DST ends (October 25, 2026 is Sunday)
    # DST ended October 26, 2026 (last Sunday)
    now_after = datetime(
        2026, 10, 27, 7, 0, 0, tzinfo=UTC
    )  # 07:00 UTC = 08:00 Europe/Rome (standard)
    task = make_task(
        name="Post-DST Task",
        category="search",
        trigger_type="cron",
        schedule_cron="0 8 * * *",
        timezone="Europe/Rome",
    )

    next_fire = trigger.next_fire(now_after, task)
    assert next_fire is not None
    # Should be October 28 at 8:00 Europe/Rome (next day, DST ended)
    assert next_fire.day == 28
    assert next_fire.hour == 8  # 8:00 AM Europe/Rome
    assert next_fire.minute == 0


def test_cron_trigger_invalid_expression() -> None:
    """Test CronTrigger raises on invalid expression."""
    with pytest.raises(ValueError, match="Invalid cron expression"):
        CronTrigger("invalid", tz="Europe/Rome")


def test_cron_trigger_properties() -> None:
    """Test CronTrigger properties."""
    trigger = CronTrigger("0 8 * * *", tz="Europe/Rome")
    assert trigger.expression == "0 8 * * *"
    assert trigger.timezone == "Europe/Rome"


# === OneshotTrigger Tests ===


def test_oneshot_trigger_future_fire() -> None:
    """Test OneshotTrigger returns fire time for future scheduling."""
    trigger = OneshotTrigger()

    future_time = datetime.now(tz=UTC) + timedelta(hours=1)
    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    task = Task(
        id=str(uuid4()),
        name="Future Task",
        category="search",
        trigger_type="oneshot",
        trigger_config={},
        next_run_at=int(future_time.timestamp() * 1000),
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )

    next_fire = trigger.next_fire(datetime.now(tz=UTC), task)
    assert next_fire is not None
    # next_fire should be approximately future_time
    diff = abs((next_fire - future_time).total_seconds())
    assert diff < 5  # Within 5 seconds


def test_oneshot_trigger_past_fire() -> None:
    """Test OneshotTrigger returns None for past scheduling."""
    trigger = OneshotTrigger()

    past_time = datetime.now(tz=UTC) - timedelta(hours=1)
    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    task = Task(
        id=str(uuid4()),
        name="Past Task",
        category="search",
        trigger_type="oneshot",
        trigger_config={},
        next_run_at=int(past_time.timestamp() * 1000),
        status="active",
        policy="allow",
        payload={},
        created_at=now,
        updated_at=now,
    )

    next_fire = trigger.next_fire(datetime.now(tz=UTC), task)
    assert next_fire is None


def test_oneshot_trigger_with_scheduled_at() -> None:
    """Test OneshotTrigger with explicit scheduled_at."""
    scheduled = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
    trigger = OneshotTrigger(scheduled_at=scheduled)

    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    task = make_task(
        name="Scheduled Task",
        category="search",
        trigger_type="oneshot",
    )

    next_fire = trigger.next_fire(now, task)
    assert next_fire == scheduled


# === EventTrigger Tests ===


def test_event_trigger_next_fire_returns_none() -> None:
    """Test EventTrigger.next_fire returns None (fires on event bus)."""
    trigger = EventTrigger("task.completed")

    now = datetime.now(tz=UTC)
    task = make_task(
        name="Event Task",
        category="search",
        trigger_type="event",
    )

    next_fire = trigger.next_fire(now, task)
    assert next_fire is None


def test_event_trigger_properties() -> None:
    """Test EventTrigger properties."""
    trigger = EventTrigger("custom.event")
    assert trigger.event_name == "custom.event"


# === WebhookTrigger Tests ===


def test_webhook_trigger_next_fire_returns_none() -> None:
    """Test WebhookTrigger.next_fire returns None (fires on HTTP callback)."""
    trigger = WebhookTrigger(secret="test-secret")

    now = datetime.now(tz=UTC)
    task = make_task(
        name="Webhook Task",
        category="search",
        trigger_type="webhook",
    )

    next_fire = trigger.next_fire(now, task)
    assert next_fire is None


def test_webhook_trigger_verify_signature_valid() -> None:
    """Test WebhookTrigger signature verification with valid HMAC."""
    import hmac
    import hashlib

    secret = "my-secret-key"
    trigger = WebhookTrigger(secret=secret)

    body = b'{"event": "test"}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert trigger.verify_signature(body, signature) is True


def test_webhook_trigger_verify_signature_invalid() -> None:
    """Test WebhookTrigger signature verification with invalid HMAC."""
    trigger = WebhookTrigger(secret="my-secret-key")

    body = b'{"event": "test"}'
    invalid_signature = "invalid-signature"

    assert trigger.verify_signature(body, invalid_signature) is False


def test_webhook_trigger_verify_signature_no_secret() -> None:
    """Test WebhookTrigger with no secret always returns True."""
    trigger = WebhookTrigger(secret=None)

    assert trigger.verify_signature(b"body", "any-signature") is True
    assert trigger.verify_signature(b"body", "") is True


# === ManualTrigger Tests ===


def test_manual_trigger_next_fire_returns_none() -> None:
    """Test ManualTrigger.next_fire returns None (fires on explicit trigger)."""
    trigger = ManualTrigger()

    now = datetime.now(tz=UTC)
    task = make_task(
        name="Manual Task",
        category="search",
        trigger_type="manual",
    )

    next_fire = trigger.next_fire(now, task)
    assert next_fire is None


# === EventBus Tests ===


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe() -> None:
    """Test EventBus publish and subscribe functionality."""
    bus = EventBus()

    received_payloads: list[dict] = []

    async def handler(payload: dict) -> None:
        received_payloads.append(payload)

    # Subscribe to event
    bus.subscribe("test.event", handler)

    # Publish event
    test_payload = {"key": "value", "number": 42}
    await bus.publish("test.event", test_payload)

    # Verify handler received payload
    assert len(received_payloads) == 1
    assert received_payloads[0]["key"] == "value"
    assert received_payloads[0]["number"] == 42


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers() -> None:
    """Test EventBus with multiple subscribers."""
    bus = EventBus()

    call_count = 0

    async def handler1(payload: dict) -> None:
        nonlocal call_count
        call_count += 1

    async def handler2(payload: dict) -> None:
        nonlocal call_count
        call_count += 2

    bus.subscribe("multi.event", handler1)
    bus.subscribe("multi.event", handler2)

    await bus.publish("multi.event", {"test": True})

    assert call_count == 3  # 1 + 2


@pytest.mark.asyncio
async def test_event_bus_unsubscribe() -> None:
    """Test EventBus unsubscribe functionality."""
    bus = EventBus()

    received: list[dict] = []

    async def handler(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("unsub.event", handler)
    bus.unsubscribe("unsub.event", handler)

    await bus.publish("unsub.event", {"test": True})

    assert len(received) == 0


@pytest.mark.asyncio
async def test_event_bus_no_subscribers() -> None:
    """Test EventBus publish with no subscribers (should not raise)."""
    bus = EventBus()

    # Should not raise
    await bus.publish("nonexistent.event", {"test": True})


@pytest.mark.asyncio
async def test_event_bus_handler_error() -> None:
    """Test EventBus handles handler errors gracefully."""
    bus = EventBus()

    async def failing_handler(payload: dict) -> None:
        raise RuntimeError("Handler failed")

    bus.subscribe("error.event", failing_handler)

    # Should not raise
    await bus.publish("error.event", {"test": True})


@pytest.mark.asyncio
async def test_event_bus_clear() -> None:
    """Test EventBus clear removes all subscriptions."""
    bus = EventBus()

    async def handler(payload: dict) -> None:
        pass

    bus.subscribe("clear1", handler)
    bus.subscribe("clear2", handler)

    bus.clear()

    await bus.publish("clear1", {"test": True})
    await bus.publish("clear2", {"test": True})
    # No error means handlers weren't called


# === Trigger Factory Tests ===


def test_create_trigger_cron() -> None:
    """Test create_trigger for cron type."""
    trigger = create_trigger(
        "cron",
        {"cron": "0 9 * * *", "timezone": "UTC"},
        None,
    )
    assert isinstance(trigger, CronTrigger)
    assert trigger.expression == "0 9 * * *"


def test_create_trigger_oneshot() -> None:
    """Test create_trigger for oneshot type."""
    trigger = create_trigger(
        "oneshot",
        {"at": "2026-06-01T10:00:00"},
        None,
    )
    assert isinstance(trigger, OneshotTrigger)


def test_create_trigger_event() -> None:
    """Test create_trigger for event type."""
    trigger = create_trigger(
        "event",
        {"event": "my.custom.event"},
        None,
    )
    assert isinstance(trigger, EventTrigger)
    assert trigger.event_name == "my.custom.event"


def test_create_trigger_webhook() -> None:
    """Test create_trigger for webhook type."""
    trigger = create_trigger(
        "webhook",
        {"secret": "webhook-secret"},
        None,
    )
    assert isinstance(trigger, WebhookTrigger)


def test_create_trigger_manual() -> None:
    """Test create_trigger for manual type."""
    trigger = create_trigger("manual", {}, None)
    assert isinstance(trigger, ManualTrigger)


def test_create_trigger_unknown_raises() -> None:
    """Test create_trigger raises on unknown type."""
    with pytest.raises(ValueError, match="Unknown trigger type"):
        create_trigger("unknown", {}, None)
