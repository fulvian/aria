"""Coordination agent — handoff and delegation contracts for agent orchestration.

Modules:
- handoff: typed request/result models for cross-agent handoff
- envelope: context envelope for sub-agent spawns
- registry: delegation policy registry
- spawn: validated spawn-subagent wrapper
"""

from aria.agents.coordination.envelope import (
    ContextEnvelope,
    WikiPageSnapshot,
    cleanup_expired_envelopes,
    create_envelope,
    load_envelope,
    save_envelope,
)
from aria.agents.coordination.handoff import (
    HandoffRequest,
    HandoffResult,
    HandoffValidationError,
    validate_handoff,
)
from aria.agents.coordination.registry import AgentRegistry
from aria.agents.coordination.spawn import (
    SpawnRequest,
    SpawnResult,
    spawn_subagent_validated,
    validate_spawn_depth,
)

__all__ = [
    "AgentRegistry",
    "ContextEnvelope",
    "HandoffRequest",
    "HandoffResult",
    "HandoffValidationError",
    "SpawnRequest",
    "SpawnResult",
    "WikiPageSnapshot",
    "cleanup_expired_envelopes",
    "create_envelope",
    "load_envelope",
    "save_envelope",
    "spawn_subagent_validated",
    "validate_handoff",
    "validate_spawn_depth",
]
