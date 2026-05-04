from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

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


ProxyEventKind = Literal[
    "proxy.start",
    "proxy.shutdown",
    "proxy.tool_denied",
    "proxy.caller_anomaly",
    "proxy.backend_quarantine",
    "proxy.cutover",
    "proxy.emergency_rollback",
]


class ProxyEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: ProxyEventKind
    agent: str = ""
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


TravellerEventKind = Literal[
    "traveller.dispatch_received",
    "traveller.skill_invoked",
    "traveller.proxy_call",
    "traveller.hitl_requested",
    "traveller.hitl_resolved",
    "traveller.export_delegated",
    "traveller.amadeus_quota_warning",
]

_TravellerEvent = tuple[TravellerEventKind, str, dict[str, object]]


class TravellerEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: TravellerEventKind
    agent: str = "traveller-agent"
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Proxy Tier Events (v2 — tier-based architecture)
ProxyTierEventKind = Literal[
    "proxy.backend_warm_pool_demote",
    "proxy.backend_circuit_open",
    "proxy.backend_circuit_closed",
    "proxy.backend_circuit_half_open",
    "proxy.backend_lazy_spawn",
    "proxy.backend_idle_shutdown",
    "proxy.backend_backpressure",
    "proxy.backend_quarantine",
    "proxy.metadata_cache_hit",
    "proxy.metadata_cache_miss",
    "proxy.list_tools_latency_ms",
    "proxy.call_tool_queued",
    "proxy.tier_recovery_attempt",
    "proxy.embedding_degraded",
]


class ProxyTierEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: ProxyTierEventKind
    agent: str = "aria-mcp-proxy"
    trace_id: str = Field(default_factory=new_trace_id)
    metadata: dict[str, Any] = Field(default_factory=dict)


_EVENT_MARKER = "aria_event"


def emit_event(  # noqa: E501
    event: CutoverEvent
    | RollbackEvent
    | DriftDetected
    | QuarantineTriggered
    | ProxyEvent
    | TravellerEvent
    | ProxyTierEvent,
) -> None:
    logger = get_aria_logger(f"aria.events.{event.agent}")
    logger.info(
        event.event_type,
        marker=_EVENT_MARKER,
        trace_id=event.trace_id,
        metadata=event.metadata,
    )
