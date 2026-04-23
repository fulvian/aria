"""Shared HTTP retry utilities for search providers.

Implements async retry with tenacity, exponential backoff, and Retry-After
awareness for 429 and 5xx responses.  Also defines *non-retryable* error
status codes so callers can immediately report key failures.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Status codes that indicate the API key itself is invalid or exhausted.
# These are NOT retryable with the same key.
KEY_FAILURE_STATUS_CODES = {401, 402, 403, 432}

URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class RetryableProviderError(Exception):
    """Retryable HTTP-level provider error."""


class KeyExhaustedError(Exception):
    """Non-retryable error indicating the API key is invalid or exhausted.

    The caller should report this key as failed and try a different one.
    """

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Key exhausted (HTTP {status_code}): {detail}")


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
    RETRYABLE_STATUS_CODES.  Raises KeyExhaustedError for status codes in
    KEY_FAILURE_STATUS_CODES (non-retryable with same key).
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

            if response.status_code in KEY_FAILURE_STATUS_CODES:
                detail_raw: object = ""
                try:
                    body = response.json()
                    if isinstance(body, dict):
                        detail_raw = body.get("detail", body.get("error", ""))
                        if isinstance(detail_raw, dict):
                            detail_raw = detail_raw.get("error", str(detail_raw))
                except Exception:
                    detail_raw = response.text[:200]
                raise KeyExhaustedError(response.status_code, str(detail_raw))

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
