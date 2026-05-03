from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from aria.agents.coordination import AgentRegistry
from aria.agents.coordination.registry import YamlCapabilityRegistry

if TYPE_CHECKING:
    from pathlib import Path


class AgentSpec:
    def __init__(
        self,
        name: str,
        description: str,
        allowed_tools: list[str],
        max_tools: int = 20,
        delegation_targets: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.allowed_tools = allowed_tools
        self.max_tools = max_tools
        self.delegation_targets = delegation_targets or []


class InMemoryAgentRegistry:
    """Concrete implementation of AgentRegistry for testing delegation policies."""

    def __init__(self, agents: dict[str, AgentSpec] | None = None) -> None:
        self._agents: dict[str, AgentSpec] = agents or {}
        self._delegation_rules: dict[str, list[str]] = {}

    def register_agent(self, spec: AgentSpec) -> None:
        self._agents[spec.name] = spec

    def add_delegation_rule(self, parent: str, child: str) -> None:
        self._agents.setdefault(parent, AgentSpec(name=parent, description="", allowed_tools=[]))
        self._agents.setdefault(child, AgentSpec(name=child, description="", allowed_tools=[]))
        self._delegation_rules.setdefault(parent, []).append(child)

    def get_agent(self, name: str) -> AgentSpec | None:
        return self._agents.get(name)

    def get_allowed_tools(self, agent_name: str) -> list[str]:
        agent = self._agents.get(agent_name)
        if agent is None:
            return []
        return list(agent.allowed_tools)

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        allowed = self._delegation_rules.get(parent_agent, [])
        return target_agent in allowed

    def validate_tool_count(self, agent_name: str) -> bool:
        agent = self._agents.get(agent_name)
        if agent is None:
            return False
        return len(agent.allowed_tools) <= agent.max_tools

    def get_delegation_targets(self, agent_name: str) -> list[str]:
        return list(self._delegation_rules.get(agent_name, []))


@pytest.fixture
def search_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="search_agent",
        description="Performs web searches",
        allowed_tools=["tavily_search", "brave_search", "fetch"],
        delegation_targets=["academic_search_agent", "social_search_agent"],
    )


@pytest.fixture
def academic_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="academic_search_agent",
        description="Searches academic sources",
        allowed_tools=["exa_search", "arxiv_fetch"],
    )


@pytest.fixture
def tool_heavy_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="tool_heavy_agent",
        description="Agent with many tools",
        allowed_tools=[f"tool_{i}" for i in range(25)],
    )


@pytest.fixture
def registry(
    search_agent_spec: AgentSpec,
    academic_agent_spec: AgentSpec,
    tool_heavy_agent_spec: AgentSpec,
) -> InMemoryAgentRegistry:
    r = InMemoryAgentRegistry()
    r.register_agent(search_agent_spec)
    r.register_agent(academic_agent_spec)
    r.register_agent(tool_heavy_agent_spec)
    r.add_delegation_rule("conductor", "search_agent")
    r.add_delegation_rule("search_agent", "academic_search_agent")
    return r


class TestAgentRegistryProtocol:
    def test_is_protocol(self) -> None:
        assert issubclass(AgentRegistry, Protocol)

    def test_concrete_implements_protocol(self, registry: InMemoryAgentRegistry) -> None:
        assert hasattr(registry, "validate_delegation")
        assert callable(registry.validate_delegation)


class TestGetAgent:
    def test_returns_correct_agent_spec(
        self, registry: InMemoryAgentRegistry, search_agent_spec: AgentSpec
    ) -> None:
        spec = registry.get_agent("search_agent")
        assert spec is not None
        assert spec.name == "search_agent"
        assert spec.description == "Performs web searches"

    def test_returns_none_for_unknown(self, registry: InMemoryAgentRegistry) -> None:
        spec = registry.get_agent("nonexistent")
        assert spec is None


class TestGetAllowedTools:
    def test_returns_tools_list(self, registry: InMemoryAgentRegistry) -> None:
        tools = registry.get_allowed_tools("search_agent")
        assert tools == ["tavily_search", "brave_search", "fetch"]

    def test_returns_empty_for_unknown(self, registry: InMemoryAgentRegistry) -> None:
        tools = registry.get_allowed_tools("unknown_agent")
        assert tools == []


