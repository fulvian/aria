"""
Tavily MCP Server (FastMCP).

Exposes Tavily search via MCP per blueprint §10.3 and §10.4.
This is the custom MCP wrapper that promotes the Python adapter to MCP.

Implements key rotation on failure: if one API key is exhausted (HTTP 432/401),
the server automatically acquires the next available key from CredentialManager.

Transport: stdio (for KiloCode MCP integration).

Usage:
    python -m aria.tools.tavily.mcp_server
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from aria.agents.search.providers.tavily import TavilyProvider
from aria.agents.search.schema import ProviderError
from aria.credentials.manager import CredentialManager

# === Setup ===
logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("tavily-mcp")

# Key rotation constants
MAX_KEY_ROTATION_ATTEMPTS = 5


async def _search_with_rotation(query: str, top_k: int) -> list[dict[str, object]]:
    """Execute search with automatic key rotation on failure.

    Acquires a key from CredentialManager, performs the search, and if the
    key is exhausted or invalid, reports the failure and tries the next key.

    Returns:
        List of normalized search result dicts.

    Raises:
        ToolError: If all keys are exhausted or no keys are available.
    """
    cm = CredentialManager()
    last_error: str = ""

    for attempt in range(MAX_KEY_ROTATION_ATTEMPTS):
        key_info = await cm.acquire("tavily")
        if key_info is None:
            raise ToolError(
                f"Tavily: no available API keys after {attempt} attempts. Last error: {last_error}"
            )

        provider = TavilyProvider(api_key=key_info.key.get_secret_value())
        try:
            hits = await provider.search(query=query, top_k=min(top_k, 20))
            # Success — report and return
            await cm.report_success("tavily", key_info.key_id, credits_used=1)
            return [
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
        except ProviderError as exc:
            last_error = exc.message
            logger.warning(
                "Tavily key %s failed (attempt %d): %s",
                key_info.key_id,
                attempt + 1,
                exc.message,
            )
            await cm.report_failure(
                "tavily",
                key_info.key_id,
                reason=exc.reason,
            )
            await provider.close()
            continue
        except Exception as exc:
            last_error = str(exc)
            logger.error("Tavily unexpected error (attempt %d): %s", attempt + 1, exc)
            await provider.close()
            continue
        finally:
            # Ensure provider client is cleaned up on each attempt
            pass

    raise ToolError(
        f"Tavily: all {MAX_KEY_ROTATION_ATTEMPTS} key attempts failed. Last error: {last_error}"
    )


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search the web using Tavily.

    Args:
        query: Search query string.
        top_k: Maximum number of results (default 10, max 20).

    Returns:
        JSON with search results or error information.
    """
    try:
        results = await _search_with_rotation(query, top_k)
        return {"success": True, "results": results}
    except ToolError:
        raise  # Let FastMCP handle ToolError -> isError: true
    except Exception as exc:
        logger.error("Tavily search error: %s", exc)
        raise ToolError(f"Tavily search failed: {exc}") from exc


if __name__ == "__main__":
    mcp.run()
