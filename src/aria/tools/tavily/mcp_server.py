"""
Tavily MCP Server (FastMCP).

Exposes Tavily search via MCP per blueprint §10.3 and §10.4.
This is the custom MCP wrapper that promotes the Python adapter to MCP.

Transport: stdio (for KiloCode MCP integration).

Usage:
    python -m aria.tools.tavily.mcp_server
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

from aria.agents.search.providers.tavily import TavilyProvider  # noqa: E402
from aria.credentials.manager import CredentialManager  # noqa: E402

# === Setup ===
logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("tavily-mcp")

# Global provider (initialized lazily)
_provider: TavilyProvider | None = None


async def _get_provider() -> TavilyProvider:
    """Get or create Firecrawl provider with credentials."""
    global _provider  # noqa: PLW0603
    if _provider is None:
        cm = CredentialManager()
        key_info = await cm.acquire("tavily")
        if key_info is None:
            raise RuntimeError("No Tavily API key available")
        _provider = TavilyProvider(api_key=key_info.key.get_secret_value())
    return _provider


@mcp.tool()
async def search(query: str, top_k: int = 10) -> str:
    """Search the web using Tavily.

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
        logger.error("Tavily search error: %s", exc)
        return json.dumps({"success": False, "error": str(exc)})


if __name__ == "__main__":
    mcp.run()
