"""Exa MCP Server (FastMCP).

Exposes Exa search as `exa-script/search` to match Search-Agent toolset.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

from aria.agents.search.providers.exa import ExaProvider
from aria.credentials.manager import CredentialManager

logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("exa-script")
_provider: ExaProvider | None = None


async def _get_provider() -> ExaProvider:
    global _provider  # noqa: PLW0603
    if _provider is None:
        cm = CredentialManager()
        key_info = await cm.acquire("exa")
        if key_info is None:
            raise RuntimeError("No Exa API key available")
        _provider = ExaProvider(api_key=key_info.key.get_secret_value())
    return _provider


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search using Exa and return normalized results."""
    provider = await _get_provider()
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
        logger.error("Exa search error: %s", exc)
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
