"""Exa MCP Server (FastMCP).

Exposes Exa search as `exa-script/search` to match Search-Agent toolset.

Implements key rotation on failure: if one API key is exhausted,
the server automatically acquires the next available key from CredentialManager.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from aria.agents.search.providers.exa import ExaProvider
from aria.agents.search.schema import ProviderError
from aria.credentials.manager import CredentialManager

logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("exa-script")

MAX_KEY_ROTATION_ATTEMPTS = 5


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search using Exa and return normalized results.

    Automatically rotates to the next API key if the current one is exhausted.

    Args:
        query: Search query string.
        top_k: Maximum number of results (default 10, max 25).

    Returns:
        JSON with search results or error information.
    """
    cm = CredentialManager()
    last_error: str = ""

    for attempt in range(MAX_KEY_ROTATION_ATTEMPTS):
        key_info = await cm.acquire("exa")
        if key_info is None:
            raise ToolError(
                f"Exa: no available API keys after {attempt} attempts. Last error: {last_error}"
            )

        provider = ExaProvider(api_key=key_info.key.get_secret_value())
        try:
            hits = await provider.search(query=query, top_k=min(top_k, 25))
            await cm.report_success("exa", key_info.key_id, credits_used=1)
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
        except ProviderError as exc:
            last_error = exc.message
            logger.warning(
                "Exa key %s failed (attempt %d): %s",
                key_info.key_id,
                attempt + 1,
                exc.message,
            )
            await cm.report_failure("exa", key_info.key_id, reason=exc.reason)
            await provider.close()
            continue
        except Exception as exc:
            last_error = str(exc)
            logger.error("Exa unexpected error (attempt %d): %s", attempt + 1, exc)
            await provider.close()
            continue

    raise ToolError(
        f"Exa: all {MAX_KEY_ROTATION_ATTEMPTS} key attempts failed. Last error: {last_error}"
    )


if __name__ == "__main__":
    mcp.run()
