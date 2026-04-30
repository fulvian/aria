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

    def test_academic_tier_list_has_7_providers(self):
        """ACADEMIC has 7 providers (pubmed removed): SEARXNG(1a) > REDDIT(1b) > SCIENTIFIC_PAPERS(2) > TAVILY(3) > EXA(4) > BRAVE(5) > FETCH(6)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert len(tiers) == 7
        assert tiers == (
            Provider.SEARXNG,  # 1a — free, unlimited
            Provider.REDDIT,  # 1b — free, unlimited
            Provider.SCIENTIFIC_PAPERS,  # 2 — covers PubMed via source="europepmc"
            Provider.TAVILY,  # 3
            Provider.EXA,  # 4
            Provider.BRAVE,  # 5
            Provider.FETCH,  # 6
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

    def test_academic_includes_scientific(self):
        """ACADEMIC includes SCIENTIFIC_PAPERS (covers PubMed via source='europepmc')."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.SCIENTIFIC_PAPERS in tiers
        # pubmed-mcp REMOVED 2026-04-30: verify by value
        assert "pubmed" not in [p.value for p in tiers]


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

    def test_fallback_reddit_returns_scientific_papers(self, router):
        """REDDIT fallback -> SCIENTIFIC_PAPERS (tier 1b -> tier 2 for academic, pubmed removed)."""
        next_provider = router.fallback(Provider.REDDIT, Intent.ACADEMIC, "network_error")
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
