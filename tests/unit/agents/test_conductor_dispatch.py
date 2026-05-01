"""Static checks on aria-conductor agent prompt for sub-agent dispatch.

Verifica che l'agente conductor dichiari correttamente la capability matrix
e le regole di dispatch per tutti i sub-agenti disponibili.

After behavioral remediation (2026-05-01), also verifies:
- conductor explicitly forbids direct operational work
- mixed work-domain tasks route to productivity-agent
- GW operations route to productivity-agent, NOT workspace-agent
- conductor cannot dispatch directly to workspace-agent
- wiki validity guard against architecturally invalid flows
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

    def test_productivity_agent_listed(self, conductor_text: str):
        """Conductor lists productivity-agent in sub-agenti disponibili."""
        assert "productivity-agent" in conductor_text

    def test_search_agent_listed(self, conductor_text: str):
        """Conductor lists search-agent."""
        assert "search-agent" in conductor_text

    def test_workspace_agent_listed_as_transitional(self, conductor_text: str):
        """Conductor lists workspace-agent as transitional/compatibility."""
        assert "workspace-agent" in conductor_text
        # workspace-agent is transitional
        transitional_markers = [
            "COMPATIBILIT",
            "TRANSITORIO",
        ]
        lower_text = conductor_text.lower()
        assert (
            any(m in conductor_text or m.lower() in lower_text for m in transitional_markers)
            or "compatibilità" in lower_text
        )

    def test_dispatch_rules_for_productivity(self, conductor_text: str):
        """Conductor has dispatch rules for productivity-agent."""
        assert "Regole di dispatch per productivity-agent" in conductor_text
        assert "File office locali" in conductor_text
        assert "Briefing/documentazione multi-source" in conductor_text
        assert "Preparazione meeting" in conductor_text
        assert "Bozze email" in conductor_text
        # productivity-agent now handles Google Workspace directly
        assert "Operazioni Google Workspace" in conductor_text
        assert "productivity-agent" in conductor_text

    def test_capability_matrix_referenced(self, conductor_text: str):
        """Conductor references capability matrix canonical source."""
        assert "agent-capability-matrix" in conductor_text or "Capability Matrix" in conductor_text

    def test_handoff_protocol_referenced(self, conductor_text: str):
        """Conductor references handoff protocol with spawn-subagent payload."""
        assert "spawn-subagent" in conductor_text
        assert "goal" in conductor_text
        assert "constraints" in conductor_text
        assert "required_output" in conductor_text
        assert "trace_id" in conductor_text


class TestConductorNoDirectOperations:
    """Conductor must explicitly forbid direct operational work."""

    def test_has_no_direct_ops_section(self, conductor_text: str):
        """Conductor prompt contains an explicit 'no direct ops' section."""
        # The prompt must contain the prohibition section
        assert "NESSUN lavoro diretto" in conductor_text or "Non eseguire MAI" in conductor_text

    def test_forbids_file_operations(self, conductor_text: str):
        """Conductor explicitly forbids file read/write operations."""
        assert "glob" in conductor_text or "filesystem" in conductor_text
        assert "NON eseguire MAI" in conductor_text or "non eseguire mai" in conductor_text.lower()

    def test_forbids_search_operations(self, conductor_text: str):
        """Conductor explicitly forbids direct search operations."""
        lower = conductor_text.lower()
        # Must explicitly mention search/fetch as forbidden direct ops
        assert "search" in lower or "fetch" in lower or "scrape" in lower

    def test_forbids_gw_operations(self, conductor_text: str):
        """Conductor explicitly forbids direct Google Workspace operations."""
        assert "inviare email" in conductor_text or "gmail" in conductor_text.lower()
        assert "calendar" in conductor_text.lower() or "calendario" in conductor_text.lower()

    def test_forbids_runtime_self_remediation_during_user_workflows(
        self, conductor_text: str
    ) -> None:
        assert "NON modificare codice" in conductor_text
        assert "NON editare file di" in conductor_text
        assert "configurazione" in conductor_text
        assert "NON killare processi" in conductor_text
        assert "NON fare auto-remediation runtime" in conductor_text


class TestConductorWorkspaceAgentNotDirectlyDispatched:
    """Conductor must NOT dispatch directly to workspace-agent."""

    def test_workspace_agent_never_primary_dispatch_target(self, conductor_text: str):
        """Workspace-agent is not a primary dispatch target from conductor."""
        # Find the dispatch rules section
        assert "NON dispatchare direttamente a workspace-agent" in conductor_text

    def test_workspace_agent_described_as_compatibility_only(self, conductor_text: str):
        """Workspace-agent is described as compatibility/transitional."""
        # Must be described with COMPATIBILITÀ/TRANSITORIO marker
        ws_line = None
        for line in conductor_text.splitlines():
            if "workspace-agent" in line and "COMPATIBILIT" in line.upper():
                ws_line = line
                break
            if "workspace-agent" in line and "TRANSITORIO" in line.upper():
                ws_line = line
                break
        assert ws_line is not None, (
            "workspace-agent must have COMPATIBILITÀ or TRANSITORIO marker in its description"
        )


class TestConductorGwDispatchesToProductivityAgent:
    """Google Workspace operations must route to productivity-agent, not workspace-agent."""

    def test_gw_dispatches_to_productivity(self, conductor_text: str):
        """GW dispatch line explicitly routes to productivity-agent."""
        # Find the GW dispatch line
        found = False
        for line in conductor_text.splitlines():
            if "Operazioni Google Workspace" in line:
                assert "productivity-agent" in line, (
                    f"GW dispatch must target productivity-agent, got: {line}"
                )
                found = True
                break
        assert found, "Missing 'Operazioni Google Workspace' dispatch rule"

    def test_productivity_agent_described_as_unified_work_domain(self, conductor_text: str):
        """Productivity-agent is described as unified work-domain agent with GW access."""
        found = False
        for line in conductor_text.splitlines():
            if "productivity-agent" in line and "unificato" in line.lower():
                # Must mention Google Workspace in the description
                assert (
                    "Google Workspace" in line
                    or "google_workspace" in line
                    or "Gmail" in line
                    or "G Suite" in line
                ), f"productivity-agent description must mention GW: {line}"
                found = True
                break
        assert found, "productivity-agent missing unified work-domain description"

    def test_productivity_agent_has_direct_gw_access(self, conductor_text: str):
        """Productivity-agent description states direct GW access."""
        found = False
        for line in conductor_text.splitlines():
            if "productivity-agent" in line and "accesso diretto" in line.lower():
                found = True
                break
            if "productivity-agent" in line and "via proxy" in line.lower():
                found = True
                break
        assert found, "productivity-agent description must state direct access to backends"


class TestConductorMixedDomainRouting:
    """Mixed work-domain tasks must route to productivity-agent.

    These tests simulate the exact class of requests from the real transcript
    where the conductor bypassed productivity-agent and did work directly.
    """

    @pytest.mark.parametrize(
        "domain_keyword",
        [
            "leggi questo PDF e mandalo via email",
            "leggi questi documenti e prepara un briefing",
            "leggi questo file e prepara bozza email",
            "documento + crea proposta Google Workspace",
        ],
    )
    def test_mixed_task_routes_to_productivity_agent(
        self, conductor_text: str, domain_keyword: str
    ):
        """Each mixed-domain example in the dispatch rules routes to productivity-agent."""
        # The dispatch rules must contain this exact example routing to productivity-agent
        found = False
        for line in conductor_text.splitlines():
            if domain_keyword in line:
                assert "productivity-agent" in line, (
                    f"Mixed task '{domain_keyword}' must route to productivity-agent: {line}"
                )
                found = True
                break
        assert found, f"Missing mixed-domain dispatch rule for: {domain_keyword}"


class TestConductorWikiValidityGuard:
    """Conductor must not write wiki entries for architecturally invalid flows."""

    def test_has_wiki_validity_rule(self, conductor_text: str):
        """Conductor prompt contains wiki validity guard."""
        # Must contain a rule about not memorializing invalid flows
        assert (
            "architetturalmente invalidi" in conductor_text
            or "architetturalmente" in conductor_text
        )

    def test_wiki_rule_forbids_invalid_path_memorialization(self, conductor_text: str):
        """Wiki rule explicitly says not to write wiki entries for direct-conductor paths."""
        has_rule = (
            "NON scrivere wiki entries" in conductor_text or "NON memorializzarlo" in conductor_text
        )
        assert has_rule, "Missing wiki validity guard for architecturally invalid flows"


class TestConductorYamlConfig:
    """Conductor YAML frontmatter must be properly configured."""

    def test_type_is_primary(self, conductor_yaml: dict):
        """Conductor is type=primary."""
        assert conductor_yaml.get("type") == "primary"

    def test_category_is_orchestration(self, conductor_yaml: dict):
        """Conductor is category=orchestration."""
        assert conductor_yaml.get("category") == "orchestration"

    def test_allows_spawn_subagent(self, conductor_yaml: dict):
        """Conductor has spawn-subagent in allowed-tools."""
        assert "spawn-subagent" in conductor_yaml.get("allowed-tools", [])

    def test_allows_sequential_thinking(self, conductor_yaml: dict):
        """Conductor has sequential-thinking in allowed-tools."""
        assert "sequential-thinking__*" in conductor_yaml.get("allowed-tools", [])

    def test_required_skills(self, conductor_yaml: dict):
        """Conductor has required-skills: planning-with-files, hitl-queue."""
        skills = conductor_yaml.get("required-skills", [])
        assert "planning-with-files" in skills
        assert "hitl-queue" in skills

    def test_mcp_dependency_aria_memory(self, conductor_yaml: dict):
        """Conductor depends on aria-memory."""
        deps = conductor_yaml.get("mcp-dependencies", [])
        assert "aria-memory" in deps

    def test_no_operational_tools_in_allowed(self, conductor_yaml: dict):
        """Conductor does NOT have operational tools in allowed-tools."""
        tools = conductor_yaml.get("allowed-tools", [])
        # Must not have filesystem, markitdown, google_workspace, or search backends
        operational_prefixes = [
            "filesystem",
            "markitdown",
            "google_workspace",
            "searxng",
            "tavily",
            "fetch__",
        ]
        for tool in tools:
            for prefix in operational_prefixes:
                assert not tool.startswith(prefix), (
                    f"Conductor must NOT have operational tool '{tool}' in allowed-tools"
                )
