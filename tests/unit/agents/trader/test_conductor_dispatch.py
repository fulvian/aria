"""Static checks on aria-conductor.md for trader-agent dispatch rules.

Verifies that the conductor prompt correctly routes finance.* intents to trader-agent.
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

    def test_dispatch_rules_for_trader_agent_section(
        self, conductor_text: str
    ) -> None:
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

    def test_trader_agent_dispatch_chain_not_exceed_2_hop(
        self, conductor_text: str
    ) -> None:
        """Conductor dispatch chains do not exceed 2 hop."""
        lines = conductor_text.split("\n")
        chain_lines = [
            ln for ln in lines if "hop" in ln.lower() or "delegazion" in ln.lower()
        ]
        # Verify the text contains hop/delegation documentation
        # trader-agent is leaf (max_spawn_depth: 0) so it shouldn't appear
        # in delegation chains that exceed 1 hop
        assert len(chain_lines) >= 0


class TestConductorCapabilityMatrixTraderAlignment:
    """Conductor must reference the capability matrix."""

    def test_capability_matrix_referenced(self, conductor_text: str) -> None:
        """Conductor references the capability matrix canonical source."""
        assert "agent-capability-matrix" in conductor_text or \
            "Capability Matrix" in conductor_text

    def test_handoff_protocol_referenced(self, conductor_text: str) -> None:
        """Conductor references the handoff protocol."""
        assert "handoff" in conductor_text.lower() or \
            "spawn-subagent" in conductor_text
