"""Unit tests for the catalog → mcpServers loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from aria.mcp.proxy.catalog import (
    BackendSpec,
    catalog_hash,
    load_backends,
)


def test_load_backends_filters_disabled(minimal_catalog: Path) -> None:
    backends = load_backends(minimal_catalog)
    names = [b.name for b in backends]
    assert "filesystem" in names
    assert "stub" not in names  # lifecycle=disabled


def test_backend_spec_to_mcpservers_entry(minimal_catalog: Path) -> None:
    backends = load_backends(minimal_catalog)
    fs = next(b for b in backends if b.name == "filesystem")
    entry = fs.to_mcp_entry()
    assert entry["command"] == "npx"
    assert entry["args"][0] == "-y"


def test_catalog_hash_stable(minimal_catalog: Path) -> None:
    h1 = catalog_hash(minimal_catalog)
    h2 = catalog_hash(minimal_catalog)
    assert h1 == h2 and len(h1) == 64  # sha256 hex


def test_catalog_hash_changes_on_edit(tmp_path: Path, minimal_catalog: Path) -> None:
    h1 = catalog_hash(minimal_catalog)
    minimal_catalog.write_text(minimal_catalog.read_text() + "\n# touch\n")
    h2 = catalog_hash(minimal_catalog)
    assert h1 != h2


def test_missing_catalog_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_backends(tmp_path / "nope.yaml")


def test_unknown_source_command_string_split(minimal_catalog: Path) -> None:
    backends = load_backends(minimal_catalog)
    fs = next(b for b in backends if b.name == "filesystem")
    # source_of_truth: "npx -y @modelcontextprotocol/server-filesystem"
    assert fs.command == "npx"
    assert "@modelcontextprotocol/server-filesystem" in fs.args


# ---------------------------------------------------------------------------
# HTTP/SSE + headers support tests
# ---------------------------------------------------------------------------


def test_to_mcp_entry_http_transport() -> None:
    """HTTP backends produce url+transport format."""
    spec = BackendSpec(
        name="helium-mcp",
        domain="finance",
        owner_agent="trader-agent",
        transport="http",
        command="",
        args=(),
        url="https://app.heliumtrades.com/mcp",
    )
    entry = spec.to_mcp_entry()
    assert entry["url"] == "https://app.heliumtrades.com/mcp"
    assert entry["transport"] == "http"
    assert "command" not in entry


def test_to_mcp_entry_sse_transport() -> None:
    """SSE backends produce url+transport format."""
    spec = BackendSpec(
        name="sse-backend",
        domain="finance",
        owner_agent="trader-agent",
        transport="sse",
        command="",
        args=(),
        url="https://example.com/sse",
    )
    entry = spec.to_mcp_entry()
    assert entry["url"] == "https://example.com/sse"
    assert entry["transport"] == "sse"


def test_to_mcp_entry_http_with_headers() -> None:
    """HTTP backend with headers includes them in the entry."""
    spec = BackendSpec(
        name="context7",
        domain="search",
        owner_agent="search-agent",
        transport="http",
        command="",
        args=(),
        url="https://mcp.context7.com/mcp",
        headers={"Authorization": "Bearer some-api-key"},
    )
    entry = spec.to_mcp_entry()
    assert entry["url"] == "https://mcp.context7.com/mcp"
    assert entry["transport"] == "http"
    assert entry["headers"] == {"Authorization": "Bearer some-api-key"}


def test_to_mcp_entry_http_without_headers() -> None:
    """HTTP backend without headers doesn't include headers key."""
    spec = BackendSpec(
        name="helium-mcp",
        domain="finance",
        owner_agent="trader-agent",
        transport="http",
        command="",
        args=(),
        url="https://app.heliumtrades.com/mcp",
    )
    entry = spec.to_mcp_entry()
    assert "headers" not in entry


def test_to_mcp_entry_stdio_ignores_headers() -> None:
    """Stdio backend ignores headers field (not applicable)."""
    spec = BackendSpec(
        name="test-backend",
        domain="test",
        owner_agent="test-agent",
        transport="stdio",
        command="npx",
        args=("-y", "test-server"),
        headers={"Authorization": "Bearer token"},
    )
    entry = spec.to_mcp_entry()
    assert "headers" not in entry
    assert entry["command"] == "npx"


