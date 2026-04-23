"""
Intent-aware search router per blueprint §11.2 and Searcher Optimizer Plan §5.

Classifies query intent using keyword-based heuristics (no LLM in Sprint 1.3)
and routes to appropriate providers via tiered free-first economic routing
with quality gates, budget enforcement, and RRF fusion.
"""

import logging
import re
import time
from typing import TYPE_CHECKING

from aria.agents.search.cost_policy import CostPolicy, CostTier, QueryBudget
from aria.agents.search.fusion import RRFConfig, reciprocal_rank_fusion
from aria.agents.search.quality_gate import QualityGate
from aria.agents.search.quota_state import QuotaState
from aria.agents.search.schema import (
    INTENT_KEYWORDS,
    INTENT_ROUTING,
    PROVIDER_WEIGHTS,
    Intent,
    ProviderStatus,
    SearchHit,
)
from aria.agents.search.telemetry import ProviderOutcome, SearchEvent, SearchTelemetry

if TYPE_CHECKING:
    from aria.agents.search.cache import SearchCache
    from aria.agents.search.health import ProviderHealth
    from aria.agents.search.schema import SearchProvider
    from aria.credentials.manager import CredentialManager

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Keyword-based intent classifier.

    Sprint 1.3: regex heuristics only (no LLM call).
    LLM-based classification planned for Phase 2 per blueprint §8.2.
    """

    def classify(self, query: str) -> Intent:
        """Classify query intent using keyword matching.

        Args:
            query: The search query string.

        Returns:
            Intent classification.
        """
        query_lower = query.lower()

        # Order matters: more specific patterns first
        for intent_key, patterns in INTENT_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent_key

        return Intent.GENERAL


class SearchRouter:
    """Routes search queries to appropriate providers based on intent.

    Implements tiered free-first economic routing per Searcher Optimizer Plan §5:

    - Tier A (free-unlimited): SearXNG (primary mass backbone).
    - Tier B (free-limited monthly): Brave, Tavily, Exa.
    - Tier C (costly extraction): Firecrawl.
    - Tier D (last resort paid): SerpAPI.

    Flow:
    1. Classify intent → get ordered provider list from INTENT_ROUTING.
    2. Execute Tier A provider first (if available for intent).
    3. Evaluate quality gates on results.
    4. If quality insufficient, escalate to Tier B, then C/D.
    5. Apply RRF fusion if multiple providers contributed.
    6. Record telemetry events for each provider outcome.
    """

    def __init__(
        self,
        cm: "CredentialManager",
        health: "ProviderHealth",
        cache: "SearchCache",
        providers: dict[str, "SearchProvider"],
        *,
        cost_policy: CostPolicy | None = None,
        quota_state: QuotaState | None = None,
        quality_gate: QualityGate | None = None,
        telemetry: SearchTelemetry | None = None,
        rrf_config: RRFConfig | None = None,
    ) -> None:
        """Initialize router with dependencies.

        Args:
            cm: CredentialManager for key acquisition.
            health: ProviderHealth for circuit breaker status.
            cache: SearchCache for query result caching.
            providers: Dict mapping provider name to provider adapter.
            cost_policy: Optional CostPolicy (creates default if None).
            quota_state: Optional QuotaState (creates default if None).
            quality_gate: Optional QualityGate (creates default if None).
            telemetry: Optional SearchTelemetry (creates default if None).
            rrf_config: Optional RRF configuration for fusion.
        """
        self._cm = cm
        self._health = health
        self._cache = cache
        self._providers = providers
        self._classifier = IntentClassifier()
        self._cost_policy = cost_policy or CostPolicy()
        self._quota_state = quota_state or QuotaState()
        self._quality_gate = quality_gate or QualityGate()
        self._telemetry = telemetry or SearchTelemetry()
        self._rrf_config = rrf_config or RRFConfig()
        self._provider_aliases = {
            "brave_news": "brave",
            "firecrawl_extract": "firecrawl",
            "firecrawl_scrape": "firecrawl",
        }
        # Providers that do not require CredentialManager acquisition.
        # SearXNG is self-hosted/local and can run without API keys.
        self._credentialless_providers = {"searxng"}

    def classify(self, query: str) -> Intent:
        """Classify query intent."""
        return self._classifier.classify(query)

    async def route(  # noqa: PLR0912
        self,
        query: str,
        intent: Intent | None = None,
        budget: QueryBudget | None = None,
    ) -> list[SearchHit]:
        """Route query to providers using tiered free-first strategy.

        Per Searcher Optimizer Plan §5.2:
        1. Classify intent if not provided.
        2. Check cache first.
        3. Execute providers in tier order (free-first).
        4. After Tier A, evaluate quality gates.
        5. If insufficient, escalate to Tier B, then C/D.
        6. Apply RRF fusion on multi-provider results.
        7. Deduplicate and rank final results.

        Args:
            query: Search query string.
            intent: Optional pre-classified intent.
            budget: Optional budget constraint for this query.

        Returns:
            List of deduplicated, ranked SearchHit.
        """
        from aria.agents.search.dedup import dedup_hits, rank_hits

        if intent is None:
            intent = self._classifier.classify(query)

        if budget is None:
            budget = QueryBudget()

        # Check cache first
        cached = await self._cache.get(query, intent.value)
        if cached is not None:
            return cached

        provider_names = INTENT_ROUTING.get(intent, ["serpapi"])

        # Group providers by cost tier for escalation strategy
        tier_groups = self._cost_policy.tier_groups(provider_names)
        sorted_tiers = sorted(tier_groups.keys())

        # Collect results per provider (for RRF fusion)
        provider_results: dict[str, list[SearchHit]] = {}
        escalated = False

        for tier in sorted_tiers:
            if not budget.allows_tier(tier):
                continue

            tier_providers = tier_groups[tier]
            # Sort providers within tier by cost
            tier_providers = self._cost_policy.sort_providers_by_cost(tier_providers, budget)

            for provider_name in tier_providers:
                resolved_name = self._provider_aliases.get(provider_name, provider_name)
                hits = await self._execute_provider(
                    query=query,
                    provider_name=provider_name,
                    resolved_name=resolved_name,
                    tier=tier,
                    escalated=escalated,
                )
                if hits is not None:
                    provider_results[provider_name] = hits

            # After Tier A (free), evaluate quality gates before escalating
            if tier == CostTier.A_FREE_UNLIMITED and provider_results:
                all_tier_a_hits: list[SearchHit] = []
                for p_hits in provider_results.values():
                    all_tier_a_hits.extend(p_hits)

                quality_report = self._quality_gate.evaluate(all_tier_a_hits, intent)
                if quality_report.passed:
                    logger.debug(
                        "Quality gate PASSED at Tier A for intent=%s (%d results)",
                        intent.value,
                        len(all_tier_a_hits),
                    )
                    break
                logger.debug(
                    "Quality gate FAILED at Tier A: %s — escalating to paid providers",
                    quality_report.failed_gates,
                )
                escalated = True

        # Fusion: if multiple providers contributed results, use RRF
        all_hits: list[SearchHit]
        if len(provider_results) > 1:
            fusion_result = reciprocal_rank_fusion(provider_results, self._rrf_config)
            all_hits = fusion_result.hits
            logger.debug(
                "RRF fusion: %d providers → %d fused hits",
                fusion_result.provider_count,
                fusion_result.fused_count,
            )
        elif len(provider_results) == 1:
            all_hits = list(provider_results.values())[0]
        else:
            all_hits = []

        # Deduplicate and rank
        deduped = dedup_hits(all_hits)
        ranked = rank_hits(deduped, provider_weights=PROVIDER_WEIGHTS)

        # Cache results
        await self._cache.put(query, intent.value, ranked)

        return ranked

    async def _execute_provider(  # noqa: PLR0911, PLR0912
        self,
        query: str,
        provider_name: str,
        resolved_name: str,
        tier: CostTier,
        escalated: bool,
    ) -> list[SearchHit] | None:
        """Execute a single provider search with telemetry tracking.

        Args:
            query: Search query.
            provider_name: Provider name (possibly aliased).
            resolved_name: Resolved provider name.
            tier: Cost tier of this provider.
            escalated: Whether this is an escalation from a lower tier.

        Returns:
            List of SearchHit or None if provider failed/skipped.
        """
        start_time = time.monotonic()

        # Skip providers not registered
        if resolved_name not in self._providers:
            self._record_event(
                query=query,
                provider=provider_name,
                outcome=ProviderOutcome.SKIPPED,
                tier=tier,
                escalated=escalated,
                start_time=start_time,
            )
            return None

        # Check quota for paid providers
        estimated_cost = self._cost_policy.estimate_cost(resolved_name)
        if tier > CostTier.A_FREE_UNLIMITED:
            if not self._quota_state.can_afford(resolved_name, estimated_cost):
                logger.debug("Quota exhausted for %s, skipping", provider_name)
                self._record_event(
                    query=query,
                    provider=provider_name,
                    outcome=ProviderOutcome.QUOTA_EXHAUSTED,
                    tier=tier,
                    escalated=escalated,
                    start_time=start_time,
                )
                return None
            # Check if provider is reserved for high-value intents only
            if self._quota_state.is_reserved(resolved_name) and tier > CostTier.B_FREE_LIMITED:
                logger.debug("Provider %s is reserved, skipping", provider_name)
                self._record_event(
                    query=query,
                    provider=provider_name,
                    outcome=ProviderOutcome.SKIPPED,
                    tier=tier,
                    escalated=escalated,
                    start_time=start_time,
                )
                return None

        # Skip based on health status
        status = self._health.status(resolved_name)
        if status in {
            ProviderStatus.DEGRADED,
            ProviderStatus.DOWN,
            ProviderStatus.CREDITS_EXHAUSTED,
        }:
            self._record_event(
                query=query,
                provider=provider_name,
                outcome=ProviderOutcome.PROVIDER_DOWN,
                tier=tier,
                escalated=escalated,
                start_time=start_time,
            )
            return None

        provider = self._providers[resolved_name]
        key_info = None

        # Try to acquire credentials when required
        if resolved_name not in self._credentialless_providers:
            key_info = await self._cm.acquire(resolved_name)
            if key_info is None:
                self._record_event(
                    query=query,
                    provider=provider_name,
                    outcome=ProviderOutcome.QUOTA_EXHAUSTED,
                    tier=tier,
                    escalated=escalated,
                    start_time=start_time,
                )
                return None

        try:
            hits = await provider.search(query, top_k=10)
            if key_info is not None:
                await self._cm.report_success(resolved_name, key_info.key_id, credits_used=1)

            # Consume quota
            if tier > CostTier.A_FREE_UNLIMITED:
                self._quota_state.consume(resolved_name, estimated_cost)

            outcome = ProviderOutcome.SUCCESS if len(hits) > 0 else ProviderOutcome.EMPTY_RESULT

            self._record_event(
                query=query,
                provider=provider_name,
                outcome=outcome,
                tier=tier,
                escalated=escalated,
                start_time=start_time,
                result_count=len(hits),
                credits_used=estimated_cost if tier > CostTier.A_FREE_UNLIMITED else 0.0,
            )

            return hits

        except Exception as exc:
            if key_info is not None:
                await self._cm.report_failure(resolved_name, key_info.key_id, reason=str(exc))

            error_msg = str(exc).lower()
            if "rate" in error_msg or "429" in error_msg:
                outcome = ProviderOutcome.RATE_LIMITED
            elif "quota" in error_msg or "credit" in error_msg or "exhausted" in error_msg:
                outcome = ProviderOutcome.QUOTA_EXHAUSTED
            else:
                outcome = ProviderOutcome.TRANSIENT_ERROR

            self._record_event(
                query=query,
                provider=provider_name,
                outcome=outcome,
                tier=tier,
                escalated=escalated,
                start_time=start_time,
            )
            return None

    def _record_event(
        self,
        query: str,
        provider: str,
        outcome: ProviderOutcome,
        tier: CostTier,
        escalated: bool,
        start_time: float,
        result_count: int = 0,
        credits_used: float = 0.0,
    ) -> None:
        """Record a telemetry event.

        Args:
            query: Search query.
            provider: Provider name.
            outcome: Provider outcome.
            tier: Cost tier.
            escalated: Whether this was an escalation.
            start_time: Start time from time.monotonic().
            result_count: Number of results.
            credits_used: Credits consumed.
        """
        latency_ms = (time.monotonic() - start_time) * 1000
        event = SearchEvent(
            query=query[:200],
            provider=provider,
            outcome=outcome,
            credits_used=credits_used,
            result_count=result_count,
            latency_ms=round(latency_ms, 1),
            tier=int(tier),
            escalated=escalated,
        )
        self._telemetry.record(event)
