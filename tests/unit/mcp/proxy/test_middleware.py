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
async def test_on_call_tool_denies_when_caller_not_in_matrix() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"_caller_id": "search-agent"}, tool_name="google_workspace__gmail_send")
    call_next = AsyncMock()
    with pytest.raises(ToolError, match="not allowed"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_permissive_when_caller_id_absent() -> None:
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)
    ctx = _ctx(args={"q": "x"}, tool_name="filesystem__read")
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"


@pytest.mark.asyncio
async def test_on_list_tools_filters_per_caller() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg, default_caller_env="ARIA_CALLER_ID")
    tool_a = MagicMock(); tool_a.name = "tavily-mcp__search"
    tool_b = MagicMock(); tool_b.name = "google_workspace__gmail_send"
    tool_c = MagicMock(); tool_c.name = "search_tools"  # always_visible synthetic
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
    tool_a = MagicMock(); tool_a.name = "filesystem__read"
    call_next = AsyncMock(return_value=[tool_a])
    ctx = _ctx()
    ctx.fastmcp_context = None  # no caller info
    out = await mw.on_list_tools(ctx, call_next)
    assert out == [tool_a]


@pytest.mark.asyncio
async def test_synthetic_tools_never_filtered() -> None:
    reg = _Reg({"search-agent": []})  # empty allow-list
    mw = CapabilityMatrixMiddleware(reg)
    sym = MagicMock(); sym.name = "search_tools"
    call = MagicMock(); call.name = "call_tool"
    other = MagicMock(); other.name = "filesystem__read"
    call_next = AsyncMock(return_value=[sym, call, other])
    ctx = _ctx()
    ctx.fastmcp_context = MagicMock()
    ctx.fastmcp_context.headers = {"X-ARIA-Caller-Id": "search-agent"}
    out = await mw.on_list_tools(ctx, call_next)
    names = [t.name for t in out]
    assert "search_tools" in names and "call_tool" in names
    assert "filesystem__read" not in names
