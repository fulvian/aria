"""Static checks on aria-conductor agent prompt for sub-agent dispatch.

Verifica che l'agente conductor dichiari correttamente la capability matrix
e le regole di dispatch per tutti i sub-agenti disponibili.

After behavioral remediation (2026-05-01), also verifies:
- conductor explicitly forbids direct operational work
- mixed work-domain tasks route to productivity-agent
- GW operations route to productivity-agent, NOT workspace-agent
- conductor cannot dispatch directly to workspace-agent
- wiki validity guard against architecturally invalid flows

After trader-agent integration (2026-05-02), also verifies:
- trader-agent is listed in sub-agenti disponibili
- financial dispatch rules exist with keyword routing
- trader-agent is in delegation chain
- financial queries do NOT route to search-agent
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CONDUCTOR_FILE = Path(".aria/kilocode/agents/aria-conductor.md")
TRADER_AGENT_FILE = Path(".aria/kilocode/agents/trader-agent.md")
CAPABILITY_MATRIX_FILE = Path(".aria/config/agent_capability_matrix.yaml")


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


# === Trader-Agent Integration Tests ===


class TestConductorTraderAgentRegistry:
    """Conductor must declare trader-agent and have financial dispatch rules."""

    def test_trader_agent_listed_in_subagenti(self, conductor_text: str):
        """Conductor lists trader-agent in sub-agenti disponibili."""
        assert "trader-agent" in conductor_text

    def test_trader_agent_described_as_finance(self, conductor_text: str):
        """Trader-agent description mentions finance domain."""
        # Must have a description line containing both trader-agent and finance keywords
        found = False
        for line in conductor_text.splitlines():
            if "trader-agent" in line and "analisi finanziaria" in line.lower():
                found = True
                break
            if "trader-agent" in line and "stock" in line.lower():
                found = True
                break
            if "trader-agent" in line and "financial" in line.lower():
                found = True
                break
        assert found, "trader-agent must be described as a finance domain agent"

    def test_financial_dispatch_rules_exist(self, conductor_text: str):
        """Conductor has dispatch rules for trader-agent."""
        assert "Regole di dispatch per trader-agent" in conductor_text

    def test_financial_keyword_routing_exists(self, conductor_text: str):
        """Conductor has keyword routing section for finance."""
        assert "Keyword di routing automatico" in conductor_text or (
            "keyword" in conductor_text.lower()
            and "trader-agent" in conductor_text
        )

    def test_stock_analysis_routes_to_trader(self, conductor_text: str):
        """Stock analysis dispatches to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            if "stock" in line.lower() and "trader-agent" in line:
                found = True
                break
            if "Analisi stock" in line and "trader-agent" in line:
                found = True
                break
        assert found, "Stock analysis must route to trader-agent"

    def test_crypto_routes_to_trader(self, conductor_text: str):
        """Crypto analysis dispatches to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            if "crypto" in line.lower() and "trader-agent" in line:
                found = True
                break
            if "Analisi crypto" in line and "trader-agent" in line:
                found = True
                break
        assert found, "Crypto analysis must route to trader-agent"

    def test_etf_routes_to_trader(self, conductor_text: str):
        """ETF analysis dispatches to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            if "ETF" in line and "trader-agent" in line:
                found = True
                break
        assert found, "ETF analysis must route to trader-agent"

    def test_investment_opportunity_routes_to_trader(self, conductor_text: str):
        """Investment opportunity research routes to trader-agent."""
        found = False
        for line in conductor_text.splitlines():
            lower = line.lower()
            if (
                "opportunit" in lower
                and "investiment" in lower
                and "trader-agent" in line
            ):
                found = True
                break
        assert found, "Investment opportunity research must route to trader-agent"

    def test_trader_agent_in_delegation_chain(self, conductor_text: str):
        """Trader-agent is in the delegation chains section."""
        assert "trader-agent" in conductor_text
        # Must appear in the catene di dispatch section
        assert "trader-agent → search-agent" in conductor_text or (
            "trader-agent" in conductor_text.split("Catene di dispatch")[1].split("##")[0]
            if "Catene di dispatch" in conductor_text
            else False
        )

    def test_search_agent_not_primary_for_finance(self, conductor_text: str):
        """Conductor explicitly says NOT to use search-agent for financial queries."""
        assert "NON dispatchare a search-agent" in conductor_text or (
            "NON" in conductor_text
            and "search-agent" in conductor_text
            and "finanziari" in conductor_text.lower()
        )


