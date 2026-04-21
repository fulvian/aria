"""SearXNG MCP Server (FastMCP).

Exposes SearXNG search as `searxng-script/search` for privacy-focused fallback.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

from aria.agents.search.providers.searxng import SearXNGProvider

logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("searxng-script")
_provider: SearXNGProvider | None = None


async def _get_provider() -> SearXNGProvider:
    global _provider  # noqa: PLW0603
    if _provider is None:
        _provider = SearXNGProvider()
    return _provider


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search using SearXNG and return normalized results."""
    provider = await _get_provider()
    if not provider.is_enabled:
        return {
            "success": False,
            "error": "SearXNG disabled: set ARIA_SEARCH_SEARXNG_URL",
            "results": [],
        }

    try:
        hits = await provider.search(query=query, top_k=min(top_k, 25))
        results: list[dict[str, object]] = [
            {
                "title": h.title,
                "url": str(h.url),
                "snippet": h.snippet,
                "published_at": h.published_at.isoformat() if h.published_at else None,
                "score": h.score,
                "provider": h.provider,
            }
            for h in hits
        ]
        return {"success": True, "results": results}
    except Exception as exc:
        logger.error("SearXNG search error: %s", exc)
        return {"success": False, "error": str(exc), "results": []}


if __name__ == "__main__":
    mcp.run()
