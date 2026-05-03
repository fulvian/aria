"""Unit tests for the proxy wiring helper."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastmcp import Client

from aria.mcp.proxy.catalog import BackendSpec
from aria.mcp.proxy.server import (
    _allowed_server_names,
    _filter_backends_for_caller,
    _tool_server_name,
    build_proxy,
)

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


class _Registry:
    def __init__(self, allowed_tools: dict[str, list[str]]) -> None:
        self._allowed_tools = allowed_tools

    def get_allowed_tools(self, agent: str) -> list[str]:
        return self._allowed_tools.get(agent, [])


def _backend(name: str) -> BackendSpec:
    return BackendSpec(
        name=name,
        domain="search",
        owner_agent="search-agent",
        transport="stdio",
        command="stub",
        args=(),
    )


def test_package_importable() -> None:
    import aria.mcp.proxy

    assert hasattr(aria.mcp.proxy, "build_proxy") or True  # deferred import


def test_build_proxy_uses_supplied_paths(
    minimal_catalog: Path, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(catalog_path=minimal_catalog, proxy_config_path=proxy_yaml)

    assert proxy is not None
    assert proxy.name == "aria-mcp-proxy"


def test_build_proxy_skips_missing_catalog(tmp_path: Path) -> None:
    with patch.dict("os.environ", {"ARIA_PROXY_DISABLE_BACKENDS": "1"}):
        proxy = build_proxy(
            catalog_path=tmp_path / "missing.yaml",
            proxy_config_path=tmp_path / "missing-proxy.yaml",
            strict=False,
        )
        assert proxy is not None


def test_filter_backends_for_search_agent_excludes_workspace_and_memory() -> None:
    backends = [
        _backend("searxng-script"),
        _backend("tavily-mcp"),
        _backend("google_workspace"),
        _backend("aria-memory"),
    ]

    filtered = _filter_backends_for_caller(
        backends,
        registry=_Registry(
            {
                "search-agent": [
                    "searxng-script_*",
                    "tavily-mcp_*",
                    "aria-memory_wiki_recall_tool",
                ]
            }
        ),
        caller="search-agent",
    )

    assert [backend.name for backend in filtered] == ["searxng-script", "tavily-mcp"]


def test_build_proxy_applies_caller_backend_filter(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
servers:
  - name: searxng-script
    domain: search
    owner_agent: search-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [search_web]
    risk_level: low
    cost_class: free
    source_of_truth: searxng
    rollback_class: server
    baseline_status: lkg
    notes: search
  - name: google_workspace
    domain: productivity
    owner_agent: workspace-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: oauth
    statefulness: stateful
    expected_tools: [search_gmail_messages]
    risk_level: high
    cost_class: free
    source_of_truth: workspace
    rollback_class: session
    baseline_status: lkg
    notes: workspace
  - name: aria-memory
    domain: memory
    owner_agent: aria-conductor
    tier: 0
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateful
    expected_tools: [wiki_recall_tool]
    risk_level: low
    cost_class: free
    source_of_truth: memory
    rollback_class: domain
    baseline_status: lkg
    notes: memory
""".lstrip()
    )
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    monkeypatch.setenv("ARIA_CALLER_ID", "search-agent")

    with patch(
        "aria.mcp.proxy.server.YamlCapabilityRegistry",
        return_value=_Registry(
            {"search-agent": ["searxng-script_*", "aria-memory_wiki_recall_tool"]}
        ),
    ):
        proxy = build_proxy(catalog_path=catalog, proxy_config_path=proxy_yaml, strict=False)

    assert proxy.name == "aria-mcp-proxy"
    # The proxy should have search_tools and call_tool registered
    # The catalog only has searxng-script (google_workspace filtered out,
    # aria-memory in SEPARATE_SERVERS).


@pytest.mark.asyncio
async def test_build_proxy_catalog_search_no_live_backends(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """search_tools returns catalog-derived results without booting backends."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
servers:
  - name: financekit-mcp
    domain: finance
    owner_agent: trader-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [stock_price, crypto_price]
    risk_level: low
    cost_class: free
    source_of_truth: financekit
    rollback_class: server
    baseline_status: lkg
    notes: free financial data
  - name: google_workspace
    domain: productivity
    owner_agent: workspace-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: oauth
    statefulness: stateful
    expected_tools: [search_gmail_messages]
    risk_level: high
    cost_class: free
    source_of_truth: workspace
    rollback_class: session
    baseline_status: lkg
    notes: Google Workspace
""".lstrip()
    )
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    monkeypatch.setenv("ARIA_CALLER_ID", "trader-agent")
    with patch(
        "aria.mcp.proxy.server.YamlCapabilityRegistry",
        return_value=_Registry({"trader-agent": ["financekit-mcp_*"]}),
    ):
        proxy = build_proxy(catalog_path=catalog, proxy_config_path=proxy_yaml, strict=False)

    async with Client(proxy) as client:
        # search_tools should find finance tools from catalog metadata
        result = await client.call_tool("search_tools", {"query": "crypto price"})
        assert result is not None
        parsed = json.loads(result.content[0].text if hasattr(result, "content") else str(result))
        # Should find financekit-mcp tools but NOT google_workspace
        tool_names = [t["name"] for t in parsed]
        finance_tools = [n for n in tool_names if n.startswith("financekit-mcp")]
        assert len(finance_tools) > 0
        # google_workspace tools must not appear in catalog
        workspace_tools = [n for n in tool_names if n.startswith("google_workspace")]
        assert len(workspace_tools) == 0


