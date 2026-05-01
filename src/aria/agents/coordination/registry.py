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

        Accepts three forms:
          - `server__tool` (convention)
          - `server/tool` (legacy pre-F3)
          - Actual proxy names like `server_toolname` (single underscore)
        """
        allowed = set(self.get_allowed_tools(agent))
        if namespaced_tool in allowed:
            return True
        # Legacy form: server/tool
        if "__" in namespaced_tool:
            legacy = namespaced_tool.replace("__", "/", 1)
            if legacy in allowed:
                return True
        # Proxy names use single _ but matrix uses __.
        # Convert first _ to __ for matching.
        if "_" in namespaced_tool and "__" not in namespaced_tool:
            first = namespaced_tool.index("_")
            double_form = namespaced_tool[:first] + "__" + namespaced_tool[first + 1:]
            if double_form in allowed:
                return True
            # Wildcard: server__* matches server_toolname
            wildcard_form = namespaced_tool[:first] + "__*"
            if wildcard_form in allowed:
                return True
        # Wildcard server__* matches any server__form
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

    def is_tool_allowed(self, agent: str, namespaced_tool: str) -> bool:
        """Return True if `namespaced_tool` is in the agent's allowed list."""
        allowed = set(self.get_allowed_tools(agent))
        if namespaced_tool in allowed:
            return True
        # Legacy form: server/tool (pre-F3) vs server__tool (F3 naming convention)
        if "__" in namespaced_tool:
            legacy = namespaced_tool.replace("__", "/", 1)
            if legacy in allowed:
                return True
        # Real tool names from proxy use single underscore (server_tool_name),
        # but the matrix uses double underscore (server__tool_name).
        # Try converting first single underscore to double underscore.
        if "_" in namespaced_tool and "__" not in namespaced_tool:
            first = namespaced_tool.index("_")
            double_form = namespaced_tool[:first] + "__" + namespaced_tool[first + 1:]
            if double_form in allowed:
                return True
            # Also try with wildcard: server__* matches server_tool_name
            wildcard_form = namespaced_tool[:first] + "__*"
            if wildcard_form in allowed:
                return True
        # Direct wildcard: server__* matches server__anything
        for entry in allowed:
            if entry.endswith("__*"):
                prefix = entry[:-3] + "__"
                if namespaced_tool.startswith(prefix):
                    return True
                # Also try converting tool name: server_xxx → matches server__*
                if "_" in namespaced_tool and "__" not in namespaced_tool:
                    first = namespaced_tool.index("_")
                    single_prefix = namespaced_tool[:first] + "__"
                    if namespaced_tool[:first] == entry[:-3] and namespaced_tool.startswith(
                        namespaced_tool[:first] + "_"
                    ):
                        return True
        return False
