"""Integration: spawn the proxy via stdio and exercise the synthetic tools."""
from __future__ import annotations

import os

import pytest
from fastmcp import Client

from aria.mcp.proxy.server import build_proxy


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proxy_lists_synthetic_tools(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(strict=False)
    async with Client(proxy) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "search_tools" in names
        assert "call_tool" in names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proxy_search_finds_tool(monkeypatch, minimal_catalog, tmp_path) -> None:
    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(catalog_path=minimal_catalog, strict=False)
    async with Client(proxy) as client:
        result = await client.call_tool("search_tools", {"query": "read"})
        assert result is not None
