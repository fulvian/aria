"""
Firecrawl MCP Server (FastMCP).

Exposes Firecrawl scrape and extract via MCP per blueprint §10.3 and §10.4.
This is the custom MCP wrapper that promotes the Python adapter to MCP.

Transport: stdio (for KiloCode MCP integration).

Usage:
    python -m aria.tools.firecrawl.mcp_server
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from aria.agents.search.providers.firecrawl import FirecrawlProvider  # noqa: E402
from aria.credentials.manager import CredentialManager  # noqa: E402

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


@mcp.tool()
async def search(query: str, top_k: int = 10) -> str:
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
        results = [
            {
                "title": h.title,
                "url": h.url,
                "snippet": h.snippet,
                "published_at": (h.published_at.isoformat() if h.published_at else None),
                "score": h.score,
                "provider": h.provider,
            }
            for h in hits
        ]
        return json.dumps({"success": True, "results": results}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Firecrawl search error: %s", exc)
        return json.dumps({"success": False, "error": str(exc)})


@mcp.tool()
async def scrape(url: str) -> str:
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
            return json.dumps({"success": False, "error": "Scrape failed"})

        return json.dumps(
            {
                "success": True,
                "url": hit.url,
                "title": hit.title,
                "markdown": hit.snippet,
                "provider": hit.provider,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error("Firecrawl scrape error: %s", exc)
        return json.dumps({"success": False, "error": str(exc)})


@mcp.tool()
async def extract(url: str, schema: str | None = None) -> str:
    """Extract structured data from a URL using Firecrawl AI extraction.

    Args:
        url: URL to extract from.
        schema: Optional JSON schema for structured extraction.

    Returns:
        JSON string with extracted data.
    """
    # Note: Firecrawl extract uses the same API as scrape with formats
    # This is a simplified implementation
    provider = await _get_provider()
    try:
        hit = await provider.scrape(url)
        if hit is None:
            return json.dumps({"success": False, "error": "Extract failed"})

        return json.dumps(
            {
                "success": True,
                "url": hit.url,
                "title": hit.title,
                "content": hit.snippet,
                "provider": hit.provider,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error("Firecrawl extract error: %s", exc)
        return json.dumps({"success": False, "error": str(exc)})


if __name__ == "__main__":
    mcp.run()
