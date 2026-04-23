"""Unit tests for telemetry module."""

import pytest

from aria.agents.search.telemetry import (
    ProviderOutcome,
    SearchEvent,
    SearchTelemetry,
)


class TestSearchEvent:
    """Tests for SearchEvent model."""

    def test_default_event(self):
        """SearchEvent has sensible defaults."""
        event = SearchEvent()
        assert event.outcome == ProviderOutcome.SUCCESS
        assert event.provider == ""
        assert event.credits_used == 0.0
        assert event.result_count == 0

    def test_event_creation(self):
        """SearchEvent can be created with all fields."""
        event = SearchEvent(
            query="test query",
            intent="general",
            provider="tavily",
            outcome=ProviderOutcome.SUCCESS,
            credits_used=1.0,
            result_count=5,
            latency_ms=250.0,
            tier=1,
            escalated=False,
        )
        assert event.provider == "tavily"
        assert event.credits_used == 1.0


class TestSearchTelemetry:
    """Tests for SearchTelemetry."""

    def test_record_and_count(self):
        """Events are recorded and counted."""
        telemetry = SearchTelemetry()
        telemetry.record(
            SearchEvent(provider="searxng", outcome=ProviderOutcome.SUCCESS, result_count=5)
        )
        telemetry.record(
            SearchEvent(provider="tavily", outcome=ProviderOutcome.SUCCESS, result_count=3)
        )

        events = telemetry.recent_events()
        assert len(events) == 2

    def test_ring_buffer_trims(self):
        """Ring buffer trims oldest events when over max_events."""
        telemetry = SearchTelemetry(max_events=5)
        for i in range(10):
            telemetry.record(SearchEvent(provider=f"p{i % 3}"))

        events = telemetry.recent_events()
        assert len(events) == 5

    def test_provider_stats(self):
        """Provider stats are aggregated correctly."""
        telemetry = SearchTelemetry()
        telemetry.record(
            SearchEvent(provider="searxng", outcome=ProviderOutcome.SUCCESS, result_count=5)
        )
        telemetry.record(
            SearchEvent(provider="searxng", outcome=ProviderOutcome.SUCCESS, result_count=3)
        )
        telemetry.record(SearchEvent(provider="searxng", outcome=ProviderOutcome.EMPTY_RESULT))

        stats = telemetry.provider_stats("searxng")
        assert "searxng" in stats
        assert stats["searxng"].total_calls == 3
        assert stats["searxng"].success_count == 2
        assert stats["searxng"].empty_count == 1
        assert stats["searxng"].hit_rate == 2 / 3

    def test_kpis_empty(self):
        """KPIs return empty dict when no events."""
        telemetry = SearchTelemetry()
        assert telemetry.kpis() == {}

    def test_kpis_with_data(self):
        """KPIs are calculated correctly."""
        telemetry = SearchTelemetry()
        # 3 free calls, 2 paid calls
        for _ in range(3):
            telemetry.record(
                SearchEvent(
                    query="test",
                    provider="searxng",
                    outcome=ProviderOutcome.SUCCESS,
                    result_count=5,
                    credits_used=0.0,
                )
            )
        for _ in range(2):
            telemetry.record(
                SearchEvent(
                    query="test",
                    provider="tavily",
                    outcome=ProviderOutcome.SUCCESS,
                    result_count=3,
                    credits_used=1.0,
                )
            )

        kpis = telemetry.kpis()
        assert kpis["paid_calls_ratio"] == 0.4  # 2/5
        assert kpis["total_credits_consumed"] == 2.0
        assert kpis["unique_queries"] == 1.0  # only "test"

    def test_filter_by_provider(self):
        """Recent events can be filtered by provider."""
        telemetry = SearchTelemetry()
        telemetry.record(SearchEvent(provider="searxng"))
        telemetry.record(SearchEvent(provider="tavily"))
        telemetry.record(SearchEvent(provider="searxng"))

        searxng_events = telemetry.recent_events(provider="searxng")
        assert len(searxng_events) == 2

    def test_reset_clears_all(self):
        """Reset clears all events."""
        telemetry = SearchTelemetry()
        telemetry.record(SearchEvent(provider="searxng"))
        telemetry.reset()
        assert len(telemetry.recent_events()) == 0
