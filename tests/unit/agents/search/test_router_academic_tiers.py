# Tests for ACADEMIC intent tier ordering and fallback behavior

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
    """Test ACADEMIC tier ladder order."""

    def test_academic_tier_list_has_7_providers(self):
        """ACADEMIC has 7 providers: SEARXNG > PUBMED > SCIENTIFIC_PAPERS > TAVILY > EXA > BRAVE > FETCH."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert len(tiers) == 7
        assert tiers == (
            Provider.SEARXNG,
            Provider.PUBMED,
            Provider.SCIENTIFIC_PAPERS,
            Provider.TAVILY,
            Provider.EXA,
            Provider.BRAVE,
            Provider.FETCH,
        )

    def test_academic_starts_with_keyless(self):
        """ACADEMIC tier 1 is SEARXNG (keyless, self-hosted)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[0] == Provider.SEARXNG

    def test_academic_ends_with_fetch(self):
        """ACADEMIC last tier is FETCH (HTTP fallback)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[-1] == Provider.FETCH

    def test_academic_includes_pubmed_and_scientific(self):
        """ACADEMIC includes PUBMED and SCIENTIFIC_PAPERS."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.PUBMED in tiers
        assert Provider.SCIENTIFIC_PAPERS in tiers

    def test_academic_excludes_reddit(self):
        """ACADEMIC does NOT include REDDIT."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.REDDIT not in tiers


class TestAcademicRouterFallback:
    """Test ACADEMIC fallback chain behavior."""

    @pytest.fixture
    def mock_rotator(self):
        rotator = MagicMock()
        rotator.acquire = AsyncMock()
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        return ResearchRouter(mock_rotator, Path("/tmp/test_state.yaml"))

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
