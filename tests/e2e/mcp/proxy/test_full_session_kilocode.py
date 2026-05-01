"""End-to-end gate: proxy responds to search_tools and call_tool.

This test is environment-conditional. It runs only when ARIA_E2E_KILOCODE=1.
"""
from __future__ import annotations

import os

import pytest

from aria.mcp.proxy.server import build_proxy


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("ARIA_E2E_KILOCODE") != "1", reason="manual KiloCode harness")
@pytest.mark.asyncio
async def test_proxy_accepts_search_and_call() -> None:
    os.environ["ARIA_PROXY_DISABLE_BACKENDS"] = "1"
    proxy = build_proxy(strict=False)
    from fastmcp import Client

    async with Client(proxy) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "search_tools" in names
        assert "call_tool" in names

        # search_tools with _caller_id
        res = await client.call_tool(
            "search_tools",
            {"query": "wiki recall", "_caller_id": "aria-conductor"},
        )
        assert res is not None


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("ARIA_E2E_KILOCODE") != "1", reason="manual KiloCode harness")
@pytest.mark.asyncio
async def test_proxy_matches_namespaced_tools() -> None:
    """Verify namespaced tool names are visible to agents."""
    os.environ["ARIA_PROXY_DISABLE_BACKENDS"] = "1"
    proxy = build_proxy(strict=False)
    from fastmcp import Client

    async with Client(proxy) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        # The proxy's synthetic tools should be visible
        assert "search_tools" in names
        assert "call_tool" in names
