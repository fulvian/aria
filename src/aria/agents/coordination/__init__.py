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
from aria.agents.coordination.registry import (
    AgentRegistry,
    AgentSpec,
    RegistryValidationError,
    YamlAgentRegistry,
    get_default_registry_path,
    load_agent_registry,
)
from aria.agents.coordination.spawn import (
    SpawnRequest,
    SpawnResult,
    spawn_subagent_validated,
    validate_spawn_depth,
)

__all__ = [
    "AgentRegistry",
    "AgentSpec",
    "ContextEnvelope",
    "HandoffRequest",
    "HandoffResult",
    "HandoffValidationError",
    "RegistryValidationError",
    "SpawnRequest",
    "SpawnResult",
    "WikiPageSnapshot",
    "cleanup_expired_envelopes",
    "create_envelope",
    "load_envelope",
    "load_agent_registry",
    "save_envelope",
    "spawn_subagent_validated",
    "validate_handoff",
    "validate_spawn_depth",
    "YamlAgentRegistry",
    "get_default_registry_path",
]
