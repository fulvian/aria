"""Static checks on traveller-agent prompt file frontmatter and content.

Verifica che il prompt canonico del traveller-agent:
- Frontmatter YAML valido (name, type, description, category, temperature,
  allowed-tools, required-skills, mcp-dependencies, intent-categories)
- _caller_id: "traveller-agent" rule presente
- canonical proxy invocation pattern presente
- boundary operativo: no host tools, no auto-remediation, disclaimer
- HITL rules per write esterne
- memory contract: wiki_recall inizio + wiki_update fine
- regole di delega chain → productivity-agent
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROMPT = Path(".aria/kilocode/agents/traveller-agent.md")


@pytest.fixture(scope="module")
def fm() -> dict:
    """Parse YAML frontmatter from traveller-agent.md."""
    text = PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "frontmatter not found"
    return yaml.safe_load(parts[1])


@pytest.fixture(scope="module")
def prompt_text() -> str:
    """Full text content of traveller-agent.md (without YAML frontmatter)."""
    text = PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


class TestTravellerAgentFrontmatter:
    """Traveller-agent YAML frontmatter validation."""

    def test_name(self, fm: dict):
        assert fm["name"] == "traveller-agent"

    def test_type(self, fm: dict):
        assert fm["type"] == "subagent"

    def test_description(self, fm: dict):
        desc = fm.get("description", "")
        assert "viaggi" in desc.lower() or "travel" in desc.lower()
        assert "NON booking executor" in desc or "NON" in desc

    def test_color(self, fm: dict):
        color = fm.get("color", "")
        assert color.startswith("#") and len(color) == 7

    def test_category(self, fm: dict):
        assert fm["category"] == "travel"

    def test_temperature(self, fm: dict):
        temp = fm["temperature"]
        assert 0.0 <= temp <= 0.4

    def test_allowed_tools_proxy(self, fm: dict):
        tools = fm["allowed-tools"]
        assert "aria-mcp-proxy__search_tools" in tools
        assert "aria-mcp-proxy__call_tool" in tools

    def test_allowed_tools_memory(self, fm: dict):
        tools = fm["allowed-tools"]
        for t in ("wiki_update_tool", "wiki_recall_tool", "wiki_show_tool", "wiki_list_tool"):
            assert f"aria-memory__{t}" in tools

    def test_allowed_tools_hitl(self, fm: dict):
        assert "hitl-queue__ask" in fm["allowed-tools"]

    def test_allowed_tools_sequential(self, fm: dict):
        assert "sequential-thinking__*" in fm["allowed-tools"]

    def test_allowed_tools_spawn(self, fm: dict):
        assert "spawn-subagent" in fm["allowed-tools"]

    def test_mcp_dependencies(self, fm: dict):
        deps = set(fm["mcp-dependencies"])
        assert {"aria-mcp-proxy", "aria-memory"}.issubset(deps)

    def test_required_skills(self, fm: dict):
        skills = fm.get("required-skills", [])
        expected = [
            "destination-research",
            "accommodation-comparison",
            "transport-planning",
            "activity-planning",
            "itinerary-building",
            "budget-analysis",
        ]
        for skill in expected:
            assert skill in skills, f"missing required skill: {skill}"

    def test_intent_categories(self, fm: dict):
        intents = set(fm["intent-categories"])
        expected = {
            "travel.destination",
            "travel.transport",
            "travel.accommodation",
            "travel.activity",
            "travel.itinerary",
            "travel.budget",
            "travel.brief",
        }
        assert expected.issubset(intents)

    def test_max_spawn_depth(self, fm: dict):
        assert fm.get("max-spawn-depth", 0) == 1


class TestTravellerAgentContent:
    """Traveller-agent prompt body validation."""

    def test_caller_id_rule(self, prompt_text: str):
        """Prompt specifies _caller_id: traveller-agent."""
        assert "_caller_id" in prompt_text
        assert "traveller-agent" in prompt_text

    def test_canonical_proxy_invocation(self, prompt_text: str):
        """Prompt contains search_tools → call_tool pattern."""
        assert "aria-mcp-proxy__search_tools" in prompt_text
        assert 'aria-mcp-proxy__call_tool\n  name: "<server>__<tool>"' in prompt_text
        assert "aria-mcp-proxy" in prompt_text
        assert 'name: "search_tools"' not in prompt_text
        assert 'aria-mcp-proxy__call_tool(name="call_tool"' not in prompt_text

    def test_no_host_tools(self, prompt_text: str):
        """Prompt forbids host-native tools for travel workflows."""
        assert "non" in prompt_text and "tool" in prompt_text
        # The prompt now says "DEVI chiamare tool" which is stronger
        assert "DEVI" in prompt_text or "REGOLA" in prompt_text

    def test_no_auto_remediation(self, prompt_text: str):
        """Prompt forbids auto-remediation during user workflows."""
        assert "NON modificare codice" in prompt_text
        assert "NON editare file" in prompt_text
        assert "configurazione" in prompt_text
        assert "NON killare processi" in prompt_text
        assert "NON fare auto-remediation" in prompt_text or "auto-remediation" in prompt_text

    def test_disclaimer_present(self, prompt_text: str):
        """Prompt contains mandatory travel disclaimer."""
        # Check across possible newlines
        flat = prompt_text.replace("\n", " ")
        assert "Nessuna prenotazione è stata eseguita" in flat
        assert "Verifica disponibilità e prezzi" in prompt_text

    def test_hitl_rules(self, prompt_text: str):
        """Prompt has HITL rules for external writes."""
        assert "hitl-queue__ask" in prompt_text
        assert "Google Drive" in prompt_text or "Drive" in prompt_text
        assert "Calendar" in prompt_text or "calendar" in prompt_text.lower()

    def test_memory_contract_recall(self, prompt_text: str):
        """Prompt specifies wiki_recall at start of turn."""
        assert "wiki_recall" in prompt_text.lower() or "wiki_recall_tool" in prompt_text

    def test_memory_contract_update(self, prompt_text: str):
        """Prompt specifies wiki_update at end of turn."""
        assert "wiki_update" in prompt_text.lower() or "wiki_update_tool" in prompt_text

    def test_delegation_to_productivity(self, prompt_text: str):
        """Prompt specifies delegation chain to productivity-agent."""
        assert "productivity-agent" in prompt_text or "productivity" in prompt_text

    def test_degraded_mode_guidance_present(self, prompt_text: str):
        """Prompt allows partial continuation when only some backends fail."""
        assert "degraded mode" in prompt_text
        assert "risultati parziali" in prompt_text
        assert "TUTTI i backend" in prompt_text

    def test_backend_backends_listed(self, prompt_text: str):
        """Prompt lists travel backend MCP servers."""
        assert "airbnb" in prompt_text
        assert "osm-mcp" in prompt_text or "google-maps" in prompt_text
        assert "aria-amadeus-mcp" in prompt_text

    def test_travel_brief_template(self, prompt_text: str):
        """Prompt contains Travel Brief template structure."""
        assert "Travel Brief" in prompt_text

    def test_intent_categories_section(self, prompt_text: str):
        """Prompt has intent categories section."""
        assert "travel.destination" in prompt_text
        assert "travel.transport" in prompt_text
        assert "travel.accommodation" in prompt_text
        assert "travel.activity" in prompt_text
        assert "travel.itinerary" in prompt_text
        assert "travel.budget" in prompt_text
        assert "travel.brief" in prompt_text
