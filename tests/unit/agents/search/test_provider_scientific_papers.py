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

    def test_is_tier_3_in_academic(self):
        """SCIENTIFIC_PAPERS is tier 3 in ACADEMIC (after SEARXNG, PUBMED)."""
        from aria.agents.search.router import INTENT_TIERS

        academic_tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert academic_tiers[0] == Provider.SEARXNG
        assert academic_tiers[1] == Provider.PUBMED
        assert academic_tiers[2] == Provider.SCIENTIFIC_PAPERS

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
