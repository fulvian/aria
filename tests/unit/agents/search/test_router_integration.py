# Router integration tests with mocked Rotator

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.agents.search.router import (
    HealthState,
    Intent,
    Provider,
    ResearchRouter,
    SearchResult,
)
from aria.credentials.rotator import CircuitState, KeyInfo


class TestRouterRoute:
    """Test router.route() with mocked Rotator."""

    @pytest.fixture
    def mock_rotator(self):
        """Create a mock Rotator."""
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        """Create router with mocked rotator."""
        return ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))

    @pytest.mark.asyncio
    async def test_route_general_news_tier1_healthy(self, router, mock_rotator):
        """general/news: tier 1 healthy -> uses searxng, no fallback."""
        # Set health to AVAILABLE for tier 1
        router._health["searxng"] = HealthState.AVAILABLE

        # Mock tier 1 (searxng) — keyless provider
        result = await router.route("latest news on AI", Intent.GENERAL_NEWS, "trace-1")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.SEARXNG
        assert key is None  # keyless provider

    @pytest.mark.asyncio
    async def test_route_tier1_rate_limit_falls_to_tier1b(self, router, mock_rotator):
        """tier 1a (searxng) DOWN -> fallback to tier 1b (reddit, keyless)."""
        # Set searxng to DOWN — should fall to reddit (tier 1b, also keyless)
        router._health["searxng"] = HealthState.DOWN

        result = await router.route("latest news on AI", Intent.GENERAL_NEWS, "trace-2")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.REDDIT  # tier 1b — free+unlimited
        assert key is None  # keyless

    @pytest.mark.asyncio
    async def test_route_all_tiers_fail_enters_degraded(self, router, mock_rotator):
        """All tiers fail -> degraded mode."""
        # All keyless providers (searxng, reddit, fetch) must be DOWN to skip
        for skip in ("searxng", "reddit", "fetch"):
            router._health[skip] = HealthState.DOWN
        for provider in [Provider.TAVILY, Provider.EXA, Provider.BRAVE]:
            router._health[provider.value] = HealthState.AVAILABLE

        mock_rotator.acquire.return_value = None  # All key-based providers return None

        result = await router.route("latest news on AI", Intent.GENERAL_NEWS, "trace-3")

        assert isinstance(result, SearchResult)
        assert result.degraded is True
        assert "All research providers unavailable" in result.degraded_message

    @pytest.mark.asyncio
    async def test_route_deep_scrape_tier1(self, router, mock_rotator):
        """deep_scrape: tier 1 is fetch (post-FIRECRAWL)."""
        # Set health to AVAILABLE for fetch
        router._health["fetch"] = HealthState.AVAILABLE

        # Mock tier 1 (fetch) - keyless provider
        result = await router.route("deep scrape this website", Intent.DEEP_SCRAPE, "trace-4")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.FETCH
        assert key is None  # keyless provider

    @pytest.mark.asyncio
    async def test_route_circuit_open_skips_provider(self, router, mock_rotator):
        """circuit_state=OPEN -> skip provider."""
        # Both keyless providers DOWN to reach key-based tiers
        router._health["searxng"] = HealthState.DOWN
        router._health["reddit"] = HealthState.DOWN
        router._health["tavily"] = HealthState.AVAILABLE
        router._health["exa"] = HealthState.AVAILABLE

        mock_key_open = MagicMock(spec=KeyInfo)
        mock_key_open.key_id = "tvly-1"
        mock_key_open.circuit_state = CircuitState.OPEN  # circuit open
        mock_key_open.credits_remaining = 500

        mock_key_exa = MagicMock(spec=KeyInfo)
        mock_key_exa.key_id = "exa-1"
        mock_key_exa.circuit_state = CircuitState.CLOSED
        mock_key_exa.credits_remaining = 800

        mock_rotator.acquire.side_effect = [
            mock_key_open,  # tavily has circuit open
            mock_key_exa,  # exa returns key
        ]

        result = await router.route("latest news on AI", Intent.GENERAL_NEWS, "trace-5")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.EXA

    @pytest.mark.asyncio
    async def test_route_health_state_down_skips_to_reddit(self, router, mock_rotator):
        """searxng DOWN -> falls to reddit (tier 1b, keyless)."""
        # Set searxng to DOWN — should go to reddit (tier 1b)
        router._health["searxng"] = HealthState.DOWN

        result = await router.route("latest news on AI", Intent.GENERAL_NEWS, "trace-6")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.REDDIT  # tier 1b
        assert key is None  # keyless

    @pytest.mark.asyncio
    async def test_route_health_state_down_skips_both_free_tiers_to_tavily(self, router, mock_rotator):
        """Both free tiers DOWN -> falls to tavily (tier 2, key-based)."""
        router._health["searxng"] = HealthState.DOWN
        router._health["reddit"] = HealthState.DOWN
        router._health["tavily"] = HealthState.AVAILABLE

        mock_key = MagicMock(spec=KeyInfo)
        mock_key.key_id = "tvly-1"
        mock_key.circuit_state = CircuitState.CLOSED
        mock_key.credits_remaining = 500

        mock_rotator.acquire.return_value = mock_key

        result = await router.route("latest news on AI", Intent.GENERAL_NEWS, "trace-7")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.TAVILY


