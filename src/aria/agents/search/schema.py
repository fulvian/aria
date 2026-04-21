"""
Search module schema and data models.

Defines SearchHit, Intent enum, and provider protocol per blueprint §11.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class Intent(StrEnum):
    """Classification of search query intent."""

    NEWS = "news"
    ACADEMIC = "academic"
    DEEP_SCRAPE = "deep_scrape"
    GENERAL = "general"
    PRIVACY = "privacy"
    FALLBACK = "fallback"


class ProviderStatus(StrEnum):
    """Health status of a search provider."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    DOWN = "down"
    CREDITS_EXHAUSTED = "credits_exhausted"


class SearchHit(BaseModel):
    """Normalized search result from any provider.

    Mirrors blueprint §11.4 schema. Raw provider payloads are stored
    in provider_raw but MUST NOT be exposed to the LLM.
    """

    title: str
    url: AnyHttpUrl = Field(description="Canonical URL")
    snippet: str
    published_at: datetime | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    provider: str = Field(description="Provider name (e.g. 'tavily', 'brave')")
    provider_raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw provider payload (internal only, not exposed in UI)",
    )

    model_config = ConfigDict(frozen=False)


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for search provider adapters per blueprint §11.1."""

    name: str

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute a search query and return normalized hits."""
        ...

    async def health_check(self) -> ProviderStatus:
        """Check provider health status."""
        ...


# Intent routing table per blueprint §11.2
INTENT_ROUTING: dict[Intent, list[str]] = {
    Intent.NEWS: ["tavily", "brave_news"],
    Intent.ACADEMIC: ["exa", "tavily"],
    Intent.DEEP_SCRAPE: ["firecrawl_extract", "firecrawl_scrape"],
    Intent.GENERAL: ["brave", "tavily"],
    Intent.PRIVACY: ["searxng", "brave"],
    Intent.FALLBACK: ["serpapi"],
}

# Provider weights for ranking per blueprint §11.4
PROVIDER_WEIGHTS: dict[str, float] = {
    "tavily": 1.0,
    "brave": 0.9,
    "brave_news": 0.85,
    "firecrawl_scrape": 0.8,
    "firecrawl_extract": 0.8,
    "exa": 0.95,
    "searxng": 0.7,
    "serpapi": 0.6,
}

# Intent keywords for classifier (regex-based, no LLM per sprint-03 plan)
INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.NEWS: [
        r"\b(oggi|ieri|ultim[ae]|breaking|news|notizi[ae]|attual[ei]|recent[ei])\b",
    ],
    Intent.ACADEMIC: [
        r"\b(paper|arxiv|publication|doi|abstract|studio|ricerc[ae]|journal|conference|research)\b",
    ],
    Intent.DEEP_SCRAPE: [
        r"\b(https?://|www\.|http://)\b",
    ],
    Intent.PRIVACY: [
        r"\b(privat[oe]|anonim[oe]|incognito|tracciament[oi]|cookies|dati person[ae]|privacy)\b",
    ],
}
