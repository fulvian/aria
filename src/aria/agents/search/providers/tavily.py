"""
Tavily search provider adapter per blueprint §11.1.

HTTP adapter using httpx with tenacity retry per blueprint §11.3.
API docs: https://docs.tavily.com/
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

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyProvider:
    """Tavily search provider adapter.

    Normalizes Tavily API response to SearchHit per blueprint §11.4.
    Uses httpx AsyncClient with tenacity retry on 5xx/429 per §11.3 hardening.
    """

    name: str = "tavily"

    def __init__(self, api_key: str) -> None:
        """Initialize with API key.

        Args:
            api_key: Tavily API key.
        """
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (lazy initialization)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        client = self._get_client()
        return await request_json_with_retry(
            client=client,
            method="POST",
            url=TAVILY_SEARCH_URL,
            json_body=params,
            request_timeout=30.0,
            attempts=3,
        )

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute a Tavily search.

        Args:
            query: Search query string.
            top_k: Maximum number of results.

        Returns:
            List of SearchHit normalized from Tavily response.

        Raises:
            ProviderError: If the API key is exhausted or invalid.
        """
        params = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": top_k,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }
        # Allow override of search_depth via kwargs
        params.update({k: v for k, v in kwargs.items() if k in params})

        try:
            data = await self._request(params)
        except KeyExhaustedError as exc:
            logger.warning("Tavily key exhausted (HTTP %s): %s", exc.status_code, exc.detail)
            raise ProviderError(
                provider=self.name,
                reason="credits_exhausted",
                status_code=exc.status_code,
                message=f"Tavily credits exhausted: {exc.detail}",
                retryable=True,
            ) from exc
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)
            raise ProviderError(
                provider=self.name,
                reason="request_failed",
                message=f"Tavily request failed: {exc}",
                retryable=True,
            ) from exc

        hits: list[SearchHit] = []
        for result in data.get("results", []):
            url = parse_http_url(result.get("url", ""))
            if url is None:
                continue
            published_at: datetime | None = None
            raw_date = result.get("published_date")
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
                    score=result.get("score", 0.0),
                    provider=self.name,
                    provider_raw=result,
                )
            )

        return hits

    async def health_check(self) -> ProviderStatus:
        """Check Tavily API health via a lightweight search.

        Returns:
            ProviderStatus based on API response.
        """
        try:
            client = self._get_client()
            response = await client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": self._api_key,
                    "query": "health check",
                    "max_results": 1,
                    "search_depth": "basic",
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                return ProviderStatus.AVAILABLE
            if response.status_code == 401:
                return ProviderStatus.DOWN
            if response.status_code in (429, 432):
                return ProviderStatus.CREDITS_EXHAUSTED
            return ProviderStatus.DEGRADED
        except httpx.TimeoutException:
            return ProviderStatus.DEGRADED
        except Exception:
            return ProviderStatus.DOWN