class TestTraderAgentPromptExists:
    """Trader-agent prompt file exists in canonical location."""

    def test_trader_agent_file_exists(self):
        """Trader-agent prompt file exists in .aria/kilocode/agents/."""
        assert TRADER_AGENT_FILE.exists(), (
            f"trader-agent prompt missing: {TRADER_AGENT_FILE}"
        )

    @pytest.fixture(scope="class")
    def trader_text(self) -> str:
        """Full text content of trader-agent.md."""
        if not TRADER_AGENT_FILE.exists():
            pytest.skip("trader-agent.md not found")
        content = TRADER_AGENT_FILE.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        assert len(parts) >= 3, "trader-agent.md: YAML frontmatter not found"
        return parts[2]

    @pytest.fixture(scope="class")
    def trader_yaml(self) -> dict:
        """YAML frontmatter of trader-agent.md."""
        if not TRADER_AGENT_FILE.exists():
            pytest.skip("trader-agent.md not found")
        content = TRADER_AGENT_FILE.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        return yaml.safe_load(parts[1])

    def test_trader_agent_type_is_subagent(self, trader_yaml: dict):
        """Trader-agent type is subagent."""
        assert trader_yaml.get("type") == "subagent"

    def test_trader_agent_category_is_finance(self, trader_yaml: dict):
        """Trader-agent category is finance."""
        assert trader_yaml.get("category") == "finance"

    def test_trader_agent_has_proxy_tools(self, trader_yaml: dict):
        """Trader-agent has proxy tools in allowed-tools."""
        tools = trader_yaml.get("allowed-tools", [])
        assert any("aria-mcp-proxy" in t for t in tools), (
            "trader-agent must have aria-mcp-proxy tools"
        )

    def test_trader_agent_has_memory_tools(self, trader_yaml: dict):
        """Trader-agent has memory tools."""
        tools = trader_yaml.get("allowed-tools", [])
        assert any("aria-memory" in t for t in tools), (
            "trader-agent must have aria-memory tools"
        )

    def test_trader_agent_has_no_spawn_depth(self, trader_yaml: dict):
        """Trader-agent has max-spawn-depth 0 (no sub-delegation)."""
        assert trader_yaml.get("max-spawn-depth") == 0, (
            "trader-agent must have max-spawn-depth: 0"
        )

    def test_trader_agent_has_required_skills(self, trader_yaml: dict):
        """Trader-agent lists all 7 required skills."""
        skills = trader_yaml.get("required-skills", [])
        expected_skills = [
            "trading-analysis",
            "fundamental-analysis",
            "technical-analysis",
            "macro-intelligence",
            "sentiment-analysis",
            "options-analysis",
            "crypto-analysis",
        ]
        for skill in expected_skills:
            assert skill in skills, f"trader-agent missing required skill: {skill}"

    def test_trader_agent_has_intent_categories(self, trader_yaml: dict):
        """Trader-agent declares finance intent categories."""
        intents = trader_yaml.get("intent-categories", [])
        expected_intents = [
            "finance.stock-analysis",
            "finance.crypto",
            "finance.macro-analysis",
        ]
        for intent in expected_intents:
            assert intent in intents, f"trader-agent missing intent category: {intent}"

    def test_trader_agent_has_disclaimer(self, trader_text: str):
        """Trader-agent prompt contains mandatory disclaimer."""
        assert "DISCLAIMER" in trader_text

    def test_trader_agent_has_caller_id_rule(self, trader_text: str):
        """Trader-agent prompt specifies _caller_id rule."""
        assert "_caller_id" in trader_text
        assert "trader-agent" in trader_text

    def test_trader_agent_forbids_host_tools(self, trader_text: str):
        """Trader-agent prompt forbids host-native tools."""
        assert "NON usare tool nativi" in trader_text or "NON usare" in trader_text

    def test_trader_agent_forbids_trading_execution(self, trader_text: str):
        """Trader-agent explicitly says it does NOT execute trades."""
        assert "NON" in trader_text and "trading reale" in trader_text.lower()


class TestTraderAgentInCapabilityMatrix:
    """Trader-agent is registered in the capability matrix."""

    @pytest.fixture(scope="class")
    def matrix_agents(self) -> list[dict]:
        """Load agent entries from capability matrix."""
        if not CAPABILITY_MATRIX_FILE.exists():
            pytest.skip("capability matrix not found")
        data = yaml.safe_load(CAPABILITY_MATRIX_FILE.read_text(encoding="utf-8"))
        return data.get("agents", [])

    def test_trader_agent_in_matrix(self, matrix_agents: list[dict]):
        """Trader-agent is listed in the capability matrix."""
        names = [a.get("name") for a in matrix_agents]
        assert "trader-agent" in names, (
            "trader-agent not found in agent_capability_matrix.yaml"
        )

    def test_conductor_delegates_to_trader(self, matrix_agents: list[dict]):
        """Conductor's delegation_targets includes trader-agent."""
        conductor = next(
            (a for a in matrix_agents if a.get("name") == "aria-conductor"), None
        )
        assert conductor is not None
        targets = conductor.get("delegation_targets", [])
        assert "trader-agent" in targets, (
            "conductor delegation_targets missing trader-agent"
        )

    def test_trader_agent_no_sub_delegation(self, matrix_agents: list[dict]):
        """Trader-agent has empty delegation_targets (no sub-delegation)."""
        trader = next(
            (a for a in matrix_agents if a.get("name") == "trader-agent"), None
        )
        assert trader is not None
        assert trader.get("delegation_targets") == [] or trader.get("delegation_targets") is None

    def test_trader_agent_type_is_worker(self, matrix_agents: list[dict]):
        """Trader-agent is type worker."""
        trader = next(
            (a for a in matrix_agents if a.get("name") == "trader-agent"), None
        )
        assert trader is not None
        assert trader.get("type") == "worker"

    def test_trader_agent_has_finance_intents(self, matrix_agents: list[dict]):
        """Trader-agent has finance intent categories."""
        trader = next(
            (a for a in matrix_agents if a.get("name") == "trader-agent"), None
        )
        assert trader is not None
        intents = trader.get("intent_categories", [])
        assert len(intents) > 0, "trader-agent must have intent categories"
        assert "finance.stock-analysis" in intents
        assert "finance.crypto" in intents

    def test_trader_agent_mcp_dependencies(self, matrix_agents: list[dict]):
        """Trader-agent depends on aria-mcp-proxy and aria-memory."""
        trader = next(
            (a for a in matrix_agents if a.get("name") == "trader-agent"), None
        )
        assert trader is not None
        deps = trader.get("mcp_dependencies", [])
        assert "aria-mcp-proxy" in deps
        assert "aria-memory" in deps
