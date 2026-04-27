# Research Router — Deterministic Tier-Based Provider Routing
#
# Implements canonical policy from docs/llm_wiki/wiki/research-routing.md
# with failure classification per blueprint §11.6.
#
# Policy Matrix:
#   general/news, academic: searxng > tavily > firecrawl > exa > brave
#   deep_scrape: firecrawl_extract > firecrawl_scrape > fetch
#
# Usage:
#   from aria.agents.search.router import ResearchRouter
#
#   router = ResearchRouter(rotator, state_path)
#   provider, key_info = await router.route("latest news on AI", Intent.GENERAL_NEWS, trace_id)

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

from aria.utils.logging import get_logger, log_event

if TYPE_CHECKING:
    from pathlib import Path

    from aria.credentials.rotator import Rotator

# === Enums ===


class Provider(StrEnum):
    """Research providers with tier assignment.

    Tier assignments per canonical policy:
    - general/news, academic: searxng > tavily > firecrawl > exa > brave
    - deep_scrape: firecrawl_extract > firecrawl_scrape > fetch
    """

    # --- Tier 1 ---
    SEARXNG = "searxng"

    # --- Tier 2 ---
    TAVILY = "tavily"

    # --- Tier 3 ---
    FIRECRAWL_EXTRACT = "firecrawl_extract"
    FIRECRAWL_SCRAPE = "firecrawl_scrape"

    # --- Tier 4 ---
    EXA = "exa"

    # --- Tier 5 ---
    BRAVE = "brave"

    # --- Deep Scrape Tier 3 fallback ---
    FETCH = "fetch"


class FailureReason(StrEnum):
    """Classified failure reasons per blueprint §11.6."""

    RATE_LIMIT = "rate_limit"
    CREDITS_EXHAUSTED = "credits_exhausted"
    CIRCUIT_OPEN = "circuit_open"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"


