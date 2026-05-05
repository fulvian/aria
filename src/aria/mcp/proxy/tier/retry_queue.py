"""Background retry queue for auto-recovery of warm backends.

Backends that fail during warm pool boot or healthcheck are scheduled
for retry with exponential backoff. Successful retries promote the
backend back to the warm pool. Persistent failures after max_attempts
result in permanent quarantine.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("aria.mcp.proxy.tier.retry_queue")

MAX_BACKOFF_S = 60.0


class RetryItem:
    """An item in the retry queue."""

    def __init__(
        self,
        backend_name: str,
        attempt: int = 1,
        max_attempts: int = 10,
    ) -> None:
        self.backend_name = backend_name
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.scheduled_at: float = 0.0

    @property
    def backoff_s(self) -> float:
        """Exponential backoff capped at MAX_BACKOFF_S."""
        return min(2.0 ** (self.attempt - 1), MAX_BACKOFF_S)

    @property
    def is_exhausted(self) -> bool:
        return self.attempt > self.max_attempts


class RetryQueue:
    """Background retry queue with exponential backoff.

    Args:
        on_retry: Async callback(retry_item) called when a retry is due.
            Should return True on success (promote) or False (schedule next).
        on_quarantine: Async callback(retry_item) called when max_attempts exhausted.
    """

    def __init__(
        self,
        on_retry: Callable[[RetryItem], bool | None],
        on_quarantine: Callable[[RetryItem], None] | None = None,
    ) -> None:
        self._queue: asyncio.Queue[RetryItem] = asyncio.Queue()
        self._on_retry = on_retry
        self._on_quarantine = on_quarantine
        self._worker_task: asyncio.Task[None] | None = None
        self._shutdown = False
        self._pending: dict[str, RetryItem] = {}

    def schedule(self, backend_name: str, attempt: int = 1) -> None:
        """Schedule a backend for retry.

        If the backend already has a pending retry, it is updated with
        the higher attempt number.
        """
        if self._shutdown:
            return

        max_attempts = (
            self._pending[backend_name].max_attempts if backend_name in self._pending else 10
        )
        item = RetryItem(
            backend_name=backend_name,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        item.scheduled_at = time.monotonic() + item.backoff_s
        self._pending[backend_name] = item
        self._queue.put_nowait(item)

    async def start(self) -> None:
        """Start the background retry worker."""
        self._shutdown = False
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop the background retry worker."""
        self._shutdown = True
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    async def _worker_loop(self) -> None:
        """Background loop that processes retry items as they become due."""
        while not self._shutdown:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            if self._shutdown:
                return

            # Wait until scheduled time
            now = time.monotonic()
            wait = item.scheduled_at - now
            if wait > 0:
                await asyncio.sleep(wait)

            if item.is_exhausted:
                logger.warning(
                    "retry_queue.exhausted",
                    extra={
                        "backend": item.backend_name,
                        "attempts": item.attempt - 1,
                    },
                )
                self._pending.pop(item.backend_name, None)
                if self._on_quarantine:
                    await asyncio.to_thread(self._on_quarantine, item)
                continue

            try:
                success = await asyncio.to_thread(self._on_retry, item)
                if success:
                    logger.info(
                        "retry_queue.success",
                        extra={
                            "backend": item.backend_name,
                            "attempt": item.attempt,
                        },
                    )
                    self._pending.pop(item.backend_name, None)
                else:
                    # Reschedule with next attempt
                    next_item = RetryItem(
                        backend_name=item.backend_name,
                        attempt=item.attempt + 1,
                        max_attempts=item.max_attempts,
                    )
                    next_item.scheduled_at = time.monotonic() + next_item.backoff_s
                    self._pending[item.backend_name] = next_item
                    self._queue.put_nowait(next_item)
            except Exception as exc:
                logger.error(
                    "retry_queue.error",
                    extra={
                        "backend": item.backend_name,
                        "error": str(exc),
                    },
                )
                # Reschedule on unexpected error
                next_item = RetryItem(
                    backend_name=item.backend_name,
                    attempt=item.attempt + 1,
                    max_attempts=item.max_attempts,
                )
                next_item.scheduled_at = time.monotonic() + next_item.backoff_s
                self._pending[item.backend_name] = next_item
                self._queue.put_nowait(next_item)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def is_pending(self, backend_name: str) -> bool:
        return backend_name in self._pending
