# Tests for SOCIAL intent tier ordering and fallback behavior (incl. Reddit conditional)

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.agents.search.router import (
    INTENT_TIERS,
    HealthState,
    Intent,
    Provider,
    ResearchRouter,
    SearchResult,
)
from aria.credentials.rotator import CircuitState, KeyInfo


class TestSocialTierOrder:
    """Test SOCIAL tier ladder order."""

    def test_social_tier_list_has_4_providers(self):
        """SOCIAL has 4 providers: REDDIT > SEARXNG > TAVILY > BRAVE."""
        tiers = INTENT_TIERS[Intent.SOCIAL]
        assert len(tiers) == 4
        assert tiers == (
            Provider.REDDIT,
            Provider.SEARXNG,
            Provider.TAVILY,
            Provider.BRAVE,
        )

    def test_social_starts_with_reddit(self):
        """SOCIAL tier 1 is REDDIT (conditional OAuth)."""
        tiers = INTENT_TIERS[Intent.SOCIAL]
        assert tiers[0] == Provider.REDDIT

    def test_social_has_keyless_fallback(self):
        """SOCIAL tier 2 is SEARXNG (keyless, self-hosted reddit engine)."""
        tiers = INTENT_TIERS[Intent.SOCIAL]
        assert tiers[1] == Provider.SEARXNG

    def test_social_ends_with_brave(self):
        """SOCIAL last tier is BRAVE."""
        tiers = INTENT_TIERS[Intent.SOCIAL]
        assert tiers[-1] == Provider.BRAVE

    def test_social_excludes_academic_providers(self):
        """SOCIAL does NOT include SCIENTIFIC_PAPERS (pubmed-mcp removed)."""
        tiers = INTENT_TIERS[Intent.SOCIAL]
        assert Provider.SCIENTIFIC_PAPERS not in tiers


class TestSocialRouterFallback:
    """Test SOCIAL fallback chain behavior."""

    @pytest.fixture
    def mock_rotator(self):
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        return ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))

    def test_fallback_reddit_down_returns_searxng(self, router):
        """REDDIT (DOWN or no creds) -> SEARXNG (for social)."""
        # Mark REDDIT as DOWN (simulating missing OAuth)
        router._health["reddit"] = HealthState.DOWN
        # SEARXNG should be the next tier attempted
        result = router.fallback(Provider.REDDIT, Intent.SOCIAL, "circuit_open")
        assert result == Provider.SEARXNG

    def test_fallback_searxng_returns_tavily(self, router):
        """SEARXNG fallback -> TAVILY (for social)."""
        next_provider = router.fallback(Provider.SEARXNG, Intent.SOCIAL, "rate_limit")
        assert next_provider == Provider.TAVILY

    def test_fallback_tavily_returns_brave(self, router):
        """TAVILY fallback -> BRAVE (for social)."""
        next_provider = router.fallback(Provider.TAVILY, Intent.SOCIAL, "credits_exhausted")
        assert next_provider == Provider.BRAVE

    def test_fallback_brave_returns_none(self, router):
        """BRAVE (last social tier) -> None."""
        next_provider = router.fallback(Provider.BRAVE, Intent.SOCIAL, "network_error")
        assert next_provider is None


class TestSocialRouterWithRedditDown:
    """Test SOCIAL routing when Reddit is DOWN (OAuth not configured)."""

    @pytest.fixture
    def mock_rotator(self):
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        router = ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))
        # Pre-set health: REDDIT DOWN, rest available
        router._health["reddit"] = HealthState.DOWN
        router._health["searxng"] = HealthState.AVAILABLE
        router._health["tavily"] = HealthState.AVAILABLE
        router._health["brave"] = HealthState.AVAILABLE
        return router

    @pytest.mark.asyncio
    async def test_social_routes_to_searxng_when_reddit_down(self, router, mock_rotator):
        """SOCIAL intent with REDDIT DOWN -> SEARXNG."""
        # Route should skip REDDIT (DOWN) and go to SEARXNG (keyless)
        result = await router.route("reddit discussion", Intent.SOCIAL, "trace-social-1")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.SEARXNG
        assert key is None  # keyless

    @pytest.mark.asyncio
    async def test_social_routes_to_tavily_when_reddit_and_searxng_down(self, router, mock_rotator):
        """SOCIAL with REDDIT DOWN + SEARXNG DOWN -> TAVILY."""
        router._health["searxng"] = HealthState.DOWN
        router._health["tavily"] = HealthState.AVAILABLE

        mock_key = MagicMock(spec=KeyInfo)
        mock_key.key_id = "tvly-1"
        mock_key.circuit_state = CircuitState.CLOSED
        mock_key.credits_remaining = 500
        mock_rotator.acquire.return_value = mock_key

        result = await router.route("reddit discussion", Intent.SOCIAL, "trace-social-2")

        assert isinstance(result, tuple)
        provider, key = result
        assert provider == Provider.TAVILY

    @pytest.mark.asyncio
    async def test_social_all_tiers_fail_degraded(self, router, mock_rotator):
        """SOCIAL all tiers fail -> degraded mode."""
        router._health["searxng"] = HealthState.DOWN
        router._health["tavily"] = HealthState.DOWN
        router._health["brave"] = HealthState.DOWN
        mock_rotator.acquire.return_value = None

        result = await router.route("reddit discussion", Intent.SOCIAL, "trace-social-3")

        assert isinstance(result, SearchResult)
        assert result.degraded is True
