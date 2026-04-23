"""Unit tests for cost_policy module."""

import pytest

from aria.agents.search.cost_policy import (
    CostPolicy,
    CostTier,
    ProviderCostProfile,
    QueryBudget,
)


class TestCostTier:
    """Tests for CostTier enum ordering."""

    def test_tier_ordering(self):
        """Tier A < Tier B < Tier C < Tier D."""
        assert CostTier.A_FREE_UNLIMITED < CostTier.B_FREE_LIMITED
        assert CostTier.B_FREE_LIMITED < CostTier.C_COSTLY_EXTRACTION
        assert CostTier.C_COSTLY_EXTRACTION < CostTier.D_PAID_FALLBACK

    def test_tier_values(self):
        """Tier values are 0, 1, 2, 3."""
        assert CostTier.A_FREE_UNLIMITED == 0
        assert CostTier.B_FREE_LIMITED == 1
        assert CostTier.C_COSTLY_EXTRACTION == 2
        assert CostTier.D_PAID_FALLBACK == 3


class TestQueryBudget:
    """Tests for QueryBudget."""

    def test_default_allows_all_tiers(self):
        """Default budget allows all tiers."""
        budget = QueryBudget()
        assert budget.allows_tier(CostTier.A_FREE_UNLIMITED)
        assert budget.allows_tier(CostTier.D_PAID_FALLBACK)

    def test_max_tier_restricts(self):
        """Budget with max_tier=B blocks tier C and D."""
        budget = QueryBudget(max_tier=CostTier.B_FREE_LIMITED)
        assert budget.allows_tier(CostTier.A_FREE_UNLIMITED)
        assert budget.allows_tier(CostTier.B_FREE_LIMITED)
        assert not budget.allows_tier(CostTier.C_COSTLY_EXTRACTION)
        assert not budget.allows_tier(CostTier.D_PAID_FALLBACK)


class TestCostPolicy:
    """Tests for CostPolicy."""

    def test_default_profiles_loaded(self):
        """All 6 default providers are loaded."""
        policy = CostPolicy()
        assert policy.get_profile("searxng") is not None
        assert policy.get_profile("brave") is not None
        assert policy.get_profile("tavily") is not None
        assert policy.get_profile("exa") is not None
        assert policy.get_profile("firecrawl") is not None
        assert policy.get_profile("serpapi") is not None

    def test_tier_classification(self):
        """Providers are classified in correct tiers."""
        policy = CostPolicy()
        assert policy.tier("searxng") == CostTier.A_FREE_UNLIMITED
        assert policy.tier("brave") == CostTier.B_FREE_LIMITED
        assert policy.tier("tavily") == CostTier.B_FREE_LIMITED
        assert policy.tier("exa") == CostTier.B_FREE_LIMITED
        assert policy.tier("firecrawl") == CostTier.C_COSTLY_EXTRACTION
        assert policy.tier("serpapi") == CostTier.D_PAID_FALLBACK

    def test_unknown_provider_defaults_to_d(self):
        """Unknown provider defaults to tier D."""
        policy = CostPolicy()
        assert policy.tier("unknown_provider") == CostTier.D_PAID_FALLBACK

    def test_estimate_cost_free(self):
        """SearXNG has zero cost."""
        policy = CostPolicy()
        assert policy.estimate_cost("searxng") == 0.0
        assert policy.estimate_cost("searxng", advanced=True) == 0.0

    def test_estimate_cost_paid(self):
        """Tavily basic costs 1.0, advanced costs 2.0."""
        policy = CostPolicy()
        assert policy.estimate_cost("tavily") == 1.0
        assert policy.estimate_cost("tavily", advanced=True) == 2.0

    def test_sort_providers_by_cost(self):
        """Providers sorted cheapest first."""
        policy = CostPolicy()
        providers = ["tavily", "searxng", "firecrawl", "brave"]
        sorted_list = policy.sort_providers_by_cost(providers)
        assert sorted_list[0] == "searxng"
        assert "tavily" in sorted_list
        assert "brave" in sorted_list
        assert "firecrawl" in sorted_list

    def test_sort_with_budget_restriction(self):
        """Budget restricts eligible providers."""
        policy = CostPolicy()
        providers = ["tavily", "searxng", "firecrawl"]
        budget = QueryBudget(max_tier=CostTier.B_FREE_LIMITED)
        sorted_list = policy.sort_providers_by_cost(providers, budget)
        assert "searxng" in sorted_list
        assert "tavily" in sorted_list
        assert "firecrawl" not in sorted_list

    def test_tier_groups(self):
        """Providers grouped by tier correctly."""
        policy = CostPolicy()
        providers = ["searxng", "tavily", "brave", "firecrawl"]
        groups = policy.tier_groups(providers)
        assert "searxng" in groups[CostTier.A_FREE_UNLIMITED]
        assert "tavily" in groups[CostTier.B_FREE_LIMITED]
        assert "brave" in groups[CostTier.B_FREE_LIMITED]
        assert "firecrawl" in groups[CostTier.C_COSTLY_EXTRACTION]

    def test_custom_profiles_merge(self):
        """Custom profiles merge with defaults."""
        custom = {
            "custom_provider": ProviderCostProfile(
                provider="custom_provider",
                tier=CostTier.B_FREE_LIMITED,
            ),
        }
        policy = CostPolicy(profiles=custom)
        assert policy.tier("custom_provider") == CostTier.B_FREE_LIMITED
        assert policy.tier("searxng") == CostTier.A_FREE_UNLIMITED  # default preserved
