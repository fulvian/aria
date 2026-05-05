"""TieredProxyProvider — FastMCP Provider with tier-based connection lifecycle.

Replaces TimeoutProxyProvider with a robust architecture:
- Warm pool (always-on) for high-frequency backends
- Lazy registry (on-demand) for low-frequency/paid backends
- Per-backend circuit breaker (fail-fast on systemic errors)
- Per-backend concurrency semaphore (backpressure control)
- Persistent metadata cache (zero-cold-start discovery)
- Auto-recovery retry queue (self-healing warm pool)
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from fastmcp.server.providers.base import Provider
from fastmcp.tools.base import Tool

from aria.mcp.proxy.tier.backend_client import BackendClient
from aria.mcp.proxy.tier.breaker import Breaker, BreakerRegistry, BreakerState
from aria.mcp.proxy.tier.lazy_registry import LazyRegistry
from aria.mcp.proxy.tier.metadata_cache import MetadataCache
from aria.mcp.proxy.tier.retry_queue import RetryQueue
from aria.mcp.proxy.tier.semaphore import (
    BackendBackpressureError,
    ConcurrencyRegistry,
    acquire_with_timeout,
)
from aria.mcp.proxy.tier.warm_pool import WarmPool
from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from aria.mcp.proxy.catalog import BackendSpec
    from aria.mcp.proxy.config import ProxyConfig

logger = get_logger("aria.mcp.proxy.tier.provider")


class TieredProxyProvider(Provider):
    """FastMCP Provider that manages tiered backend connections.

    Args:
        backends: List of BackendSpec from the catalog.
        config: ProxyConfig with tier defaults.
        catalog_hash: Current catalog hash for cache invalidation.
        metadata_cache: Optional pre-configured cache instance.
        event_emitter: Optional callable(event_kind, **kwargs) for observability.
    """

    def __init__(
        self,
        backends: list[BackendSpec],
        config: ProxyConfig,
        catalog_hash: str = "",
        metadata_cache: MetadataCache | None = None,
        event_emitter: Any | None = None,  # noqa: ANN401
    ) -> None:
        super().__init__()
        self._backends = backends
        self._cfg = config
        self._catalog_hash = catalog_hash
        self._event_emitter = event_emitter

        # Sub-components
        self._metadata_cache = metadata_cache or MetadataCache()
        self._breaker_registry = BreakerRegistry()
        self._concurrency_registry = ConcurrencyRegistry()
        self._warm_pool = WarmPool(
            boot_timeout_s=config.tier.warm_boot_timeout_s,
            healthcheck_interval_s=config.tier.healthcheck_interval_s,
            on_demote=self._on_warm_demote,
            retry_schedule=self._schedule_retry,
        )
        self._lazy_registry = LazyRegistry(
            on_spawn=self._on_lazy_spawn,
            on_idle_shutdown=self._on_lazy_idle_shutdown,
        )
        self._retry_queue = RetryQueue(
            on_retry=self._on_retry_tick,  # type: ignore[arg-type]
            on_quarantine=self._on_quarantine,  # type: ignore[arg-type]
        )

        # Classify and register backends
        self._warm_specs: list[BackendSpec] = []
        for backend in backends:
            lifecycle = getattr(backend, "proxy_lifecycle", "lazy")
            if lifecycle == "warm":
                self._warm_specs.append(backend)
            else:
                self._lazy_registry.register(
                    name=backend.name,
                    command=backend.command,
                    args=backend.args,
                    env=backend.env,
                    idle_ttl_s=getattr(backend, "proxy_idle_ttl_s", 300),
                )

            # Create circuit breaker for every backend
            self._breaker_registry.get_or_create(
                backend.name,
                failure_threshold=getattr(backend, "proxy_breaker_threshold", 3),
                cooldown_s=getattr(backend, "proxy_breaker_cooldown_s", 60),
                on_event=self._on_breaker_event,
            )

            # Create concurrency limiter for every backend
            self._concurrency_registry.get_or_create(
                backend.name,
                max_concurrency=getattr(backend, "proxy_concurrency", 4),
            )

        self._started = False

    # ---- Lifecycle ----

    async def lifespan(self) -> AsyncIterator[None]:  # type: ignore[override]
        """Start all background tasks, yield, then shutdown.

        Async context manager called by FastMCP. Code before yield runs
        at startup, code after yield runs at shutdown.
        """
        if self._started:
            yield
            return

        # Load metadata cache from disk
        await self._metadata_cache.load()

        # Invalidate cache if catalog changed
        if self._catalog_hash and self._metadata_cache.catalog_hash != self._catalog_hash:
            logger.info(
                "tier.cache_invalidated",
                extra={
                    "old_hash": self._metadata_cache.catalog_hash,
                    "new_hash": self._catalog_hash,
                },
            )
            self._metadata_cache.invalidate()
            self._metadata_cache.catalog_hash = self._catalog_hash

        # Start retry queue worker
        await self._retry_queue.start()

        # Start warm pool (connects in parallel)
        warm_entries = [
            (
                b.name,
                b.command,
                b.args,
                b.env,
            )
            for b in self._warm_specs
        ]
        if warm_entries:
            await self._warm_pool.start(warm_entries)

        # Start lazy sweep loop
        await self._lazy_registry.start_sweeper()

        self._started = True
        logger.info(
            "tier.started",
            extra={
                "warm_count": len(self._warm_specs),
                "lazy_count": len(self._lazy_registry.known_backends()),
            },
        )

        yield

        # Shutdown
        await self._warm_pool.shutdown()
        await self._lazy_registry.shutdown()
        await self._retry_queue.stop()
        self._started = False
        logger.info("tier.shutdown")

    # ---- Provider interface ----

    async def _list_tools(self) -> Sequence[Tool]:
        """Aggregate warm live tools + lazy tools from metadata cache.

        Warm pool: live query each backend with 3s timeout.
          - Success → update metadata cache.
          - Timeout/failure → use cached metadata, schedule retry.

        Lazy: all tools come from metadata cache (no connect).
        """
        start = time.monotonic()
        warm_tools: list[Tool] = []
        lazy_tools: list[Tool] = []

        # Collect warm tools (live, with isolation)
        warm_tasks: list[asyncio.Task[None]] = []
        warm_results: dict[str, list[dict[str, Any]]] = {}

        async def _fetch_warm(name: str) -> None:
            client = self._warm_pool.get(name)
            if client is None:
                return
            breaker = self._breaker_registry.get(name)
            if breaker is not None and not breaker.is_closed:
                return

            try:
                tools_data = await asyncio.wait_for(
                    client.list_tools(),
                    timeout=3.0,
                )
                warm_results[name] = tools_data
                await self._metadata_cache.update(name, tools_data)
            except (TimeoutError, Exception) as exc:
                logger.warning(
                    "tier.warm_list_tools_failed",
                    extra={"backend": name, "error": str(exc)},
                )
                if breaker is not None:
                    breaker.record_failure()
                if self._retry_queue is not None:
                    self._retry_queue.schedule(name, attempt=1)

        for name in list(self._warm_pool.clients.keys()):
            task = asyncio.create_task(_fetch_warm(name))
            warm_tasks.append(task)

        if warm_tasks:
            await asyncio.gather(*warm_tasks, return_exceptions=True)

        # Convert warm results to Tool objects
        for name, tools_data in warm_results.items():
            for td in tools_data:
                tool = Tool(
                    name=td.get("name", f"{name}__unknown"),
                    description=td.get("description", ""),
                    parameters=td.get("parameters", {}),
                )
                object.__setattr__(tool, "_backend_name", name)
                warm_tools.append(tool)

        # Fallback: use cached metadata for warm backends that failed
        for name in list(self._warm_pool.clients.keys()):
            if name not in warm_results:
                for td in self._metadata_cache.get(name):
                    tool = Tool(
                        name=td.get("name", f"{name}__unknown"),
                        description=td.get("description", ""),
                        parameters=td.get("parameters", {}),
                    )
                    object.__setattr__(tool, "_backend_name", name)
                    warm_tools.append(tool)

        # Collect lazy tools from metadata cache
        for name in self._lazy_registry.known_backends():
            for td in self._metadata_cache.get(name):
                tool = Tool(
                    name=td.get("name", f"{name}__unknown"),
                    description=td.get("description", ""),
                    parameters=td.get("parameters", {}),
                )
                object.__setattr__(tool, "_backend_name", name)
                lazy_tools.append(tool)

        total_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tier.list_tools",
            extra={
                "warm_count": len(warm_tools),
                "lazy_count": len(lazy_tools),
                "total_ms": round(total_ms, 1),
            },
        )

        return [*warm_tools, *lazy_tools]

    async def _get_tool(self, name: str, version: Any = None) -> Tool | None:  # noqa: ANN401
        """Resolve a tool to its backend client wrapper.

        Args:
            name: Tool name in format `server__tool`.
            version: Optional version spec (unused, for FastMCP compatibility).

        Returns:
            A ProxyTool bound to the appropriate backend client, or None
            if the tool backend cannot be identified.
        """
        backend_name = self._parse_backend(name)
        if backend_name is None:
            logger.warning("tier.unparseable_tool_name", extra={"name": name})
            return None

        # Check breaker
        breaker = self._breaker_registry.get(backend_name)
        if breaker is not None and not breaker.is_closed:
            logger.warning(
                "tier.circuit_open_for_tool",
                extra={"backend": backend_name, "tool": name, "state": breaker.state.value},
            )
            return None

        # Get client
        client = self._warm_pool.get(backend_name)
        is_warm = True
        if client is None:
            is_warm = False
            try:
                client = await self._lazy_registry.acquire(backend_name)
            except Exception as exc:
                logger.error(
                    "tier.acquire_failed",
                    extra={"backend": backend_name, "tool": name, "error": str(exc)},
                )
                return None

        actual_tool_name = self._extract_tool_name(name)
        return ProxyTool(
            tool_name=actual_tool_name,
            backend_name=backend_name,
            client=client,
            semaphore=self._concurrency_registry.limit_for(backend_name),
            breaker=breaker,
            lazy_registry=self._lazy_registry if not is_warm else None,
            event_emitter=self._event_emitter,
        )

    # ---- Event callbacks ----

    def _on_warm_demote(self, name: str) -> None:
        logger.warning("tier.warm_demoted", extra={"backend": name})
        if self._event_emitter:
            self._event_emitter(  # noqa: E501
                "proxy.backend_warm_pool_demote", backend=name, reason="healthcheck"
            )

    def _on_lazy_spawn(self, name: str) -> None:
        if self._event_emitter:
            self._event_emitter("proxy.backend_lazy_spawn", backend=name)

    def _on_lazy_idle_shutdown(self, name: str, idle_s: float) -> None:
        if self._event_emitter:
            self._event_emitter(  # noqa: E501
                "proxy.backend_idle_shutdown", backend=name, idle_s=round(idle_s, 1)
            )

    def _on_breaker_event(self, name: str, old: BreakerState, new: BreakerState) -> None:
        logger.info(
            "tier.breaker_transition",
            extra={"backend": name, "from": old.value, "to": new.value},
        )
        if self._event_emitter:
            event_map = {
                (BreakerState.CLOSED, BreakerState.OPEN): "proxy.backend_circuit_open",
                (BreakerState.OPEN, BreakerState.HALF_OPEN): "proxy.backend_circuit_half_open",
                (BreakerState.HALF_OPEN, BreakerState.CLOSED): "proxy.backend_circuit_closed",
            }
            event = event_map.get((old, new))
            if event:
                self._event_emitter(event, backend=name)

    def _schedule_retry(self, name: str, attempt: int = 1) -> None:
        if self._retry_queue is not None:
            self._retry_queue.schedule(name, attempt)

    async def _on_retry_tick(self, item: Any) -> bool:  # noqa: ANN401
        """Retry callback: attempt to reconnect a warm backend."""
        name = item.backend_name
        spec = next((b for b in self._warm_specs if b.name == name), None)
        if spec is None:
            logger.warning("tier.retry_no_spec", extra={"backend": name})
            return False

        client = BackendClient(
            name=name,
            command=spec.command,
            args=spec.args,
            env=spec.env,
        )
        try:
            await client.connect(timeout_s=self._cfg.tier.warm_boot_timeout_s)
            await self._warm_pool.promote(name, client)
            logger.info("tier.retry_success", extra={"backend": name, "attempt": item.attempt})
            return True
        except Exception as exc:
            await client.disconnect()
            logger.warning(
                "tier.retry_failed",
                extra={"backend": name, "attempt": item.attempt, "error": str(exc)},
            )
            return False

    async def _on_quarantine(self, item: Any) -> None:  # noqa: ANN401
        logger.error(
            "tier.quarantine",
            extra={"backend": item.backend_name, "attempts": item.attempt - 1},
        )
        if self._event_emitter:
            self._event_emitter(
                "proxy.backend_quarantine",
                backend=item.backend_name,
                attempts=item.attempt - 1,
            )

    # ---- Helpers ----

    @staticmethod
    def _parse_backend(tool_name: str) -> str | None:
        """Extract backend name from `server__tool_name`."""
        if "__" in tool_name:
            return tool_name.split("__", 1)[0]
        if "/" in tool_name:
            return tool_name.split("/", 1)[0]
        return None

    @staticmethod
    def _extract_tool_name(tool_name: str) -> str:
        """Extract actual tool name from `server__tool_name`."""
        if "__" in tool_name:
            return tool_name.split("__", 1)[1]
        if "/" in tool_name:
            return tool_name.split("/", 1)[1]
        return tool_name


class ProxyTool(Tool):
    """A Tool wrapper that routes execution to a BackendClient.

    Binds the tool_name, backend_name, client, semaphore, breaker,
    and optional lazy_registry for TTL touch.
    """

    def __init__(
        self,
        tool_name: str,
        backend_name: str,
        client: BackendClient,
        semaphore: asyncio.Semaphore,
        breaker: Breaker | None = None,
        lazy_registry: LazyRegistry | None = None,
        event_emitter: Any | None = None,  # noqa: ANN401
    ) -> None:
        super().__init__(
            name=tool_name,
            description=f"Proxy tool for {backend_name}::{tool_name}",
            parameters={"type": "object", "properties": {}},
        )
        self._backend_name = backend_name
        self._client = client
        self._semaphore = semaphore
        self._breaker = breaker
        self._lazy_registry = lazy_registry
        self._event_emitter = event_emitter

    async def run(self, arguments: dict[str, Any] | None = None) -> Any:  # noqa: ANN401
        """Execute the tool with concurrency limiting and circuit breaker."""
        # Acquire semaphore with timeout
        try:
            await acquire_with_timeout(
                self._semaphore,
                self._backend_name,
                timeout_s=30.0,
            )
        except BackendBackpressureError:
            if self._event_emitter:
                self._event_emitter(
                    "proxy.backend_backpressure",
                    backend=self._backend_name,
                )
            raise

        try:
            result = await self._client.call_tool(self.name, arguments or {})

            # Record success in breaker
            if self._breaker is not None:
                self._breaker.record_success()

            # Touch lazy backend TTL
            if self._lazy_registry is not None:
                self._lazy_registry.touch(self._backend_name)

            return result

        except Exception:
            # Record failure in breaker
            if self._breaker is not None:
                self._breaker.record_failure()
            raise
        finally:
            self._semaphore.release()
