"""
SerpAPI search provider adapter per blueprint §11.1.

Stub fallback provider - only enabled when ARIA_SEARCH_SERPAPI_ENABLED=1.
API: GET https://serpapi.com/search?api_key=...&q=...

SerpAPI is the last resort fallback per blueprint §11.6.
"""

import logging
import os
from datetime import datetime
from typing import Any

import httpx

from aria.agents.search.schema import ProviderStatus, SearchHit

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"


class SerpAPIProvider:
    """SerpAPI fallback provider.

    Last resort fallback per blueprint §11.6.
    Only enabled when ARIA_SEARCH_SERPAPI_ENABLED=1.
    """

    name: str = "serpapi"

    def __init__(self, api_key: str) -> None:
        """Initialize with API key.

        Args:
            api_key: SerpAPI key.
        """
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._enabled = os.getenv("ARIA_SEARCH_SERPAPI_ENABLED", "0") == "1"

    @property
    def is_enabled(self) -> bool:
        """Check if SerpAPI is enabled."""
        return self._enabled

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (lazy initialization)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute a SerpAPI search.

        Args:
            query: Search query.
            top_k: Maximum results.

        Returns:
            List of SearchHit.
        """
        if not self._enabled:
            return []

        params = {"api_key": self._api_key, "q": query, "num": str(top_k)}

        try:
            client = self._get_client()
            response = await client.get(SERPAPI_URL, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("SerpAPI search failed: %s", exc)
            return []
        except Exception as exc:
            logger.warning("SerpAPI search error: %s", exc)
            return []

        hits: list[SearchHit] = []
        for result in data.get("organic_results", [])[:top_k]:
            url = result.get("link", "")
            snippet = result.get("snippet", "")
            published_at: datetime | None = None

            # SerpAPI sometimes includes date in snippet
            raw_date = result.get("date")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(raw_date)
                except (ValueError, TypeError):
                    published_at = None

            hits.append(
                SearchHit(
                    title=result.get("title", ""),
                    url=url,
                    snippet=snippet,
                    published_at=published_at,
                    score=0.0,
                    provider=self.name,
                    provider_raw=result,
                )
            )

        return hits

    async def health_check(self) -> ProviderStatus:  # noqa: PLR0911
        """Check SerpAPI health.

        Returns:
            ProviderStatus based on API response.
        """
        if not self._enabled:
            return ProviderStatus.DOWN

        try:
            client = self._get_client()
            response = await client.get(
                SERPAPI_URL,
                params={"api_key": self._api_key, "q": "health", "num": 1},
                timeout=10.0,
            )
        except httpx.TimeoutException:
            return ProviderStatus.DEGRADED
        except Exception:
            return ProviderStatus.DOWN

        status_map = {
            200: ProviderStatus.AVAILABLE,
            401: ProviderStatus.DOWN,
            429: ProviderStatus.CREDITS_EXHAUSTED,
        }
        return status_map.get(response.status_code, ProviderStatus.DEGRADED)