def test_to_mcp_entry_http_without_url_falls_back_to_stdio() -> None:
    """HTTP backend without url set falls back to command+args."""
    spec = BackendSpec(
        name="test-backend",
        domain="test",
        owner_agent="test-agent",
        transport="http",
        command="npx",
        args=("-y", "test-server"),
        url="",
        headers={"Authorization": "Bearer token"},
    )
    entry = spec.to_mcp_entry()
    assert entry["command"] == "npx"
    assert "url" not in entry
    # headers should not appear either since it's a stdio fallback
    assert "headers" not in entry


def test_parse_http_backend_with_url_field(tmp_path: Path) -> None:
    """HTTP backend with explicit url field uses it."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("""\
servers:
  - name: helium-mcp
    domain: finance
    owner_agent: trader-agent
    transport: http
    lifecycle: enabled
    expected_tools: [get_ticker, search_news]
    source_of_truth: https://app.heliumtrades.com/mcp
    url: https://app.heliumtrades.com/mcp
    notes: Helium test
""")
    backends = load_backends(catalog)
    assert len(backends) == 1
    h = backends[0]
    assert h.name == "helium-mcp"
    assert h.transport == "http"
    assert h.url == "https://app.heliumtrades.com/mcp"
    assert h.command == ""
    entry = h.to_mcp_entry()
    assert entry["url"] == "https://app.heliumtrades.com/mcp"
    assert entry["transport"] == "http"


def test_parse_http_backend_auto_url_from_source(tmp_path: Path) -> None:
    """HTTP backend without explicit url field auto-detects from source_of_truth."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("""\
servers:
  - name: auto-url-backend
    domain: search
    owner_agent: search-agent
    transport: http
    lifecycle: enabled
    expected_tools: [resolve-library-id, query-docs]
    source_of_truth: https://mcp.context7.com/mcp
    notes: Auto URL test
""")
    backends = load_backends(catalog)
    assert len(backends) == 1
    b = backends[0]
    assert b.url == "https://mcp.context7.com/mcp"


def test_parse_http_backend_with_headers(tmp_path: Path) -> None:
    """HTTP backend with headers parses them correctly."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("""\
servers:
  - name: context7
    domain: search
    owner_agent: search-agent
    transport: http
    lifecycle: enabled
    expected_tools: [resolve-library-id, query-docs]
    source_of_truth: https://mcp.context7.com/mcp
    url: https://mcp.context7.com/mcp
    headers:
      Authorization: Bearer ${CONTEXT7_API_KEY}
    notes: Context7 MCP
""")
    backends = load_backends(catalog)
    assert len(backends) == 1
    b = backends[0]
    assert b.name == "context7"
    assert b.headers == {"Authorization": "Bearer ${CONTEXT7_API_KEY}"}


def test_parse_http_backend_env_and_headers(tmp_path: Path) -> None:
    """HTTP backend with both env and headers parses both."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("""\
servers:
  - name: context7
    domain: search
    owner_agent: search-agent
    transport: http
    lifecycle: enabled
    expected_tools: [resolve-library-id, query-docs]
    source_of_truth: https://mcp.context7.com/mcp
    url: https://mcp.context7.com/mcp
    headers:
      Authorization: Bearer ${CONTEXT7_API_KEY}
    env:
      CONTEXT7_API_KEY: ${CONTEXT7_API_KEY}
    notes: Context7 MCP
""")
    backends = load_backends(catalog)
    assert len(backends) == 1
    b = backends[0]
    assert b.headers == {"Authorization": "Bearer ${CONTEXT7_API_KEY}"}
    assert b.env == {"CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"}


def test_parse_stdio_backend_ignores_headers(tmp_path: Path) -> None:
    """Stdio backend ignores any headers in YAML."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("""\
servers:
  - name: test-backend
    domain: test
    owner_agent: test-agent
    transport: stdio
    lifecycle: enabled
    expected_tools: [test_tool]
    source_of_truth: npx -y test-server
    headers:
      Authorization: Bearer token
    notes: Headers ignored for stdio
""")
    backends = load_backends(catalog)
    assert len(backends) == 1
    b = backends[0]
    assert b.headers == {"Authorization": "Bearer token"}
    # Headers are stored but ignored in to_mcp_entry for stdio
    entry = b.to_mcp_entry()
    assert "headers" not in entry
