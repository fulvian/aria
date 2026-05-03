"""Unit tests for LazyBackendBroker and resolve_server_from_tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aria.mcp.proxy.broker import LazyBackendBroker, resolve_server_from_tool
from aria.mcp.proxy.catalog import BackendSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spec(
    name: str = "financekit-mcp",
    *,
    domain: str = "finance",
    owner_agent: str = "trader-agent",
    expected_tools: tuple[str, ...] = ("stock_price", "crypto_price"),
    notes: str = "Finance tools",
) -> BackendSpec:
    return BackendSpec(
        name=name,
        domain=domain,
        owner_agent=owner_agent,
        transport="stdio",
        command="stub",
        args=(),
        expected_tools=expected_tools,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# resolve_server_from_tool
# ---------------------------------------------------------------------------


class TestResolveServerFromTool:
    NAMES = {"financekit-mcp", "mcp-fredapi", "alpaca-mcp", "google_workspace"}

    def test_single_underscore_runtime_name(self) -> None:
        result = resolve_server_from_tool("financekit-mcp_crypto_price", self.NAMES)
        assert result == ("financekit-mcp", "crypto_price")

    def test_double_underscore_matrix_name(self) -> None:
        result = resolve_server_from_tool("financekit-mcp__crypto_price", self.NAMES)
        assert result == ("financekit-mcp", "crypto_price")

    def test_slash_legacy_name(self) -> None:
        result = resolve_server_from_tool("financekit-mcp/crypto_price", self.NAMES)
        assert result == ("financekit-mcp", "crypto_price")

    def test_server_with_underscore_name(self) -> None:
        """Server 'google_workspace' contains underscore."""
        result = resolve_server_from_tool("google_workspace_send_gmail_message", self.NAMES)
        assert result == ("google_workspace", "send_gmail_message")

    def test_hyphenated_server_name(self) -> None:
        result = resolve_server_from_tool("mcp-fredapi_get_series", self.NAMES)
        assert result == ("mcp-fredapi", "get_series")

    def test_unknown_server_returns_none(self) -> None:
        result = resolve_server_from_tool("unknown-server_tool", self.NAMES)
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        result = resolve_server_from_tool("", self.NAMES)
        assert result is None

    def test_no_separator_returns_none(self) -> None:
        result = resolve_server_from_tool("financekit-mcp", self.NAMES)
        assert result is None


# ---------------------------------------------------------------------------
# LazyBackendBroker
# ---------------------------------------------------------------------------


class TestLazyBackendBroker:
    def test_backend_names(self) -> None:
        broker = LazyBackendBroker([_spec("financekit-mcp"), _spec("alpaca-mcp")])
        assert broker.backend_names == {"financekit-mcp", "alpaca-mcp"}

    def test_catalog_tools_returns_namespaced_tools(self) -> None:
        broker = LazyBackendBroker(
            [_spec("financekit-mcp", expected_tools=("stock_price", "crypto_price"))]
        )
        tools = broker.catalog_tools()
        assert len(tools) == 2
        assert tools[0].name == "financekit-mcp_stock_price"
        assert tools[1].name == "financekit-mcp_crypto_price"

    def test_catalog_tools_includes_domain_and_notes(self) -> None:
        broker = LazyBackendBroker(
            [
                _spec(
                    "financekit-mcp",
                    domain="finance",
                    expected_tools=("stock_price",),
                    notes="free financial data",
                )
            ]
        )
        tools = broker.catalog_tools()
        assert len(tools) == 1
        assert "[finance]" in tools[0].description
        assert "free financial data" in tools[0].description

    def test_catalog_tools_empty_when_no_backends(self) -> None:
        broker = LazyBackendBroker([])
        assert broker.catalog_tools() == []

    def test_catalog_tools_no_live_backends_contacted(self) -> None:
        """catalog_tools must never touch a live backend session."""
        broker = LazyBackendBroker([_spec("financekit-mcp")])
        tools = broker.catalog_tools()
        assert len(tools) == 2
        # No proxy sessions should exist
        assert len(broker._proxies) == 0

    def test_resolve_tool_delegates_to_helper(self) -> None:
        broker = LazyBackendBroker([_spec("financekit-mcp")])
        assert broker.resolve_tool("financekit-mcp_stock_price") == (
            "financekit-mcp",
            "stock_price",
        )
        assert broker.resolve_tool("unknown_tool") is None

    def test_resolve_tool_normalizes_legacy_google_workspace_aliases(self) -> None:
        broker = LazyBackendBroker(
            [
                _spec(
                    "google_workspace",
                    domain="productivity",
                    owner_agent="productivity-agent",
                    expected_tools=("search_gmail_messages", "list_drive_items"),
                )
            ]
        )
        assert broker.resolve_tool("google_workspace__gmail_search") == (
            "google_workspace",
            "search_gmail_messages",
        )
        assert broker.resolve_tool("google_workspace_drive_list") == (
            "google_workspace",
            "list_drive_items",
        )

    @pytest.mark.asyncio
    async def test_call_raises_on_unknown_backend(self) -> None:
        broker = LazyBackendBroker([_spec("financekit-mcp")])
        with pytest.raises(ValueError, match="Unknown backend"):
            await broker.call("nonexistent", "tool", {})

    @pytest.mark.asyncio
    async def test_call_creates_single_backend_proxy_lazily(self) -> None:
        """Only the requested backend should be contacted."""
        spec = _spec("financekit-mcp")
        broker = LazyBackendBroker([spec, _spec("alpaca-mcp")])

        fake_proxy = AsyncMock()
        fake_client = AsyncMock()
        fake_client.call_tool = AsyncMock(return_value={"price": 42000.0})
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aria.mcp.proxy.broker.create_proxy", return_value=fake_proxy) as mock_create,
            patch("aria.mcp.proxy.broker.Client", return_value=fake_client),
        ):
            result = await broker.call("financekit-mcp", "crypto_price", {"coin": "bitcoin"})

        # Only financekit-mcp proxy created, not alpaca-mcp
        mock_create.assert_called_once()
        assert broker._proxies == {"financekit-mcp": fake_proxy}
        assert result == {"price": 42000.0}

    @pytest.mark.asyncio
    async def test_call_reuses_cached_proxy(self) -> None:
        """Second call to the same backend should reuse the cached proxy."""
        spec = _spec("financekit-mcp")
        broker = LazyBackendBroker([spec])

        fake_proxy = AsyncMock()
        fake_client = AsyncMock()
        fake_client.call_tool = AsyncMock(return_value="result")
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aria.mcp.proxy.broker.create_proxy", return_value=fake_proxy),
            patch("aria.mcp.proxy.broker.Client", return_value=fake_client),
        ):
            await broker.call("financekit-mcp", "stock_price", {})
            await broker.call("financekit-mcp", "crypto_price", {})

        # create_proxy called only once despite two tool calls
        assert len(broker._proxies) == 1

    def test_catalog_only_shows_relevant_domains(self) -> None:
        """Catalog tools from finance backends don't include workspace tools."""
        finance = _spec("financekit-mcp", domain="finance")
        workspace = _spec(
            "google_workspace",
            domain="productivity",
            expected_tools=("send_gmail_message",),
        )
        broker = LazyBackendBroker([finance, workspace])
        tools = broker.catalog_tools()

        finance_tools = [t for t in tools if t.name.startswith("financekit-mcp")]
        workspace_tools = [t for t in tools if t.name.startswith("google_workspace")]

        assert len(finance_tools) == 2
        assert len(workspace_tools) == 1
        assert "[finance]" in finance_tools[0].description
        assert "[productivity]" in workspace_tools[0].description
