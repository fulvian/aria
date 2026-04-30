from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from aria.agents.coordination import AgentRegistry, load_agent_registry
from aria.agents.coordination.registry import RegistryValidationError, YamlAgentRegistry

if TYPE_CHECKING:
    from pathlib import Path


def _write_matrix(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestAgentRegistryProtocol:
    def test_is_protocol(self) -> None:
        assert issubclass(AgentRegistry, Protocol)


class TestYamlAgentRegistry:
    def test_loads_real_matrix_shape(self, tmp_path: Path) -> None:
        matrix = _write_matrix(
            tmp_path / "agent_capability_matrix.yaml",
            """
agents:
  - name: aria-conductor
    type: primary
    allowed_tools: [spawn-subagent, sequential-thinking/*]
    mcp_dependencies: [aria-memory]
    delegation_targets: [search-agent, productivity-agent]
    max_tools: 5
    max_spawn_depth: 2
  - name: search-agent
    type: worker
    allowed_tools: [fetch/fetch]
    mcp_dependencies: [fetch]
    delegation_targets: []
    max_tools: 5
    max_spawn_depth: 0
  - name: productivity-agent
    type: worker
    allowed_tools: [filesystem/read]
    mcp_dependencies: [filesystem]
    delegation_targets: []
    max_tools: 5
    max_spawn_depth: 1
""".strip(),
        )

        registry = load_agent_registry(matrix)

        assert isinstance(registry, YamlAgentRegistry)
        assert registry.get_agent("aria-conductor") is not None
        assert registry.get_allowed_tools("aria-conductor") == [
            "spawn-subagent",
            "sequential-thinking/*",
        ]
        assert registry.get_delegation_targets("aria-conductor") == [
            "search-agent",
            "productivity-agent",
        ]
        assert registry.validate_delegation("aria-conductor", "search-agent") is True
        assert registry.validate_delegation("search-agent", "aria-conductor") is False
        assert registry.validate_tool_count("aria-conductor") is True

    def test_unknown_agent_returns_safe_defaults(self, tmp_path: Path) -> None:
        matrix = _write_matrix(
            tmp_path / "agent_capability_matrix.yaml",
            (
                "agents: [{name: aria-conductor, type: primary, "
                "allowed_tools: [], delegation_targets: []}]"
            ),
        )
        registry = load_agent_registry(matrix)

        assert registry.get_agent("missing") is None
        assert registry.get_allowed_tools("missing") == []
        assert registry.get_delegation_targets("missing") == []
        assert registry.validate_tool_count("missing") is False
        assert registry.validate_delegation("missing", "aria-conductor") is False

    def test_rejects_unknown_delegation_targets(self, tmp_path: Path) -> None:
        matrix = _write_matrix(
            tmp_path / "agent_capability_matrix.yaml",
            """
agents:
  - name: aria-conductor
    type: primary
    allowed_tools: []
    delegation_targets: [ghost-agent]
""".strip(),
        )

        with pytest.raises(RegistryValidationError, match="ghost-agent"):
            load_agent_registry(matrix)

    def test_rejects_tool_overflow(self, tmp_path: Path) -> None:
        tools = ", ".join(f"tool_{i}" for i in range(3))
        matrix = _write_matrix(
            tmp_path / "agent_capability_matrix.yaml",
            f"""
agents:
  - name: overloaded-agent
    type: worker
    allowed_tools: [{tools}]
    delegation_targets: []
    max_tools: 2
""".strip(),
        )

        with pytest.raises(RegistryValidationError, match="declares 3 tools"):
            load_agent_registry(matrix)

    def test_rejects_duplicate_agent_names(self, tmp_path: Path) -> None:
        matrix = _write_matrix(
            tmp_path / "agent_capability_matrix.yaml",
            """
agents:
  - name: dup-agent
    type: worker
    allowed_tools: []
    delegation_targets: []
  - name: dup-agent
    type: worker
    allowed_tools: []
    delegation_targets: []
""".strip(),
        )

        with pytest.raises(RegistryValidationError, match="Duplicate agent name"):
            load_agent_registry(matrix)

    def test_rejects_non_list_agents_field(self, tmp_path: Path) -> None:
        matrix = _write_matrix(tmp_path / "agent_capability_matrix.yaml", "agents: {}")

        with pytest.raises(RegistryValidationError, match="field 'agents' must be a list"):
            load_agent_registry(matrix)
