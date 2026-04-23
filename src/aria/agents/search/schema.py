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


class ProviderError(Exception):
    """Raised when a search provider call fails with a recoverable error.

    Carries enough context for the MCP server to decide whether to
    report failure to CredentialManager and retry with a different key.

    Attributes:
        provider: Provider name (e.g. "tavily").
        reason:  Machine-readable error category.
        status_code: HTTP status code, if applicable.
        message: Human-readable error description.
        retryable: Whether the caller should try another key.
    """

    def __init__(
        self,
        provider: str,
        reason: str,
        status_code: int | None = None,
        message: str = "",
        retryable: bool = True,
    ) -> None:
        self.provider = provider
        self.reason = reason
        self.status_code = status_code
        self.message = message or f"{provider} error: {reason}"
        self.retryable = retryable
        super().__init__(self.message)


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


# Intent routing table — free-first order per Searcher Optimizer Plan §5.2.
# Providers ordered by ascending cost tier:
# A(searxng) → B(brave,tavily,exa) → C(firecrawl) → D(serpapi)
INTENT_ROUTING: dict[Intent, list[str]] = {
    Intent.NEWS: ["searxng", "tavily", "brave_news", "exa"],
    Intent.ACADEMIC: ["exa", "tavily", "searxng"],
    Intent.DEEP_SCRAPE: ["firecrawl_extract", "firecrawl_scrape"],
    Intent.GENERAL: ["searxng", "brave", "exa", "tavily"],
    Intent.PRIVACY: ["searxng", "brave"],
    Intent.FALLBACK: ["serpapi"],
}

# Provider weights for ranking per blueprint §11.4 and Searcher Optimizer Plan §5.
# Free providers get competitive weight; paid providers get premium weight.
PROVIDER_WEIGHTS: dict[str, float] = {
    "searxng": 0.85,
    "brave": 0.9,
    "brave_news": 0.85,
    "tavily": 1.0,
    "exa": 0.95,
    "firecrawl_scrape": 0.8,
    "firecrawl_extract": 0.8,
    "serpapi": 0.6,
}

# Unified error reason constants per Searcher Optimizer Plan §6.3
ERROR_QUOTA_EXHAUSTED = "quota_exhausted"
ERROR_RATE_LIMITED = "rate_limited"
ERROR_TRANSIENT_UPSTREAM = "transient_upstream"
ERROR_INVALID_REQUEST = "invalid_request"
ERROR_PROVIDER_DOWN = "provider_down"

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
