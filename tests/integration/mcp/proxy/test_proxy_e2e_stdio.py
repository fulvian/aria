"""Integration: spawn the proxy via stdio and exercise the synthetic tools."""

from __future__ import annotations

import json

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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proxy_search_returns_catalog_tools_json(
    monkeypatch, minimal_catalog, tmp_path
) -> None:
    """search_tools returns JSON with tool names from catalog metadata."""
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")
    # Do NOT disable backends — we want catalog tools from minimal_catalog
    monkeypatch.delenv("ARIA_CALLER_ID", raising=False)
    proxy = build_proxy(
        catalog_path=minimal_catalog,
        proxy_config_path=proxy_yaml,
        strict=False,
    )
    async with Client(proxy) as client:
        result = await client.call_tool("search_tools", {"query": "read"})
        text = result.content[0].text if hasattr(result, "content") else str(result)
        parsed = json.loads(text)
        tool_names = [t["name"] for t in parsed]
        # minimal_catalog has filesystem with read/write
        assert any("filesystem" in n for n in tool_names)
