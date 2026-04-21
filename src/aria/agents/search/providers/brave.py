"""
Brave search provider adapter per blueprint §11.1.

NOTE: In MVP, Brave search is accessed via the upstream MCP server
`@brave/brave-search-mcp-server` (blueprint §10.3). This adapter exists
primarily for health monitoring and circuit breaker integration via the
CredentialManager, as the MCP server handles the actual search calls.

API docs: https://brave.com/search/api/
"""

import logging
from typing import Any

import httpx

from aria.agents.search.providers._http import parse_http_url, request_json_with_retry
from aria.agents.search.schema import ProviderStatus, SearchHit

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider:
    """Brave Search provider adapter.

    Wraps the Brave Search API directly for health checking.
    Actual search routing goes through brave-mcp MCP server per blueprint §10.3.

    This adapter is used by ProviderHealth for circuit breaker status.
    """

    name: str = "brave"

    def __init__(self, api_key: str) -> None:
        """Initialize with API key.

        Args:
            api_key: Brave Search API key.
        """
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (lazy initialization)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20),
                headers={
                    "X-Subscription-Token": self._api_key,
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET with retry logic."""
        client = self._get_client()
        return await request_json_with_retry(
            client=client,
            method="GET",
            url=BRAVE_SEARCH_URL,
            params=params,
            request_timeout=30.0,
            attempts=3,
        )

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute a Brave Search.

        Args:
            query: Search query.
            top_k: Maximum results.

        Returns:
            List of SearchHit.
        """
        params = {
            "q": query,
            "count": min(top_k, 20),
        }

        try:
            data = await self._get(params)
        except Exception as exc:
            logger.warning("Brave search failed: %s", exc)
            return []

        hits: list[SearchHit] = []
        web_results = data.get("web", {}).get("results", [])
        for item in web_results:
            url = parse_http_url(item.get("url", ""))
            if url is None:
                continue
            # Brave doesn't always provide published_date
            published_at = None
            raw_date = item.get("age")
            if raw_date:
                published_at = None  # Brave uses 'age' like "2 days ago" - skip parsing

            hits.append(
                SearchHit(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("description", ""),
                    published_at=published_at,
                    score=0.0,  # Brave doesn't provide relevance score
                    provider=self.name,
                    provider_raw=item,
                )
            )

        return hits

    async def health_check(self) -> ProviderStatus:
        """Check Brave API health.

        Returns:
            ProviderStatus based on API response.
        """
        try:
            client = self._get_client()
            response = await client.get(
                BRAVE_SEARCH_URL,
                params={"q": "health", "count": 1},
                timeout=10.0,
            )
            if response.status_code == 200:
                return ProviderStatus.AVAILABLE
            if response.status_code == 401:
                return ProviderStatus.DOWN
            if response.status_code == 429:
                return ProviderStatus.CREDITS_EXHAUSTED
            return ProviderStatus.DEGRADED
        except httpx.TimeoutException:
            return ProviderStatus.DEGRADED
        except Exception:
            return ProviderStatus.DOWN
