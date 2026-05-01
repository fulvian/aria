"""Agent registry — delegation policy for cross-agent handoffs.

Provides the registry that tracks which agents can delegate to which
sub-agents, enforcing the allowed delegation graph.
"""

from __future__ import annotations

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
        """Return True if `namespaced_tool` (server__tool form) is in the agent's allowed list.

        Accepts both legacy `server/tool` and new `server__tool` forms in the
        YAML matrix during the migration window.
        """
        allowed = set(self.get_allowed_tools(agent))
        if namespaced_tool in allowed:
            return True
        # fall back to legacy form: convert "server__tool" → "server/tool"
        if "__" in namespaced_tool:
            legacy = namespaced_tool.replace("__", "/", 1)
            if legacy in allowed:
                return True
        return False
