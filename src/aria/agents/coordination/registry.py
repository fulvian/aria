"""Agent registry backed by the capability-matrix YAML.

Provides a small runtime registry for delegation checks and related validation
helpers. The canonical source is ``.aria/config/agent_capability_matrix.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from aria.config import get_config


class RegistryValidationError(ValueError):
    """Raised when the capability matrix file is malformed."""


@dataclass(frozen=True)
class AgentSpec:
    """Normalized agent definition loaded from the capability matrix."""

    name: str
    type: str
    allowed_tools: list[str] = field(default_factory=list)
    mcp_dependencies: list[str] = field(default_factory=list)
    delegation_targets: list[str] = field(default_factory=list)
    hitl_triggers: list[str] = field(default_factory=list)
    intent_categories: list[str] = field(default_factory=list)
    max_tools: int = 20
    max_spawn_depth: int = 0


class AgentRegistry(Protocol):
    """Protocol for agent delegation registries."""

    def get_agent(self, name: str) -> AgentSpec | None:
        """Return the normalized spec for an agent, if known."""

    def get_allowed_tools(self, agent_name: str) -> list[str]:
        """Return the allowed tools declared for an agent."""

    def get_delegation_targets(self, agent_name: str) -> list[str]:
        """Return the configured child-agent targets for an agent."""

    def validate_tool_count(self, agent_name: str) -> bool:
        """Return True when the declared tool count is within limits."""

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        """Return True if *parent_agent* is allowed to delegate to *target_agent*."""
        ...


def get_default_registry_path() -> Path:
    """Return the default capability-matrix path under the ARIA workspace."""

    return get_config().home / ".aria" / "config" / "agent_capability_matrix.yaml"


def _as_list(raw: object, *, field_name: str, agent_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        msg = f"Agent '{agent_name}' field '{field_name}' must be a list"
        raise RegistryValidationError(msg)
    return [str(item) for item in raw if str(item).strip()]


def _as_int(raw: object, *, field_name: str, agent_name: str, default: int) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool):
        msg = f"Agent '{agent_name}' field '{field_name}' must be an integer"
        raise RegistryValidationError(msg)
    if not isinstance(raw, (int, str)):
        msg = f"Agent '{agent_name}' field '{field_name}' must be an integer"
        raise RegistryValidationError(msg)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        msg = f"Agent '{agent_name}' field '{field_name}' must be an integer"
        raise RegistryValidationError(msg) from exc


def _parse_agent_spec(raw: object, *, index: int) -> AgentSpec:
    if not isinstance(raw, dict):
        msg = f"Agent entry at index {index} must be a mapping"
        raise RegistryValidationError(msg)

    name = str(raw.get("name", "")).strip()
    if not name:
        msg = f"Agent entry at index {index} is missing a non-empty 'name'"
        raise RegistryValidationError(msg)

    return AgentSpec(
        name=name,
        type=str(raw.get("type", "worker") or "worker"),
        allowed_tools=_as_list(
            raw.get("allowed_tools"),
            field_name="allowed_tools",
            agent_name=name,
        ),
        mcp_dependencies=_as_list(
            raw.get("mcp_dependencies"),
            field_name="mcp_dependencies",
            agent_name=name,
        ),
        delegation_targets=_as_list(
            raw.get("delegation_targets"),
            field_name="delegation_targets",
            agent_name=name,
        ),
        hitl_triggers=_as_list(
            raw.get("hitl_triggers"),
            field_name="hitl_triggers",
            agent_name=name,
        ),
        intent_categories=_as_list(
            raw.get("intent_categories"),
            field_name="intent_categories",
            agent_name=name,
        ),
        max_tools=_as_int(
            raw.get("max_tools"),
            field_name="max_tools",
            agent_name=name,
            default=20,
        ),
        max_spawn_depth=_as_int(
            raw.get("max_spawn_depth"),
            field_name="max_spawn_depth",
            agent_name=name,
            default=0,
        ),
    )


class YamlAgentRegistry:
    """Concrete registry loaded from ``agent_capability_matrix.yaml``."""

    def __init__(self, agents: dict[str, AgentSpec], *, source_path: Path | None = None) -> None:
        self._agents = dict(agents)
        self.source_path = source_path

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> YamlAgentRegistry:
        """Load and validate the registry from disk."""

        source_path = Path(path) if path is not None else get_default_registry_path()
        if not source_path.exists():
            msg = f"Capability matrix not found: {source_path}"
            raise RegistryValidationError(msg)

        raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg = f"Capability matrix must be a mapping: {source_path}"
            raise RegistryValidationError(msg)

        entries = raw.get("agents")
        if not isinstance(entries, list):
            msg = f"Capability matrix field 'agents' must be a list: {source_path}"
            raise RegistryValidationError(msg)

        agents: dict[str, AgentSpec] = {}
        for index, entry in enumerate(entries):
            spec = _parse_agent_spec(entry, index=index)
            if spec.name in agents:
                msg = f"Duplicate agent name '{spec.name}' in {source_path}"
                raise RegistryValidationError(msg)
            agents[spec.name] = spec

        registry = cls(agents, source_path=source_path)
        registry.ensure_valid()
        return registry

    def get_agent(self, name: str) -> AgentSpec | None:
        return self._agents.get(name)

    def get_allowed_tools(self, agent_name: str) -> list[str]:
        agent = self.get_agent(agent_name)
        return list(agent.allowed_tools) if agent is not None else []

    def get_delegation_targets(self, agent_name: str) -> list[str]:
        agent = self.get_agent(agent_name)
        return list(agent.delegation_targets) if agent is not None else []

    def validate_tool_count(self, agent_name: str) -> bool:
        agent = self.get_agent(agent_name)
        if agent is None:
            return False
        return len(agent.allowed_tools) <= agent.max_tools

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        parent = self.get_agent(parent_agent)
        if parent is None:
            return False
        return target_agent in parent.delegation_targets

    def unknown_delegation_targets(self) -> dict[str, list[str]]:
        """Return unknown delegation targets keyed by parent agent."""

        known_agents = set(self._agents)
        unknown: dict[str, list[str]] = {}
        for name, spec in self._agents.items():
            missing = [target for target in spec.delegation_targets if target not in known_agents]
            if missing:
                unknown[name] = missing
        return unknown

    def validate_matrix(self) -> list[str]:
        """Return human-readable matrix validation errors."""

        errors: list[str] = []
        if not self._agents:
            errors.append("Capability matrix does not define any agents")

        for name, spec in self._agents.items():
            if spec.max_tools < 0:
                errors.append(f"Agent '{name}' has negative max_tools={spec.max_tools}")
            if spec.max_spawn_depth < 0:
                errors.append(
                    f"Agent '{name}' has negative max_spawn_depth={spec.max_spawn_depth}"
                )
            if len(spec.allowed_tools) > spec.max_tools:
                errors.append(
                    "Agent "
                    f"'{name}' declares {len(spec.allowed_tools)} tools "
                    f"but max_tools is {spec.max_tools}"
                )

        for name, targets in self.unknown_delegation_targets().items():
            for target in targets:
                errors.append(f"Agent '{name}' delegates to unknown target '{target}'")

        return errors

    def ensure_valid(self) -> None:
        """Raise when the loaded matrix violates basic invariants."""

        errors = self.validate_matrix()
        if errors:
            raise RegistryValidationError("; ".join(errors))


def load_agent_registry(path: str | Path | None = None) -> YamlAgentRegistry:
    """Compatibility helper returning the default YAML-backed registry."""

    return YamlAgentRegistry.from_file(path)


__all__ = [
    "AgentRegistry",
    "AgentSpec",
    "RegistryValidationError",
    "YamlAgentRegistry",
    "get_default_registry_path",
    "load_agent_registry",
]
