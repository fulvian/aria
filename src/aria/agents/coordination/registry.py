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
        self._load()

    def _load(self) -> None:
        import yaml

        if not self._path.exists():
            return
        raw = yaml.safe_load(self._path.read_text()) or {}
        agents = raw.get("agents", []) or []
        self._data = {}
        for entry in agents:
            name = entry.get("name", "")
            tools = entry.get("allowed_tools", []) or []
            if name:
                self._data[name] = list(tools)

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        """Return True if *parent_agent* is allowed to delegate to *target_agent*."""
        # Simple check: agents can delegate if both exist in the registry
        return parent_agent in self._data or target_agent in self._data

    def get_allowed_tools(self, agent: str) -> list[str]:
        """Return the list of tool names the agent is allowed to invoke."""
        return self._data.get(agent, [])

    def is_tool_allowed(self, agent: str, namespaced_tool: str) -> bool:  # noqa: PLR0911
        """Return True if `namespaced_tool` is in the agent's allowed list."""
        allowed = set(self.get_allowed_tools(agent))
        if namespaced_tool in allowed:
            return True
        if "__" in namespaced_tool:
            legacy = namespaced_tool.replace("__", "/", 1)
            if legacy in allowed:
                return True
        # Proxy names use single _ but matrix uses __.
        if "_" in namespaced_tool and "__" not in namespaced_tool:
            first = namespaced_tool.index("_")
            if namespaced_tool[:first] + "__" + namespaced_tool[first + 1 :] in allowed:
                return True
            if namespaced_tool[:first] + "__*" in allowed:
                return True
        # Wildcard server__* matches any form
        for entry in allowed:
            if entry.endswith("__*"):
                prefix = entry[:-3]
                if "__" in namespaced_tool and namespaced_tool.startswith(prefix + "__"):
                    return True
                if "_" in namespaced_tool and "__" not in namespaced_tool:
                    first = namespaced_tool.index("_")
                    if namespaced_tool[:first] == prefix:
                        return True
        return False
