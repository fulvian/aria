"""Wrapper around fastmcp.client.Client with mono-server transport.

Manages a single stdio subprocess backend. Provides connect, disconnect,
list_tools, call_tool, and is_healthy operations.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport
from mcp.types import TextContent

from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy.tier.backend_client")


class BackendClientError(Exception):
    """Generic error from BackendClient operations."""


class BackendClient:
    """Wraps a single fastmcp Client connected to a stdio backend.

    Args:
        name: Logical backend name for logging/metrics.
        command: Executable command.
        args: Command arguments.
        env: Environment variables dict.
    """

    def __init__(
        self,
        name: str,
        command: str,
        args: tuple[str, ...] = (),
        env: dict[str, str] | None = None,
    ) -> None:
        self._name = name
        self._command = command
        self._args = args
        self._env = env or {}
        self._client: Client | None = None
        self._transport: StdioTransport | None = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self, timeout_s: float = 10.0) -> None:
        """Connect to the backend stdio process.

        Args:
            timeout_s: Maximum time to wait for connection/initialization.

        Raises:
            BackendClientError: On connection failure or timeout.
        """
        if self._connected:
            return

        try:
            self._transport = StdioTransport(
                command=self._command,
                args=list(self._args),
                env=self._env,
            )
            self._client = Client(transport=self._transport)

            async with asyncio.timeout(timeout_s):
                await self._client.__aenter__()

            self._connected = True
            logger.info(
                "backend_client.connected",
                extra={"backend": self._name, "timeout_s": timeout_s},
            )
        except TimeoutError:
            self._connected = False
            await self._cleanup_transport()
            raise BackendClientError(
                f"backend {self._name} connect timed out after {timeout_s}s"
            ) from None
        except Exception as exc:
            self._connected = False
            await self._cleanup_transport()
            raise BackendClientError(f"backend {self._name} connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        """Disconnect from the backend process cleanly."""
        if not self._connected or self._client is None:
            return

        try:
            async with asyncio.timeout(5.0):
                await self._client.__aexit__(None, None, None)
        except (TimeoutError, Exception) as exc:
            logger.warning(
                "backend_client.disconnect_timeout",
                extra={"backend": self._name, "error": str(exc)},
            )
        finally:
            self._connected = False
            self._client = None
            await self._cleanup_transport()

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools from the backend.

        Returns:
            List of tool dicts with name, description, parameters (inputSchema).

        Raises:
            BackendClientError: If not connected or call fails.
        """
        if not self._connected or self._client is None:
            raise BackendClientError(f"backend {self._name} not connected")

        try:
            mcp_tools = await self._client.list_tools()
            result: list[dict[str, Any]] = []
            for t in mcp_tools:
                input_schema = t.inputSchema or {"type": "object", "properties": {}}
                result.append(
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": (
                            input_schema.model_dump()
                            if hasattr(input_schema, "model_dump")
                            else dict(input_schema)
                        ),
                    }
                )
            return result
        except Exception as exc:
            raise BackendClientError(f"backend {self._name} list_tools failed: {exc}") from exc

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a tool on the backend.

        Returns:
            Dict with content and isError fields.

        Raises:
            BackendClientError: If not connected or call fails.
        """
        if not self._connected or self._client is None:
            raise BackendClientError(f"backend {self._name} not connected")

        try:
            result = await self._client.call_tool(
                name=tool_name,
                arguments=arguments or {},
            )

            # Serialize content into plain dicts
            serialized_content: list[dict[str, Any]] = []
            for item in result.content:
                if isinstance(item, TextContent):
                    serialized_content.append(
                        {
                            "type": "text",
                            "text": item.text,
                        }
                    )
                else:
                    serialized_content.append(
                        {
                            "type": getattr(item, "type", "unknown"),
                            "text": str(getattr(item, "text", "")),
                        }
                    )

            is_error: bool = getattr(result, "is_error", False) or getattr(result, "isError", False)
            return {
                "content": serialized_content,
                "isError": is_error,
            }
        except Exception as exc:
            raise BackendClientError(
                f"backend {self._name} call_tool('{tool_name}') failed: {exc}"
            ) from exc

    async def ping(self, timeout_s: float = 2.0) -> bool:
        """Healthcheck: returns True if backend responds to a lightweight probe.

        Uses list_tools with a short timeout as the probe since not all
        backends support a dedicated ping.
        """
        if not self._connected or self._client is None:
            return False

        try:
            async with asyncio.timeout(timeout_s):
                await self._client.list_tools()
            return True
        except (TimeoutError, Exception):
            return False

    async def _cleanup_transport(self) -> None:
        """Force-kill the subprocess transport if still alive."""
        if self._transport is not None:
            try:
                proc = getattr(self._transport, "_process", None)
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
            except (TimeoutError, Exception):
                pass
            finally:
                self._transport = None
