"""ARIA MCP tool-search proxy — FastMCP-native multi-server aggregator.

Replaces the static lazy loader with a runtime BM25/hybrid search surface
exposed as two synthetic tools (search_tools, call_tool) backed by every
catalogued MCP server.

See docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md.
"""

from aria.mcp.proxy.server import build_proxy

__all__ = ["build_proxy"]
