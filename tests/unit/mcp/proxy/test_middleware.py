"""Unit tests for CapabilityMatrixMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.exceptions import ToolError

from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware


class _Reg:
    def __init__(self, mapping: dict[str, list[str]]):
        self._m = mapping

    def get_allowed_tools(self, agent: str) -> list[str]:
        return self._m.get(agent, [])

    def is_tool_allowed(self, agent: str, tool: str) -> bool:
        return tool in self._m.get(agent, [])


def _ctx(*, args: dict | None = None, tool_name: str | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.fastmcp_context = None  # prevent MagicMock auto-creation
    msg = MagicMock()
    msg.arguments = dict(args or {})
    if tool_name is not None:
        msg.name = tool_name
    ctx.message = msg
    return ctx


@pytest.mark.asyncio
async def test_on_call_tool_allows_when_caller_in_matrix() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"_caller_id": "search-agent", "q": "x"}, tool_name="tavily-mcp__search")
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"
    call_next.assert_awaited_once()
    # _caller_id must be stripped before forwarding
    args_passed = call_next.call_args[0][0].message.arguments
    assert "_caller_id" not in args_passed


@pytest.mark.asyncio
async def test_on_call_tool_extracts_nested_caller_id_for_proxy_call() -> None:
    reg = _Reg({"productivity-agent": ["google_workspace__create_doc"]})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(
        args={
            "name": "google_workspace__create_doc",
            "arguments": {
                "_caller_id": "productivity-agent",
                "title": "Briefing",
            },
        },
        tool_name="call_tool",
    )
    ctx.copy.side_effect = lambda **kwargs: MagicMock(message=kwargs["message"])
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"
    forwarded = call_next.call_args[0][0].message.arguments
    assert forwarded["name"] == "google_workspace__create_doc"
    assert "_caller_id" not in forwarded["arguments"]


@pytest.mark.asyncio
async def test_on_call_tool_denies_when_caller_not_in_matrix() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"_caller_id": "search-agent"}, tool_name="google_workspace__gmail_send")
    call_next = AsyncMock()
    with pytest.raises(ToolError, match="not allowed"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_denies_when_caller_absent() -> None:
    """Fail-closed: middleware denies non-synthetic tools when no caller identity is present."""
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"q": "x"}, tool_name="filesystem__read")
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="denied: no caller identity"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_proxy_requires_caller() -> None:
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(
        args={"name": "filesystem__read", "arguments": {"path": "/tmp/x"}},
        tool_name="call_tool",
    )
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="denied: no caller identity"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_proxy_does_not_borrow_ambient_legacy_env_caller(monkeypatch) -> None:
    reg = _Reg({"traveller-agent": ["airbnb__airbnb_search"]})
    mw = CapabilityMatrixMiddleware(reg)
    monkeypatch.setenv("ARIA_CALLER_ID", "traveller-agent")
    ctx = _ctx(
        args={"name": "fetch__fetch", "arguments": {"url": "https://example.com"}},
        tool_name="call_tool",
    )
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="denied: no caller identity"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_proxy_denies_synthetic_recursion() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(
        args={
            "name": "search_tools",
            "arguments": {"query": "tavily", "_caller_id": "search-agent"},
        },
        tool_name="call_tool",
    )
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="must be invoked directly"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_proxy_checks_backend_authorization() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(
        args={
            "name": "google_workspace__gmail_send",
            "arguments": {"_caller_id": "search-agent", "to": "x@example.com"},
        },
        tool_name="call_tool",
    )
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="not allowed"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_allows_synthetic_when_caller_absent() -> None:
    """Synthetic tools (search_tools, call_tool) are allowed even without caller."""
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"query": "test"}, tool_name="search_tools")
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"


@pytest.mark.asyncio
async def test_on_call_tool_permissive_when_caller_id_absent() -> None:
    """Legacy test name — now verifies fail-closed behavior for non-synthetic tools."""
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"q": "x"}, tool_name="filesystem__read")
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="denied: no caller identity"):
        await mw.on_call_tool(ctx, call_next)


@pytest.mark.asyncio
async def test_on_list_tools_filters_per_caller() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg, default_caller_env="ARIA_CALLER_ID")
    tool_a = MagicMock()
    tool_a.name = "tavily-mcp__search"
    tool_b = MagicMock()
    tool_b.name = "google_workspace__gmail_send"
    tool_c = MagicMock()
    tool_c.name = "search_tools"  # always_visible synthetic
    call_next = AsyncMock(return_value=[tool_a, tool_b, tool_c])
    ctx = _ctx()
    ctx.fastmcp_context = MagicMock()
    ctx.fastmcp_context.headers = {"X-ARIA-Caller-Id": "search-agent"}
    out = await mw.on_list_tools(ctx, call_next)
    names = [t.name for t in out]
    assert "tavily-mcp__search" in names
    assert "google_workspace__gmail_send" not in names
    # synthetic tools are always visible
    assert "search_tools" in names


@pytest.mark.asyncio
async def test_on_list_tools_passthrough_when_no_caller() -> None:
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)
    tool_s = MagicMock()
    tool_s.name = "search_tools"
    tool_a = MagicMock()
    tool_a.name = "filesystem__read"
    call_next = AsyncMock(return_value=[tool_a, tool_s])
    ctx = _ctx()
    ctx.fastmcp_context = None  # no caller info
    out = await mw.on_list_tools(ctx, call_next)
    assert out == [tool_s]


@pytest.mark.asyncio
async def test_synthetic_tools_never_filtered() -> None:
    reg = _Reg({"search-agent": []})  # empty allow-list
    mw = CapabilityMatrixMiddleware(reg)
    sym = MagicMock()
    sym.name = "search_tools"
    call = MagicMock()
    call.name = "call_tool"
    other = MagicMock()
    other.name = "filesystem__read"
    call_next = AsyncMock(return_value=[sym, call, other])
    ctx = _ctx()
    ctx.fastmcp_context = MagicMock()
    ctx.fastmcp_context.headers = {"X-ARIA-Caller-Id": "search-agent"}
    out = await mw.on_list_tools(ctx, call_next)
    names = [t.name for t in out]
    assert "search_tools" in names and "call_tool" in names
    assert "filesystem__read" not in names
