"""
Search telemetry for cost/quality/provider metrics per Searcher Optimizer Plan §4.7.

Collects structured metrics on search operations: provider outcomes, credit costs,
quality gate results, latency, and escalation events. Provides KPI calculations
for continuous optimization.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderOutcome(StrEnum):
    """Outcome of a single provider search attempt."""

    SUCCESS = "success"
    EMPTY_RESULT = "empty_result"
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    TRANSIENT_ERROR = "transient_error"
    PROVIDER_DOWN = "provider_down"
    INVALID_REQUEST = "invalid_request"
    SKIPPED = "skipped"


class SearchEvent(BaseModel):
    """A single search event record.

    Attributes:
        timestamp: When the event occurred.
        query: Search query (truncated for privacy).
        intent: Classified intent.
        provider: Provider name.
        outcome: Provider outcome.
        credits_used: Credits consumed (0 for free providers).
        result_count: Number of results returned.
        latency_ms: Request latency in milliseconds.
        tier: Cost tier of the provider.
        escalated: Whether this event triggered a tier escalation.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    query: str = Field(default="", max_length=200)
    intent: str = "general"
    provider: str = ""
    outcome: ProviderOutcome = ProviderOutcome.SUCCESS
    credits_used: float = 0.0
    result_count: int = 0
    latency_ms: float = 0.0
    tier: int = 0
    escalated: bool = False


class ProviderStats(BaseModel):
    """Aggregated statistics for a single provider.

    Attributes:
        provider: Provider name.
        total_calls: Total number of calls.
        success_count: Successful calls with results.
        empty_count: Calls that returned empty results.
        error_count: Failed calls.
        total_credits: Total credits consumed.
        avg_latency_ms: Average latency in milliseconds.
        hit_rate: Ratio of successful calls to total calls.
    """

    provider: str
    total_calls: int = 0
    success_count: int = 0
    empty_count: int = 0
    error_count: int = 0
    total_credits: float = 0.0
    avg_latency_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Success ratio."""
        return self.success_count / self.total_calls if self.total_calls > 0 else 0.0


class SearchTelemetry:
    """Collects and aggregates search operation metrics.

    Tracks per-provider and global KPIs:
    - paid_calls_ratio: ratio of paid calls to total calls
    - avg_credit_cost_per_query: average credits consumed per query
    - quality_pass_rate_first_tier: ratio of queries satisfied by first tier
    - fallback_success_rate: ratio of successful fallbacks after first tier failure
    - empty_success_rate: ratio of "successful but empty" results

    Usage:
        telemetry = SearchTelemetry()
        telemetry.record(event=SearchEvent(...))
        kpis = telemetry.kpis()
    """

    def __init__(self, max_events: int = 10000) -> None:
        """Initialize telemetry.

        Args:
            max_events: Maximum events to keep in memory (ring buffer).
        """
        self._events: list[SearchEvent] = []
        self._max_events = max_events

    def record(self, event: SearchEvent) -> None:
        """Record a search event.

        Args:
            event: Search event to record.
        """
        self._events.append(event)
        # Ring buffer: trim oldest events if over limit
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]

    def provider_stats(self, provider: str | None = None) -> dict[str, ProviderStats]:
        """Get aggregated statistics per provider.

        Args:
            provider: Optional specific provider. Returns all if None.

        Returns:
            Dict mapping provider name to ProviderStats.
        """
        latency_sums: dict[str, float] = defaultdict(float)
        stats: dict[str, ProviderStats] = {}

        for event in self._events:
            p = event.provider
            if provider is not None and p != provider:
                continue

            if p not in stats:
                stats[p] = ProviderStats(provider=p)

            s = stats[p]
            s.total_calls += 1
            s.total_credits += event.credits_used
            latency_sums[p] += event.latency_ms

            if event.outcome == ProviderOutcome.SUCCESS and event.result_count > 0:
                s.success_count += 1
            elif event.outcome == ProviderOutcome.EMPTY_RESULT:
                s.empty_count += 1
            else:
                s.error_count += 1

        # Calculate averages
        for p, s in stats.items():
            if s.total_calls > 0:
                s.avg_latency_ms = round(latency_sums[p] / s.total_calls, 1)

        return stats

    def kpis(self) -> dict[str, float]:
        """Calculate key performance indicators.

        Returns:
            Dict of KPI name to value.
        """
        if not self._events:
            return {}

        total = len(self._events)
        paid_calls = sum(1 for e in self._events if e.credits_used > 0)
        total_credits = sum(e.credits_used for e in self._events)

        # First tier pass: events that didn't escalate and had results
        first_tier_success = sum(
            1
            for e in self._events
            if not e.escalated and e.outcome == ProviderOutcome.SUCCESS and e.result_count > 0
        )
        escalated_events = sum(1 for e in self._events if e.escalated)
        # Fallback success: escalated events that eventually had results
        fallback_success = sum(
            1
            for e in self._events
            if e.escalated and e.outcome == ProviderOutcome.SUCCESS and e.result_count > 0
        )

        # Empty success: success with 0 results
        empty_success = sum(1 for e in self._events if e.outcome == ProviderOutcome.EMPTY_RESULT)

        # Unique queries (approximation by dedup on query text)
        unique_queries: set[str] = set()
        query_credits: dict[str, float] = defaultdict(float)
        for e in self._events:
            unique_queries.add(e.query)
            query_credits[e.query] += e.credits_used

        return {
            "paid_calls_ratio": round(paid_calls / total, 4) if total > 0 else 0.0,
            "avg_credit_cost_per_query": (
                round(total_credits / len(unique_queries), 4) if unique_queries else 0.0
            ),
            "quality_pass_rate_first_tier": (
                round(first_tier_success / total, 4) if total > 0 else 0.0
            ),
            "fallback_success_rate": (
                round(fallback_success / escalated_events, 4) if escalated_events > 0 else 1.0
            ),
            "empty_success_rate": round(empty_success / total, 4) if total > 0 else 0.0,
            "total_events": float(total),
            "unique_queries": float(len(unique_queries)),
            "total_credits_consumed": round(total_credits, 2),
        }

    def recent_events(
        self,
        limit: int = 100,
        provider: str | None = None,
    ) -> list[SearchEvent]:
        """Get recent events, optionally filtered by provider.

        Args:
            limit: Maximum events to return.
            provider: Optional provider filter.

        Returns:
            List of recent SearchEvent.
        """
        events = self._events
        if provider is not None:
            events = [e for e in events if e.provider == provider]
        return events[-limit:]

    def reset(self) -> None:
        """Clear all telemetry data."""
        self._events.clear()
