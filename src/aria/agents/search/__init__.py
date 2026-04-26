# ARIA search agents module
#
# Sub-agent wrappers and orchestration helpers:
# - search: web search router (SearXNG, Tavily, Firecrawl, Exa, Brave)
# - workspace: Google Workspace operations via MCP
#
# Usage:
#   from aria.agents.search import ResearchRouter, classify_intent
#   from aria.agents.search.router import Provider, Intent, FailureReason, SearchResult
#
#   router = ResearchRouter(rotator, state_path)
#   provider, key_info = await router.route(query, Intent.GENERAL_NEWS)

from aria.agents.search.intent import classify_intent
from aria.agents.search.router import (
    FailureReason,
    HealthState,
    Intent,
    NoProviderAvailableError,
    Provider,
    ResearchRouter,
    RouterError,
    SearchResult,
)

__all__ = [
    # Router
    "ResearchRouter",
    "RouterError",
    "NoProviderAvailableError",
    # Enums
    "Provider",
    "FailureReason",
    "HealthState",
    "Intent",
    # Data classes
    "SearchResult",
    # Intent classification
    "classify_intent",
]
