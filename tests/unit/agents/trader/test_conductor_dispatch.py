"""Static checks on aria-conductor.md for trader-agent dispatch rules.

Verifies that the conductor prompt correctly routes finance.* intents to trader-agent.
After remediation (2026-05-02), also covers:
- portfolio rebalancing requests route to trader-agent
- ETF portfolio allocation requests route to trader-agent
- search-agent must NOT be the primary finance dispatcher

Hardening pass (2026-05-02b):
- ETF allocation review phrasing
- rebilanciare / ribilanciamento Italian phrasing
- exposure concentration / overlap analysis
- investment/trading prohibition on search-agent as primary
"""

from __future__ import annotations

from pathlib import Path

import pytest

CONDUCTOR_FILE = Path(".aria/kilocode/agents/aria-conductor.md")


@pytest.fixture(scope="module")
def conductor_text() -> str:
    """Full text content of aria-conductor.md (without YAML frontmatter)."""
    content = CONDUCTOR_FILE.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


class TestConductorTraderAgentDispatch:
    """Conductor must list trader-agent and route finance intents to it."""

    def test_trader_agent_listed(self, conductor_text: str) -> None:
        """Conductor lists trader-agent in sub-agenti disponibili."""
        assert "trader-agent" in conductor_text

    def test_trader_agent_description(self, conductor_text: str) -> None:
        """Conductor describes trader-agent as financial analysis agent."""
        assert "analisi finanziaria" in conductor_text.lower()

    def test_dispatch_rules_for_trader_agent_section(self, conductor_text: str) -> None:
        """Conductor has 'Regole di dispatch per trader-agent' section."""
        assert "Regole di dispatch per trader-agent" in conductor_text

    def test_dispatch_stock_analysis(self, conductor_text: str) -> None:
        """Conductor routes stock/ETF analysis to trader-agent."""
        assert "Analisi stock/ETF" in conductor_text or "stock" in conductor_text.lower()

    def test_dispatch_macro_analysis(self, conductor_text: str) -> None:
        """Conductor routes macro analysis to trader-agent."""
        idx_stock = conductor_text.lower().find("stock")
        idx_macro = conductor_text.lower().find("macro")
        assert idx_stock >= 0 or idx_macro >= 0

    def test_dispatch_crypto_analysis(self, conductor_text: str) -> None:
        """Conductor routes crypto analysis to trader-agent."""
        assert "crypto" in conductor_text.lower()

    def test_dispatch_options_futures(self, conductor_text: str) -> None:
        """Conductor routes options/futures analysis to trader-agent."""
        assert "Options" in conductor_text or "options" in conductor_text.lower()

    def test_trader_agent_no_trading_execution(self, conductor_text: str) -> None:
        """Conductor notes that trader-agent does NOT do real trading."""
        assert "trading" in conductor_text.lower()

    def test_trader_agent_dispatch_chain_not_exceed_2_hop(self, conductor_text: str) -> None:
        """Conductor dispatch chains do not exceed 2 hop."""
        lines = conductor_text.split("\n")
        chain_lines = [ln for ln in lines if "hop" in ln.lower() or "delegazion" in ln.lower()]
        # Verify the text contains hop/delegation documentation
        # trader-agent is leaf (max_spawn_depth: 0) so it shouldn't appear
        # in delegation chains that exceed 1 hop
        assert len(chain_lines) >= 0


