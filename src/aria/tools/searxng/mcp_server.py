"""SearXNG MCP Server (FastMCP).

Exposes SearXNG search as `searxng-script/search` for privacy-focused fallback.
No API key needed — only requires ARIA_SEARCH_SEARXNG_URL env var.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from aria.agents.search.providers.searxng import SearXNGProvider

logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("searxng-script")

_provider: SearXNGProvider | None = None


def _get_provider() -> SearXNGProvider:
    global _provider  # noqa: PLW0603
    if _provider is None:
        _provider = SearXNGProvider()
    return _provider


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search using SearXNG and return normalized results.

    Args:
        query: Search query string.
        top_k: Maximum number of results (default 10, max 25).

    Returns:
        JSON with search results or error information.
    """
    provider = _get_provider()
    if not provider.is_enabled:
        raise ToolError("SearXNG disabled: set ARIA_SEARCH_SEARXNG_URL environment variable")

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
        raise ToolError(f"SearXNG search failed: {exc}") from exc


if __name__ == "__main__":
    mcp.run()
