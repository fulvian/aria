"""Config consistency tests for search-agent.

Verifica che la definizione YAML di search-agent (allowed-tools, mcp-dependencies)
sia allineata con il modello canonico del proxy.

Il frontmatter espone solo i tool sintetici del proxy (`aria-mcp-proxy_search_tools`,
`aria-mcp-proxy_call_tool`) più i tool aria-memory diretti. I backend MCP reali
(searxng, tavily, exa, etc.) sono gestiti dalla capability matrix YAML
(`.aria/config/agent_capability_matrix.yaml`), non dal frontmatter.

Questi test garantiscono l'assenza di drift tra il modello canonico e la config.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SEARCH_AGENT_FILE = Path(".aria/kilocode/agents/search-agent.md")


@pytest.fixture(scope="module")
def search_agent_yaml() -> dict:
    """Parse YAML frontmatter from search-agent.md."""
    content = SEARCH_AGENT_FILE.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{SEARCH_AGENT_FILE}: YAML frontmatter not found"
    return yaml.safe_load(parts[1])


@pytest.fixture(scope="module")
def allowed_tools_set(search_agent_yaml: dict) -> set[str]:
    """Set of allowed-tool entries from search-agent.md."""
    return set(search_agent_yaml.get("allowed-tools", []))


@pytest.fixture(scope="module")
def mcp_deps_set(search_agent_yaml: dict) -> set[str]:
    """Set of mcp-dependencies from search-agent.md."""
    return set(search_agent_yaml.get("mcp-dependencies", []))


class TestSearchAgentProxyExposure:
    """Search-agent YAML exposes proxy canonical tools, not backend wildcards."""

    def test_exposes_proxy_search_tools(self, allowed_tools_set: set[str]):
        """search-agent exposes aria-mcp-proxy_search_tools."""
        assert "aria-mcp-proxy_search_tools" in allowed_tools_set

    def test_exposes_proxy_call_tool(self, allowed_tools_set: set[str]):
        """search-agent exposes aria-mcp-proxy_call_tool."""
        assert "aria-mcp-proxy_call_tool" in allowed_tools_set

    def test_exposes_memory_tools(self, allowed_tools_set: set[str]):
        """search-agent exposes aria-memory tools."""
        assert "aria-memory_wiki_update_tool" in allowed_tools_set
        assert "aria-memory_wiki_recall_tool" in allowed_tools_set

    def test_no_backend_wildcards_in_frontmatter(self, allowed_tools_set: set[str]):
        """Frontmatter does NOT contain backend-specific wildcards (those are in capability matrix)."""
        backend_wildcards = {
            "searxng-script_*",
            "tavily-mcp_*",
            "exa-script_*",
            "brave-mcp_*",
            "reddit-search_*",
            "scientific-papers-mcp_*",
        }
        overlap = backend_wildcards & allowed_tools_set
        assert overlap == set(), (
            f"Frontmatter should not contain backend wildcards: {overlap}. "
            f"Backend access is governed by agent_capability_matrix.yaml."
        )


class TestSearchAgentMcpDeps:
    """Search-agent depends on proxy + memory."""

    def test_mcp_deps_has_2_entries(self, search_agent_yaml: dict):
        """search-agent.md depends on proxy plus aria-memory."""
        deps = search_agent_yaml.get("mcp-dependencies", [])
        assert len(deps) == 2, f"Expected 2 mcp-dependencies, got {len(deps)}"

    def test_mcp_deps_proxy(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes the shared proxy."""
        assert "aria-mcp-proxy" in mcp_deps_set

    def test_mcp_deps_memory(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes aria-memory."""
        assert "aria-memory" in mcp_deps_set


class TestSearchAgentRequiredSkills:
    """search-agent required-skills should reference existing skills only."""

    def test_required_skills_exist(self, search_agent_yaml: dict):
        """All required-skills reference existing skill directories."""
        required_skills = search_agent_yaml.get("required-skills", [])
        skills_dir = Path(".aria/kilocode/skills")
        for skill_name in required_skills:
            skill_path = skills_dir / skill_name / "SKILL.md"
            assert skill_path.exists(), f"Required skill '{skill_name}' not found at {skill_path}"
