# Tests for ACADEMIC intent tier ordering and fallback behavior (v3 dual tier 1)

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.agents.search.router import (
    INTENT_TIERS,
    Intent,
    Provider,
    ResearchRouter,
)


class TestAcademicTierOrder:
    """Test ACADEMIC tier ladder order (v3 dual tier 1)."""

    def test_academic_tier_list_has_8_providers(self):
        """ACADEMIC has 8 providers: SEARXNG(1a) > REDDIT(1b) > PUBMED(2) > SCIENTIFIC_PAPERS(3) > TAVILY(4) > EXA(5) > BRAVE(6) > FETCH(7)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert len(tiers) == 8
        assert tiers == (
            Provider.SEARXNG,  # 1a — free, unlimited
            Provider.REDDIT,  # 1b — free, unlimited
            Provider.PUBMED,  # 2
            Provider.SCIENTIFIC_PAPERS,  # 3
            Provider.TAVILY,  # 4
            Provider.EXA,  # 5
            Provider.BRAVE,  # 6
            Provider.FETCH,  # 7
        )

    def test_academic_starts_with_searxng(self):
        """ACADEMIC tier 1a is SEARXNG (keyless, self-hosted)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[0] == Provider.SEARXNG
        assert tiers[1] == Provider.REDDIT  # tier 1b

    def test_academic_ends_with_fetch(self):
        """ACADEMIC last tier is FETCH (HTTP fallback)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[-1] == Provider.FETCH

    def test_academic_includes_reddit(self):
        """ACADEMIC includes REDDIT as tier 1b (v3 dual tier 1)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.REDDIT in tiers

    def test_academic_includes_pubmed_and_scientific(self):
        """ACADEMIC includes PUBMED and SCIENTIFIC_PAPERS."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.PUBMED in tiers
        assert Provider.SCIENTIFIC_PAPERS in tiers


class TestAcademicRouterFallback:
    """Test ACADEMIC fallback chain behavior (v3)."""

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
        """SEARXNG fallback -> REDDIT (tier 1a -> tier 1b for academic)."""
        next_provider = router.fallback(Provider.SEARXNG, Intent.ACADEMIC, "rate_limit")
        assert next_provider == Provider.REDDIT

    def test_fallback_reddit_returns_pubmed(self, router):
        """REDDIT fallback -> PUBMED (tier 1b -> tier 2 for academic)."""
        next_provider = router.fallback(Provider.REDDIT, Intent.ACADEMIC, "network_error")
        assert next_provider == Provider.PUBMED

    def test_fallback_pubmed_returns_scientific_papers(self, router):
        """PUBMED fallback -> SCIENTIFIC_PAPERS (for academic)."""
        next_provider = router.fallback(Provider.PUBMED, Intent.ACADEMIC, "rate_limit")
        assert next_provider == Provider.SCIENTIFIC_PAPERS

    def test_fallback_scientific_papers_returns_tavily(self, router):
        """SCIENTIFIC_PAPERS fallback -> TAVILY (for academic)."""
        next_provider = router.fallback(Provider.SCIENTIFIC_PAPERS, Intent.ACADEMIC, "circuit_open")
        assert next_provider == Provider.TAVILY

    def test_fallback_academic_tavily_returns_exa(self, router):
        """TAVILY fallback -> EXA (for academic)."""
        next_provider = router.fallback(Provider.TAVILY, Intent.ACADEMIC, "credits_exhausted")
        assert next_provider == Provider.EXA

    def test_fallback_academic_exa_returns_brave(self, router):
        """EXA fallback -> BRAVE (for academic)."""
        next_provider = router.fallback(Provider.EXA, Intent.ACADEMIC, "timeout")
        assert next_provider == Provider.BRAVE

    def test_fallback_academic_brave_returns_fetch(self, router):
        """BRAVE fallback -> FETCH (for academic)."""
        next_provider = router.fallback(Provider.BRAVE, Intent.ACADEMIC, "network_error")
        assert next_provider == Provider.FETCH

    def test_fallback_academic_fetch_returns_none(self, router):
        """FETCH (last academic tier) -> None."""
        next_provider = router.fallback(Provider.FETCH, Intent.ACADEMIC, "rate_limit")
        assert next_provider is None
