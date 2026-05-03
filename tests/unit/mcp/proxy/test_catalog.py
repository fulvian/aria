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


def test_to_mcp_entry_http_transport() -> None:
    """HTTP backends produce url+transport format (Bug B1)."""
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


def test_to_mcp_entry_stdio_transport() -> None:
    """Stdio backends still produce command+args format."""
    spec = BackendSpec(
        name="test-backend",
        domain="test",
        owner_agent="test-agent",
        transport="stdio",
        command="npx",
        args=("-y", "test-server"),
    )
    entry = spec.to_mcp_entry()
    assert entry["command"] == "npx"
    assert "-y" in entry["args"]
    assert "url" not in entry


def test_to_mcp_entry_http_without_url_falls_back_to_stdio() -> None:
    """HTTP backend without url set falls back to command+args."""
    spec = BackendSpec(
        name="test-backend",
        domain="test",
        owner_agent="test-agent",
        transport="http",
        command="npx",
        args=("-y", "test-server"),
        url="",  # no URL configured
    )
    entry = spec.to_mcp_entry()
    # Falls back to command+args since url is empty
    assert entry["command"] == "npx"
    assert "url" not in entry


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
# HTTP/SSE YAML parsing tests
# ---------------------------------------------------------------------------


def test_parse_http_backend_with_url_field(tmp_path: Path) -> None:
    """HTTP backend with explicit url field uses it."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
servers:
  - name: helium-mcp
    domain: finance
    owner_agent: trader-agent
    transport: http
    lifecycle: enabled
    auth_mode: api_key
    statefulness: stateless
    expected_tools: [get_ticker, search_news]
    risk_level: low
    cost_class: freemium
    source_of_truth: https://app.heliumtrades.com/mcp
    url: https://app.heliumtrades.com/mcp
    rollback_class: server
    baseline_status: lkg
    notes: Helium test
""".lstrip()
    )
    backends = load_backends(catalog)
    assert len(backends) == 1
    h = backends[0]
    assert h.name == "helium-mcp"
    assert h.transport == "http"
    assert h.url == "https://app.heliumtrades.com/mcp"
    assert h.command == ""  # no command for HTTP backends
    entry = h.to_mcp_entry()
    assert entry["url"] == "https://app.heliumtrades.com/mcp"
    assert entry["transport"] == "http"


def test_parse_http_backend_auto_url_from_source(tmp_path: Path) -> None:
    """HTTP backend without explicit url field auto-detects from source_of_truth."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
servers:
  - name: auto-url-backend
    domain: finance
    owner_agent: trader-agent
    transport: http
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [test_tool]
    risk_level: low
    cost_class: free
    source_of_truth: https://api.example.com/mcp
    rollback_class: server
    baseline_status: lkg
    notes: Auto URL test
""".lstrip()
    )
    backends = load_backends(catalog)
    assert len(backends) == 1
    b = backends[0]
    assert b.url == "https://api.example.com/mcp"
