"""Shared credential manager for MCP servers.

Caches the CredentialManager instance at module level so that SOPS decryption
only happens once per MCP server process lifetime, not once per tool call.

This fixes intermittent provider failures caused by SOPS subprocess failures
when CredentialManager was instantiated fresh on every MCP tool invocation.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.credentials.manager import CredentialManager

logger = logging.getLogger(__name__)

_cm_instance: CredentialManager | None = None
_cm_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Get or create the asyncio lock for thread-safe singleton creation."""
    global _cm_lock  # noqa: PLW0603 – intentional singleton pattern
    if _cm_lock is None:
        _cm_lock = asyncio.Lock()
    return _cm_lock


async def get_credential_manager() -> CredentialManager:
    """Get or create the cached CredentialManager singleton.

    On first call, creates the CredentialManager (which triggers SOPS decryption
    with built-in retry). Subsequent calls return the cached instance, avoiding
    repeated SOPS subprocess invocations.

    Returns:
        The singleton CredentialManager instance.
    """
    global _cm_instance  # noqa: PLW0603 – intentional singleton pattern
    if _cm_instance is not None:
        return _cm_instance

    async with _get_lock():
        # Double-check after acquiring lock
        if _cm_instance is not None:
            return _cm_instance

        from aria.credentials.manager import CredentialManager

        cm = CredentialManager()

        # Diagnostic: verify keys loaded
        providers_with_keys = [p for p in ("tavily", "exa", "firecrawl") if cm._api_keys.get(p)]
        if not providers_with_keys:
            logger.warning(
                "CredentialManager initialized with NO provider keys. SOPS_AGE_KEY_FILE=%s PATH=%s",
                os.environ.get("SOPS_AGE_KEY_FILE", "NOT SET"),
                os.environ.get("PATH", "NOT SET"),
            )
        else:
            logger.info(
                "CredentialManager initialized with keys for: %s",
                ", ".join(providers_with_keys),
            )

        _cm_instance = cm
        return _cm_instance


def reset_credential_manager() -> None:
    """Reset the cached instance (for testing or forced reload)."""
    global _cm_instance  # noqa: PLW0603 – intentional singleton pattern
    _cm_instance = None