class TestValidateDelegation:
    def test_valid_parent_target(self, registry: InMemoryAgentRegistry) -> None:
        assert registry.validate_delegation("conductor", "search_agent") is True
        assert registry.validate_delegation("search_agent", "academic_search_agent") is True

    def test_invalid_target_returns_false(self, registry: InMemoryAgentRegistry) -> None:
        assert registry.validate_delegation("conductor", "nonexistent") is False
        assert registry.validate_delegation("academic_search_agent", "search_agent") is False

    def test_unknown_parent_returns_false(self, registry: InMemoryAgentRegistry) -> None:
        assert registry.validate_delegation("unknown", "search_agent") is False


class TestValidateToolCount:
    def test_under_limit_returns_true(self, registry: InMemoryAgentRegistry) -> None:
        assert registry.validate_tool_count("search_agent") is True

    def test_over_limit_returns_false(self, registry: InMemoryAgentRegistry) -> None:
        assert registry.validate_tool_count("tool_heavy_agent") is False

    def test_unknown_agent_returns_false(self, registry: InMemoryAgentRegistry) -> None:
        assert registry.validate_tool_count("unknown") is False


class TestGetDelegationTargets:
    def test_returns_list(self, registry: InMemoryAgentRegistry) -> None:
        targets = registry.get_delegation_targets("search_agent")
        assert targets == ["academic_search_agent"]

    def test_returns_empty_for_unknown(self, registry: InMemoryAgentRegistry) -> None:
        targets = registry.get_delegation_targets("unknown_agent")
        assert targets == []


class TestYamlCapabilityRegistry:
    def test_validate_delegation_enforces_configured_edge(self, tmp_path: Path) -> None:
        matrix = tmp_path / "agent_capability_matrix.yaml"
        matrix.write_text(
            """
agents:
  - name: aria-conductor
    allowed_tools: [spawn-subagent]
    delegation_targets: [search-agent, productivity-agent]
  - name: search-agent
    allowed_tools: [searxng-script__*]
    delegation_targets: []
  - name: productivity-agent
    allowed_tools: [markitdown-mcp__*, google_workspace__*]
    delegation_targets: [workspace-agent]
  - name: workspace-agent
    allowed_tools: [google_workspace__*]
    delegation_targets: []
""".lstrip()
        )

        registry = YamlCapabilityRegistry(path=matrix)

        assert registry.validate_delegation("aria-conductor", "search-agent") is True
        assert registry.validate_delegation("aria-conductor", "productivity-agent") is True
        assert registry.validate_delegation("productivity-agent", "workspace-agent") is True
        # workspace-agent cannot delegate
        assert registry.validate_delegation("aria-conductor", "workspace-agent") is False
        assert registry.validate_delegation("search-agent", "workspace-agent") is False

    def test_get_delegation_targets_returns_configured_list(self, tmp_path: Path) -> None:
        matrix = tmp_path / "agent_capability_matrix.yaml"
        matrix.write_text(
            """
agents:
  - name: productivity-agent
    allowed_tools: [spawn-subagent, google_workspace__*]
    delegation_targets: [workspace-agent]
  - name: workspace-agent
    allowed_tools: [google_workspace__*]
    delegation_targets: []
""".lstrip()
        )

        registry = YamlCapabilityRegistry(path=matrix)

        assert registry.get_delegation_targets("productivity-agent") == ["workspace-agent"]
        assert registry.get_delegation_targets("workspace-agent") == []

    def test_productivity_agent_has_google_workspace_tools(self, tmp_path: Path) -> None:
        matrix = tmp_path / "agent_capability_matrix.yaml"
        matrix.write_text(
            """
agents:
  - name: productivity-agent
    allowed_tools: [markitdown-mcp__*, filesystem__*, google_workspace__*]
    delegation_targets: []
""".lstrip()
        )

        registry = YamlCapabilityRegistry(path=matrix)
        tools = registry.get_allowed_tools("productivity-agent")
        assert "google_workspace__*" in tools
        assert (
            registry.is_tool_allowed(
                "productivity-agent",
                "google_workspace__send_gmail_message",
            )
            is True
        )
