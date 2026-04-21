"""
SearXNG search provider adapter per blueprint §11.1.

Self-hosted meta-search engine for privacy-focused routing.
Disabled by default in MVP; enabled when ARIA_SEARCH_SEARXNG_URL is set.
API: GET <SEARXNG_URL>/search?format=json&q=...
"""

import logging
import os
from datetime import datetime
from typing import Any

import httpx

from aria.agents.search.providers._http import parse_http_url, request_json_with_retry
from aria.agents.search.schema import ProviderStatus, SearchHit

logger = logging.getLogger(__name__)

DEFAULT_SEARXNG_URL = os.getenv("ARIA_SEARCH_SEARXNG_URL", "")


class SearXNGProvider:
    """SearXNG meta-search provider.

    Privacy-focused fallback per blueprint §11.1.
    Self-hosted option - only active when ARIA_SEARCH_SEARXNG_URL is configured.
    """

    name: str = "searxng"

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize with SearXNG instance URL.

        Args:
            base_url: Base URL of SearXNG instance. Falls back to
                      ARIA_SEARCH_SEARXNG_URL env var.
        """
        self._base_url = base_url or DEFAULT_SEARXNG_URL
        self._client: httpx.AsyncClient | None = None
        self._enabled = bool(self._base_url)

    @property
    def is_enabled(self) -> bool:
        """Check if SearXNG is configured."""
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
        """Execute a SearXNG search.

        Args:
            query: Search query.
            top_k: Maximum results.

        Returns:
            List of SearchHit.
        """
        if not self._enabled:
            return []

        params = {
            "q": query,
            "format": "json",
            "engines": "google,duckduckgo,bing",
        }

        try:
            client = self._get_client()
            data = await request_json_with_retry(
                client=client,
                method="GET",
                url=f"{self._base_url}/search",
                params=params,
                request_timeout=30.0,
                attempts=3,
            )
        except Exception as exc:
            logger.warning("SearXNG search error: %s", exc)
            return []

        hits: list[SearchHit] = []
        for result in data.get("results", [])[:top_k]:
            url = parse_http_url(result.get("url", ""))
            if url is None:
                continue
            published_at: datetime | None = None
            raw_date = result.get("publishedDate")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    published_at = None

            hits.append(
                SearchHit(
                    title=result.get("title", ""),
                    url=url,
                    snippet=result.get("content", ""),
                    published_at=published_at,
                    score=0.0,
                    provider=self.name,
                    provider_raw=result,
                )
            )

        return hits

    async def health_check(self) -> ProviderStatus:
        """Check SearXNG instance health.

        Returns:
            ProviderStatus based on health check response.
        """
        if not self._enabled:
            return ProviderStatus.DOWN

        try:
            client = self._get_client()
            response = await client.get(
                f"{self._base_url}/search",
                params={"q": "health", "format": "json"},
                timeout=10.0,
            )
            if response.status_code == 200:
                return ProviderStatus.AVAILABLE
            return ProviderStatus.DEGRADED
        except httpx.TimeoutException:
            return ProviderStatus.DEGRADED
        except Exception:
            return ProviderStatus.DOWN
