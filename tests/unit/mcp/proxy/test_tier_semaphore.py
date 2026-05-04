"""Unit tests for the concurrency limiter."""

from __future__ import annotations

import asyncio

import pytest

from aria.mcp.proxy.tier.semaphore import (
    BackendBackpressureError,
    ConcurrencyRegistry,
    acquire_with_timeout,
)


class TestConcurrencyRegistry:
    def test_get_or_create_creates_new(self) -> None:
        r = ConcurrencyRegistry()
        entry = r.get_or_create("test", max_concurrency=2)
        assert entry.max_concurrency == 2
        assert not entry.semaphore.locked()

    def test_get_or_create_returns_existing(self) -> None:
        r = ConcurrencyRegistry()
        e1 = r.get_or_create("test", max_concurrency=2)
        e2 = r.get_or_create("test", max_concurrency=5)
        assert e1 is e2
        assert e1.max_concurrency == 2  # first creation wins

    def test_limit_for_returns_semaphore(self) -> None:
        r = ConcurrencyRegistry()
        sem = r.limit_for("test")
        assert sem is not None
        assert isinstance(sem, asyncio.Semaphore)

    def test_contains(self) -> None:
        r = ConcurrencyRegistry()
        assert "test" not in r
        r.get_or_create("test")
        assert "test" in r


@pytest.mark.asyncio
async def test_acquire_with_timeout_succeeds() -> None:
    sem = asyncio.Semaphore(1)
    await acquire_with_timeout(sem, "test", timeout_s=5.0)
    sem.release()


@pytest.mark.asyncio
async def test_acquire_with_timeout_blocks_then_succeeds() -> None:
    sem = asyncio.Semaphore(1)
    await sem.acquire()  # lock it

    async def release_later() -> None:
        await asyncio.sleep(0.05)
        sem.release()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(release_later())
        await acquire_with_timeout(sem, "test", timeout_s=5.0)


@pytest.mark.asyncio
async def test_acquire_with_timeout_raises_on_timeout() -> None:
    sem = asyncio.Semaphore(1)
    await sem.acquire()  # lock it permanently

    with pytest.raises(BackendBackpressureError):
        await acquire_with_timeout(sem, "test", timeout_s=0.05)


@pytest.mark.asyncio
async def test_concurrency_limit_enforced() -> None:
    """N concurrent acquires allowed, N+1 blocks."""
    sem = asyncio.Semaphore(2)

    # Acquire both slots
    await sem.acquire()
    await sem.acquire()
    assert sem.locked()

    # Third acquire should time out
    with pytest.raises(BackendBackpressureError):
        await acquire_with_timeout(sem, "test", timeout_s=0.05)

    # Release one slot
    sem.release()

    # Now acquire should succeed
    await acquire_with_timeout(sem, "test", timeout_s=0.05)
    sem.release()
    sem.release()
