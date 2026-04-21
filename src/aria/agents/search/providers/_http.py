"""Shared HTTP retry utilities for search providers.

Implements async retry with tenacity, exponential backoff, and Retry-After
awareness for 429 and 5xx responses.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class RetryableProviderError(Exception):
    """Retryable HTTP-level provider error."""


def _retry_after_seconds(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if not header:
        return None
    try:
        value = float(header)
    except ValueError:
        return None
    return max(0.0, value)


async def request_json_with_retry(
    *,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    request_timeout: float = 30.0,
    attempts: int = 3,
) -> dict[str, Any]:
    """Execute an HTTP request and return a JSON object.

    Retries on network timeouts, network errors, and HTTP status codes in
    RETRYABLE_STATUS_CODES.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(
            (RetryableProviderError, httpx.TimeoutException, httpx.NetworkError)
        ),
        reraise=True,
    ):
        with attempt:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=request_timeout,
            )

            if response.status_code in RETRYABLE_STATUS_CODES:
                retry_after = _retry_after_seconds(response)
                if retry_after is not None:
                    await asyncio.sleep(retry_after)
                raise RetryableProviderError(f"retryable status code: {response.status_code}")

            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}

    return {}


def parse_http_url(url: str) -> AnyHttpUrl | None:
    """Validate and normalize HTTP URL values."""
    value = url.strip()
    if not value:
        return None
    try:
        return URL_ADAPTER.validate_python(value)
    except ValidationError:
        return None
