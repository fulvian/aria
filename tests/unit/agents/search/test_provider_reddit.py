# Tests for Reddit provider — enum, tier SOCIAL, OAuth condizionalità

from __future__ import annotations

from aria.agents.search.router import Intent, Provider


class TestRedditProviderEnum:
    """Test REDDIT provider enum value and properties."""

    def test_provider_value(self):
        """REDDIT value is 'reddit'."""
        assert Provider.REDDIT.value == "reddit"

    def test_provider_in_enum(self):
        """REDDIT is a valid Provider."""
        assert Provider.REDDIT in Provider

    def test_in_social_tiers(self):
        """REDDIT is in SOCIAL intent tier list."""
        from aria.agents.search.router import INTENT_TIERS

        social_tiers = INTENT_TIERS[Intent.SOCIAL]
        assert Provider.REDDIT in social_tiers

    def test_is_tier_1_in_social(self):
        """REDDIT is tier 1 in SOCIAL intent."""
        from aria.agents.search.router import INTENT_TIERS

        social_tiers = INTENT_TIERS[Intent.SOCIAL]
        assert social_tiers[0] == Provider.REDDIT

    def test_social_has_fallback_chain(self):
        """SOCIAL has fallback chain: REDDIT > SEARXNG > TAVILY > BRAVE."""
        from aria.agents.search.router import INTENT_TIERS

        social_tiers = INTENT_TIERS[Intent.SOCIAL]
        assert social_tiers == (
            Provider.REDDIT,
            Provider.SEARXNG,
            Provider.TAVILY,
            Provider.BRAVE,
        )

    def test_not_in_general_news(self):
        """REDDIT is NOT in GENERAL_NEWS tier list."""
        from aria.agents.search.router import INTENT_TIERS

        general_tiers = INTENT_TIERS[Intent.GENERAL_NEWS]
        assert Provider.REDDIT not in general_tiers

    def test_reddit_is_key_based(self):
        """REDDIT is a key-based provider (not in KEYLESS_PROVIDERS)."""
        from aria.agents.search.router import KEYLESS_PROVIDERS

        assert Provider.REDDIT.value not in KEYLESS_PROVIDERS
