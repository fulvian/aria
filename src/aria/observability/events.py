from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from aria.utils.logging import new_trace_id

from .logger import get_aria_logger


class CutoverEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = "cutover"
    agent: str
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RollbackEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = "rollback"
    agent: str
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DriftDetected(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = "drift_detected"
    agent: str
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuarantineTriggered(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = "quarantine_triggered"
    agent: str
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


_EVENT_MARKER = "aria_event"


def emit_event(event: CutoverEvent | RollbackEvent | DriftDetected | QuarantineTriggered) -> None:
    logger = get_aria_logger(f"aria.events.{event.agent}")
    logger.info(
        event.event_type,
        marker=_EVENT_MARKER,
        trace_id=event.trace_id,
        metadata=event.metadata,
    )
