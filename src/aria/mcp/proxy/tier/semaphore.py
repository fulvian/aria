"""Per-backend concurrency limiter using asyncio.Semaphore.

Provides a registry of semaphores keyed by backend name, with
configurable acquire timeout that raises BackendBackpressureError.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


class BackendBackpressureError(Exception):
    """Raised when the acquire on a backend semaphore times out."""


@dataclass
class SemaphoreEntry:
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(4))
    max_concurrency: int = 4


class ConcurrencyRegistry:
    """Registry of per-backend asyncio.Semaphore instances."""

    def __init__(self) -> None:
        self._entries: dict[str, SemaphoreEntry] = {}

    def get_or_create(self, name: str, max_concurrency: int = 4) -> SemaphoreEntry:
        if name not in self._entries:
            self._entries[name] = SemaphoreEntry(
                semaphore=asyncio.Semaphore(max_concurrency),
                max_concurrency=max_concurrency,
            )
        return self._entries[name]

    def get(self, name: str) -> SemaphoreEntry | None:
        return self._entries.get(name)

    def limit_for(self, name: str) -> asyncio.Semaphore:
        """Get the semaphore for a backend (creates with default if missing)."""
        return self.get_or_create(name).semaphore

    def __contains__(self, name: str) -> bool:
        return name in self._entries


async def acquire_with_timeout(
    sem: asyncio.Semaphore,
    backend_name: str,
    timeout_s: float = 30.0,
) -> None:
    """Acquire semaphore with timeout. Raises BackendBackpressureError on timeout."""
    try:
        async with asyncio.timeout(timeout_s):
            await sem.acquire()
    except TimeoutError:
        raise BackendBackpressureError(
            f"backend {backend_name} backpressure: acquire timed out after {timeout_s}s"
        ) from None