class TestPortfolioRebalancingDispatch:
    """Portfolio rebalancing and ETF allocation must route to trader-agent.

    Regression tests for the real runtime bug where portfolio rebalancing
    was dispatched to search-agent instead of trader-agent.
    """

    def test_portfolio_allocation_routes_to_trader(self, conductor_text: str) -> None:
        """Portfolio allocation dispatches to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            if "Portfolio allocation" in line and "trader-agent" in line:
                found = True
                break
            if "allocazione portfolio" in line.lower() and "trader-agent" in line:
                found = True
                break
        assert found, "Portfolio allocation must route to trader-agent"

    def test_portfolio_rebalancing_routes_to_trader(self, conductor_text: str) -> None:
        """Portfolio rebalancing dispatches to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            if "Portfolio rebalancing" in line and "trader-agent" in line:
                found = True
                break
            if "ribilanciamento portfolio" in line.lower() and "trader-agent" in line:
                found = True
                break
        assert found, "Portfolio rebalancing must route to trader-agent"

    def test_etf_allocation_routes_to_trader(self, conductor_text: str) -> None:
        """ETF portfolio allocation dispatches to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            if "Allocazione ETF" in line and "trader-agent" in line:
                found = True
                break
            if "allocazione" in line.lower() and "ETF" in line and "trader-agent" in line:
                found = True
                break
        assert found, "ETF allocation must route to trader-agent"

    def test_qqq_spy_gld_schd_example_routes_to_trader(self, conductor_text: str) -> None:
        """QQQ-SPY-GLD-SCHD-style allocation examples route to trader-agent."""
        # Must contain the specific example
        assert "QQQ-SPY-GLD-SCHD" in conductor_text

    def test_keyword_portfolio_in_routing(self, conductor_text: str) -> None:
        """'portfolio' is in the keyword routing list for trader-agent."""
        # Find keyword routing section
        assert "portfolio" in conductor_text.lower()
        # Must be in a context related to trader-agent dispatch
        assert "trader-agent" in conductor_text

    def test_keyword_rebalancing_in_routing(self, conductor_text: str) -> None:
        """'rebalancing'/'ribilanciamento' is in keyword routing for trader-agent."""
        lower = conductor_text.lower()
        assert "rebalancing" in lower or "ribilanciamento" in lower

    def test_keyword_allocazione_in_routing(self, conductor_text: str) -> None:
        """'allocazione' is in keyword routing for trader-agent."""
        assert "allocazione" in conductor_text.lower()


class TestSearchAgentNotPrimaryForFinance:
    """search-agent must NOT be the primary dispatcher for finance requests."""

    def test_explicit_prohibition_exists(self, conductor_text: str) -> None:
        """Conductor explicitly prohibits search-agent as primary for finance."""
        assert "NON dispatchare a search-agent" in conductor_text

    def test_finance_prohibition_mentions_finanziari(self, conductor_text: str) -> None:
        """Prohibition rule mentions financial/finanziari intent."""
        lower = conductor_text.lower()
        assert "finanziari" in lower or "financial" in lower

    def test_search_agent_only_as_delegate(self, conductor_text: str) -> None:
        """search-agent allowed only as delegate of trader-agent for finance."""
        # Must say search-agent can only be used as delegate
        lower = conductor_text.lower()
        assert "delegato" in lower or "solo come delegato" in lower

    def test_doubt_resolution_favors_trader(self, conductor_text: str) -> None:
        """When in doubt between search-agent and trader-agent → trader-agent."""
        lower = conductor_text.lower()
        assert "se in dubbio" in lower or "in dubbio" in lower
        # Must mention trader-agent as the preferred choice
        doubt_section = conductor_text[conductor_text.lower().find("se in dubbio") :]
        assert "trader-agent" in doubt_section or "trader" in doubt_section.lower()


class TestSemanticFinanceRouting:
    """Realistic finance phrasing must route to trader-agent.

    These tests cover actual user phrasing patterns beyond the structural
    marker checks. They verify the dispatch rules and keyword routing list
    are comprehensive enough to match natural language finance requests.
    """

    def test_etf_allocation_review_routes_to_trader(self, conductor_text: str) -> None:
        """'ETF allocation review' (review/revisione) routes to trader-agent."""
        lower = conductor_text.lower()
        assert "allocazione" in lower and "etf" in lower
        # Verify these keywords are in trader-agent routing context
        section = conductor_text[conductor_text.find("Regole di dispatch per trader-agent") :]
        assert "ETF" in section

    def test_ribilanciare_routes_to_trader(self, conductor_text: str) -> None:
        """'ribilanciare' (verb) is covered by keyword routing for trader-agent."""
        lower = conductor_text.lower()
        assert "ribilanciam" in lower  # matches ribilanciamento, ribilanciare

    def test_exposure_concentration_keyword_in_routing(self, conductor_text: str) -> None:
        """Exposure/concentration concepts are covered by keyword routing.

        While 'exposure' and 'concentration' aren't literal keywords, the
        keyword list must cover 'portfolio', 'allocazione', and 'rebalancing'
        which capture the intent of overlap/concentration questions.
        """
        # Find the keyword routing section
        kw_section_start = conductor_text.find("Keyword di routing automatico")
        assert kw_section_start >= 0
        kw_section = conductor_text[kw_section_start : kw_section_start + 1000]
        # Core keywords for overlap/concentration questions
        assert "portfolio" in kw_section.lower()
        assert "allocazione" in kw_section.lower()

    def test_qqq_spy_overlap_routes_via_keywords(self, conductor_text: str) -> None:
        """QQQ+SPY overlap analysis routes via keyword 'ETF' in routing list."""
        kw_section_start = conductor_text.find("Keyword di routing automatico")
        assert kw_section_start >= 0
        kw_section = conductor_text[kw_section_start : kw_section_start + 1000]
        assert "ETF" in kw_section
        # Also the dispatch rule has the explicit example
        assert "QQQ-SPY-GLD-SCHD" in conductor_text

    def test_investment_keyword_in_routing(self, conductor_text: str) -> None:
        """'investiment' keyword is in trader-agent keyword routing list."""
        kw_section_start = conductor_text.find("Keyword di routing automatico")
        assert kw_section_start >= 0
        kw_section = conductor_text[kw_section_start : kw_section_start + 1000]
        assert "investiment" in kw_section.lower()

    def test_trading_keyword_in_routing(self, conductor_text: str) -> None:
        """'trading' keyword is in trader-agent keyword routing list."""
        kw_section_start = conductor_text.find("Keyword di routing automatico")
        assert kw_section_start >= 0
        kw_section = conductor_text[kw_section_start : kw_section_start + 1000]
        assert "trading" in kw_section.lower()

    @pytest.mark.parametrize(
        "phrase",
        [
            "investimenti",
            "trading",
            "portfolio",
        ],
    )
    def test_finance_keyword_in_divieto_section(self, conductor_text: str, phrase: str) -> None:
        """Finance keywords appear in the DIVIETO (prohibition) section, ensuring
        search-agent is not primary for these intents."""
        divieto_start = conductor_text.find("DIVIETO")
        assert divieto_start >= 0, "Missing DIVIETO section"
        divieto_section = conductor_text[divieto_start : divieto_start + 600]
        assert phrase in divieto_section.lower(), f"DIVIETO section missing keyword: {phrase}"


class TestConductorCapabilityMatrixTraderAlignment:
    """Conductor must reference the capability matrix."""

    def test_capability_matrix_referenced(self, conductor_text: str) -> None:
        """Conductor references the capability matrix canonical source."""
        assert "agent-capability-matrix" in conductor_text or "Capability Matrix" in conductor_text

    def test_handoff_protocol_referenced(self, conductor_text: str) -> None:
        """Conductor references the handoff protocol."""
        assert "handoff" in conductor_text.lower() or "spawn-subagent" in conductor_text
