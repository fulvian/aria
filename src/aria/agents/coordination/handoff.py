"""Agent handoff request model — typed contract for cross-agent delegation.

Provides the Pydantic model for handoff requests, a result dataclass for
outcome tracking, a domain exception, and a validation helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError


class HandoffValidationError(ValueError):
    """Raised when a handoff request payload fails validation."""


class HandoffRequest(BaseModel):
    """Typed contract for delegating a goal from a parent agent to a child agent.

    Fields
    ------
    goal : str
        Natural-language description of what the child agent should accomplish.
    constraints : str | None
        Optional instructions limiting scope, tool access, or approach.
    required_output : str | None
        Description of the expected deliverable shape.
    timeout_seconds : int
        Hard deadline for the handoff (10-300s, default 120).
    trace_id : str
        Propagation ID linking this handoff to the broader request tree.
    parent_agent : str
        Name of the agent issuing the handoff.
    spawn_depth : int
        How deep in the delegation tree this handoff lives (1 or 2).
    envelope_ref : str | None
        Optional reference to a ContextEnvelope ID for additional context.
    """

    goal: str = Field(..., max_length=500)
    constraints: str | None = None
    required_output: str | None = None
    timeout_seconds: int = Field(default=120, ge=10, le=300)
    trace_id: str
    parent_agent: str
    spawn_depth: int = Field(default=1, ge=1, le=2)
    envelope_ref: str | None = None

    model_config = {"extra": "forbid", "frozen": False}


@dataclass
class HandoffResult:
    """Tracks the outcome of an executed agent handoff.

    Attributes
    ----------
    success : bool
        Whether the handoff completed without error.
    output : Any
        The result produced by the child agent (if any).
    failure_reason : str | None
        Human-readable explanation when success is False.
    duration_ms : int
        Wall-clock time the handoff took, in milliseconds.
    trace_id : str
        Trace identifier propagated from the handoff request.
    child_agent : str
        Name of the agent that executed the handoff.
    """

    success: bool
    output: Any = None
    failure_reason: str | None = None
    duration_ms: int = 0
    trace_id: str = ""
    child_agent: str = ""


def validate_handoff(payload: dict[str, Any]) -> HandoffRequest:
    """Validate a raw dictionary and return a HandoffRequest.

    Parameters
    ----------
    payload : dict
        Raw handoff payload (e.g. from JSON deserialisation).

    Returns
    -------
    HandoffRequest
        Validated model instance.

    Raises
    ------
    HandoffValidationError
        If the payload fails Pydantic validation or is not a dict.
    """
    if not isinstance(payload, dict):
        msg = f"Expected dict, got {type(payload).__name__}"
        raise HandoffValidationError(msg)

    try:
        return HandoffRequest.model_validate(payload)
    except PydanticValidationError as exc:
        raise HandoffValidationError(str(exc)) from exc
