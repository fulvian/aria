"""
Google Workspace Retry Utilities

Provides standardized retry logic with truncated exponential backoff and jitter
for Google Workspace write operations.

Based on Google Cloud Storage retry strategy and best practices for 429/5xx errors.

Usage:
    from aria.tools.workspace_retry import (
        WorkspaceRetryConfig,
        create_google_api_retry,
    )

    config = create_google_api_retry()
"""

from dataclasses import dataclass

import httpx

from aria.tools.workspace_errors import QuotaError


@dataclass
class WorkspaceRetryConfig:
    """Configuration for workspace retry behavior."""

    max_attempts: int = 5
    multiplier: float = 1.0
    max_wait: float = 60.0
    jitter: float = 5.0

    def is_retryable(self, exception: BaseException) -> bool:
        """Determine if exception is retryable."""
        if isinstance(exception, QuotaError):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code in (429, 500, 502, 503, 504)
        if isinstance(exception, httpx.TimeoutException):
            return True
        return isinstance(exception, httpx.NetworkError)


def create_google_api_retry(
    max_attempts: int = 5,
    max_wait: float = 60.0,
) -> WorkspaceRetryConfig:
    """
    Create retry config optimized for Google API calls.

    Args:
        max_attempts: Maximum retry attempts (default 5)
        max_wait: Maximum wait between retries in seconds (default 60)

    Returns:
        WorkspaceRetryConfig optimized for Google APIs
    """
    return WorkspaceRetryConfig(
        max_attempts=max_attempts,
        multiplier=1.0,
        max_wait=max_wait,
        jitter=5.0,
    )


def extract_retry_after(response: httpx.Response) -> int | None:
    """
    Extract Retry-After header from response if present.

    Args:
        response: HTTP response

    Returns:
        Retry-After value in seconds, or None if not present
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return int(retry_after)
        except ValueError:
            pass
    return None


def calculate_backoff(
    attempt: int,
    config: WorkspaceRetryConfig,
) -> float:
    """
    Calculate wait time with truncated exponential backoff and jitter.

    Uses formula: min(multiplier * 2^attempt + random(0, jitter), max_wait)

    Args:
        attempt: Current attempt number (1-indexed)
        config: Retry configuration

    Returns:
        Wait time in seconds
    """
    import random

    base_wait = config.multiplier * (2**attempt)
    jitter = random.uniform(0, config.jitter)
    return min(base_wait + jitter, config.max_wait)  # type: ignore[no-any-return]
