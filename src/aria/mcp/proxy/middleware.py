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
            logger.warning(
                "proxy.caller_missing_list_tools",
                extra={"tool_count": len(tools)},
            )
            return tools
        allowed = set(self._registry.get_allowed_tools(caller))
        return [t for t in tools if t.name in ALWAYS_VISIBLE or self._matches(t.name, allowed)]

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: Callable[..., Any],  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        args = dict(context.message.arguments or {})
        # _caller_id may live at top-level (when schema allows it) or nested
        # inside the "arguments" dict (when the MCP client strips unknown
        # top-level keys due to additionalProperties:false).
        nested = args.get("arguments")
        caller = (
            args.pop("_caller_id", None)
            or (isinstance(nested, dict) and nested.pop("_caller_id", None))
            or self._resolve_caller(context)
        )
        proxy_tool_name = getattr(context.message, "name", "")

        tool_to_check = args.get("name", "") if proxy_tool_name == "call_tool" else proxy_tool_name

        # When processing the synthetic call_tool (pass 1), re-inject
        # _caller_id into the nested arguments dict so it survives into the
        # second middleware pass that fires when the proxy forwards to the
        # actual backend tool.  Without this, pass 2 has no caller identity
        # and the middleware fail-closes incorrectly.
        if proxy_tool_name == "call_tool" and caller and isinstance(nested, dict):
            nested["_caller_id"] = caller

        clean_params = CallToolRequestParams(name=proxy_tool_name, arguments=args)
        clean_ctx = context.copy(message=clean_params)

        # Fail-closed: deny when caller identity is absent and the target
        # tool is not a synthetic proxy tool.  Synthetic tools (search_tools,
        # call_tool) are always allowed since they are the proxy's own
        # entry-points and perform their own policy checks.
        if not caller and tool_to_check not in ALWAYS_VISIBLE:
            logger.warning(
                "proxy.caller_missing",
                extra={
                    "tool": tool_to_check,
                    "proxy_tool": proxy_tool_name,
                },
            )
            raise ToolError(f"tool {tool_to_check} denied: no caller identity provided")

        if caller and tool_to_check not in ALWAYS_VISIBLE:
            allowed = set(self._registry.get_allowed_tools(caller))
            if not self._matches(tool_to_check, allowed):
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
        # wildcard `server_*`
        for entry in allowed:
            if entry.endswith("_*") and tool_name.startswith(entry[:-2] + "_"):
                return True
        return False