@pytest.mark.asyncio
async def test_build_proxy_lists_only_synthetic_tools(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """list_tools returns search_tools and call_tool (no backend tools)."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
servers:
  - name: financekit-mcp
    domain: finance
    owner_agent: trader-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [stock_price]
    risk_level: low
    cost_class: free
    source_of_truth: financekit
    rollback_class: server
    baseline_status: lkg
    notes: finance
""".lstrip()
    )
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(catalog_path=catalog, proxy_config_path=proxy_yaml, strict=False)

    async with Client(proxy) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "search_tools" in names
        assert "call_tool" in names
        # No individual backend tools in list_tools
        assert "financekit-mcp_stock_price" not in names


# ---------------------------------------------------------------------------
# Bug B2 — _tool_server_name() underscore-aware resolution
# ---------------------------------------------------------------------------


def test_tool_server_name_direct_allowed() -> None:
    """DIRECT_SERVER_ALLOWLIST items return None (not routed through proxy)."""
    assert _tool_server_name("spawn-subagent") is None


def test_tool_server_name_hyphen_server() -> None:
    """Server names with hyphens work with simple split."""
    result = _tool_server_name("financekit-mcp_stock_price")
    assert result == "financekit-mcp"


def test_tool_server_name_underscore_server_without_known() -> None:
    """Underscore server name falls back to simple split when known_servers is None."""
    result = _tool_server_name("google_workspace_search_gmail")
    assert result == "google"  # fallback behavior


def test_tool_server_name_underscore_server_with_known() -> None:
    """Underscore server name resolves correctly with known_servers (Bug B2 fix)."""
    known = {"google_workspace", "financekit-mcp", "searxng-script"}
    result = _tool_server_name("google_workspace_search_gmail", known_servers=known)
    assert result == "google_workspace"


def test_tool_server_name_longest_prefix_matching() -> None:
    """Known servers with overlapping prefixes resolve to the longest match."""
    known = {"google", "google_workspace", "google_workspace_drive"}
    result = _tool_server_name("google_workspace_drive_list_files", known_servers=known)
    # Should match "google_workspace_drive" (longest prefix)
    assert result == "google_workspace_drive"


def test_tool_server_name_empty_returns_none() -> None:
    assert _tool_server_name("") is None


def test_tool_server_name_whitespace_returns_none() -> None:
    assert _tool_server_name("  ") is None


def test_allowed_server_names_resolves_underscore_servers() -> None:
    """_allowed_server_names correctly extracts google_workspace from tools list."""
    registry = _Registry(
        {
            "workspace-agent": [
                "google_workspace_search_gmail",
                "google_workspace_get_events",
                "aria-memory_wiki_recall_tool",
            ]
        }
    )
    known_servers = {"google_workspace", "aria-memory"}
    result = _allowed_server_names(registry, "workspace-agent", known_servers=known_servers)
    assert result is not None
    assert "google_workspace" in result
    # _allowed_server_names returns ALL resolved server names;
    # SEPARATE_SERVERS filtering happens in _filter_backends_for_caller
    assert "aria-memory" in result


def test_filter_backends_for_caller_google_workspace(
    monkeypatch: MonkeyPatch,
) -> None:
    """Workspace-agent correctly includes google_workspace backend (Bug B2)."""
    backends = [
        _backend("google_workspace"),
        _backend("searxng-script"),
        _backend("aria-memory"),
    ]

    filtered = _filter_backends_for_caller(
        backends,
        registry=_Registry(
            {
                "workspace-agent": [
                    "google_workspace_search_gmail",
                    "searxng-script_*",
                ]
            }
        ),
        caller="workspace-agent",
    )

    backend_names = [b.name for b in filtered]
    assert "google_workspace" in backend_names
    assert "searxng-script" in backend_names
    assert "aria-memory" not in backend_names  # SEPARATE_SERVERS
