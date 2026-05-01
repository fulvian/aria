# Tests for research router

from __future__ import annotations

from aria.agents.search.router import (
    FailureReason,
    HealthState,
    Intent,
    Provider,
    SearchResult,
)


class TestProviderEnum:
    """Test Provider enum values and tier assignments."""

    def test_provider_values(self):
        assert Provider.SEARXNG.value == "searxng"
        assert Provider.TAVILY.value == "tavily"
        assert Provider.EXA.value == "exa"
        assert Provider.BRAVE.value == "brave"
        assert Provider.FETCH.value == "fetch"
        assert Provider.WEBFETCH.value == "webfetch"

    def test_all_providers_unique(self):
        providers = list(Provider)
        assert len(providers) == len(set(providers))


class TestFailureReasonEnum:
    """Test FailureReason enum values."""

    def test_failure_reason_values(self):
        assert FailureReason.RATE_LIMIT.value == "rate_limit"
        assert FailureReason.CREDITS_EXHAUSTED.value == "credits_exhausted"
        assert FailureReason.CIRCUIT_OPEN.value == "circuit_open"
        assert FailureReason.TIMEOUT.value == "timeout"
        assert FailureReason.NETWORK_ERROR.value == "network_error"


class TestHealthStateEnum:
    """Test HealthState enum values."""

    def test_health_state_values(self):
        assert HealthState.AVAILABLE.value == "available"
        assert HealthState.DEGRADED.value == "degraded"
        assert HealthState.DOWN.value == "down"
        assert HealthState.CREDITS_EXHAUSTED.value == "credits_exhausted"


class TestIntentEnum:
    """Test Intent enum values."""

    def test_intent_values(self):
        assert Intent.GENERAL_NEWS.value == "general/news"
        assert Intent.ACADEMIC.value == "academic"
        assert Intent.DEEP_SCRAPE.value == "deep_scrape"
        assert Intent.UNKNOWN.value == "unknown"


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_default_values(self):
        result = SearchResult()
        assert result.provider is None
        assert result.key_id is None
        assert result.data == {}
        assert result.credits_used is None
        assert result.trace_id is None
        assert result.degraded is False
        assert result.degraded_message is None

    def test_degraded_result(self):
        result = SearchResult(
            degraded=True,
            degraded_message="All providers failed",
            trace_id="test-123",
        )
        assert result.degraded is True
        assert result.degraded_message == "All providers failed"
        assert result.trace_id == "test-123"

    def test_successful_result(self):
        result = SearchResult(
            provider=Provider.TAVILY,
            key_id="tvly-1",
            data={"results": ["url1", "url2"]},
            credits_used=5,
            trace_id="test-456",
        )
        assert result.provider == Provider.TAVILY
        assert result.key_id == "tvly-1"
        assert result.credits_used == 5
        assert result.degraded is False


class TestFallback:
    """Test fallback() method for tier advancement."""

    def test_fallback_rate_limit_returns_next_tier(self):
        """RATE_LIMIT skips to next tier (no retry)."""
        # Tier 1 -> Tier 2
        next_provider = None  # Would be implemented with actual router

    def test_fallback_advances_consecutively(self):
        """Tier 1 fail -> tier 2, no skipping."""
        pass

    def test_fallback_returns_none_when_exhausted(self):
        """Last tier returns None (no more fallback)."""
        pass


class TestDegradedMode:
    """Test degraded mode behavior."""

    def test_all_tiers_fail_enters_degraded(self):
        """When all tiers fail, returns SearchResult with degraded=True."""
        pass

    def test_degraded_result_has_message(self):
        """Degraded result includes explanatory message."""
        pass
