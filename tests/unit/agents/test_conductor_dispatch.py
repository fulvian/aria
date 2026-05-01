"""Static checks on aria-conductor agent prompt for sub-agent dispatch.

Verifica che l'agente conductor dichiari correttamente la capability matrix
e le regole di dispatch per tutti i sub-agenti disponibili.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CONDUCTOR_FILE = Path(".aria/kilocode/agents/aria-conductor.md")


@pytest.fixture(scope="module")
def conductor_yaml() -> dict:
    """Parse YAML frontmatter from aria-conductor.md."""
    content = CONDUCTOR_FILE.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{CONDUCTOR_FILE}: YAML frontmatter not found"
    return yaml.safe_load(parts[1])


@pytest.fixture(scope="module")
def conductor_text() -> str:
    """Full text content of aria-conductor.md (without YAML frontmatter)."""
    content = CONDUCTOR_FILE.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


class TestConductorSubAgentRegistry:
    """Conductor must declare all three sub-agents."""

    def test_productivity_agent_listed(self, conductor_text: str) -> None:
        """Conductor lists productivity-agent in sub-agenti disponibili."""
        assert "productivity-agent" in conductor_text

    def test_search_agent_listed(self, conductor_text: str) -> None:
        """Conductor lists search-agent."""
        assert "search-agent" in conductor_text

    def test_workspace_agent_listed(self, conductor_text: str) -> None:
        """Conductor lists workspace-agent."""
        assert "workspace-agent" in conductor_text

    def test_trader_agent_listed(self, conductor_text: str) -> None:
        """Conductor lists trader-agent in sub-agenti disponibili."""
        assert "trader-agent" in conductor_text

    def test_dispatch_rules_for_productivity(self, conductor_text: str) -> None:
        """Conductor has dispatch rules for productivity-agent."""
        assert "Regole di dispatch per productivity-agent" in conductor_text
        assert "File office locali" in conductor_text
        assert "Briefing/documentazione multi-source" in conductor_text
        assert "Preparazione meeting" in conductor_text
        assert "Bozze email" in conductor_text

    def test_dispatch_rules_for_trader_agent(self, conductor_text: str) -> None:
        """Conductor has dispatch rules for trader-agent."""
        assert "Regole di dispatch per trader-agent" in conductor_text
        assert "Analisi stock/ETF" in conductor_text
        assert "Analisi macroeconomica" in conductor_text
        assert "crypto" in conductor_text.lower()
        assert "Options" in conductor_text or "options" in conductor_text.lower()

    def test_capability_matrix_referenced(self, conductor_text: str) -> None:
        """Conductor references capability matrix canonical source."""
        assert "agent-capability-matrix" in conductor_text or \
            "Capability Matrix" in conductor_text

    def test_handoff_protocol_referenced(self, conductor_text: str) -> None:
        """Conductor references handoff protocol with spawn-subagent payload."""
        assert "spawn-subagent" in conductor_text
        assert "goal" in conductor_text
        assert "constraints" in conductor_text
        assert "required_output" in conductor_text
        assert "trace_id" in conductor_text


class TestConductorYamlConfig:
    """Conductor YAML frontmatter must be properly configured."""

    def test_type_is_primary(self, conductor_yaml: dict) -> None:
        """Conductor is type=primary."""
        assert conductor_yaml.get("type") == "primary"

    def test_category_is_orchestration(self, conductor_yaml: dict) -> None:
        """Conductor is category=orchestration."""
        assert conductor_yaml.get("category") == "orchestration"

    def test_allows_spawn_subagent(self, conductor_yaml: dict) -> None:
        """Conductor has spawn-subagent in allowed-tools."""
        assert "spawn-subagent" in conductor_yaml.get("allowed-tools", [])

    def test_allows_sequential_thinking(self, conductor_yaml: dict) -> None:
        """Conductor has sequential-thinking in allowed-tools."""
        assert "sequential-thinking/*" in conductor_yaml.get("allowed-tools", [])

    def test_required_skills(self, conductor_yaml: dict) -> None:
        """Conductor has required-skills: planning-with-files, hitl-queue."""
        skills = conductor_yaml.get("required-skills", [])
        assert "planning-with-files" in skills
        assert "hitl-queue" in skills

    def test_mcp_dependency_aria_memory(self, conductor_yaml: dict) -> None:
        """Conductor depends on aria-memory."""
        deps = conductor_yaml.get("mcp-dependencies", [])
        assert "aria-memory" in deps
