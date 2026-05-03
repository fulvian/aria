"""Per-agent capability enforcement on top of FastMCP's middleware pipeline.

The conventions:
- Agent prompts pass `_caller_id: "<agent>"` inside `call_tool.arguments`
  because the synthetic `call_tool` schema accepts only `name` and
  `arguments`.
- `search_tools` accepts only `query`, so caller-aware discovery can only rely
  on transport metadata (`X-ARIA-Caller-Id`) or the proxy process env var.
- Synthetic tools (`search_tools`, `call_tool`) are always visible in
  `tools/list`, but backend execution remains capability-scoped.
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
            return [t for t in tools if t.name in ALWAYS_VISIBLE]
        allowed = set(self._registry.get_allowed_tools(caller))
        return [t for t in tools if t.name in ALWAYS_VISIBLE or self._matches(t.name, allowed)]

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: Callable[..., Any],  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        args = dict(context.message.arguments or {})
        nested = args.get("arguments")
        caller = (
            args.pop("_caller_id", None)
            or (isinstance(nested, dict) and nested.pop("_caller_id", None))
            or self._resolve_caller(context)
        )
        proxy_tool_name = getattr(context.message, "name", "")

        tool_to_check = args.get("name", "") if proxy_tool_name == "call_tool" else proxy_tool_name

        # Forward without _caller_id
        clean_params = CallToolRequestParams(name=proxy_tool_name, arguments=args)
        clean_ctx = context.copy(message=clean_params)

        if proxy_tool_name == "search_tools" and not caller:
            logger.warning("proxy.caller_missing_search_tools")
            return await call_next(clean_ctx)

        if not caller:
            logger.warning(
                "proxy.caller_missing",
                extra={
                    "tool": tool_to_check,
                    "proxy_tool": proxy_tool_name,
                },
            )
            raise ToolError(
                f"tool {tool_to_check or proxy_tool_name} denied: no caller identity provided"
            )

        if proxy_tool_name == "call_tool" and tool_to_check in ALWAYS_VISIBLE:
            logger.warning(
                "proxy.synthetic_tool_via_call_tool_denied",
                extra={"agent": caller, "tool": tool_to_check},
            )
            raise ToolError(f"synthetic proxy tool {tool_to_check} must be invoked directly")

        if tool_to_check not in ALWAYS_VISIBLE and not self._registry.is_tool_allowed(
            caller,
            tool_to_check,
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
        value = os.environ.get(self._env)
        return value or None

    @staticmethod
    def _matches(tool_name: str, allowed: Iterable[str]) -> bool:  # noqa: PLR0911
        if tool_name in allowed:
            return True
        # legacy form: "server/tool" in matrix vs "server__tool" in proxy
        if "__" in tool_name:
            legacy = tool_name.replace("__", "/", 1)
            if legacy in allowed:
                return True
        # Real proxy names use single _ but matrix uses __.
        # Convert first _ to __ and try matching.
        if "_" in tool_name and "__" not in tool_name:
            first = tool_name.index("_")
            double_form = tool_name[:first] + "__" + tool_name[first + 1 :]
            if double_form in allowed:
                return True
        # wildcard `server/*` or `server__*`
        for entry in allowed:
            if entry.endswith("/*") and tool_name.startswith(entry[:-2].replace("/", "__") + "__"):
                return True
            if entry.endswith("__*") and tool_name.startswith(entry[:-3] + "__"):
                return True
            # Wildcard applies to single-underscore names too
            if entry.endswith("__*") and "_" in tool_name and "__" not in tool_name:
                first = tool_name.index("_")
                if tool_name[:first] == entry[:-3]:
                    return True
        return False
