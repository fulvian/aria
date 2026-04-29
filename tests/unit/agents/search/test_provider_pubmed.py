# Tests for PubMed provider — enum, tier ACADEMIC, health check

from __future__ import annotations

from aria.agents.search.router import HealthState, Intent, Provider, ResearchRouter


class TestPubmedProviderEnum:
    """Test PUBMED provider enum value and properties."""

    def test_provider_value(self):
        """PUBMED value is 'pubmed'."""
        assert Provider.PUBMED.value == "pubmed"

    def test_provider_in_enum(self):
        """PUBMED is a valid Provider."""
        assert Provider.PUBMED in Provider

    def test_pubmed_in_academic_tiers(self):
        """PUBMED is in ACADEMIC intent tier list."""
        from aria.agents.search.router import INTENT_TIERS

        academic_tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.PUBMED in academic_tiers

    def test_pubmed_is_tier_3_in_academic(self):
        """PUBMED is tier 3 in ACADEMIC (after SEARXNG 1a, REDDIT 1b)."""
        from aria.agents.search.router import INTENT_TIERS

        academic_tiers = INTENT_TIERS[Intent.ACADEMIC]
        # v3 dual tier 1: searxng(1a) > reddit(1b) > pubmed(2)
        assert academic_tiers[0] == Provider.SEARXNG  # tier 1a
        assert academic_tiers[1] == Provider.REDDIT  # tier 1b
        assert academic_tiers[2] == Provider.PUBMED  # tier 2

    def test_pubmed_not_in_general_news(self):
        """PUBMED is NOT in GENERAL_NEWS tier list."""
        from aria.agents.search.router import INTENT_TIERS

        general_tiers = INTENT_TIERS[Intent.GENERAL_NEWS]
        assert Provider.PUBMED not in general_tiers

    def test_pubmed_not_keyless(self):
        """PUBMED is a key-based provider (not in KEYLESS_PROVIDERS)."""
        from aria.agents.search.router import KEYLESS_PROVIDERS

        assert Provider.PUBMED.value not in KEYLESS_PROVIDERS
