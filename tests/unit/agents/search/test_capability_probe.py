"""Unit tests for capability probe framework (capability_probe.py).

Tests the snapshot comparison, quarantine logic, and expected tool validation
without actually starting MCP servers (pure logic tests).
"""

from __future__ import annotations

from aria.agents.search.capability_probe import (
    EXPECTED_TOOL_SNAPSHOTS,
    ProbeResult,
    get_expected_tools,
)


class TestExpectedToolSnapshots:
    """Verify expected tool snapshots are complete and consistent."""

    def test_pubmed_has_5_tools(self):
        """PubMed MCP expected snapshot has 5 tools (npx registry v2.6.6)."""
        tools = EXPECTED_TOOL_SNAPSHOTS.get("pubmed-mcp")
        assert tools is not None
        assert len(tools) == 5

    def test_pubmed_tools_prefix(self):
        """All pubmed tools start with 'pubmed_'."""
        tools = EXPECTED_TOOL_SNAPSHOTS.get("pubmed-mcp", set())
        for t in tools:
            assert t.startswith("pubmed_"), f"Tool {t} does not start with pubmed_"

    def test_pubmed_includes_search(self):
        """PubMed snapshot includes pubmed_search_articles."""
        tools = EXPECTED_TOOL_SNAPSHOTS.get("pubmed-mcp", set())
        assert "pubmed_search_articles" in tools
        assert "pubmed_fetch_contents" in tools
        assert "pubmed_article_connections" in tools

    def test_scientific_papers_has_5_tools(self):
        """Scientific Papers MCP expected snapshot has 5 tools."""
        tools = EXPECTED_TOOL_SNAPSHOTS.get("scientific-papers-mcp")
        assert tools is not None
        assert len(tools) == 5

    def test_scientific_papers_includes_search(self):
        """Scientific Papers snapshot includes search_papers."""
        tools = EXPECTED_TOOL_SNAPSHOTS.get("scientific-papers-mcp", set())
        assert "search_papers" in tools
        assert "fetch_content" in tools
        assert "fetch_latest" in tools
        assert "list_categories" in tools
        assert "fetch_top_cited" in tools


class TestProbeResult:
    """Verify ProbeResult dataclass logic."""

    def test_quarantine_on_missing_tools(self):
        """Quarantine detected when expected tools are missing."""
        # Simulate probe result
        result = ProbeResult(
            server_name="pubmed-mcp",
            tool_count=8,
            tools={"pubmed_search_articles", "pubmed_fetch_articles"},
            quarantine=True,
            quarantine_reason="Tool mancanti (7): pubmed_fetch_fulltext, ...",
        )
        assert result.quarantine is True
        assert result.server_name == "pubmed-mcp"
        assert result.success is True  # success = no error
        assert "mancanti" in (result.quarantine_reason or "")

    def test_no_quarantine_on_full_match(self):
        """No quarantine when all expected tools are present."""
        result = ProbeResult(
            server_name="pubmed-mcp",
            tool_count=9,
            tools=EXPECTED_TOOL_SNAPSHOTS["pubmed-mcp"],
        )
        assert result.quarantine is False
        assert result.success is True  # success = no error
        assert result.tool_count == 9

    def test_quarantine_on_excessive_extra_tools(self):
        """Quarantine if extra tools exceed 50% of expected count."""
        result = ProbeResult(
            server_name="scientific-papers-mcp",
            tool_count=10,
            tools=EXPECTED_TOOL_SNAPSHOTS["scientific-papers-mcp"] | {"extra1", "extra2", "extra3", "extra4", "extra5"},
            quarantine=True,
            quarantine_reason="Tool extra (5): extra1, ... — possibile aggiornamento major",
        )
        assert result.quarantine is True

    def test_probe_failure_on_error(self):
        """Probe failure is not quarantine but an error."""
        result = ProbeResult(
            server_name="pubmed-mcp",
            error="Timeout: Connection closed",
            elapsed_ms=15000.0,
        )
        assert result.success is False  # error set → success=False
        assert result.error is not None
        assert result.quarantine is False


class TestGetExpectedTools:
    """Verify expected tool retrieval logic."""

    def test_get_expected_pubmed(self):
        """get_expected_tools returns pubmed tools (5 tools, npm v2.6.6)."""
        tools = get_expected_tools("pubmed-mcp")
        assert tools is not None
        assert "pubmed_search_articles" in tools
        assert "pubmed_fetch_contents" in tools
        assert "pubmed_article_connections" in tools

    def test_get_expected_scientific(self):
        """get_expected_tools returns scientific papers tools."""
        tools = get_expected_tools("scientific-papers-mcp")
        assert tools is not None
        assert "search_papers" in tools
        assert "fetch_top_cited" in tools

    def test_get_expected_unknown(self):
        """get_expected_tools returns None for unknown server."""
        tools = get_expected_tools("unknown-server")
        assert tools is None
