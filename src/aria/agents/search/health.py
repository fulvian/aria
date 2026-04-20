"""
Provider health monitoring and circuit breaker per blueprint §11.3 and §11.6.

ProviderHealth probes providers every 5 minutes and exposes status for
SearchRouter circuit breaker integration.
"""

import asyncio
import logging
from contextlib import suppress
from typing import Any

from aria.agents.search.schema import ProviderStatus, SearchProvider

logger = logging.getLogger(__name__)


class ProviderHealth:
    """Health monitor for search providers per blueprint §11.6.

    Runs periodic health probes (every 5 min cadence) and maintains
    in-memory status for circuit breaker integration.

    Metrics: `aria_provider_status{provider}` gauge (0=available, 1=degraded, 2=down).
    """

    PROBE_INTERVAL_SECONDS = 300  # 5 minutes per blueprint §11.6

    def __init__(
        self,
        providers: dict[str, SearchProvider],
        status_callback: Any | None = None,  # noqa: ANN401
    ) -> None:
        """Initialize health monitor.

        Args:
            providers: Dict mapping provider name to provider adapter.
            status_callback: Optional callback(status_dict) called after each probe.
        """
        self._providers = providers
        self._status_callback = status_callback
        # status: provider_name -> ProviderStatus
        self._status: dict[str, ProviderStatus] = {}
        self._probe_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def status(self, provider: str) -> ProviderStatus:
        """Get current health status for a provider.

        Args:
            provider: Provider name.

        Returns:
            Current status (default AVAILABLE if unknown).
        """
        return self._status.get(provider, ProviderStatus.AVAILABLE)

    def status_all(self) -> dict[str, ProviderStatus]:
        """Get health status for all providers.

        Returns:
            Dict mapping provider name to status.
        """
        return dict(self._status)

    async def probe_all(self) -> dict[str, ProviderStatus]:
        """Probe all registered providers concurrently.

        Returns:
            Dict mapping provider name to status.
        """
        tasks = {}
        for name, provider in self._providers.items():
            tasks[name] = asyncio.create_task(self._probe(name, provider))

        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as exc:
                logger.error("Health probe failed for %s: %s", name, exc)
                results[name] = ProviderStatus.DOWN

        self._status = results

        # Emit metrics if callback provided
        if self._status_callback:
            self._status_callback(self._status)

        return results

    async def _probe(self, name: str, provider: SearchProvider) -> ProviderStatus:
        """Probe a single provider.

        Args:
            name: Provider name.
            provider: Provider adapter instance.

        Returns:
            Provider status.
        """
        try:
            status = await provider.health_check()
            logger.debug("Health probe %s: %s", name, status.value)
            return status
        except Exception as exc:
            logger.warning("Health probe error for %s: %s", name, exc)
            return ProviderStatus.DOWN

    async def run_forever(self, interval_s: int | None = None) -> None:
        """Run health probe loop indefinitely.

        Args:
            interval_s: Probe interval in seconds (default 300 per blueprint).
        """
        interval = interval_s or self.PROBE_INTERVAL_SECONDS
        logger.info(
            "Starting health monitor with %ds probe interval",
            interval,
        )

        # Initial probe
        await self.probe_all()

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)
                if not self._stop_event.is_set():
                    await self.probe_all()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Health probe loop error: %s", exc)

    async def start(self) -> None:
        """Start the health monitor in background."""
        if self._probe_task is None or self._probe_task.done():
            self._stop_event.clear()
            self._probe_task = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        """Stop the health monitor."""
        self._stop_event.set()
        if self._probe_task is not None and not self._probe_task.done():
            try:
                await asyncio.wait_for(self._probe_task, timeout=5.0)
            except TimeoutError:
                self._probe_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._probe_task
        logger.info("Health monitor stopped")
