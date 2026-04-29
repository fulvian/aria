# Tests for Reddit provider — enum, tier SOCIAL, keyless (v3)
#
# v3: Reddit passa da OAuth-gated (jordanburke/reddit-mcp-server) a keyless
# (eliasbiondo/reddit-mcp-server). KEYLESS_PROVIDERS ora include 'reddit'.
# Vedi docs/analysis/report_gemme_reddit_mcp.md

from __future__ import annotations

from aria.agents.search.router import Intent, Provider


class TestRedditProviderEnum:
    """Test REDDIT provider enum value and properties (v3 keyless)."""

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

    def test_is_tier_1b_in_general_news(self):
        """REDDIT is tier 1b in GENERAL_NEWS (v3 dual tier 1)."""
        from aria.agents.search.router import INTENT_TIERS

        general_tiers = INTENT_TIERS[Intent.GENERAL_NEWS]
        # v3: REDDIT is always tier 1b (free+unlimited)
        assert Provider.REDDIT in general_tiers
        assert general_tiers[0] == Provider.SEARXNG  # tier 1a
        assert general_tiers[1] == Provider.REDDIT  # tier 1b

    def test_is_tier_1b_in_academic(self):
        """REDDIT is tier 1b in ACADEMIC (v3 dual tier 1)."""
        from aria.agents.search.router import INTENT_TIERS

        academic_tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert Provider.REDDIT in academic_tiers
        assert academic_tiers[0] == Provider.SEARXNG  # tier 1a
        assert academic_tiers[1] == Provider.REDDIT  # tier 1b

    def test_reddit_is_keyless(self):
        """REDDIT is now a keyless provider (in KEYLESS_PROVIDERS)."""
        from aria.agents.search.router import KEYLESS_PROVIDERS

        assert Provider.REDDIT.value in KEYLESS_PROVIDERS

    def test_reddit_bypasses_rotator(self):
        """REDDIT in KEYLESS_PROVIDERS means it bypasses Rotator."""
        from aria.agents.search.router import KEYLESS_PROVIDERS

        assert "reddit" in KEYLESS_PROVIDERS
