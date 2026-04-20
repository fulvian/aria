# ARIA credentials module
#
# Provides unified credential management with:
# - SOPS+age encrypted storage for API keys
# - OS keyring integration for OAuth tokens
# - Circuit breaker pattern for key rotation
# - Audit logging
#
# Usage:
#   from aria.credentials import CredentialManager
#   cm = CredentialManager()
#   key_info = cm.acquire(provider="tavily", strategy="least_used")

from __future__ import annotations

__all__ = ["CredentialManager"]


class CredentialManager:
    """Credential manager stub - full implementation in Phase 1."""

    def __init__(self) -> None:
        """Initialize credential manager."""
        pass

    def acquire(self, provider: str, strategy: str = "least_used") -> dict:
        """Acquire a credential for the given provider."""
        return {"key": "stub", "id": "stub", "budget_remaining": 0}

    def get_oauth(self, service: str, account: str = "primary") -> dict:
        """Get OAuth token for service."""
        return {"access_token": "stub", "scopes": []}

    def report_success(self, provider: str, key_id: str, **kwargs: object) -> None:
        """Report successful credential usage."""
        pass

    def report_failure(self, provider: str, key_id: str, reason: str, **kwargs: object) -> None:
        """Report failed credential usage."""
        pass

    def status(self, provider: str) -> dict:
        """Get status for provider."""
        return {"active_keys": [], "blocked_keys": [], "credits_remaining_total": 0}
