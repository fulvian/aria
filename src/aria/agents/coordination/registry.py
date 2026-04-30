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
