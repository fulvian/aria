"""Integration tests: capability matrix validation — tool count overflow, delegation violations."""

from __future__ import annotations

from dataclasses import dataclass, field

from aria.agents.coordination.handoff import HandoffRequest
from aria.agents.coordination.spawn import spawn_subagent_validated

# --- Helpers: minimal capability matrix representation ---


@dataclass
class AgentCapability:
    """Declared tool set for a single agent."""

    agent_name: str
    tools: list[str] = field(default_factory=list)


@dataclass
class CapabilityMatrix:
    """Registry of agent capabilities with validation rules."""

    agents: dict[str, AgentCapability] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> CapabilityMatrix:
        agents = {
            name: AgentCapability(agent_name=name, tools=tools) for name, tools in data.items()
        }
        return cls(agents=agents)

    def detect_tool_overflow(self, max_tools: int = 20) -> list[str]:
        """Return list of agent names whose tool count exceeds *max_tools*."""
        return [name for name, cap in self.agents.items() if len(cap.tools) > max_tools]


# --- Concrete registry for delegation validation ---


class StaticDelegationRegistry:
    """A registry that only allows delegations to known agents."""

    def __init__(self, known_agents: set[str]) -> None:
        self._known = known_agents

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        return target_agent in self._known


# --- Tests ---


class TestCapabilityMatrixToolOverflow:
    """Validator must flag agents with more than 20 tools."""

    @staticmethod
    def _sample_matrix() -> CapabilityMatrix:
        tools_5 = [f"tool_{i}" for i in range(5)]
        tools_25 = [f"tool_{i}" for i in range(25)]
        return CapabilityMatrix.from_dict(
            {
                "aria-conductor": tools_5,
                "search-agent": tools_25,
                "productivity-agent": tools_5,
            }
        )

    def test_validator_detect_tool_over_20(self) -> None:
        matrix = self._sample_matrix()
        overflow = matrix.detect_tool_overflow(max_tools=20)
        assert "search-agent" in overflow
        assert "aria-conductor" not in overflow

    def test_agent_under_limit_not_flagged(self) -> None:
        matrix = CapabilityMatrix.from_dict(
            {
                "light-agent": [f"t_{i}" for i in range(3)],
            }
        )
        assert matrix.detect_tool_overflow() == []

    def test_empty_matrix_no_overflow(self) -> None:
        assert CapabilityMatrix.from_dict({}).detect_tool_overflow() == []


class TestCapabilityMatrixDelegationViolation:
    """Validator must detect delegations to non-existent agents."""

    @staticmethod
    def _make_handoff(parent: str = "aria-conductor") -> HandoffRequest:
        return HandoffRequest(
            goal="Test delegation validation",
            trace_id="trace-delegation",
            parent_agent=parent,
            spawn_depth=1,
        )

    async def test_delegation_to_nonexistent_agent_rejected(self) -> None:
        registry = StaticDelegationRegistry(known_agents={"search-agent", "productivity-agent"})
        result = await spawn_subagent_validated(
            target_agent="nonexistent-agent",
            handoff_request=self._make_handoff(),
            registry=registry,
        )
        assert result.success is False
        assert result.error is not None
        assert "not allowed by registry" in result.error

    async def test_delegation_to_known_agent_accepted(self) -> None:
        registry = StaticDelegationRegistry(known_agents={"search-agent", "productivity-agent"})
        result = await spawn_subagent_validated(
            target_agent="search-agent",
            handoff_request=self._make_handoff(),
            registry=registry,
        )
        assert result.success is True
        assert result.error is None

    async def test_no_registry_skips_delegation_check(self) -> None:
        result = await spawn_subagent_validated(
            target_agent="whatever-agent",
            handoff_request=self._make_handoff(),
            registry=None,
        )
        assert result.success is True
