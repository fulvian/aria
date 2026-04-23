"""
Firecrawl search provider adapter per blueprint §11.1.

HTTP adapter for Firecrawl scrape/extract API per blueprint §11.1.
API docs: https://docs.firecrawl.dev/
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from aria.agents.search.providers._http import (
    KeyExhaustedError,
    parse_http_url,
    request_json_with_retry,
)
from aria.agents.search.schema import ProviderError, ProviderStatus, SearchHit

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"
FIRECRAWL_EXTRACT_URL = "https://api.firecrawl.dev/v1/extract"


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

    async def _post(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        """POST with retry logic."""
        client = self._get_client()
        return await request_json_with_retry(
            client=client,
            method="POST",
            url=url,
            json_body=data,
            request_timeout=30.0,
            attempts=3,
        )

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute a Firecrawl web search.

        Uses the Firecrawl /search endpoint per docs.

        Args:
            query: Search query.
            top_k: Maximum results.

        Returns:
            List of SearchHit.

        Raises:
            ProviderError: If the API key is exhausted or invalid.
        """
        payload = {
            "query": query,
            "limit": top_k,
        }
        payload.update({k: v for k, v in kwargs.items() if k in {"sources", "lang", "country"}})

        try:
            data = await self._post(FIRECRAWL_SEARCH_URL, payload)
        except KeyExhaustedError as exc:
            logger.warning("Firecrawl key exhausted (HTTP %s): %s", exc.status_code, exc.detail)
            raise ProviderError(
                provider=self.name,
                reason="credits_exhausted",
                status_code=exc.status_code,
                message=f"Firecrawl credits exhausted: {exc.detail}",
                retryable=True,
            ) from exc
        except Exception as exc:
            logger.warning("Firecrawl search failed: %s", exc)
            raise ProviderError(
                provider=self.name,
                reason="request_failed",
                message=f"Firecrawl request failed: {exc}",
                retryable=True,
            ) from exc

        hits: list[SearchHit] = []
        for item in data.get("data", []):
            url = parse_http_url(item.get("url", ""))
            if url is None:
                continue
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
            SearchHit with full content in snippet, or None on error.
        """
        payload = {
            "url": url,
            "formats": ["markdown"],
        }
        payload.update({k: v for k, v in kwargs.items() if k in {"onlyMainContent", "waitFor"}})

        try:
            data = await self._post(FIRECRAWL_SCRAPE_URL, payload)
        except KeyExhaustedError as exc:
            logger.warning("Firecrawl scrape key exhausted: %s", exc)
            raise ProviderError(
                provider=self.name,
                reason="credits_exhausted",
                status_code=exc.status_code,
                message=f"Firecrawl credits exhausted: {exc.detail}",
                retryable=True,
            ) from exc
        except Exception as exc:
            logger.warning("Firecrawl scrape failed for %s: %s", url, exc)
            return None

        if not data.get("success"):
            return None

        content = data.get("data", {})
        markdown = content.get("markdown", "")
        metadata = content.get("metadata", {})

        parsed_url = parse_http_url(url)
        if parsed_url is None:
            return None

        return SearchHit(
            title=metadata.get("title", url),
            url=parsed_url,
            snippet=markdown if isinstance(markdown, str) else "",
            published_at=None,
            score=1.0,
            provider=self.name,
            provider_raw=data,
        )

    async def extract(
        self,
        url: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run Firecrawl structured extraction."""
        payload: dict[str, Any] = {
            "urls": [url],
            "prompt": prompt,
        }
        if schema is not None:
            payload["schema"] = schema

        return await self._post(FIRECRAWL_EXTRACT_URL, payload)

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
            if response.status_code in (429, 402):
                return ProviderStatus.CREDITS_EXHAUSTED
            return ProviderStatus.DEGRADED
        except httpx.TimeoutException:
            return ProviderStatus.DEGRADED
        except Exception:
            return ProviderStatus.DOWN
