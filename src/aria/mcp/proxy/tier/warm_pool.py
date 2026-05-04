"""Warm pool — always-on backend connections.

Maintains a pool of BackendClient instances for warm backends.
Connects eagerly at boot, runs periodic healthchecks, and demotes
failed backends to the retry queue.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from aria.mcp.proxy.tier.backend_client import BackendClient, BackendClientError
from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("aria.mcp.proxy.tier.warm_pool")


class WarmPool:
    """Pool of always-on backend connections.

    Args:
        boot_timeout_s: Per-backend connect timeout (default 5s).
        healthcheck_interval_s: Interval between healthcheck sweeps (default 30s).
        on_demote: Callback(name) when a backend is demoted to lazy/retry.
        retry_schedule: Callable(name, attempt) to schedule a retry.
    """

    def __init__(
        self,
        boot_timeout_s: float = 5.0,
        healthcheck_interval_s: float = 30.0,
        on_demote: Callable[[str], None] | None = None,
        retry_schedule: Callable[[str, int], None] | None = None,
    ) -> None:
        self._clients: dict[str, BackendClient] = {}
        self._boot_timeout_s = boot_timeout_s
        self._healthcheck_interval_s = healthcheck_interval_s
        self._on_demote = on_demote
        self._retry_schedule = retry_schedule
        self._healthcheck_task: asyncio.Task[None] | None = None
        self._shutdown = False

    @property
    def clients(self) -> dict[str, BackendClient]:
        return dict(self._clients)

    @property
    def size(self) -> int:
        return len(self._clients)

    def has_backend(self, name: str) -> bool:
        return name in self._clients

    def get(self, name: str) -> BackendClient | None:
        return self._clients.get(name)

    async def start(
        self,
        backends: list[tuple[str, str, tuple[str, ...], dict[str, str]]],
    ) -> None:
        """Connect all warm backends in parallel.

        Each entry is (name, command, args, env). Backends that fail
        to connect are scheduled for retry.
        """
        if not backends:
            return

        async def _connect_one(
            name: str, command: str, args: tuple[str, ...], env: dict[str, str]
        ) -> tuple[str, BackendClient | None]:
            client = BackendClient(name=name, command=command, args=args, env=env)
            try:
                await client.connect(timeout_s=self._boot_timeout_s)
                return name, client
            except BackendClientError as exc:
                logger.warning(
                    "warm_pool.boot_failed",
                    extra={"backend": name, "error": str(exc)},
                )
                if self._retry_schedule:
                    self._retry_schedule(name, 1)
                return name, None

        tasks = [_connect_one(n, c, a, e) for n, c, a, e in backends]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, BaseException):
                logger.error("warm_pool.boot_crash", extra={"error": str(result)})
                continue
            name, client = result
            if client is not None:
                self._clients[name] = client
                logger.info(
                    "warm_pool.connected",
                    extra={"backend": name},
                )

        # Start healthcheck loop
        self._healthcheck_task = asyncio.create_task(self._healthcheck_loop())

    async def promote(self, name: str, client: BackendClient) -> None:
        """Add or replace a backend in the warm pool (called by retry queue)."""
        old = self._clients.get(name)
        if old is not None:
            await old.disconnect()
        self._clients[name] = client
        logger.info("warm_pool.promoted", extra={"backend": name})

    async def shutdown(self) -> None:
        """Disconnect all backends and stop healthcheck loop."""
        self._shutdown = True
        if self._healthcheck_task is not None:
            self._healthcheck_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._healthcheck_task
            self._healthcheck_task = None

        disconnect_tasks = [client.disconnect() for client in self._clients.values()]
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        self._clients.clear()

    async def _healthcheck_loop(self) -> None:
        """Periodic healthcheck of all warm backends."""
        while not self._shutdown:
            await asyncio.sleep(self._healthcheck_interval_s)
            for name, client in list(self._clients.items()):
                healthy = await client.ping(timeout_s=2.0)
                if not healthy:
                    logger.warning(
                        "warm_pool.healthcheck_failed",
                        extra={"backend": name},
                    )
                    await client.disconnect()
                    del self._clients[name]
                    if self._on_demote:
                        self._on_demote(name)
                    if self._retry_schedule:
                        self._retry_schedule(name, 1)
