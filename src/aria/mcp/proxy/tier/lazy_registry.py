"""Lazy registry — on-demand backend connections.

Backends marked as 'lazy' are spawned on first call_tool and kept
alive for a configurable idle TTL. Background sweep closes idle
backends. Subsequent call_tool re-spawns them.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aria.mcp.proxy.tier.backend_client import BackendClient, BackendClientError
from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("aria.mcp.proxy.tier.lazy_registry")


@dataclass
class LazyEntry:
    client: BackendClient
    last_used: float = field(default_factory=time.monotonic)
    spawn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class LazyRegistry:
    """Registry of lazy backend connections with idle TTL sweep.

    Args:
        on_spawn: Callable(name) called when a backend is spawned.
        on_idle_shutdown: Callable(name, idle_s) called on sweep.
    """

    def __init__(
        self,
        on_spawn: Callable[[str], None] | None = None,
        on_idle_shutdown: Callable[[str, float], None] | None = None,
    ) -> None:
        self._pool: dict[str, LazyEntry] = {}
        self._known_backends: dict[str, tuple[str, tuple[str, ...], dict[str, str], int]] = {}
        self._on_spawn = on_spawn
        self._on_idle_shutdown = on_idle_shutdown
        self._sweep_task: asyncio.Task[None] | None = None
        self._shutdown = False

    def register(
        self,
        name: str,
        command: str,
        args: tuple[str, ...] = (),
        env: dict[str, str] | None = None,
        idle_ttl_s: int = 300,
    ) -> None:
        """Register a lazy backend that can be spawned on demand."""
        self._known_backends[name] = (command, args, env or {}, idle_ttl_s)

    def known_backends(self) -> list[str]:
        return list(self._known_backends.keys())

    async def acquire(self, name: str, connect_timeout_s: float = 15.0) -> BackendClient:
        """Get a client for a lazy backend, spawning if necessary.

        If the backend is already in the pool, returns it immediately.
        Otherwise spawns a new BackendClient (thread-safe via per-backend lock).
        """
        if name not in self._known_backends:
            raise BackendClientError(f"unknown lazy backend: {name}")

        entry = self._pool.get(name)
        if entry is not None and entry.client.is_connected:
            entry.last_used = time.monotonic()
            return entry.client

        # Need to spawn — use per-backend lock
        if entry is None:
            entry = LazyEntry(
                client=BackendClient(
                    name=name,
                    command=self._known_backends[name][0],
                    args=self._known_backends[name][1],
                    env=self._known_backends[name][2],
                ),
            )
            self._pool[name] = entry

        async with entry.spawn_lock:
            if not entry.client.is_connected:
                start = time.monotonic()
                idle_ttl = self._known_backends[name][3]

                try:
                    await entry.client.connect(timeout_s=connect_timeout_s)
                except BackendClientError:
                    self._pool.pop(name, None)
                    raise

                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info(
                    "lazy_registry.spawned",
                    extra={
                        "backend": name,
                        "cold_start_ms": round(elapsed_ms, 1),
                        "idle_ttl_s": idle_ttl,
                    },
                )
                if self._on_spawn:
                    self._on_spawn(name)

            entry.last_used = time.monotonic()
            return entry.client

    def touch(self, name: str) -> None:
        """Update the last_used timestamp (call after successful tool use)."""
        entry = self._pool.get(name)
        if entry is not None:
            entry.last_used = time.monotonic()

    async def start_sweeper(self, interval_s: float = 30.0) -> None:
        """Start the background idle TTL sweep loop."""
        self._sweep_task = asyncio.create_task(self._sweep_loop(interval_s))

    async def _sweep_loop(self, interval_s: float) -> None:
        """Background sweep: close backends idle beyond their TTL."""
        while not self._shutdown:
            await asyncio.sleep(interval_s)
            now = time.monotonic()
            for name, entry in list(self._pool.items()):
                idle_ttl = self._known_backends.get(name, (None, None, None, 300))[3]
                idle_s = now - entry.last_used
                if idle_s > idle_ttl:
                    logger.info(
                        "lazy_registry.sweep_closing",
                        extra={
                            "backend": name,
                            "idle_s": round(idle_s, 1),
                            "ttl_s": idle_ttl,
                        },
                    )
                    await entry.client.disconnect()
                    del self._pool[name]
                    if self._on_idle_shutdown:
                        self._on_idle_shutdown(name, idle_s)

    async def shutdown(self) -> None:
        """Disconnect all lazy backends and stop the sweeper."""
        self._shutdown = True
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweep_task
            self._sweep_task = None

        disconnect_tasks = [entry.client.disconnect() for entry in self._pool.values()]
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        self._pool.clear()

    @property
    def size(self) -> int:
        return len(self._pool)
