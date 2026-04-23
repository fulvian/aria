"""
Runtime quota state tracking for search providers per Searcher Optimizer Plan §5.4.

Tracks credits consumed per provider with daily and monthly reset windows.
Used by the economic router to enforce budget guardrails and reserve mode.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderQuota(BaseModel):
    """Quota state for a single provider.

    Attributes:
        provider: Provider name.
        daily_used: Credits used today.
        daily_limit: Maximum credits per day (None = unlimited).
        monthly_used: Credits used this month.
        monthly_limit: Maximum credits per month (None = unlimited).
        last_daily_reset: Timestamp of last daily reset.
        last_monthly_reset: Timestamp of last monthly reset.
        reserved: Whether this provider is in reserve mode.
    """

    provider: str
    daily_used: float = 0.0
    daily_limit: float | None = None
    monthly_used: float = 0.0
    monthly_limit: float | None = None
    last_daily_reset: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_monthly_reset: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reserved: bool = False

    def check_and_reset_windows(self, now: datetime | None = None) -> None:
        """Check and reset quota windows if they have expired.

        Args:
            now: Current time (default: UTC now).
        """
        if now is None:
            now = datetime.now(UTC)

        # Daily reset
        if now.date() > self.last_daily_reset.date():
            self.daily_used = 0.0
            self.last_daily_reset = now

        # Monthly reset
        if now.month != self.last_monthly_reset.month or now.year != self.last_monthly_reset.year:
            self.monthly_used = 0.0
            self.last_monthly_reset = now

    def can_afford(self, credits: float = 1.0) -> bool:
        """Check if provider has remaining quota for the given credits.

        Args:
            credits: Credits to check.

        Returns:
            True if quota is available.
        """
        if self.daily_limit is not None and self.daily_used + credits > self.daily_limit:
            return False
        if self.monthly_limit is not None and self.monthly_used + credits > self.monthly_limit:  # noqa: SIM103
            return False
        return True

    def consume(self, credits: float = 1.0) -> None:
        """Record credit consumption.

        Args:
            credits: Credits consumed.
        """
        self.daily_used += credits
        self.monthly_used += credits

    @property
    def daily_remaining(self) -> float | None:
        """Credits remaining today (None = unlimited)."""
        if self.daily_limit is None:
            return None
        return max(0.0, self.daily_limit - self.daily_used)

    @property
    def monthly_remaining(self) -> float | None:
        """Credits remaining this month (None = unlimited)."""
        if self.monthly_limit is None:
            return None
        return max(0.0, self.monthly_limit - self.monthly_used)


class QuotaState:
    """Centralized quota tracking for all search providers.

    Maintains quota state per provider with configurable limits and
    automatic reset windows (daily/monthly).

    Supports reserve mode: when a provider is reserved, it is only used
    for high-value intents (academic, deep_scrape) even if quota remains.
    """

    def __init__(
        self,
        default_daily_limit: float | None = None,
        default_monthly_limit: float | None = None,
    ) -> None:
        """Initialize quota state.

        Args:
            default_daily_limit: Default daily credit limit per provider.
            default_monthly_limit: Default monthly credit limit per provider.
        """
        self._quotas: dict[str, ProviderQuota] = {}
        self._default_daily_limit = default_daily_limit
        self._default_monthly_limit = default_monthly_limit

    def get_or_create(self, provider: str) -> ProviderQuota:
        """Get or create quota for a provider.

        Args:
            provider: Provider name.

        Returns:
            ProviderQuota instance.
        """
        if provider not in self._quotas:
            self._quotas[provider] = ProviderQuota(
                provider=provider,
                daily_limit=self._default_daily_limit,
                monthly_limit=self._default_monthly_limit,
            )
        return self._quotas[provider]

    def can_afford(self, provider: str, credits: float = 1.0) -> bool:
        """Check if a provider can afford the given credits.

        Args:
            provider: Provider name.
            credits: Credits to check.

        Returns:
            True if quota is available.
        """
        quota = self.get_or_create(provider)
        quota.check_and_reset_windows()
        return quota.can_afford(credits)

    def consume(self, provider: str, credits: float = 1.0) -> None:
        """Record credit consumption for a provider.

        Args:
            provider: Provider name.
            credits: Credits consumed.
        """
        quota = self.get_or_create(provider)
        quota.check_and_reset_windows()
        quota.consume(credits)
        logger.debug(
            "Quota consumed: %s += %.1f (daily=%.1f, monthly=%.1f)",
            provider,
            credits,
            quota.daily_used,
            quota.monthly_used,
        )

    def set_reserve(self, provider: str, reserved: bool = True) -> None:
        """Set reserve mode for a provider.

        Reserved providers are only used for high-value intents.

        Args:
            provider: Provider name.
            reserved: Whether to enable reserve mode.
        """
        quota = self.get_or_create(provider)
        quota.reserved = reserved

    def is_reserved(self, provider: str) -> bool:
        """Check if a provider is in reserve mode.

        Args:
            provider: Provider name.

        Returns:
            True if reserved.
        """
        return self.get_or_create(provider).reserved

    def set_limits(
        self,
        provider: str,
        daily_limit: float | None = None,
        monthly_limit: float | None = None,
    ) -> None:
        """Set custom quota limits for a provider.

        Args:
            provider: Provider name.
            daily_limit: Daily credit limit (None = unlimited).
            monthly_limit: Monthly credit limit (None = unlimited).
        """
        quota = self.get_or_create(provider)
        if daily_limit is not None:
            quota.daily_limit = daily_limit
        if monthly_limit is not None:
            quota.monthly_limit = monthly_limit

    def status(self) -> dict[str, dict[str, Any]]:
        """Get quota status for all providers.

        Returns:
            Dict mapping provider name to quota info.
        """
        now = datetime.now(UTC)
        result: dict[str, dict[str, Any]] = {}
        for name, quota in self._quotas.items():
            quota.check_and_reset_windows(now)
            result[name] = {
                "daily_used": quota.daily_used,
                "daily_limit": quota.daily_limit,
                "daily_remaining": quota.daily_remaining,
                "monthly_used": quota.monthly_used,
                "monthly_limit": quota.monthly_limit,
                "monthly_remaining": quota.monthly_remaining,
                "reserved": quota.reserved,
            }
        return result
