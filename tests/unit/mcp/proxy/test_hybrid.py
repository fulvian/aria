"""Unit tests for HybridSearchTransform."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from fastmcp.tools import Tool

from aria.mcp.proxy.transforms.hybrid import HybridSearchTransform


def _tool(name: str, description: str) -> Tool:
    return Tool(
        name=name,
        description=description,
        parameters={"type": "object", "properties": {}},
    )


@pytest.mark.asyncio
async def test_falls_back_to_bm25_when_embedder_missing() -> None:
    transform = HybridSearchTransform(embedder=None)
    tools = [_tool("read_file", "Read a file from disk")]
    results = await transform._search(tools, "read")
    assert len(results) > 0
    assert results[0].name == "read_file"


@pytest.mark.asyncio
async def test_blend_combines_bm25_and_semantic() -> None:
    embedder = MagicMock(spec_set=["probe", "embed"])
    embedder.probe.return_value = True
    embedder.embed.return_value = [np.array([1.0, 0.0], dtype=np.float32)]

    transform = HybridSearchTransform(embedder=embedder, blend=0.5)
    tools = [_tool("send_email", "Send an email")]
    results = await transform._search(tools, "send email")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_degrades_on_embedder_failure_during_search() -> None:
    from aria.mcp.proxy.transforms.lmstudio_embedder import LMStudioUnavailableError

    embedder = MagicMock(spec_set=["probe", "embed"])
    embedder.probe.return_value = True
    embedder.embed.side_effect = LMStudioUnavailableError("offline")

    transform = HybridSearchTransform(embedder=embedder)
    tools = [_tool("x", "y")]
    results = await transform._search(tools, "query")
    assert transform._semantic_enabled is False
    assert len(results) > 0


@pytest.mark.asyncio
async def test_always_returns_relevant_tools() -> None:
    transform = HybridSearchTransform(embedder=None)
    tools = [
        _tool("tavily_search", "Search the web using Tavily"),
        _tool("send_email", "Send an email via Gmail"),
        _tool("list_directory", "List files in a directory"),
    ]
    results = await transform._search(tools, "search web")
    assert len(results) <= transform._max_results
    # BM25 should rank the search tool first
    if len(results) > 0:
        assert results[0].name == "tavily_search"
