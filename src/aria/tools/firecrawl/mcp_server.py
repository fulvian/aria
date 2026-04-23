"""
Firecrawl MCP Server (FastMCP).

Exposes Firecrawl scrape and extract via MCP per blueprint §10.3 and §10.4.
This is the custom MCP wrapper that promotes the Python adapter to MCP.

Implements key rotation on failure: if one API key is exhausted,
the server automatically acquires the next available key from CredentialManager.

Transport: stdio (for KiloCode MCP integration).

Usage:
    python -m aria.tools.firecrawl.mcp_server
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from aria.agents.search.providers.firecrawl import FirecrawlProvider
from aria.agents.search.schema import ProviderError
from aria.credentials.manager import CredentialManager

# === Setup ===
logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("firecrawl-mcp")

DEFAULT_MAX_KEY_ROTATION_ATTEMPTS = 5


def _rotation_attempts(cm: CredentialManager, provider: str) -> int:
    """Compute rotation attempts to cover all configured keys at least once."""
    status = cm.status(provider)
    key_count = len(status.get("keys", [])) if isinstance(status, dict) else 0
    return max(DEFAULT_MAX_KEY_ROTATION_ATTEMPTS, key_count)


@mcp.tool
async def search(query: str, top_k: int = 10) -> dict[str, object]:
    """Search the web using Firecrawl.

    Args:
        query: Search query string.
        top_k: Maximum number of results (default 10, max 20).

    Returns:
        JSON with search results or error information.
    """
    cm = CredentialManager()
    last_error: str = ""
    max_attempts = _rotation_attempts(cm, "firecrawl")

    for attempt in range(max_attempts):
        key_info = await cm.acquire("firecrawl")
        if key_info is None:
            raise ToolError(
                f"Firecrawl: no available API keys after {attempt} attempts. "
                f"Last error: {last_error}"
            )

        provider = FirecrawlProvider(api_key=key_info.key.get_secret_value())
        try:
            hits = await provider.search(query=query, top_k=min(top_k, 20))
            await cm.report_success("firecrawl", key_info.key_id, credits_used=1)
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
        except ProviderError as exc:
            last_error = exc.message
            logger.warning(
                "Firecrawl key %s failed (attempt %d): %s",
                key_info.key_id,
                attempt + 1,
                exc.message,
            )
            await cm.report_failure("firecrawl", key_info.key_id, reason=exc.reason)
            continue
        except Exception as exc:
            last_error = str(exc)
            logger.error("Firecrawl unexpected error (attempt %d): %s", attempt + 1, exc)
            continue
        finally:
            await provider.close()

    raise ToolError(f"Firecrawl: all {max_attempts} key attempts failed. Last error: {last_error}")


@mcp.tool
async def scrape(url: str) -> dict[str, object]:
    """Scrape a URL and return content as markdown.

    Args:
        url: URL to scrape.

    Returns:
        JSON with markdown content and metadata.
    """
    cm = CredentialManager()
    last_error: str = ""
    max_attempts = _rotation_attempts(cm, "firecrawl")

    for attempt in range(max_attempts):
        key_info = await cm.acquire("firecrawl")
        if key_info is None:
            raise ToolError(
                "Firecrawl scrape: no available API keys "
                f"after {attempt} attempts. Last error: {last_error}"
            )

        provider = FirecrawlProvider(api_key=key_info.key.get_secret_value())
        try:
            hit = await provider.scrape(url)
            await cm.report_success("firecrawl", key_info.key_id, credits_used=1)
            if hit is None:
                return {"success": False, "error": "Scrape returned no content"}

            return {
                "success": True,
                "url": str(hit.url),
                "title": hit.title,
                "markdown": hit.snippet,
                "provider": hit.provider,
            }
        except ProviderError as exc:
            last_error = exc.message
            logger.warning(
                "Firecrawl scrape key %s failed (attempt %d): %s",
                key_info.key_id,
                attempt + 1,
                exc.message,
            )
            await cm.report_failure("firecrawl", key_info.key_id, reason=exc.reason)
            continue
        except Exception as exc:
            last_error = str(exc)
            logger.error("Firecrawl scrape unexpected error (attempt %d): %s", attempt + 1, exc)
            continue
        finally:
            await provider.close()

    raise ToolError(
        f"Firecrawl scrape: all {max_attempts} key attempts failed. Last error: {last_error}"
    )


@mcp.tool
async def extract(
    url: str,
    prompt: str = "Extract key information from this page",
    schema: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Extract structured data from a URL using Firecrawl AI extraction.

    Args:
        url: URL to extract from.
        prompt: What to extract.
        schema: Optional JSON schema for structured extraction.

    Returns:
        JSON with extracted data.
    """
    cm = CredentialManager()
    last_error: str = ""
    max_attempts = _rotation_attempts(cm, "firecrawl")

    for attempt in range(max_attempts):
        key_info = await cm.acquire("firecrawl")
        if key_info is None:
            raise ToolError(
                "Firecrawl extract: no available API keys "
                f"after {attempt} attempts. Last error: {last_error}"
            )

        provider = FirecrawlProvider(api_key=key_info.key.get_secret_value())
        try:
            data = await provider.extract(url=url, prompt=prompt, schema=schema)
            await cm.report_success("firecrawl", key_info.key_id, credits_used=1)
            return {"success": True, "data": data}
        except ProviderError as exc:
            last_error = exc.message
            logger.warning(
                "Firecrawl extract key %s failed (attempt %d): %s",
                key_info.key_id,
                attempt + 1,
                exc.message,
            )
            await cm.report_failure("firecrawl", key_info.key_id, reason=exc.reason)
            continue
        except Exception as exc:
            last_error = str(exc)
            logger.error("Firecrawl extract unexpected error (attempt %d): %s", attempt + 1, exc)
            continue
        finally:
            await provider.close()

    raise ToolError(
        f"Firecrawl extract: all {max_attempts} key attempts failed. Last error: {last_error}"
    )


if __name__ == "__main__":
    mcp.run()
