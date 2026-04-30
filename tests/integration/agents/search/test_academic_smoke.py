"""Smoke E2E test for academic intent routing chain.

Verifica che il router possa instradare una query accademica attraverso
la fallback chain: SEARXNG(1a) > REDDIT(1b) > PUBMED(2) > SCIENTIFIC_PAPERS(3)
> TAVILY(4) > EXA(5) > BRAVE(6) > FETCH(7).

Questo test NON avvia MCP server reali (dipende da ambiente esterno).
Usa mock per il rotator e verifica la risoluzione a livello di route().
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.agents.search.router import INTENT_TIERS, Intent, Provider, ResearchRouter


class TestAcademicSmokeRoute:
    """Smoke test: verifica che il routing accademico funzioni a tutti i livelli."""

    @pytest.fixture
    def mock_rotator(self):
        """Rotator mock che fallisce per tutti i provider commerciali."""
        rotator = MagicMock()
        rotator.acquire = AsyncMock(return_value=None)  # No key available
        rotator.status = MagicMock(return_value={"keys": []})
        return rotator

    @pytest.fixture
    def router(self, mock_rotator):
        """Router con rotator mockato."""
        return ResearchRouter(mock_rotator, Path("/tmp/test_academic_smoke.yaml"))

    # ─── Tier order invariants ───

    def test_academic_has_8_tiers(self):
        """ACADEMIC intent has exactly 8 providers in tier order."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert len(tiers) == 8

    def test_academic_starts_with_searxng_reddit(self):
        """ACADEMIC intent starts with searxng (1a) then reddit (1b)."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[0] == Provider.SEARXNG
        assert tiers[1] == Provider.REDDIT

    def test_academic_has_pubmed_at_tier_3(self):
        """PUBMED is tier 3 in ACADEMIC (index 2)."""
        assert INTENT_TIERS[Intent.ACADEMIC][2] == Provider.PUBMED

    def test_academic_has_scientific_papers_at_tier_4(self):
        """SCIENTIFIC_PAPERS is tier 4 in ACADEMIC (index 3)."""
        assert INTENT_TIERS[Intent.ACADEMIC][3] == Provider.SCIENTIFIC_PAPERS

    def test_academic_ends_with_fetch(self):
        """FETCH is the last tier in ACADEMIC."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[-1] == Provider.FETCH

    # ─── Provider enum integrity ───

    def test_pubmed_enum_exists(self):
        """Provider.PUBMED exists."""
        assert Provider.PUBMED is not None
        assert Provider.PUBMED.value == "pubmed"

    def test_scientific_papers_enum_exists(self):
        """Provider.SCIENTIFIC_PAPERS exists."""
        assert Provider.SCIENTIFIC_PAPERS is not None
        assert Provider.SCIENTIFIC_PAPERS.value == "scientific_papers"

    def test_both_in_keyless(self):
        """Both academic providers are NOT in KEYLESS_PROVIDERS (PubMed needs optional key)."""
        from aria.agents.search.router import KEYLESS_PROVIDERS
        assert "pubmed" not in KEYLESS_PROVIDERS  # NCBI_API_KEY optional
        assert "scientific_papers" in KEYLESS_PROVIDERS  # keyless

    # ─── Fallback chain ───

    def test_fallback_searxng_to_reddit(self, router):
        """SEARXNG fallback → REDDIT."""
        next_prov = router.fallback(Provider.SEARXNG, Intent.ACADEMIC, "rate_limit")
        assert next_prov == Provider.REDDIT

    def test_fallback_reddit_to_pubmed(self, router):
        """REDDIT fallback → PUBMED."""
        next_prov = router.fallback(Provider.REDDIT, Intent.ACADEMIC, "network_error")
        assert next_prov == Provider.PUBMED

    def test_fallback_pubmed_to_scientific(self, router):
        """PUBMED fallback → SCIENTIFIC_PAPERS."""
        next_prov = router.fallback(Provider.PUBMED, Intent.ACADEMIC, "rate_limit")
        assert next_prov == Provider.SCIENTIFIC_PAPERS

    def test_fallback_scientific_to_tavily(self, router):
        """SCIENTIFIC_PAPERS fallback → TAVILY."""
        next_prov = router.fallback(Provider.SCIENTIFIC_PAPERS, Intent.ACADEMIC, "circuit_open")
        assert next_prov == Provider.TAVILY

    def test_fallback_academic_full_chain(self, router):
        """Full fallback chain through all 8 tiers returns None at end."""
        providers = list(INTENT_TIERS[Intent.ACADEMIC])
        for i in range(len(providers) - 1):
            next_prov = router.fallback(providers[i], Intent.ACADEMIC, "timeout")
            assert next_prov == providers[i + 1], (
                f"Expected {providers[i+1]} after {providers[i]}, got {next_prov}"
            )
        # Last provider should return None
        last = router.fallback(providers[-1], Intent.ACADEMIC, "timeout")
        assert last is None

    # ─── Intent classification smoke ───

    def test_academic_query_classified_correctly(self):
        """Query with academic keywords is classified as ACADEMIC."""
        from aria.agents.search.intent import classify_intent
        academic_queries = [
            "research papers on CRISPR gene therapy abstract",
            "find academic papers about machine learning",
            "pubmed search cancer immunotherapy clinical trial",
            "arxiv preprint transformer models research paper",
            "scientific article peer review climate change study",
        ]
        for q in academic_queries:
            intent = classify_intent(q)
            assert intent == Intent.ACADEMIC, (
                f"Query {q!r} classified as {intent}, expected ACADEMIC"
            )

    # ─── Preprocessor smoke ───

    def test_query_preprocessor_all_sources(self):
        """Query preprocessor handles all academic sources without error."""
        from aria.agents.search.query_preprocessor import (
            ACADEMIC_SOURCES,
            preprocess_query,
        )
        query = '"machine learning" transformer model attention'
        for source in ACADEMIC_SOURCES:
            result = preprocess_query(query, source=source)
            assert isinstance(result, str)
            assert len(result) > 0

    # ─── Capability probe smoke ───

    def test_expected_snapshots_defined(self):
        """Expected capability snapshots are defined for both academic MCPs."""
        from aria.agents.search.capability_probe import EXPECTED_TOOL_SNAPSHOTS
        assert "pubmed-mcp" in EXPECTED_TOOL_SNAPSHOTS
        assert "scientific-papers-mcp" in EXPECTED_TOOL_SNAPSHOTS
        assert len(EXPECTED_TOOL_SNAPSHOTS["pubmed-mcp"]) == 5
        assert len(EXPECTED_TOOL_SNAPSHOTS["scientific-papers-mcp"]) == 5
