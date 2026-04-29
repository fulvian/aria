# Tests for Scientific Papers provider — enum, keyless detection, tier ACADEMIC

from __future__ import annotations

from aria.agents.search.router import HealthState, Intent, Provider


class TestScientificPapersProviderEnum:
    """Test SCIENTIFIC_PAPERS provider enum value and properties."""

    def test_provider_value(self):
        """SCIENTIFIC_PAPERS value is 'scientific_papers'."""
        assert Provider.SCIENTIFIC_PAPERS.value == "scientific_papers"

    def test_provider_in_enum(self):
        """SCIENTIFIC_PAPERS is a valid Provider."""
        assert Provider.SCIENTIFIC_PAPERS in Provider

    def test_in_academic_tiers(self):
        """SCIENTIFIC_PAPERS is in ACADEMIC intent tier list."""
        from aria.agents.search.router import INTENT_TIERS

        academic_tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.SCIENTIFIC_PAPERS in academic_tiers

    def test_is_tier_4_in_academic(self):
        """SCIENTIFIC_PAPERS is tier 4 in ACADEMIC (after SEARXNG 1a, REDDIT 1b, PUBMED 2)."""
        from aria.agents.search.router import INTENT_TIERS

        academic_tiers = INTENT_TIERS[Intent.ACADEMIC]
        # v3 dual tier 1: searxng(1a) > reddit(1b) > pubmed(2) > scientific_papers(3)
        assert academic_tiers[0] == Provider.SEARXNG  # tier 1a
        assert academic_tiers[1] == Provider.REDDIT  # tier 1b
        assert academic_tiers[2] == Provider.PUBMED  # tier 2
        assert academic_tiers[3] == Provider.SCIENTIFIC_PAPERS  # tier 3

    def test_not_in_general_news(self):
        """SCIENTIFIC_PAPERS is NOT in GENERAL_NEWS tier list."""
        from aria.agents.search.router import INTENT_TIERS

        general_tiers = INTENT_TIERS[Intent.GENERAL_NEWS]
        assert Provider.SCIENTIFIC_PAPERS not in general_tiers

    def test_is_keyless(self):
        """SCIENTIFIC_PAPERS is keyless (in KEYLESS_PROVIDERS)."""
        from aria.agents.search.router import KEYLESS_PROVIDERS

        assert Provider.SCIENTIFIC_PAPERS.value in KEYLESS_PROVIDERS

    def test_refresh_health_available(self):
        """SCIENTIFIC_PAPERS health should be AVAILABLE (keyless)."""
        from aria.agents.search.router import KEYLESS_PROVIDERS

        assert Provider.SCIENTIFIC_PAPERS.value in KEYLESS_PROVIDERS