class HealthState(StrEnum):
    """Provider health states per blueprint §11.6."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    DOWN = "down"
    CREDITS_EXHAUSTED = "credits_exhausted"


class Intent(StrEnum):
    """Research intent classification (deterministic, keyword-based)."""

    GENERAL_NEWS = "general/news"
    ACADEMIC = "academic"
    DEEP_SCRAPE = "deep_scrape"
    UNKNOWN = "unknown"


# === Data Classes ===


class SearchResult(BaseModel):
    """Unified search response."""

    provider: Provider | None = None
    key_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    credits_used: int | None = None
    trace_id: str | None = None
    degraded: bool = False
    degraded_message: str | None = None


# === Policy Matrix ===

INTENT_TIERS: dict[Intent, tuple[Provider, ...]] = {
    Intent.GENERAL_NEWS: (
        Provider.SEARXNG,  # tier 1
        Provider.TAVILY,  # tier 2
        Provider.FIRECRAWL_EXTRACT,  # tier 3 (uses firecrawl)
        Provider.EXA,  # tier 4
        Provider.BRAVE,  # tier 5
    ),
    Intent.ACADEMIC: (
        Provider.SEARXNG,  # tier 1
        Provider.TAVILY,  # tier 2
        Provider.FIRECRAWL_EXTRACT,  # tier 3
        Provider.EXA,  # tier 4
        Provider.BRAVE,  # tier 5
    ),
    Intent.DEEP_SCRAPE: (
        Provider.FIRECRAWL_EXTRACT,  # tier 1
        Provider.FIRECRAWL_SCRAPE,  # tier 2
        Provider.FETCH,  # tier 3
    ),
}

# Failure action matrix: retryable?
RETRYABLE_FAILURE: set[FailureReason] = {FailureReason.TIMEOUT, FailureReason.NETWORK_ERROR}

# === Router ===


class RouterError(Exception):
    """Base exception for router errors."""

    pass


class NoProviderAvailableError(RouterError):
    """Raised when no provider is available (all tiers exhausted)."""

    pass


class ResearchRouter:
    """Deterministic tier-based router for research providers.

    Implements canonical policy from docs/llm_wiki/wiki/research-routing.md
    with failure classification per blueprint §11.6.

    Args:
        rotator: Rotator instance for key + circuit breaker management
        state_path: Path to encrypted provider state
    """

    HEALTH_CHECK_INTERVAL: ClassVar[float] = 300.0  # 5 minutes per §11.6

    def __init__(
        self,
        rotator: Rotator,
        state_path: Path,
    ) -> None:
        """Initialize research router.

        Args:
            rotator: Rotator instance for key + circuit breaker management
            state_path: Path to encrypted provider state
        """
        self._rotator = rotator
        self._state_path = state_path
        self._health: dict[str, HealthState] = {}
        self._health_task: asyncio.Task[None] | None = None
        self._logger = get_logger("aria.agents.search.router")

    async def route(
        self,
        query: str,
        intent: Intent,
        trace_id: str | None = None,
    ) -> tuple[Provider, Any] | SearchResult:
        """Route to best available provider.

        Args:
            query: Search query string
            intent: Classified intent
            trace_id: Optional trace ID for logging

        Returns:
            tuple[Provider, KeyInfo] on success
            SearchResult (degraded=True) if all tiers failed
        """
        default_tiers = INTENT_TIERS[Intent.GENERAL_NEWS]
        tier_list = INTENT_TIERS.get(intent, default_tiers)
        tier = 1

        for provider in tier_list:
            # Log provider attempt
            log_event(
                self._logger,
                20,  # INFO
                "provider_attempted",
                trace_id=trace_id,
                provider=provider.value,
                tier=tier,
                query=query[:50],
            )

            # Check health state - skip if down or credits exhausted
            health = self._get_provider_health(provider)
            if health in (HealthState.DOWN, HealthState.CREDITS_EXHAUSTED):
                log_event(
                    self._logger,
                    20,
                    "provider_skipped",
                    trace_id=trace_id,
                    provider=provider.value,
                    tier=tier,
                    reason=health.value,
                    action="health_state",
                )
                tier += 1
                continue

            # Acquire key from rotator (map composite names to base provider)
            rotator_provider = provider.value.replace("_extract", "").replace("_scrape", "")
            # searxng doesn't use the rotator (no API key)
            if rotator_provider == "searxng":
                return provider, None

            key_info = await self._rotator.acquire(rotator_provider)
            if key_info is None:
                log_event(
                    self._logger,
                    20,
                    "provider_skipped",
                    trace_id=trace_id,
                    provider=provider.value,
                    tier=tier,
                    reason="no_key_available",
                    action="advance_tier",
                )
                tier += 1
                continue

            # Check circuit breaker state
            from aria.credentials.rotator import CircuitState

            if key_info.circuit_state == CircuitState.OPEN:
                log_event(
                    self._logger,
                    20,
                    "provider_skipped",
                    trace_id=trace_id,
                    provider=provider.value,
                    tier=tier,
                    reason="circuit_open",
                    action="advance_tier",
                )
                tier += 1
                continue

            # Success - return provider and key info
            return provider, key_info

        # All tiers exhausted - enter degraded mode
        return await self.enter_degraded_mode(query, trace_id)

    def fallback(
        self,
        provider: Provider,
        intent: Intent,
        reason: FailureReason,
    ) -> Provider | None:
        """Get next tier provider after failure.

        Args:
            provider: Current provider that failed
            intent: Intent context (to resolve ambiguous providers)
            reason: Classified failure reason

        Returns:
            Next provider in tier list, or None if no more tiers
        """
        # Get tier list for specific intent
        tier_list = INTENT_TIERS.get(intent)
        if tier_list is None:
            return None

        # Find current provider in this intent's tier list
        current_tier_index: int | None = None
        for idx, p in enumerate(tier_list):
            if p == provider:
                current_tier_index = idx
                break

        if current_tier_index is None:
            return None

        # Get next tier in same intent
        next_index = current_tier_index + 1

        if next_index >= len(tier_list):
            return None

        return tier_list[next_index]

    def _get_provider_health(self, provider: Provider) -> HealthState:
        """Get cached health state for provider.

        Default to AVAILABLE so providers work immediately on first call.
        Health check loop (every 5 min) marks providers as DOWN when circuit breakers open.
        """
        return self._health.get(provider.value, HealthState.AVAILABLE)

    async def get_health_status(self, provider: str) -> HealthState:
        """Get current health state for provider (with refresh)."""
        await self._refresh_health(provider)
        return self._health.get(provider, HealthState.DOWN)

    async def _refresh_health(self, provider: str) -> None:
        """Refresh health state for a single provider."""
        # Special cases: searxng is self-hosted (no Rotator keys)
        if provider == "searxng":
            self._health[provider] = HealthState.AVAILABLE
            return

        # Map composite providers (firecrawl_extract, firecrawl_scrape) to base
        rotator_provider = provider.replace("_extract", "").replace("_scrape", "")

        status = self._rotator.status(rotator_provider)
        if not status.get("keys"):
            self._health[provider] = HealthState.DOWN
            return

        # Check circuit states
        from aria.credentials.rotator import CircuitState

        any_open = any(k.get("circuit_state") == CircuitState.OPEN.value for k in status["keys"])
        any_exhausted = any(k.get("credits_remaining", 1) == 0 for k in status["keys"])

        if any_open:
            self._health[provider] = HealthState.DEGRADED
        elif any_exhausted:
            self._health[provider] = HealthState.CREDITS_EXHAUSTED
        else:
            self._health[provider] = HealthState.AVAILABLE

    async def enter_degraded_mode(
        self,
        query: str,
        trace_id: str | None,
    ) -> SearchResult:
        """Return local-only response with degraded banner."""
        log_event(
            self._logger,
            40,  # ERROR
            "degraded_mode_entered",
            trace_id=trace_id,
            query=query[:50],
            all_tiers_exhausted=True,
        )

        return SearchResult(
            data={},
            degraded=True,
            degraded_message=(
                "All research providers unavailable. "
                "Returning local-only results. Query not processed."
            ),
            trace_id=trace_id,
        )

    async def start_health_checks(self) -> None:
        """Background task: health check at startup + every 5 minutes."""
        self._health_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Continuously check provider health every 5 minutes."""
        while True:
            try:
                await self._check_all_providers()
            except Exception as e:
                log_event(
                    self._logger,
                    30,  # WARNING
                    "health_check_error",
                    error=str(e),
                )
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

    async def _check_all_providers(self) -> None:
        """Check health of all configured providers."""
        all_provider_strs: set[str] = set()
        for tier_list in INTENT_TIERS.values():
            for provider in tier_list:
                all_provider_strs.add(provider.value)

        for provider_str in all_provider_strs:
            await self._refresh_health(provider_str)

    async def stop_health_checks(self) -> None:
        """Stop the health check background task."""
        import contextlib

        if self._health_task:
            self._health_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_task
            self._health_task = None


# === Exports ===

__all__ = [
    "NoProviderAvailableError",
    "ResearchRouter",
    "RouterError",
]
