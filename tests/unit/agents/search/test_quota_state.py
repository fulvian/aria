"""Unit tests for quota_state module."""

from datetime import UTC, datetime, timedelta

import pytest

from aria.agents.search.quota_state import ProviderQuota, QuotaState


class TestProviderQuota:
    """Tests for ProviderQuota model."""

    def test_can_afford_unlimited(self):
        """No limits means always can afford."""
        quota = ProviderQuota(provider="searxng")
        assert quota.can_afford(1000.0)

    def test_can_afford_daily_limit(self):
        """Daily limit is respected."""
        quota = ProviderQuota(provider="tavily", daily_limit=10.0)
        assert quota.can_afford(5.0)
        quota.consume(8.0)
        assert not quota.can_afford(5.0)
        assert quota.can_afford(2.0)

    def test_can_afford_monthly_limit(self):
        """Monthly limit is respected."""
        quota = ProviderQuota(provider="tavily", monthly_limit=100.0)
        quota.consume(95.0)
        assert quota.can_afford(5.0)
        assert not quota.can_afford(10.0)

    def test_daily_remaining(self):
        """Daily remaining calculation."""
        quota = ProviderQuota(provider="tavily", daily_limit=10.0)
        quota.consume(3.0)
        assert quota.daily_remaining == 7.0

    def test_monthly_remaining(self):
        """Monthly remaining calculation."""
        quota = ProviderQuota(provider="tavily", monthly_limit=100.0)
        quota.consume(30.0)
        assert quota.monthly_remaining == 70.0

    def test_daily_reset(self):
        """Daily quota resets when date changes."""
        yesterday = datetime.now(UTC) - timedelta(days=1)
        quota = ProviderQuota(
            provider="tavily",
            daily_limit=10.0,
            last_daily_reset=yesterday,
        )
        quota.consume(8.0)
        # After check_and_reset_windows, daily should reset
        quota.check_and_reset_windows()
        assert quota.daily_used == 0.0
        assert quota.can_afford(10.0)

    def test_monthly_reset(self):
        """Monthly quota resets when month changes."""
        last_month = datetime.now(UTC) - timedelta(days=35)
        quota = ProviderQuota(
            provider="tavily",
            monthly_limit=100.0,
            last_monthly_reset=last_month,
        )
        quota.consume(80.0)
        quota.check_and_reset_windows()
        assert quota.monthly_used == 0.0

    def test_unlimited_remaining_is_none(self):
        """No limit means remaining is None."""
        quota = ProviderQuota(provider="searxng")
        assert quota.daily_remaining is None
        assert quota.monthly_remaining is None


class TestQuotaState:
    """Tests for QuotaState."""

    def test_get_or_create(self):
        """Providers are lazily created."""
        state = QuotaState()
        quota = state.get_or_create("tavily")
        assert quota.provider == "tavily"

    def test_can_afford_checks(self):
        """can_afford checks reset windows."""
        state = QuotaState(default_daily_limit=10.0)
        assert state.can_afford("tavily", 5.0)
        state.consume("tavily", 8.0)
        assert not state.can_afford("tavily", 5.0)

    def test_reserve_mode(self):
        """Reserved providers are tracked."""
        state = QuotaState()
        state.set_reserve("exa", reserved=True)
        assert state.is_reserved("exa")
        assert not state.is_reserved("tavily")

    def test_custom_limits(self):
        """Custom limits can be set per provider."""
        state = QuotaState()
        state.set_limits("tavily", daily_limit=50.0, monthly_limit=1000.0)
        quota = state.get_or_create("tavily")
        assert quota.daily_limit == 50.0
        assert quota.monthly_limit == 1000.0

    def test_status_report(self):
        """Status report includes all tracked providers."""
        state = QuotaState(default_daily_limit=100.0)
        state.consume("searxng", 5.0)
        state.consume("tavily", 10.0)

        status = state.status()
        assert "searxng" in status
        assert "tavily" in status
        assert status["searxng"]["daily_used"] == 5.0
        assert status["tavily"]["daily_used"] == 10.0
