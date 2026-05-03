"""Agent registry — delegation policy for cross-agent handoffs.

Provides the registry that tracks which agents can delegate to which
sub-agents, enforcing the allowed delegation graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AgentRegistry(Protocol):
    """Protocol for agent delegation registries.

    Implementations define the allowed parent→child delegation graph
    and provide a validation check.
    """

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        """Return True if *parent_agent* is allowed to delegate to *target_agent*."""
        ...

    def get_allowed_tools(self, agent: str) -> list[str]:
        """Return the list of tool names the agent is allowed to invoke."""
        ...

    def is_tool_allowed(self, agent: str, namespaced_tool: str) -> bool:
        """Return True if `namespaced_tool` is in the agent's allowed list.

        Accepts server__tool, server/tool, and server_tool (proxy) forms.
        """
        ...


class YamlCapabilityRegistry:
    """Concrete registry backed by agent_capability_matrix.yaml.

    Reads the YAML file and caches the parsed data.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path(".aria/config/agent_capability_matrix.yaml")
        self._path = Path(path)
        self._data: dict[str, list[str]] = {}
        self._delegations: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        import yaml

        if not self._path.exists():
            return
        raw = yaml.safe_load(self._path.read_text()) or {}
        agents = raw.get("agents", []) or []
        self._data = {}
        self._delegations = {}
        for entry in agents:
            name = entry.get("name", "")
            tools = entry.get("allowed_tools", []) or []
            if name:
                self._data[name] = list(tools)
                self._delegations[name] = list(entry.get("delegation_targets", []) or [])

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        """Return True if *parent_agent* is allowed to delegate to *target_agent*."""
        return target_agent in self._delegations.get(parent_agent, [])

    def get_delegation_targets(self, agent: str) -> list[str]:
        """Return the configured delegation targets for *agent*."""
        return self._delegations.get(agent, [])

    def get_allowed_tools(self, agent: str) -> list[str]:
        """Return the list of tool names the agent is allowed to invoke."""
        return self._data.get(agent, [])

    def is_tool_allowed(self, agent: str, namespaced_tool: str) -> bool:
        """Return True if `namespaced_tool` is in the agent's allowed list.

        Handles the ``server_tool`` (proxy single-underscore) form.
        """
        allowed = set(self.get_allowed_tools(agent))
        if namespaced_tool in allowed:
            return True
        # Wildcard server_* matches any tool under that server
        for entry in allowed:
            if entry.endswith("_*") and namespaced_tool.startswith(entry[:-2] + "_"):
                return True
        return False
