"""
Firecrawl search provider adapter per blueprint §11.1.

HTTP adapter for Firecrawl scrape/extract API per blueprint §11.1.
API docs: https://docs.firecrawl.dev/
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from aria.agents.search.schema import ProviderStatus, SearchHit

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"


class FirecrawlProvider:
    """Firecrawl provider for deep scraping and structured extraction.

    Supports both scrape (full page) and search (web search) per §11.1.
    """

    name: str = "firecrawl"

    def __init__(self, api_key: str) -> None:
        """Initialize with API key.

        Args:
            api_key: Firecrawl API key.
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
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, url: str, data: dict) -> httpx.Response:
        """POST with retry logic."""
        client = self._get_client()
        response = await client.post(url, json=data)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "1")
            await asyncio.sleep(float(retry_after))
            response = await client.post(url, json=data)
        return response

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute a Firecrawl web search.

        Uses the Firecrawl /search endpoint per docs.

        Args:
            query: Search query.
            top_k: Maximum results.

        Returns:
            List of SearchHit.
        """
        payload = {
            "query": query,
            "limit": top_k,
            "type": "websearch",
        }

        try:
            response = await self._post(FIRECRAWL_SEARCH_URL, payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Firecrawl search failed: %s", exc)
            return []

        hits: list[SearchHit] = []
        for item in data.get("data", []):
            url = item.get("url", "")
            # Published date handling
            published_at: datetime | None = None
            raw_date = item.get("published_date")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    published_at = None

            hits.append(
                SearchHit(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("description", ""),
                    published_at=published_at,
                    score=item.get("score", 0.0),
                    provider=self.name,
                    provider_raw=item,
                )
            )

        return hits

    async def scrape(self, url: str, **kwargs: Any) -> SearchHit | None:  # noqa: ANN401
        """Scrape a single URL and return content.

        Args:
            url: URL to scrape.

        Returns:
            SearchHit with full content in snippet.
        """
        payload = {
            "url": url,
            "formats": ["markdown", "metadata"],
        }

        try:
            response = await self._post(FIRECRAWL_SCRAPE_URL, payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Firecrawl scrape failed for %s: %s", url, exc)
            return None

        if not data.get("success"):
            return None

        content = data.get("data", {})
        markdown = content.get("markdown", "")
        metadata = content.get("metadata", {})

        return SearchHit(
            title=metadata.get("title", url),
            url=url,
            snippet=markdown[:500] if markdown else "",
            published_at=None,
            score=1.0,
            provider=self.name,
            provider_raw=data,
        )

    async def health_check(self) -> ProviderStatus:
        """Check Firecrawl API health.

        Returns:
            ProviderStatus based on API response.
        """
        try:
            client = self._get_client()
            response = await client.post(
                FIRECRAWL_SEARCH_URL,
                json={"query": "health", "limit": 1},
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
