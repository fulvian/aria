"""Tests for aria.tools._cred — cached CredentialManager singleton."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from aria.tools._cred import get_credential_manager, reset_credential_manager

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def _reset_singleton() -> Generator[None, None, None]:
    """Reset the cached singleton before and after each test."""
    reset_credential_manager()
    yield
    reset_credential_manager()


def _make_fake_manager(api_keys: dict | None = None) -> MagicMock:
    """Create a mock CredentialManager with the given api_keys."""
    cm = MagicMock()
    cm._api_keys = api_keys or {}
    return cm


@pytest.mark.asyncio
async def test_returns_same_instance_on_repeated_calls() -> None:
    """Repeated calls to get_credential_manager return the same instance."""
    fake_cm = _make_fake_manager({"tavily": [{"key_id": "k1", "key": "v1"}]})
    with patch("aria.credentials.manager.CredentialManager", return_value=fake_cm):
        cm1 = await get_credential_manager()
        cm2 = await get_credential_manager()
        cm3 = await get_credential_manager()

    assert cm1 is cm2 is cm3


@pytest.mark.asyncio
async def test_creates_credential_manager_once() -> None:
    """CredentialManager constructor is called exactly once."""
    fake_cm = _make_fake_manager({"exa": [{"key_id": "k1", "key": "v1"}]})
    with patch("aria.credentials.manager.CredentialManager", return_value=fake_cm) as mock_cls:
        await get_credential_manager()
        await get_credential_manager()
        await get_credential_manager()

    assert mock_cls.call_count == 1


@pytest.mark.asyncio
async def test_reset_allows_new_instance() -> None:
    """After reset_credential_manager, next call creates a new instance."""
    fake_cm1 = _make_fake_manager({"tavily": [{"key_id": "k1", "key": "v1"}]})
    fake_cm2 = _make_fake_manager({"exa": [{"key_id": "k2", "key": "v2"}]})

    with patch("aria.credentials.manager.CredentialManager", return_value=fake_cm1):
        cm1 = await get_credential_manager()

    reset_credential_manager()

    with patch("aria.credentials.manager.CredentialManager", return_value=fake_cm2):
        cm2 = await get_credential_manager()

    assert cm1 is not cm2
    assert cm1 is fake_cm1
    assert cm2 is fake_cm2


@pytest.mark.asyncio
async def test_logs_warning_when_no_provider_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When CredentialManager has no keys for tavily/exa/firecrawl, logs warning."""
    fake_cm = _make_fake_manager({})
    with (
        patch("aria.credentials.manager.CredentialManager", return_value=fake_cm),
        caplog.at_level(logging.WARNING),
    ):
        await get_credential_manager()

    assert any("NO provider keys" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_logs_info_when_keys_present(caplog: pytest.LogCaptureFixture) -> None:
    """When CredentialManager has provider keys, logs info with provider names."""
    fake_cm = _make_fake_manager(
        {"tavily": [{"key_id": "k1", "key": "v1"}], "exa": [{"key_id": "k2", "key": "v2"}]}
    )
    with (
        patch("aria.credentials.manager.CredentialManager", return_value=fake_cm),
        caplog.at_level(logging.INFO),
    ):
        await get_credential_manager()

    assert any("keys for" in r.message and "tavily" in r.message for r in caplog.records)
