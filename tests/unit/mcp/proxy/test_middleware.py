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
    # _caller_id is re-injected into nested args so it survives pass 2
    assert forwarded["arguments"]["_caller_id"] == "productivity-agent"


@pytest.mark.asyncio
async def test_two_pass_call_tool_preserves_caller_into_backend_pass() -> None:
    """Regression: nested _caller_id must survive into the second middleware
    pass (backend tool invocation) and be stripped before the real backend call.

    Simulates the two-pass flow:
      Pass 1: synthetic call_tool with nested _caller_id
      Pass 2: backend tool receives _caller_id at top-level, strips it
    """
    reg = _Reg({"trader-agent": ["financekit-mcp_crypto_price"]})
    mw = CapabilityMatrixMiddleware(reg)

    # --- Pass 1: synthetic call_tool ---
    ctx_pass1 = _ctx(
        args={
            "name": "financekit-mcp_crypto_price",
            "arguments": {
                "coin": "bitcoin",
                "_caller_id": "trader-agent",
            },
        },
        tool_name="call_tool",
    )
    ctx_pass1.copy.side_effect = lambda **kwargs: MagicMock(message=kwargs["message"])
    call_next_pass1 = AsyncMock(return_value="ok")
    out1 = await mw.on_call_tool(ctx_pass1, call_next_pass1)
    assert out1 == "ok"

    # Verify _caller_id was re-injected into nested args
    forwarded_args = call_next_pass1.call_args[0][0].message.arguments
    assert forwarded_args["arguments"]["_caller_id"] == "trader-agent"

    # --- Pass 2: backend tool (as the proxy would forward) ---
    backend_args = dict(forwarded_args["arguments"])
    ctx_pass2 = _ctx(args=backend_args, tool_name="financekit-mcp_crypto_price")
    ctx_pass2.copy.side_effect = lambda **kwargs: MagicMock(message=kwargs["message"])
    call_next_pass2 = AsyncMock(return_value="backend_result")
    out2 = await mw.on_call_tool(ctx_pass2, call_next_pass2)
    assert out2 == "backend_result"

    # Verify _caller_id was stripped before the actual backend invocation
    final_args = call_next_pass2.call_args[0][0].message.arguments
    assert "_caller_id" not in final_args
    assert final_args["coin"] == "bitcoin"


@pytest.mark.asyncio
async def test_two_pass_call_tool_denies_backend_without_caller() -> None:
    """If caller identity is truly absent in pass 2 (e.g. re-injection was
    somehow skipped), the middleware must still fail-closed."""
    reg = _Reg({"trader-agent": ["financekit-mcp_crypto_price"]})
    mw = CapabilityMatrixMiddleware(reg)

    # Simulate pass 2 with no _caller_id (as would happen without the fix)
    ctx = _ctx(args={"coin": "bitcoin"}, tool_name="financekit-mcp_crypto_price")
    call_next = AsyncMock(return_value="ok")
    with pytest.raises(ToolError, match="denied: no caller identity"):
        await mw.on_call_tool(ctx, call_next)


@pytest.mark.asyncio
async def test_two_pass_single_underscore_runtime_name() -> None:
    """Regression for runtime names like financekit-mcp_crypto_price
    (single underscore). The _matches helper must map these to the
    double-underscore entries in the capability matrix."""
    reg = _Reg({"trader-agent": ["financekit-mcp__crypto_price"]})
    mw = CapabilityMatrixMiddleware(reg)

    # Pass 1: synthetic call_tool with runtime-style single-underscore name
    ctx = _ctx(
        args={
            "name": "financekit-mcp_crypto_price",
            "arguments": {
                "coin": "bitcoin",
                "_caller_id": "trader-agent",
            },
        },
        tool_name="call_tool",
    )
    ctx.copy.side_effect = lambda **kwargs: MagicMock(message=kwargs["message"])
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"

    # Pass 2: backend tool with single-underscore runtime name + _caller_id
    ctx2 = _ctx(
        args={"coin": "bitcoin", "_caller_id": "trader-agent"},
        tool_name="financekit-mcp_crypto_price",
    )
    ctx2.copy.side_effect = lambda **kwargs: MagicMock(message=kwargs["message"])
    call_next2 = AsyncMock(return_value="result")
    out2 = await mw.on_call_tool(ctx2, call_next2)
    assert out2 == "result"
    final_args = call_next2.call_args[0][0].message.arguments
    assert "_caller_id" not in final_args


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
    tool_a = MagicMock()
    tool_a.name = "filesystem__read"
    call_next = AsyncMock(return_value=[tool_a])
    ctx = _ctx()
    ctx.fastmcp_context = None  # no caller info
    out = await mw.on_list_tools(ctx, call_next)
    assert out == [tool_a]


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
