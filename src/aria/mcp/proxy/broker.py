"""Lazy backend broker for on-demand MCP backend session management.

Instead of eagerly connecting to all catalogued backends at proxy boot,
the broker creates single-backend proxies only when a tool call requires one.
Tool discovery uses catalog metadata (``expected_tools``) without touching
any live backend — this eliminates the latency and stdout noise from
booting irrelevant backends during ``search_tools``.

Key design decisions
--------------------
* **Catalog-driven discovery**: ``catalog_tools()`` builds lightweight
  ``Tool`` objects from ``mcp_catalog.yaml`` metadata. No backend sessions
  are created.
* **Lazy invocation**: ``call()`` creates a single-backend proxy on first
  use and caches it for subsequent calls to the same backend.
* **Scoped resolution**: ``resolve_tool()`` maps namespaced tool names to
  ``(server_name, tool_name)`` pairs using the known backend name set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy
from fastmcp.tools import Tool

from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from aria.mcp.proxy.catalog import BackendSpec

logger = get_logger("aria.mcp.proxy.broker")


LEGACY_GOOGLE_WORKSPACE_TOOL_ALIASES: dict[str, str] = {
    "gmail_send": "send_gmail_message",
    "gmail_search": "search_gmail_messages",
    "gmail_get": "get_gmail_message_content",
    "gmail_draft_create": "draft_gmail_message",
    "calendar_list_events": "get_events",
    "calendar_create_event": "create_event",
    "calendar_get_event": "get_event",
    "drive_list": "list_drive_items",
    "drive_read_file": "get_drive_file_content",
    "docs_create": "create_doc",
    "docs_get": "get_doc_content",
    "sheets_create": "create_spreadsheet",
    "sheets_get_values": "read_sheet_values",
    "sheets_update_values": "modify_sheet_values",
    "slides_create": "create_presentation",
}


def _normalize_tool_name(server_name: str, tool_name: str) -> str:
    """Normalize legacy tool aliases to the live backend tool names.

    This preserves compatibility for stale prompt/wiki/runtime examples while the
    canonical catalog and skills are aligned to the upstream contract.
    """
    if server_name == "google_workspace":
        return LEGACY_GOOGLE_WORKSPACE_TOOL_ALIASES.get(tool_name, tool_name)
    return tool_name


def resolve_server_from_tool(
    namespaced_name: str,
    backend_names: set[str],
) -> tuple[str, str] | None:
    """Parse a namespaced tool name into ``(server_name, tool_name)``.

    Handles the single-underscore runtime form: ``financekit-mcp_crypto_price``.
    Tries each ``_`` position longest-prefix-first so that server names
    containing underscores (e.g. ``google_workspace``) are resolved correctly.

    Returns ``None`` when the server portion does not match any known
    backend name.
    """
    cleaned = namespaced_name.strip()
    if not cleaned:
        return None

    # Single-underscore form — try each _ split longest-server-prefix-first
    # so names like "google_workspace_gmail_send" resolve correctly.
    if "_" in cleaned:
        idx = 0
        while (idx := cleaned.find("_", idx)) != -1:
            candidate = cleaned[:idx]
            if candidate in backend_names:
                return candidate, cleaned[idx + 1 :]
            idx += 1

    return None


class LazyBackendBroker:
    """Manages lazy connections to individual MCP backends.

    Parameters
    ----------
    backends:
        Enabled ``BackendSpec`` objects loaded from the catalog.
    """

    def __init__(self, backends: list[BackendSpec]) -> None:
        self._backends: dict[str, BackendSpec] = {b.name: b for b in backends}
        self._proxies: dict[str, FastMCP] = {}

    @property
    def backend_names(self) -> set[str]:
        """Return the set of known backend server names."""
        return set(self._backends.keys())

    def catalog_tools(self) -> list[Tool]:
        """Build lightweight ``Tool`` objects from catalog metadata.

        No live backends are contacted. Tools are derived from the
        ``expected_tools`` entries in ``mcp_catalog.yaml``.
        """
        tools: list[Tool] = []
        for spec in self._backends.values():
            for tool_name in spec.expected_tools:
                namespaced = f"{spec.name}_{tool_name}"
                description = f"[{spec.domain}] {tool_name}"
                if spec.notes:
                    description += f" — {spec.notes}"
                tools.append(
                    Tool(
                        name=namespaced,
                        description=description,
                        parameters={"type": "object", "properties": {}},
                    )
                )
        return tools

    async def call(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> Any:  # noqa: ANN401
        """Call a tool on a backend, creating the session lazily.

        Only the requested backend is contacted; other backends remain
        untouched.
        """
        if server_name not in self._backends:
            raise ValueError(f"Unknown backend: {server_name}")
        proxy = self._get_or_create(server_name)
        async with Client(proxy) as client:
            return await client.call_tool(tool_name, arguments)

    def resolve_tool(self, namespaced_name: str) -> tuple[str, str] | None:
        """Resolve a namespaced tool name to ``(server_name, tool_name)``."""
        resolved = resolve_server_from_tool(namespaced_name, self.backend_names)
        if resolved is None:
            return None
        server_name, tool_name = resolved
        return server_name, _normalize_tool_name(server_name, tool_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, server_name: str) -> FastMCP:
        """Return a cached single-backend proxy or create one on demand."""
        if server_name not in self._proxies:
            spec = self._backends[server_name]
            logger.info(
                "broker.creating_backend",
                extra={"backend": server_name},
            )
            self._proxies[server_name] = create_proxy(
                {"mcpServers": {spec.name: spec.to_mcp_entry()}},
                name=f"aria-lazy-{spec.name}",
            )
        return self._proxies[server_name]
