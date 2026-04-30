"""Config consistency tests for search-agent.

Verifica che la definizione YAML di search-agent (allowed-tools, mcp-dependencies)
sia allineata con il router Python (Provider enum, INTENT_TIERS) e con le policy
documentate nel wiki.

Questi test garantiscono l'assenza di drift tra config dichiarativa e implementazione.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from aria.agents.search.router import INTENT_TIERS, Intent, Provider

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


class TestSearchAgentExposure:
    """Search-agent YAML must expose tools for all providers declared in the router."""

    def test_allowed_tools_has_19_entries(self, search_agent_yaml: dict):
        """search-agent.md declares exactly 19 allowed-tools (pubmed-mcp removed)."""
        tools = search_agent_yaml.get("allowed-tools", [])
        assert len(tools) == 19, f"Expected 19 allowed-tools, got {len(tools)}"

    def test_mcp_dependencies_has_6_entries(self, search_agent_yaml: dict):
        """search-agent.md declares exactly 6 mcp-dependencies (pubmed-mcp removed)."""
        deps = search_agent_yaml.get("mcp-dependencies", [])
        assert len(deps) == 6, f"Expected 6 mcp-dependencies, got {len(deps)}"

    # --- Provider-level exposure checks ---

    def test_exposes_searxng(self, allowed_tools_set: set[str]):
        """search-agent exposes searxng-script/search."""
        assert "searxng-script/search" in allowed_tools_set

    def test_exposes_tavily(self, allowed_tools_set: set[str]):
        """search-agent exposes tavily-mcp/search."""
        assert "tavily-mcp/search" in allowed_tools_set

    def test_exposes_exa(self, allowed_tools_set: set[str]):
        """search-agent exposes exa-script/search."""
        assert "exa-script/search" in allowed_tools_set

    def test_exposes_brave(self, allowed_tools_set: set[str]):
        """search-agent exposes both brave-mcp tools."""
        assert "brave-mcp/web_search" in allowed_tools_set
        assert "brave-mcp/news_search" in allowed_tools_set

    def test_exposes_reddit(self, allowed_tools_set: set[str]):
        """search-agent exposes all 6 reddit-search tools."""
        reddit_tools = {t for t in allowed_tools_set if t.startswith("reddit-search/")}
        assert len(reddit_tools) == 6, (
            f"Expected 6 reddit-search tools, got {len(reddit_tools)}: {reddit_tools}"
        )

    def test_exposes_scientific_papers(self, allowed_tools_set: set[str]):
        """search-agent exposes all 5 scientific-papers-mcp tools."""
        sci_tools = {t for t in allowed_tools_set if t.startswith("scientific-papers-mcp/")}
        assert len(sci_tools) == 5, (
            f"Expected 5 scientific-papers-mcp tools, got {len(sci_tools)}: {sci_tools}"
        )

    # --- MCP dependencies checks ---

    def test_mcp_deps_scientific_papers(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes scientific-papers-mcp."""
        assert "scientific-papers-mcp" in mcp_deps_set

    def test_mcp_deps_reddit(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes reddit-search."""
        assert "reddit-search" in mcp_deps_set

    def test_mcp_deps_tavily(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes tavily-mcp."""
        assert "tavily-mcp" in mcp_deps_set

    def test_mcp_deps_brave(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes brave-mcp."""
        assert "brave-mcp" in mcp_deps_set

    def test_mcp_deps_exa(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes exa-script."""
        assert "exa-script" in mcp_deps_set

    def test_mcp_deps_searxng(self, mcp_deps_set: set[str]):
        """mcp-dependencies includes searxng-script."""
        assert "searxng-script" in mcp_deps_set

    # --- Router-to-YAML alignment ---

    def test_every_router_provider_has_tools(self, allowed_tools_set: set[str]):
        """Every non-trivially-named provider in INTENT_TIERS has a corresponding tool entry.

        Some providers (FETCH, WEBFETCH) don't have MCP tools in allowed-tools
        because they use implicit tools (fetch/fetch). This test checks that
        providers with MCP backends are all exposed.
        """
        provider_to_mcp_key = {
            "searxng": "searxng-script",
            "tavily": "tavily-mcp",
            "exa": "exa-script",
            "brave": "brave-mcp",
            "reddit": "reddit-search",
            "scientific_papers": "scientific-papers-mcp",
        }
        known_implicit = {"fetch", "webfetch"}

        all_providers: set[str] = set()
        for intent in Intent:
            tiers = INTENT_TIERS.get(intent)
            if tiers:
                for p in tiers:
                    all_providers.add(p.value)

        for p_name in all_providers:
            if p_name in known_implicit:
                continue
            mcp_key = provider_to_mcp_key.get(p_name)
            assert mcp_key is not None, f"No MCP key mapping for provider '{p_name}'"
            has_tool = any(t.startswith(f"{mcp_key}/") for t in allowed_tools_set)
            assert has_tool, (
                f"Provider '{p_name}' (MCP key: {mcp_key}) declared in INTENT_TIERS "
                f"but no tool starting with '{mcp_key}/' in search-agent.md allowed-tools"
            )

    def test_every_router_provider_in_mcp_deps(self, mcp_deps_set: set[str]):
        """Every provider with an MCP server backend is in mcp-dependencies."""
        # Map provider values to their MCP dependency keys
        provider_to_dep = {
            "searxng": "searxng-script",
            "tavily": "tavily-mcp",
            "exa": "exa-script",
            "brave": "brave-mcp",
            "reddit": "reddit-search",
            "scientific_papers": "scientific-papers-mcp",
        }

        for p_value, dep_key in provider_to_dep.items():
            assert dep_key in mcp_deps_set, (
                f"Provider '{p_value}' mapped to dependency '{dep_key}' "
                f"but not found in search-agent.md mcp-dependencies"
            )


class TestRouterAcademicExposure:
    """Router must include SCIENTIFIC_PAPERS in ACADEMIC tiers (pubmed removed)."""

    def test_academic_tiers_include_scientific_papers(self):
        """ACADEMIC INTENT_TIERS includes Provider.SCIENTIFIC_PAPERS."""
        assert Provider.SCIENTIFIC_PAPERS in INTENT_TIERS[Intent.ACADEMIC]

    def test_pubmed_string_not_in_academic_tiers(self):
        """'pubmed' is NOT in ACADEMIC tiers anymore (removed 2026-04-30)."""
        tier_values = [p.value for p in INTENT_TIERS[Intent.ACADEMIC]]
        assert "pubmed" not in tier_values

    def test_scientific_papers_is_tier_2_in_academic(self):
        """SCIENTIFIC_PAPERS is at position 2 (index 2) in ACADEMIC tier list."""
        tiers = INTENT_TIERS[Intent.ACADEMIC]
        assert tiers[2] == Provider.SCIENTIFIC_PAPERS, (
            f"Expected SCIENTIFIC_PAPERS at position 2, got {tiers[2]}"
        )
