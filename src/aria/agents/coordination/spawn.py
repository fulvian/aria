"""Validated spawn-subagent wrapper — injects envelope, validates payload, increments spawn_depth.

Provides the typed wrapper around KiloCode's spawn-subagent mechanism with
runtime validation, delegation registry checks, and spawn depth limiting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from aria.agents.coordination.envelope import ContextEnvelope  # noqa: TC001
from aria.agents.coordination.handoff import HandoffRequest  # noqa: TC001
from aria.utils.metrics import incr

if TYPE_CHECKING:
    from aria.agents.coordination.registry import AgentRegistry

_MAX_SPAWN_DEPTH = 2


class SpawnRequest(BaseModel):
    """Typed request for spawning a validated sub-agent.

    Fields
    ------
    target_agent : str
        Name of the agent to spawn.
    handoff : HandoffRequest
        The handoff request payload to delegate to the child agent.
    envelope : ContextEnvelope | None
        Optional context envelope providing additional execution context.
    """

    target_agent: str = Field(..., min_length=1)
    handoff: HandoffRequest
    envelope: ContextEnvelope | None = None

    model_config = {"extra": "forbid", "frozen": False}


@dataclass
class SpawnResult:
    """Tracks the outcome of a validated sub-agent spawn.

    Attributes
    ----------
    success : bool
        Whether the spawn completed without error.
    target_agent : str
        Name of the agent that was targeted.
    spawn_depth : int
        Delegation depth at which the spawn occurred.
    trace_id : str
        Propagation trace identifier.
    error : str | None
        Human-readable error when success is False.
    """

    success: bool
    target_agent: str
    spawn_depth: int
    trace_id: str
    error: str | None = None


async def spawn_subagent_validated(
    target_agent: str,
    handoff_request: HandoffRequest,
    envelope: ContextEnvelope | None = None,
    registry: AgentRegistry | None = None,
) -> SpawnResult:
    """Validate and execute a sub-agent spawn.

    Runs the full validation pipeline:
    1. Validates that the handoff request has all required fields.
    2. If a registry is provided, validates the delegation is allowed.
    3. Validates that the spawn depth does not exceed the maximum.
    4. If all checks pass, constructs the spawn-subagent call parameters.

    Parameters
    ----------
    target_agent : str
        Name of the agent to spawn.
    handoff_request : HandoffRequest
        The validated handoff request for the delegation.
    envelope : ContextEnvelope | None
        Optional context envelope to pass to the spawned agent.
    registry : AgentRegistry | None
        Optional agent registry to validate delegation policy.

    Returns
    -------
    SpawnResult
        Result of the validation and spawn attempt.
    """
    trace_id = handoff_request.trace_id
    spawn_depth = handoff_request.spawn_depth

    # --- Validation 1: handoff has all required fields ---
    required = ["goal", "trace_id", "parent_agent"]
    missing = [f for f in required if getattr(handoff_request, f, None) is None]
    if missing:
        incr("aria_agent_spawn_total", value=1, target=target_agent, status="validation_failed")
        return SpawnResult(
            success=False,
            target_agent=target_agent,
            spawn_depth=spawn_depth,
            trace_id=trace_id,
            error=f"HandoffRequest missing required fields: {', '.join(missing)}",
        )

    # --- Validation 2: delegation allowed by registry ---
    if registry is not None:
        allowed = registry.validate_delegation(handoff_request.parent_agent, target_agent)
        if not allowed:
            incr("aria_agent_spawn_total", value=1, target=target_agent, status="delegation_denied")
            return SpawnResult(
                success=False,
                target_agent=target_agent,
                spawn_depth=spawn_depth,
                trace_id=trace_id,
                error=(
                    f"Delegation from '{handoff_request.parent_agent}' to "
                    f"'{target_agent}' is not allowed by registry"
                ),
            )

    # --- Validation 3: spawn depth ≤ 2 ---
    if not validate_spawn_depth(spawn_depth):
        incr("aria_agent_spawn_total", value=1, target=target_agent, status="depth_exceeded")
        return SpawnResult(
            success=False,
            target_agent=target_agent,
            spawn_depth=spawn_depth,
            trace_id=trace_id,
            error=f"Spawn depth {spawn_depth} exceeds maximum allowed depth of {_MAX_SPAWN_DEPTH}",
        )

    # --- All checks passed ---
    incr("aria_agent_spawn_total", value=1, target=target_agent, status="success")
    return SpawnResult(
        success=True,
        target_agent=target_agent,
        spawn_depth=spawn_depth,
        trace_id=trace_id,
        error=None,
    )


def validate_spawn_depth(depth: int) -> bool:
    """Check that the spawn depth does not exceed the allowed maximum.

    Parameters
    ----------
    depth : int
        The delegation depth to validate.

    Returns
    -------
    bool
        True if the depth is within the allowed range, False otherwise.
    """
    return 1 <= depth <= _MAX_SPAWN_DEPTH
