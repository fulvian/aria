"""
Intent-aware search router per blueprint §11.2.

Classifies query intent using keyword-based heuristics (no LLM in Sprint 1.3)
and routes to appropriate providers via SearchRouter.
"""

import re
from typing import TYPE_CHECKING

from aria.agents.search.schema import (
    INTENT_KEYWORDS,
    INTENT_ROUTING,
    PROVIDER_WEIGHTS,
    Intent,
    SearchHit,
)

if TYPE_CHECKING:
    from aria.agents.search.cache import SearchCache
    from aria.agents.search.health import ProviderHealth
    from aria.agents.search.schema import SearchProvider
    from aria.credentials.manager import CredentialManager


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

    Respects ProviderHealth status and CredentialManager state per
    blueprint §11.3 (circuit breaker) and §11.6 (graceful degradation).
    """

    def __init__(
        self,
        cm: "CredentialManager",
        health: "ProviderHealth",
        cache: "SearchCache",
        providers: dict[str, "SearchProvider"],
    ) -> None:
        """Initialize router with dependencies.

        Args:
            cm: CredentialManager for key acquisition.
            health: ProviderHealth for circuit breaker status.
            cache: SearchCache for query result caching.
            providers: Dict mapping provider name to provider adapter.
        """
        self._cm = cm
        self._health = health
        self._cache = cache
        self._providers = providers
        self._classifier = IntentClassifier()

    def classify(self, query: str) -> Intent:
        """Classify query intent."""
        return self._classifier.classify(query)

    async def route(self, query: str, intent: Intent | None = None) -> list[SearchHit]:
        """Route query to providers and return consolidated hits.

        1. Classify intent if not provided.
        2. Check cache first.
        3. For each provider in intent routing order:
           - Skip if health status is degraded/down/credits_exhausted.
           - Skip if no credits remaining in CredentialManager.
        4. Deduplicate and rank results.

        Args:
            query: Search query string.
            intent: Optional pre-classified intent.

        Returns:
            List of deduplicated, ranked SearchHit.
        """
        from aria.agents.search.dedup import dedup_hits, rank_hits

        if intent is None:
            intent = self._classifier.classify(query)

        # Check cache first
        cached = await self._cache.get(query, intent.value)
        if cached is not None:
            return cached

        provider_names = INTENT_ROUTING.get(intent, ["serpapi"])
        all_hits: list[SearchHit] = []

        for provider_name in provider_names:
            # Skip providers not registered
            if provider_name not in self._providers:
                continue

            # Skip based on health status
            status = self._health.status(provider_name)
            if status.value in ("degraded", "down", "credits_exhausted"):
                continue

            # Try to acquire credentials
            key_info = await self._cm.acquire(provider_name)
            if key_info is None:
                # No credits or no key available
                continue

            provider = self._providers[provider_name]
            try:
                hits = await provider.search(query, top_k=10)
                await self._cm.report_success(provider_name, key_info.key_id, credits_used=1)
                all_hits.extend(hits)
            except Exception as exc:
                await self._cm.report_failure(provider_name, key_info.key_id, reason=str(exc))
                continue

        # Deduplicate and rank
        deduped = dedup_hits(all_hits)
        ranked = rank_hits(deduped, provider_weights=PROVIDER_WEIGHTS)

        # Cache results
        await self._cache.put(query, intent.value, ranked)

        return ranked
