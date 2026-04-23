"""
Exa search provider adapter per blueprint §11.1.

HTTP adapter for Exa semantic search API.
API docs: https://exa.ai/
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

    async def _post(self, data: dict[str, Any]) -> dict[str, Any]:
        """POST with retry logic."""
        client = self._get_client()
        return await request_json_with_retry(
            client=client,
            method="POST",
            url=EXA_SEARCH_URL,
            json_body=data,
            request_timeout=30.0,
            attempts=3,
        )

    async def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:  # noqa: ANN401
        """Execute an Exa semantic search.

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
            "num_results": top_k,
            "text": True,
            "highlights": True,
        }

        try:
            data = await self._post(payload)
        except KeyExhaustedError as exc:
            logger.warning("Exa key exhausted (HTTP %s): %s", exc.status_code, exc.detail)
            raise ProviderError(
                provider=self.name,
                reason="credits_exhausted",
                status_code=exc.status_code,
                message=f"Exa credits exhausted: {exc.detail}",
                retryable=True,
            ) from exc
        except Exception as exc:
            logger.warning("Exa search failed: %s", exc)
            raise ProviderError(
                provider=self.name,
                reason="request_failed",
                message=f"Exa request failed: {exc}",
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
