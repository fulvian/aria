"""Per-agent capability enforcement on top of FastMCP's middleware pipeline.

The conventions:
- Agent prompts pass `_caller_id: "<agent>"` as an extra argument to
  search_tools / call_tool. The middleware strips it before forwarding.
- `tools/list` filtering uses the caller hint from a request header
  (`X-ARIA-Caller-Id`) when available, otherwise falls back to the
  `ARIA_CALLER_ID` env var.
- Synthetic tools (`search_tools`, `call_tool`) are always visible.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.types import CallToolRequestParams

from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from fastmcp.tools import Tool

logger = get_logger("aria.mcp.proxy.middleware")

ALWAYS_VISIBLE: frozenset[str] = frozenset({"search_tools", "call_tool"})


class _Registry(Protocol):
    def get_allowed_tools(self, agent: str) -> list[str]: ...
    def is_tool_allowed(self, agent: str, tool: str) -> bool: ...


class CapabilityMatrixMiddleware(Middleware):
    def __init__(
        self,
        registry: _Registry,
        *,
        default_caller_env: str = "ARIA_CALLER_ID",
        caller_header: str = "X-ARIA-Caller-Id",
    ) -> None:
        self._registry = registry
        self._env = default_caller_env
        self._header = caller_header

    async def on_list_tools(
        self,
        context: MiddlewareContext,
        call_next: Callable[..., Any],
    ) -> Sequence[Tool]:
        tools: Sequence[Tool] = await call_next(context)
        caller = self._resolve_caller(context)
        if not caller:
            return tools
        allowed = set(self._registry.get_allowed_tools(caller))
        return [t for t in tools if t.name in ALWAYS_VISIBLE or self._matches(t.name, allowed)]

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: Callable[..., Any],  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        args = dict(context.message.arguments or {})
        caller = args.pop("_caller_id", None) or self._resolve_caller(context)
        proxy_tool_name = getattr(context.message, "name", "")

        tool_to_check = args.get("name", "") if proxy_tool_name == "call_tool" else proxy_tool_name

        # Forward without _caller_id
        clean_params = CallToolRequestParams(name=proxy_tool_name, arguments=args)
        clean_ctx = context.copy(message=clean_params)

        if (
            caller
            and tool_to_check not in ALWAYS_VISIBLE
            and not self._registry.is_tool_allowed(caller, tool_to_check)
        ):
            logger.warning(
                "proxy.tool_denied",
                extra={
                    "agent": caller,
                    "tool": tool_to_check,
                    "proxy_tool": proxy_tool_name,
                },
            )
            raise ToolError(f"tool {tool_to_check} not allowed for {caller}")

        return await call_next(clean_ctx)

    def _resolve_caller(self, context: MiddlewareContext) -> str | None:
        fctx = getattr(context, "fastmcp_context", None)
        if fctx is not None:
            headers = getattr(fctx, "headers", None) or {}
            value = headers.get(self._header)
            if value:
                return str(value)
        return os.environ.get(self._env)

    @staticmethod
    def _matches(tool_name: str, allowed: Iterable[str]) -> bool:
        if tool_name in allowed:
            return True
        # legacy form: "server/tool" in matrix vs "server__tool" in proxy
        if "__" in tool_name:
            legacy = tool_name.replace("__", "/", 1)
            if legacy in allowed:
                return True
        # wildcard `server/*` or `server__*`
        for entry in allowed:
            if entry.endswith("/*") and tool_name.startswith(entry[:-2].replace("/", "__") + "__"):
                return True
            if entry.endswith("__*") and tool_name.startswith(entry[:-3] + "__"):
                return True
        return False
