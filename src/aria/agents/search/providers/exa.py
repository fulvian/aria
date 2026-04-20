"""
Exa search provider adapter per blueprint §11.1.

HTTP adapter for Exa semantic search API.
API docs: https://exa.ai/
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx
import tenacity

from aria.agents.search.schema import ProviderStatus, SearchHit

logger = logging.getLogger(__name__)

EXA_SEARCH_URL = "https://api.exa.ai/search"


class ExaProvider:
    """Exa semantic search provider.

    Specializes in academic and deep content search per §11.1.
    """

    name: str = "exa"

    def __init__(self, api_key: str) -> None:
        """Initialize with API key.

        Args:
            api_key: Exa API key.
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

    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=4),
        retry=tenacity.retry_if_result(
            lambda r: r is not None and r.status_code in (429, 500, 502, 503, 504)
        ),
        stop=tenacity.stop_after_attempt(3),
        reraise=True,
    )
    async def _post(self, data: dict) -> httpx.Response:
        """POST with retry logic."""
        client = self._get_client()
        response = await client.post(EXA_SEARCH_URL, json=data)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "1")
            await asyncio.sleep(float(retry_after))
            response = await client.post(EXA_SEARCH_URL, json=data)
        return response

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute an Exa semantic search.

        Args:
            query: Search query.
            top_k: Maximum results.

        Returns:
            List of SearchHit.
        """
        payload = {
            "query": query,
            "num_results": top_k,
            "text": True,
            "highlights": True,
        }

        try:
            response = await self._post(payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Exa search failed: %s", exc)
            return []

        hits: list[SearchHit] = []
        for result in data.get("results", []):
            url = result.get("url", "")
            published_at: datetime | None = None
            raw_date = result.get("published_date")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    published_at = None

            # Build snippet from highlights or abstract
            snippet = ""
            highlights = result.get("highlights", [])
            if highlights:
                snippet = highlights[0][:500]
            elif result.get("text"):
                snippet = result["text"][:500]

            hits.append(
                SearchHit(
                    title=result.get("title", ""),
                    url=url,
                    snippet=snippet,
                    published_at=published_at,
                    score=result.get("score", 0.0),
                    provider=self.name,
                    provider_raw=result,
                )
            )

        return hits

    async def health_check(self) -> ProviderStatus:
        """Check Exa API health.

        Returns:
            ProviderStatus based on API response.
        """
        try:
            client = self._get_client()
            response = await client.post(
                EXA_SEARCH_URL,
                json={"query": "health", "num_results": 1},
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
