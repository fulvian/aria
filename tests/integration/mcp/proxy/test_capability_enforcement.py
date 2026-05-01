"""Integration: middleware blocks tools not in agent_capability_matrix.yaml."""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware
from aria.mcp.proxy.server import build_proxy


class _StubReg:
    def get_allowed_tools(self, agent: str) -> list[str]:
        return {"search-agent": ["filesystem__read"]}.get(agent, [])

    def is_tool_allowed(self, agent: str, tool: str) -> bool:
        return tool in self.get_allowed_tools(agent)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_agent_blocked_from_workspace(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(strict=False)
    # replace the registry-backed middleware with our stub
    proxy.middleware = [
        m for m in (proxy.middleware or []) if not isinstance(m, CapabilityMatrixMiddleware)
    ]
    proxy.add_middleware(CapabilityMatrixMiddleware(_StubReg()))

    async with Client(proxy) as client:
        with pytest.raises(ToolError, match="not allowed"):
            await client.call_tool(
                "call_tool",
                {
                    "_caller_id": "search-agent",
                    "name": "google_workspace__gmail_send",
                    "arguments": {"to": "x"},
                },
            )