class TestRouterFallback:
    """Test router.fallback() method."""

    @pytest.fixture
    def mock_rotator(self):
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        return ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))

    def test_fallback_searxng_returns_reddit(self, router):
        """SEARXNG fallback -> REDDIT (tier 1a -> tier 1b for general_news)."""
        next_provider = router.fallback(Provider.SEARXNG, Intent.GENERAL_NEWS, "rate_limit")
        assert next_provider == Provider.REDDIT  # tier 1b

    def test_fallback_reddit_returns_tavily(self, router):
        """REDDIT fallback -> TAVILY (tier 1b -> tier 2 for general_news)."""
        next_provider = router.fallback(Provider.REDDIT, Intent.GENERAL_NEWS, "rate_limit")
        assert next_provider == Provider.TAVILY

    def test_fallback_tavily_returns_exa(self, router):
        """TAVILY fallback -> EXA (for general_news)."""
        next_provider = router.fallback(Provider.TAVILY, Intent.GENERAL_NEWS, "rate_limit")
        assert next_provider == Provider.EXA

    def test_fallback_exa_returns_brave(self, router):
        """EXA fallback -> BRAVE (for general_news)."""
        next_provider = router.fallback(Provider.EXA, Intent.GENERAL_NEWS, "timeout")
        assert next_provider == Provider.BRAVE

    def test_fallback_brave_returns_fetch(self, router):
        """BRAVE fallback -> FETCH (for general_news)."""
        next_provider = router.fallback(Provider.BRAVE, Intent.GENERAL_NEWS, "rate_limit")
        assert next_provider == Provider.FETCH

    def test_fallback_fetch_returns_none(self, router):
        """FETCH (last tier) fallback -> None (for general_news)."""
        next_provider = router.fallback(Provider.FETCH, Intent.GENERAL_NEWS, "rate_limit")
        assert next_provider is None

    def test_fallback_deep_scrape_tier1_returns_tier2(self, router):
        """DEEP_SCRAPE: FETCH -> WEBFETCH."""
        next_provider = router.fallback(Provider.FETCH, Intent.DEEP_SCRAPE, "timeout")
        assert next_provider == Provider.WEBFETCH

    def test_fallback_deep_scrape_tier2_returns_none(self, router):
        """DEEP_SCRAPE: WEBFETCH (last tier) -> None."""
        next_provider = router.fallback(Provider.WEBFETCH, Intent.DEEP_SCRAPE, "timeout")
        assert next_provider is None


class TestRouterDegradedMode:
    """Test degraded mode behavior."""

    @pytest.fixture
    def mock_rotator(self):
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        return ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))

    @pytest.mark.asyncio
    async def test_enter_degraded_mode(self, router):
        """Enter degraded mode returns SearchResult with degraded=True."""
        result = await router.enter_degraded_mode("test query", "trace-7")

        assert isinstance(result, SearchResult)
        assert result.degraded is True
        assert result.trace_id == "trace-7"
        assert "All research providers unavailable" in result.degraded_message

    @pytest.mark.asyncio
    async def test_degraded_mode_has_no_provider(self, router):
        """Degraded result has provider=None."""
        result = await router.enter_degraded_mode("test query", "trace-8")

        assert result.provider is None
        assert result.key_id is None


class TestHealthStatus:
    """Test health status methods."""

    @pytest.fixture
    def mock_rotator(self):
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        return ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))

    def test_get_provider_health_default_available(self, router):
        """Unknown provider defaults to AVAILABLE."""
        health = router._get_provider_health(Provider.SEARXNG)
        assert health == HealthState.AVAILABLE

    def test_get_provider_health_cached(self, router):
        """Health is cached in _health dict."""
        router._health["searxng"] = HealthState.AVAILABLE
        health = router._get_provider_health(Provider.SEARXNG)
        assert health == HealthState.AVAILABLE

    @pytest.mark.asyncio
    async def test_refresh_health_no_keys(self, router, mock_rotator):
        """Key-based provider with no keys -> DOWN."""
        mock_rotator.status.return_value = {"keys": []}

        await router._refresh_health("tavily")

        assert router._health["tavily"] == HealthState.DOWN

    @pytest.mark.asyncio
    async def test_refresh_health_circuit_open(self, router, mock_rotator):
        """Provider with circuit OPEN -> DEGRADED."""
        mock_rotator.status.return_value = {
            "keys": [{"key_id": "k1", "circuit_state": "open", "credits_remaining": 500}]
        }

        await router._refresh_health("tavily")

        assert router._health["tavily"] == HealthState.DEGRADED

    @pytest.mark.asyncio
    async def test_refresh_health_credits_exhausted(self, router, mock_rotator):
        """Provider with credits_remaining=0 -> CREDITS_EXHAUSTED."""
        mock_rotator.status.return_value = {
            "keys": [{"key_id": "k1", "circuit_state": "closed", "credits_remaining": 0}]
        }

        await router._refresh_health("tavily")

        assert router._health["tavily"] == HealthState.CREDITS_EXHAUSTED

    @pytest.mark.asyncio
    async def test_refresh_health_available(self, router, mock_rotator):
        """Provider with credits and closed circuit -> AVAILABLE."""
        mock_rotator.status.return_value = {
            "keys": [{"key_id": "k1", "circuit_state": "closed", "credits_remaining": 500}]
        }

        await router._refresh_health("tavily")

        assert router._health["tavily"] == HealthState.AVAILABLE
