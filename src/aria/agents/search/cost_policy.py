"""
Cost policy engine for search provider tiering per Searcher Optimizer Plan §5.

Classifies providers into cost tiers and estimates marginal cost per query
to enable free-first routing with budget-aware escalation.
"""

from enum import IntEnum

from pydantic import BaseModel, Field


class CostTier(IntEnum):
    """Provider cost tiers — lower value = cheaper/more preferred.

    Tier A: Free-unlimited (self-hosted)
    Tier B: Free-limited (monthly credits)
    Tier C: Costly extraction (per-page pricing)
    Tier D: Last-resort paid fallback
    """

    A_FREE_UNLIMITED = 0
    B_FREE_LIMITED = 1
    C_COSTLY_EXTRACTION = 2
    D_PAID_FALLBACK = 3


class ProviderCostProfile(BaseModel):
    """Cost profile for a single search provider.

    Attributes:
        provider: Provider name (e.g., 'searxng', 'tavily').
        tier: Cost tier classification.
        credits_per_search: Credits consumed per basic search.
        credits_per_advanced: Credits consumed per advanced/deep search.
        monthly_free_credits: Free credits available per month (None = unlimited).
        cost_per_1k_usd: Approximate cost per 1000 paid requests in USD.
    """

    provider: str
    tier: CostTier
    credits_per_search: float = 1.0
    credits_per_advanced: float = 2.0
    monthly_free_credits: float | None = None
    cost_per_1k_usd: float = 0.0


class QueryBudget(BaseModel):
    """Budget constraints for a single search query.

    Attributes:
        max_credits: Maximum credits to spend on this query.
        max_tier: Maximum cost tier to escalate to.
        reserve_budget: If True, prefer reserving credits for future queries.
    """

    max_credits: float = Field(default=10.0, ge=0.0)
    max_tier: CostTier = CostTier.D_PAID_FALLBACK
    reserve_budget: bool = False

    def allows_tier(self, tier: CostTier) -> bool:
        """Check if this budget allows using the given tier."""
        return tier <= self.max_tier


class CostPolicy:
    """Centralized cost policy engine for search provider selection.

    Maintains cost profiles for all providers and provides methods
    to estimate cost, classify tiers, and enforce budgets.
    """

    # Default profiles based on Searcher Optimizer Plan §3
    DEFAULT_PROFILES: dict[str, ProviderCostProfile] = {
        "searxng": ProviderCostProfile(
            provider="searxng",
            tier=CostTier.A_FREE_UNLIMITED,
            credits_per_search=0.0,
            credits_per_advanced=0.0,
            monthly_free_credits=None,  # unlimited
            cost_per_1k_usd=0.0,
        ),
        "brave": ProviderCostProfile(
            provider="brave",
            tier=CostTier.B_FREE_LIMITED,
            credits_per_search=1.0,
            credits_per_advanced=1.0,
            monthly_free_credits=1000.0,  # $5 free/month at $5/1k
            cost_per_1k_usd=5.0,
        ),
        "tavily": ProviderCostProfile(
            provider="tavily",
            tier=CostTier.B_FREE_LIMITED,
            credits_per_search=1.0,
            credits_per_advanced=2.0,
            monthly_free_credits=1000.0,
            cost_per_1k_usd=8.0,
        ),
        "exa": ProviderCostProfile(
            provider="exa",
            tier=CostTier.B_FREE_LIMITED,
            credits_per_search=1.0,
            credits_per_advanced=1.5,  # deep search
            monthly_free_credits=1000.0,
            cost_per_1k_usd=7.0,
        ),
        "firecrawl": ProviderCostProfile(
            provider="firecrawl",
            tier=CostTier.C_COSTLY_EXTRACTION,
            credits_per_search=2.0,
            credits_per_advanced=2.0,
            monthly_free_credits=500.0,  # one-time, not monthly
            cost_per_1k_usd=10.0,
        ),
        "serpapi": ProviderCostProfile(
            provider="serpapi",
            tier=CostTier.D_PAID_FALLBACK,
            credits_per_search=1.0,
            credits_per_advanced=1.0,
            monthly_free_credits=250.0,
            cost_per_1k_usd=25.0,
        ),
    }

    def __init__(
        self,
        profiles: dict[str, ProviderCostProfile] | None = None,
    ) -> None:
        """Initialize with optional custom profiles.

        Args:
            profiles: Custom provider cost profiles. Merged with defaults.
        """
        self._profiles = dict(self.DEFAULT_PROFILES)
        if profiles:
            self._profiles.update(profiles)

    def get_profile(self, provider: str) -> ProviderCostProfile | None:
        """Get cost profile for a provider.

        Args:
            provider: Provider name.

        Returns:
            Cost profile or None if unknown.
        """
        return self._profiles.get(provider)

    def tier(self, provider: str) -> CostTier:
        """Get cost tier for a provider.

        Args:
            provider: Provider name.

        Returns:
            Cost tier (defaults to D_PAID_FALLBACK for unknown providers).
        """
        profile = self._profiles.get(provider)
        return profile.tier if profile else CostTier.D_PAID_FALLBACK

    def estimate_cost(
        self,
        provider: str,
        advanced: bool = False,
    ) -> float:
        """Estimate credit cost for a single query to a provider.

        Args:
            provider: Provider name.
            advanced: Whether to use advanced/deep search mode.

        Returns:
            Estimated credits consumed.
        """
        profile = self._profiles.get(provider)
        if profile is None:
            return 1.0
        return profile.credits_per_advanced if advanced else profile.credits_per_search

    def sort_providers_by_cost(
        self,
        providers: list[str],
        budget: QueryBudget | None = None,
    ) -> list[str]:
        """Sort providers by ascending cost tier and credit cost.

        Args:
            providers: List of provider names to sort.
            budget: Optional budget constraint to filter by.

        Returns:
            Sorted list of provider names (cheapest first).
        """
        if budget is None:
            budget = QueryBudget()

        eligible = [p for p in providers if budget.allows_tier(self.tier(p))]

        return sorted(eligible, key=lambda p: (self.tier(p), self.estimate_cost(p)))

    def tier_groups(self, providers: list[str]) -> dict[CostTier, list[str]]:
        """Group providers by cost tier.

        Args:
            providers: List of provider names.

        Returns:
            Dict mapping CostTier to list of provider names.
        """
        groups: dict[CostTier, list[str]] = {}
        for p in providers:
            t = self.tier(p)
            groups.setdefault(t, []).append(p)
        return groups
