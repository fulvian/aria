# ARIA Memory Schema - Pydantic Models
#
# Per blueprint §5.5 and sprint plan W1.1.H.
#
# Models:
# - Actor (Enum): USER_INPUT, TOOL_OUTPUT, AGENT_INFERENCE, SYSTEM_EVENT
# - EpisodicEntry: Tier 0 raw verbatim memory
# - SemanticChunk: Tier 1 distilled facts/concepts
# - ProceduralSkill: Skills registry
# - MemoryStats: Telemetry
#
# Usage:
#   from aria.memory.schema import Actor, EpisodicEntry, SemanticChunk, MemoryStats
#
#   entry = EpisodicEntry(
#       session_id=uuid4(), ts=datetime.now(tz=UTC), actor=Actor.USER_INPUT,
#       role="user", content="Hello"
#   )

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# === Actor Enum ===


class Actor(StrEnum):
    """Actor types for memory entries.

    Per blueprint P5 - Actor-Aware Memory:
    - USER_INPUT: original user message, maximum trust
    - TOOL_OUTPUT: verifiable output from tools, high trust
    - AGENT_INFERENCE: LLM deduction, trust conditional - cannot auto-promote
    - SYSTEM_EVENT: system log, metadata only
    """

    USER_INPUT = "user_input"
    TOOL_OUTPUT = "tool_output"
    AGENT_INFERENCE = "agent_inference"
    SYSTEM_EVENT = "system_event"


# === Content Hash ===


def content_hash(text: str) -> str:
    """Generate SHA256 content hash.

    Returns: "sha256:<hexdigest>"
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# === Tier 0: Episodic Entry ===


class EpisodicEntry(BaseModel):
    """Tier 0 episodic memory entry (verbatim preservation).

    Per blueprint P6 - Verbatim Preservation:
    - NO UPDATE on content columns allowed
    - Only INSERT, tombstone via episodic_tombstones table
    - content is always verbatim, never synthesized
    """

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    ts: datetime  # Must be timezone-aware (Pydantic v2)
    actor: Actor
    role: Literal["user", "assistant", "system", "tool"]
    content: str  # verbatim, never synthesized
    content_hash: str = Field(default_factory=lambda: "")  # sha256:<hex>
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)

    def __init__(self, **data: object) -> None:  # noqa: ANN003
        # Auto-generate content_hash if not provided
        if ("content_hash" not in data or not data["content_hash"]) and "content" in data:
            data["content_hash"] = content_hash(data["content"])
        super().__init__(**data)

    model_config = {
        "use_enum_values": False,  # Keep enum instances, not strings
    }


# === Tier 1: Semantic Chunk ===


class SemanticChunk(BaseModel):
    """Tier 1 semantic memory chunk (distilled from T0).

    Per blueprint §5.4 - CLM:
    - Derived from episodic entries via distillation
    - Actor is aggregated (downgrade if mix of types)
    - Confidence reflects trust score
    """

    id: UUID = Field(default_factory=uuid4)
    source_episodic_ids: list[UUID]  # Provenance: T0 entries
    actor: Actor  # Aggregated from source entries
    kind: Literal["fact", "preference", "decision", "action_item", "concept"]
    text: str  # Synthesized distillation
    keywords: list[str] = Field(default_factory=list)
    confidence: float = 1.0  # 0.0-1.0
    first_seen: datetime
    last_seen: datetime
    occurrences: int = 1
    embedding_id: UUID | None = None  # T2 embedding (lazy)

    model_config = {
        "use_enum_values": False,
    }


# === Procedural Memory: Skills Registry ===


class ProceduralSkill(BaseModel):
    """Procedural memory entry (skill/workflow definition)."""

    id: str  # slug e.g. "deep-research"
    path: str  # path to SKILL.md
    name: str
    description: str  # ~100 tokens for advertise
    trigger_keywords: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    version: str = "1.0.0"


# === Memory Stats (Telemetry) ===


class MemoryStats(BaseModel):
    """Memory subsystem statistics."""

    t0_count: int = 0  # Number of episodic entries
    t1_count: int = 0  # Number of semantic chunks
    sessions: int = 0  # Number of unique sessions
    last_session_ts: datetime | None = None
    avg_entry_size: float = 0.0  # Average content size in bytes
    storage_bytes: int = 0  # Total DB file size


# === Association (Fase 2 - not implemented) ===


class Association(BaseModel):
    """Associative memory entry (future Tier 3).

    Not implemented in Sprint 1.1 - stub for future.
    """

    id: UUID = Field(default_factory=uuid4)
    subject_id: UUID
    relation: str  # "works_at", "prefers", "depends_on"
    object_id: UUID
    confidence: float = 1.0
    source_episodic_ids: list[UUID] = Field(default_factory=list)


# === Convenience Functions ===


def make_episodic_entry(
    session_id: UUID,
    content: str,
    actor: Actor,
    role: Literal["user", "assistant", "system", "tool"],
    ts: datetime | None = None,
    tags: list[str] | None = None,
    meta: dict[str, object] | None = None,
) -> EpisodicEntry:
    """Create an EpisodicEntry with auto-generated fields.

    Args:
        session_id: Session identifier
        content: Verbatim content
        actor: Actor enum value
        role: Role string
        ts: Timestamp (default: now UTC)
        tags: Optional tags list
        meta: Optional metadata dict

    Returns:
        Fully populated EpisodicEntry
    """
    return EpisodicEntry(
        id=uuid4(),
        session_id=session_id,
        ts=ts or datetime.now(UTC),
        actor=actor,
        role=role,
        content=content,
        content_hash=content_hash(content),
        tags=tags or [],
        meta=meta or {},
    )


def make_semantic_chunk(
    source_episodic_ids: list[UUID],
    actor: Actor,
    kind: Literal["fact", "preference", "decision", "action_item", "concept"],
    text: str,
    keywords: list[str] | None = None,
    confidence: float = 1.0,
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
) -> SemanticChunk:
    """Create a SemanticChunk.

    Args:
        source_episodic_ids: Source T0 entry IDs
        actor: Aggregated actor
        kind: Chunk type
        text: Distilled text
        keywords: Optional keywords
        confidence: Trust score
        first_seen: First occurrence time
        last_seen: Most recent occurrence time

    Returns:
        SemanticChunk instance
    """
    now = datetime.now(UTC)
    return SemanticChunk(
        source_episodic_ids=source_episodic_ids,
        actor=actor,
        kind=kind,
        text=text,
        keywords=keywords or [],
        confidence=confidence,
        first_seen=first_seen or now,
        last_seen=last_seen or now,
    )
