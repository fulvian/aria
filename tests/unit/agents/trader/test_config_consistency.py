"""Config consistency tests for trader-agent.

Verifies that the YAML frontmatter of trader-agent.md declares correct
allowed-tools, mcp-dependencies, intent-categories, and required-skills.
Also verifies alignment with the capability matrix YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

TRADER_AGENT_FILE = Path(".aria/kilocode/agents/trader-agent.md")
CAPABILITY_MATRIX_FILE = Path(".aria/config/agent_capability_matrix.yaml")


@pytest.fixture(scope="module")
def trader_agent_yaml() -> dict:
    """Parse YAML frontmatter from trader-agent.md."""
    content = TRADER_AGENT_FILE.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{TRADER_AGENT_FILE}: YAML frontmatter not found"
    return yaml.safe_load(parts[1])


@pytest.fixture(scope="module")
def trader_agent_text() -> str:
    """Full text content of trader-agent.md (without YAML frontmatter)."""
    content = TRADER_AGENT_FILE.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


@pytest.fixture(scope="module")
def capability_matrix_yaml() -> dict:
    """Parse the capability matrix YAML."""
    return yaml.safe_load(CAPABILITY_MATRIX_FILE.read_text(encoding="utf-8"))


class TestTraderAgentFrontmatter:
    """Frontmatter of trader-agent.md must be well-formed and complete."""

    def test_trader_agent_has_name(self, trader_agent_yaml: dict) -> None:
        """Frontmatter declares name: trader-agent."""
        assert trader_agent_yaml.get("name") == "trader-agent"

    def test_trader_agent_type_is_subagent(self, trader_agent_yaml: dict) -> None:
        """type must be 'subagent'."""
        assert trader_agent_yaml.get("type") == "subagent"

    def test_trader_agent_has_color(self, trader_agent_yaml: dict) -> None:
        """color must be declared."""
        assert trader_agent_yaml.get("color") is not None

    def test_trader_agent_has_category(self, trader_agent_yaml: dict) -> None:
        """category must be 'finance'."""
        assert trader_agent_yaml.get("category") == "finance"

    def test_trader_agent_has_temperature(self, trader_agent_yaml: dict) -> None:
        """temperature must be declared (0.2 for analytical agent)."""
        assert trader_agent_yaml.get("temperature") == 0.2

    def test_max_spawn_depth_is_zero(self, trader_agent_yaml: dict) -> None:
        """trader-agent is a leaf agent — max_spawn_depth must be 0."""
        assert trader_agent_yaml.get("max-spawn-depth") == 0


class TestTraderAgentAllowedTools:
    """allowed-tools must declare the canonical proxy surface and memory tools."""

    def test_allowed_tools_not_empty(self, trader_agent_yaml: dict) -> None:
        """allowed-tools list must not be empty."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        assert len(tools) > 0

    def test_allowed_tools_uses_proxy(self, trader_agent_yaml: dict) -> None:
        """allowed-tools must include aria-mcp-proxy_search_tools."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        assert "aria-mcp-proxy_search_tools" in tools

    def test_allowed_tools_uses_call_tool(self, trader_agent_yaml: dict) -> None:
        """allowed-tools must include aria-mcp-proxy_call_tool."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        assert "aria-mcp-proxy_call_tool" in tools

    def test_allowed_tools_includes_memory(self, trader_agent_yaml: dict) -> None:
        """allowed-tools must include aria-memory wiki tools."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        memory_tools = [t for t in tools if t.startswith(("aria-memory_", "aria-memory/"))]
        assert len(memory_tools) >= 4

    def test_allowed_tools_includes_hitl(self, trader_agent_yaml: dict) -> None:
        """allowed-tools must include hitl-queue_ask."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        assert "hitl-queue_ask" in tools

    def test_allowed_tools_includes_sequential_thinking(self, trader_agent_yaml: dict) -> None:
        """allowed-tools must include sequential-thinking."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        assert any(t.startswith("sequential-thinking") for t in tools)

    def test_allowed_tools_under_20_entries(self, trader_agent_yaml: dict) -> None:
        """P9: allowed-tools must be <= 20 entries."""
        tools = trader_agent_yaml.get("allowed-tools", [])
        assert len(tools) <= 20


class TestTraderAgentMcpDependencies:
    """mcp-dependencies must list the required proxy and memory deps."""

    def test_has_mcp_dependencies(self, trader_agent_yaml: dict) -> None:
        """mcp-dependencies must not be empty."""
        deps = trader_agent_yaml.get("mcp-dependencies", [])
        assert len(deps) > 0

    def test_includes_aria_mcp_proxy(self, trader_agent_yaml: dict) -> None:
        """mcp-dependencies must include aria-mcp-proxy."""
        deps = trader_agent_yaml.get("mcp-dependencies", [])
        assert "aria-mcp-proxy" in deps

    def test_includes_aria_memory(self, trader_agent_yaml: dict) -> None:
        """mcp-dependencies must include aria-memory."""
        deps = trader_agent_yaml.get("mcp-dependencies", [])
        assert "aria-memory" in deps


class TestTraderAgentRequiredSkills:
    """required-skills must declare all 7 trading skills."""

    def test_has_required_skills(self, trader_agent_yaml: dict) -> None:
        """required-skills must not be empty."""
        skills = trader_agent_yaml.get("required-skills", [])
        assert len(skills) > 0

    def test_has_trading_analysis_skill(self, trader_agent_yaml: dict) -> None:
        """required-skills must include trading-analysis."""
        skills = trader_agent_yaml.get("required-skills", [])
        assert "trading-analysis" in skills

    def test_has_7_skills(self, trader_agent_yaml: dict) -> None:
        """trader-agent must have exactly 7 required skills."""
        skills = trader_agent_yaml.get("required-skills", [])
        assert len(skills) == 7

    def test_all_7_trading_skills_present(self, trader_agent_yaml: dict) -> None:
        """All 7 trading skills must be declared."""
        expected_skills = {
            "trading-analysis",
            "fundamental-analysis",
            "technical-analysis",
            "macro-intelligence",
            "sentiment-analysis",
            "options-analysis",
            "crypto-analysis",
        }
        skills = set(trader_agent_yaml.get("required-skills", []))
        missing = expected_skills - skills
        assert not missing


class TestTraderAgentIntentCategories:
    """intent-categories must list all finance.* categories."""

    def test_has_intent_categories(self, trader_agent_yaml: dict) -> None:
        """intent-categories must not be empty."""
        categories = trader_agent_yaml.get("intent-categories", [])
        assert len(categories) > 0

    def test_intent_categories_8_entries(self, trader_agent_yaml: dict) -> None:
        """trader-agent must declare exactly 8 intent categories."""
        categories = trader_agent_yaml.get("intent-categories", [])
        assert len(categories) == 8

    def test_all_intent_categories_are_finance(self, trader_agent_yaml: dict) -> None:
        """All intent categories must start with 'finance.'."""
        categories = trader_agent_yaml.get("intent-categories", [])
        for cat in categories:
            assert cat.startswith("finance.")


class TestTraderAgentCapabilityMatrix:
    """trader-agent entry in capability matrix must be aligned."""

    def test_trader_in_capability_matrix(self, capability_matrix_yaml: dict) -> None:
        """trader-agent must appear in the capability matrix."""
        agents = capability_matrix_yaml.get("agents", [])
        agent_names = {a.get("name") for a in agents}
        assert "trader-agent" in agent_names

    def test_trader_capability_matrix_proxy_deps(self, capability_matrix_yaml: dict) -> None:
        """trader-agent in capability matrix must have aria-mcp-proxy dep."""
        agents = capability_matrix_yaml.get("agents", [])
        for agent in agents:
            if agent.get("name") == "trader-agent":
                deps = agent.get("mcp_dependencies", [])
                assert "aria-mcp-proxy" in deps
                assert "aria-memory" in deps
                return

    def test_trader_capability_matrix_max_spawn_zero(self, capability_matrix_yaml: dict) -> None:
        """trader-agent must have max_spawn_depth: 0 in capability matrix."""
        agents = capability_matrix_yaml.get("agents", [])
        for agent in agents:
            if agent.get("name") == "trader-agent":
                assert agent.get("max_spawn_depth") == 0
                return

    def test_trader_capability_matrix_intent_categories(self, capability_matrix_yaml: dict) -> None:
        """trader-agent must have finance.* intent_categories."""
        agents = capability_matrix_yaml.get("agents", [])
        for agent in agents:
            if agent.get("name") == "trader-agent":
                categories = agent.get("intent_categories", [])
                assert len(categories) > 0
                assert all(c.startswith("finance.") for c in categories)
                return


class TestTraderAgentPromptContract:
    """Prompt body of trader-agent.md must contain required sections."""

    def test_has_proxy_invocation_rule(self, trader_agent_text: str) -> None:
        """Prompt body must contain proxy invocation rule."""
        assert "_caller_id" in trader_agent_text
        assert "trader-agent" in trader_agent_text

    def test_has_disclaimer(self, trader_agent_text: str) -> None:
        """Prompt body must contain the mandatory disclaimer."""
        assert "DISCLAIMER" in trader_agent_text
        assert "consulenza finanziaria" in trader_agent_text.lower()

    def test_has_hitl_rule(self, trader_agent_text: str) -> None:
        """Prompt body must describe when HITL is required."""
        assert "hitl" in trader_agent_text.lower()

    def test_forbids_native_host_tools(self, trader_agent_text: str) -> None:
        """Prompt must prohibit native host tools (Glob, Read, Write)."""
        assert "Glob" in trader_agent_text
        assert "Read" in trader_agent_text
        assert "Write" in trader_agent_text

    def test_has_boundary_rules(self, trader_agent_text: str) -> None:
        """Prompt must describe boundary rules (no trading, no execution)."""
        assert "NON" in trader_agent_text or "no" in trader_agent_text.lower()

    def test_has_wiki_memory_rules(self, trader_agent_text: str) -> None:
        """Prompt must describe wiki_recall and wiki_update rules."""
        assert "wiki_recall" in trader_agent_text
        assert "wiki_update" in trader_agent_text

    def test_describes_intent_categories(self, trader_agent_text: str) -> None:
        """Prompt must enumerate the intent categories."""
        assert "finance.stock-analysis" in trader_agent_text
        assert "finance.macro-analysis" in trader_agent_text
        assert "finance.crypto" in trader_agent_text
