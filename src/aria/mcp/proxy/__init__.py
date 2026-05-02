"""ARIA MCP tool-search proxy — catalog-driven discovery with lazy backend invocation.

Exposes two synthetic tools (``search_tools``, ``call_tool``) to agents.
Tool discovery uses ``mcp_catalog.yaml`` metadata without contacting live
backends.  Actual backend sessions are created on demand by the
:class:`~aria.mcp.proxy.broker.LazyBackendBroker`.

See docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md.
"""
