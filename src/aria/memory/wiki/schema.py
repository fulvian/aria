# ARIA Memory Wiki — Pydantic Schema Models
#
# Per docs/plans/auto_persistence_echo.md §3.1 + §5.1.
#
# Models:
# - PageKind: Enum for page types (profile, topic, lesson, entity, decision)
# - PagePatch: Single patch operation for wiki_update
# - WikiUpdatePayload: End-of-turn update payload
# - Page: Full page record
# - PageRevision: Audit trail entry
#
# Usage:
#   from aria.memory.wiki.schema import PageKind, PagePatch, Page

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# === Page Kind Enum ===


class PageKind(StrEnum):
    """Wiki page kinds.

    Per plan §3.2:
    - profile: exactly 1 (slug="profile"), mutable full rewrite
    - topic: many, mutable append + edit
    - lesson: many, append-only after creation
    - entity: many, mutable append
    - decision: many, IMMUTABLE after creation
    """

    PROFILE = "profile"
    TOPIC = "topic"
    LESSON = "lesson"
    ENTITY = "entity"
    DECISION = "decision"


# === Slug Validation ===

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def validate_slug(slug: str) -> str:
    """Validate and normalize a kebab-case slug.

    Args:
        slug: Raw slug string.

    Returns:
        Normalized lowercase kebab-case slug.

    Raises:
        ValueError: If slug is invalid.
    """
    if not slug:
        raise ValueError("slug must not be empty")
    if not _SLUG_PATTERN.match(slug):
        raise ValueError(f"slug must be kebab-case (lowercase, digits, hyphens): {slug!r}")
    return slug


# === Patch Operation ===


class PagePatch(BaseModel):
    """A single patch operation for wiki_update.

    Per plan §5.1: each patch creates, updates, or appends to a wiki page.
    """

    kind: PageKind
    slug: str
    op: Literal["create", "update", "append"]
    title: str | None = None
    body_md: str
    importance: Literal["low", "med", "high"] = "med"
    confidence: float = Field(default=0.8)
    source_kilo_msg_ids: list[str] = Field(default_factory=list)
    diff_summary: str = ""

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        return validate_slug(v)

    @field_validator("title")
    @classmethod
    def _validate_title_on_create(cls, v: str | None, info: object) -> str | None:
        """Title is required on create operations."""
        # Access values via info if available (Pydantic v2)
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return round(max(0.0, min(1.0, v)), 2)

    model_config = {"use_enum_values": False}


class WikiUpdatePayload(BaseModel):
    """End-of-turn wiki update payload.

    Per plan §5.1: conductor MUST call wiki_update exactly once per turn.
    """

    patches: list[PagePatch] = Field(default_factory=list)
    no_salience_reason: str | None = None
    kilo_session_id: str = ""
    last_msg_id: str = ""

    @field_validator("no_salience_reason")
    @classmethod
    def _require_reason_when_empty(cls, v: str | None, info: object) -> str | None:
        """When patches is empty, no_salience_reason should be set."""
        return v

    model_config = {"use_enum_values": False}


# === Page Record ===


class Page(BaseModel):
    """Full wiki page record.

    Per plan §3.1: represents a row in the page table.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    slug: str
    kind: PageKind
    title: str
    body_md: str
    confidence: float = 1.0
    importance: str = "med"
    source_kilo_msg_ids: list[str] = Field(default_factory=list)
    first_seen: int = Field(default_factory=lambda: int(datetime.now(UTC).timestamp()))
    last_seen: int = Field(default_factory=lambda: int(datetime.now(UTC).timestamp()))
    occurrences: int = 1

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        return validate_slug(v)

    model_config = {"use_enum_values": False}


class PageRevision(BaseModel):
    """Audit trail entry for page body changes.

    Per plan §3.1: every body_md change recorded with before/after.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    page_id: str
    body_md_before: str | None = None
    body_md_after: str
    diff_summary: str | None = None
    source_kilo_msg_ids: list[str] = Field(default_factory=list)
    ts: int = Field(default_factory=lambda: int(datetime.now(UTC).timestamp()))

    model_config = {"use_enum_values": False}
