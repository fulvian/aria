"""Validated spawn-subagent wrapper — injects envelope, validates payload, increments spawn_depth.

Provides the typed wrapper around KiloCode's spawn-subagent mechanism with
runtime validation, delegation registry checks, and spawn depth limiting.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from aria.agents.coordination.envelope import ContextEnvelope  # noqa: TC001
from aria.agents.coordination.handoff import HandoffRequest  # noqa: TC001
from aria.observability.metrics import (
    observe_agent_spawn,
    observe_agent_spawn_duration,
    observe_tool_call,
)

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
    """Tracks the outcome of a validated sub-agent spawn request.

    Attributes
    ----------
    success : bool
        Whether validation and payload preparation completed without error.
    target_agent : str
        Name of the agent that was targeted.
    spawn_depth : int
        Delegation depth at which the spawn occurred.
    trace_id : str
        Propagation trace identifier.
    error : str | None
        Human-readable error when success is False.
    payload : dict[str, object] | None
        Prepared spawn payload. Present only when validation succeeds.
    """

    success: bool
    target_agent: str
    spawn_depth: int
    trace_id: str
    error: str | None = None
    payload: dict[str, object] | None = None


def _failure(
    *,
    parent_agent: str,
    target_agent: str,
    spawn_depth: int,
    trace_id: str,
    error: str,
    duration_s: float,
) -> SpawnResult:
    observe_tool_call(parent_agent or "unknown", "spawn-subagent", outcome="validation_failed")
    observe_agent_spawn_duration(target_agent or "unknown", duration_s)
    return SpawnResult(
        success=False,
        target_agent=target_agent,
        spawn_depth=spawn_depth,
        trace_id=trace_id,
        error=error,
    )


async def spawn_subagent_validated(
    target_agent: str,
    handoff_request: HandoffRequest,
    envelope: ContextEnvelope | None = None,
    registry: AgentRegistry | None = None,
) -> SpawnResult:
    """Validate and prepare a sub-agent spawn request.

    Runs the full validation pipeline:
    1. Validates that the handoff request has all required fields.
    2. If a registry is provided, validates the delegation is allowed.
    3. Validates that the spawn depth does not exceed the maximum.
    4. If all checks pass, constructs the spawn-subagent payload.

    This function does not invoke the actual Kilo spawn tool. It only prepares
    the validated payload and emits telemetry for the caller.

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
    started = perf_counter()
    trace_id = handoff_request.trace_id
    spawn_depth = handoff_request.spawn_depth
    parent_agent = handoff_request.parent_agent
    normalized_target = target_agent.strip()

    # --- Validation 1: handoff has all required fields ---
    missing = [
        field_name
        for field_name in ("goal", "trace_id", "parent_agent")
        if not isinstance(getattr(handoff_request, field_name, None), str)
        or not str(getattr(handoff_request, field_name, "")).strip()
    ]
    if missing:
        return _failure(
            parent_agent=parent_agent,
            target_agent=normalized_target,
            spawn_depth=spawn_depth,
            trace_id=trace_id,
            error=f"HandoffRequest missing required fields: {', '.join(missing)}",
            duration_s=perf_counter() - started,
        )

    if not normalized_target:
        return _failure(
            parent_agent=parent_agent,
            target_agent=target_agent,
            spawn_depth=spawn_depth,
            trace_id=trace_id,
            error="Target agent must be a non-empty string",
            duration_s=perf_counter() - started,
        )

    if envelope is not None and envelope.trace_id != trace_id:
        return _failure(
            parent_agent=parent_agent,
            target_agent=normalized_target,
            spawn_depth=spawn_depth,
            trace_id=trace_id,
            error="ContextEnvelope trace_id does not match HandoffRequest trace_id",
            duration_s=perf_counter() - started,
        )

    # --- Validation 2: delegation allowed by registry ---
    if registry is not None:
        allowed = registry.validate_delegation(parent_agent, normalized_target)
        if not allowed:
            return _failure(
                parent_agent=parent_agent,
                target_agent=normalized_target,
                spawn_depth=spawn_depth,
                trace_id=trace_id,
                error=(
                    f"Delegation from '{parent_agent}' to '{normalized_target}' "
                    "is not allowed by registry"
                ),
                duration_s=perf_counter() - started,
            )

    # --- Validation 3: spawn depth ≤ 2 ---
    if not validate_spawn_depth(spawn_depth):
        return _failure(
            parent_agent=parent_agent,
            target_agent=normalized_target,
            spawn_depth=spawn_depth,
            trace_id=trace_id,
            error=f"Spawn depth {spawn_depth} exceeds maximum allowed depth of {_MAX_SPAWN_DEPTH}",
            duration_s=perf_counter() - started,
        )

    # --- All checks passed ---
    payload = handoff_request.model_dump(mode="json")
    if envelope is not None:
        payload["envelope_ref"] = envelope.envelope_id

    observe_tool_call(parent_agent, "spawn-subagent", outcome="validated")
    observe_agent_spawn(normalized_target, parent_agent)
    observe_agent_spawn_duration(normalized_target, perf_counter() - started)
    return SpawnResult(
        success=True,
        target_agent=normalized_target,
        spawn_depth=spawn_depth,
        trace_id=trace_id,
        error=None,
        payload=payload,
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
