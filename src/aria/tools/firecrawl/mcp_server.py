"""
Firecrawl MCP Server (FastMCP).

Exposes Firecrawl scrape and extract via MCP per blueprint §10.3 and §10.4.
This is the custom MCP wrapper that promotes the Python adapter to MCP.

Transport: stdio (for KiloCode MCP integration).

Usage:
    python -m aria.tools.firecrawl.mcp_server
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastmcp import FastMCP

from aria.agents.search.providers.firecrawl import FirecrawlProvider
from aria.credentials.manager import CredentialManager

# === Setup ===
logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("firecrawl-mcp")

# Global provider (initialized lazily)
_provider: FirecrawlProvider | None = None


async def _get_provider() -> FirecrawlProvider:
    """Get or create Firecrawl provider with credentials."""
    global _provider  # noqa: PLW0603
    if _provider is None:
        cm = CredentialManager()
        key_info = await cm.acquire("firecrawl")
        if key_info is None:
            raise RuntimeError("No Firecrawl API key available")
        _provider = FirecrawlProvider(api_key=key_info.key.get_secret_value())
    return _provider


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search the web using Firecrawl.

    Args:
        query: Search query string.
        top_k: Maximum number of results (default 10, max 20).

    Returns:
        JSON string of search results.
    """
    provider = await _get_provider()
    try:
        hits = await provider.search(query=query, top_k=min(top_k, 20))
        results: list[dict[str, object]] = [
            {
                "title": h.title,
                "url": str(h.url),
                "snippet": h.snippet,
                "published_at": (h.published_at.isoformat() if h.published_at else None),
                "score": h.score,
                "provider": h.provider,
            }
            for h in hits
        ]
        return {"success": True, "results": results}
    except Exception as exc:
        logger.error("Firecrawl search error: %s", exc)
        return {"success": False, "error": str(exc)}


@mcp.tool
async def scrape(url: str) -> dict[str, object]:
    """Scrape a URL and return content as markdown.

    Args:
        url: URL to scrape.

    Returns:
        JSON string with markdown content and metadata.
    """
    provider = await _get_provider()
    try:
        hit = await provider.scrape(url)
        if hit is None:
            return {"success": False, "error": "Scrape failed"}

        return {
            "success": True,
            "url": str(hit.url),
            "title": hit.title,
            "markdown": hit.snippet,
            "provider": hit.provider,
        }
    except Exception as exc:
        logger.error("Firecrawl scrape error: %s", exc)
        return {"success": False, "error": str(exc)}


@mcp.tool
async def extract(
    url: str,
    prompt: str = "Extract key information from this page",
    schema: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Extract structured data from a URL using Firecrawl AI extraction.

    Args:
        url: URL to extract from.
        schema: Optional JSON schema for structured extraction.

    Returns:
        JSON string with extracted data.
    """
    provider = await _get_provider()
    try:
        data = await provider.extract(url=url, prompt=prompt, schema=schema)
        return {"success": True, "data": data}
    except Exception as exc:
        logger.error("Firecrawl extract error: %s", exc)
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
