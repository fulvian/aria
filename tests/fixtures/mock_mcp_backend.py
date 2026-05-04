#!/usr/bin/env python3
"""Configurable fake MCP stdio backend for integration testing.

Usage:
    python mock_mcp_backend.py --name X --tools '[{"name":"foo","description":"..."}]'
                               [--delay-list 5] [--delay-call 2]
                               [--fail-after 3] [--always-hang]
                               [--rate-limit-after 10]

Implements a real MCP stdio server using the `mcp` package so that
integration tests can exercise full protocol handshake without
external dependencies.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
    Tool,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock MCP backend for testing")
    parser.add_argument("--name", default="mock-backend", help="Backend name")
    parser.add_argument(
        "--tools",
        type=str,
        default='[{"name":"mock_tool","description":"A mock tool"}]',
        help="JSON list of tool definitions",
    )
    parser.add_argument(
        "--delay-list", type=float, default=0.0, help="Delay before list_tools response"
    )  # noqa: E501
    parser.add_argument(
        "--delay-call", type=float, default=0.0, help="Delay before call_tool response"
    )  # noqa: E501
    parser.add_argument(
        "--fail-after", type=int, default=0, help="Fail after N call_tool invocations"
    )  # noqa: E501
    parser.add_argument("--always-hang", action="store_true", help="Never respond to any request")
    parser.add_argument(
        "--rate-limit-after", type=int, default=0, help="Return rate-limit error after N calls"
    )  # noqa: E501
    return parser.parse_args()


def _build_tools(raw: str) -> list[Tool]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = []
    tools: list[Tool] = []
    for item in data:
        tools.append(
            Tool(
                name=item.get("name", "mock_tool"),
                description=item.get("description", ""),
                inputSchema=item.get("parameters", {"type": "object", "properties": {}}),
            )
        )
    return tools


async def _run(args: argparse.Namespace) -> None:
    tools = _build_tools(args.tools)
    call_count = 0

    app = Server(args.name)

    @app.list_tools()
    async def handle_list_tools(req: ListToolsRequest) -> ListToolsResult:  # noqa: ARG001
        if args.always_hang:
            await asyncio.Event().wait()  # hang forever

        if args.delay_list > 0:
            await asyncio.sleep(args.delay_list)

        return ListToolsResult(tools=tools)

    @app.call_tool()
    async def handle_call_tool(req: CallToolRequest) -> CallToolResult:  # noqa: ARG001
        nonlocal call_count
        call_count += 1

        if args.always_hang:
            await asyncio.Event().wait()  # hang forever

        if args.delay_call > 0:
            await asyncio.sleep(args.delay_call)

        if args.fail_after > 0 and call_count > args.fail_after:
            return CallToolResult(
                content=[TextContent(type="text", text="mock error")],
                isError=True,
            )

        if args.rate_limit_after > 0 and call_count > args.rate_limit_after:
            return CallToolResult(
                content=[TextContent(type="text", text="rate limit exceeded")],
                isError=True,
            )

        return CallToolResult(
            content=[TextContent(type="text", text=f"ok: {req.params.name}")],
            isError=False,
        )

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
