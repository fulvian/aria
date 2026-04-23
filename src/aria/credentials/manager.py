# Credential Manager - Unified API
#
# Aggregates SOPS adapter, KeyringStore, Rotator, and AuditLogger into
# a single unified facade for credential management.
# Per blueprint §13.4 and sprint plan W1.1.G.
#
# API:
#   - acquire(provider, strategy) -> KeyInfo
#   - report_success(provider, key_id, credits_used)
#   - report_failure(provider, key_id, reason, retry_after)
#   - status(provider) -> dict
#   - get_oauth(service, account) -> str | None
#   - put_oauth(service, account, refresh_token)
#   - revoke_oauth(service, account)
#
# Usage:
#   from aria.credentials import CredentialManager
#
#   cm = CredentialManager()
#   key = cm.acquire("tavily")

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Literal

from pydantic import SecretStr

from aria.config import ARIAConfig, get_config
from aria.credentials.audit import get_audit_logger
from aria.credentials.keyring_store import KeyringStore
from aria.credentials.rotator import CircuitState, KeyInfo, Rotator
from aria.credentials.sops import SopsAdapter, SopsError

logger = logging.getLogger(__name__)

# === OAuth Bundle ===


class OAuthBundle:
    """Bundle of OAuth credentials."""

    def __init__(self, service: str, account: str, refresh_token: str) -> None:
        self.service = service
        self.account = account
        self.refresh_token = refresh_token


# === Credential Manager ===


class CredentialManager:
    """Unified credential management facade.

    Handles:
    - API key rotation via SOPS + Rotator
    - OAuth token storage via KeyringStore
    - Audit logging for all operations
    """

    # Default paths (can be overridden via config)
    DEFAULT_API_KEYS_PATH = Path("~/.aria/credentials/secrets/api-keys.enc.yaml").expanduser()
    DEFAULT_STATE_PATH = Path("~/.aria/runtime/credentials/providers_state.enc.yaml").expanduser()

    def __init__(self, config: ARIAConfig | None = None) -> None:
        """Initialize credential manager.

        Args:
            config: Optional AriaConfig (uses get_config() if not provided)
        """
        if config is None:
            config = get_config()

        self._config = config

        # Initialize components
        self._sops = SopsAdapter(config.sops.age_key_file)

        # Runtime state path
        runtime_dir = config.paths.runtime / "credentials"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = runtime_dir / "providers_state.enc.yaml"

        self._rotator = Rotator(sops=self._sops, state_path=self._state_path)
        self._keyring = KeyringStore()
        self._audit = get_audit_logger()

        # Load API keys (decrypted once at startup)
        self._api_keys: dict[str, list[dict[str, str | int | None]]] = {}
        self._load_api_keys()

    def _load_keys_from_list(
        self,
        provider: str,
        key_list: object,
    ) -> None:
        """Handle legacy list-style key format.

        Legacy: providers.tavily = [{id, key, owner, credits_total}, ...]
        Canonical: providers.tavily = {keys: [{key_id, key, credits_total}, ...]}

        This method normalizes the legacy format to canonical.
        """
        if not isinstance(key_list, list):
            return

        normalized: list[dict[str, str | int | None]] = []
        for item in key_list:
            if not isinstance(item, dict):
                continue
            # Legacy format uses 'id' instead of 'key_id'
            key_id = str(item.get("id") or item.get("key_id") or "").strip()
            key_value = item.get("key") or item.get("api_key") or item.get("token")
            if not key_id or not isinstance(key_value, str):
                continue
            credits_val = item.get("credits_total")
            credits_int: int | None = None
            if credits_val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    credits_int = int(credits_val)  # noqa: SIM105
            normalized.append(
                {
                    "key_id": key_id,
                    "key": key_value,
                    "credits_total": credits_int,
                }
            )

        if normalized:
            self._api_keys[provider] = normalized

    def _load_api_keys(self) -> None:
        """Load API keys from encrypted storage.

        Includes retry logic: if SOPS decryption fails on the first attempt,
        waits 1 second and retries once before giving up. This handles transient
        failures caused by race conditions, I/O jitter, or fd limits.
        """
        api_keys_path = self._config.paths.credentials / "secrets" / "api-keys.enc.yaml"
        self._api_keys = {}
        if api_keys_path.exists():
            data = self._try_decrypt_with_retry(api_keys_path)
            if data is not None:
                self._parse_providers(data)

        # Keep rotator state aligned with configured keys.
        for provider, keys in self._api_keys.items():
            self._rotator.sync_provider_keys(provider, keys)

    def _try_decrypt_with_retry(self, api_keys_path: Path) -> dict | None:
        """Attempt SOPS decryption with one retry on failure.

        Args:
            api_keys_path: Path to the encrypted API keys file.

        Returns:
            Decrypted data dict, or None if both attempts fail.
        """
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                return self._sops.decrypt(api_keys_path)
            except SopsError as e:
                if attempt < max_attempts - 1:
                    logger.warning(
                        "SOPS decryption failed (attempt %d/%d), retrying in 1s: %s "
                        "SOPS_AGE_KEY_FILE=%s age_key_exists=%s",
                        attempt + 1,
                        max_attempts,
                        e,
                        self._sops.age_key_file,
                        self._sops.age_key_file.exists(),
                    )
                    self._audit.record_no_key(
                        "all", f"SOPS decrypt failed (attempt {attempt + 1}): {e}"
                    )
                    time.sleep(1.0)
                else:
                    logger.error(
                        "SOPS decryption failed after %d attempts: %s "
                        "SOPS_AGE_KEY_FILE=%s age_key_exists=%s path_exists=%s",
                        max_attempts,
                        e,
                        self._sops.age_key_file,
                        self._sops.age_key_file.exists(),
                        api_keys_path.exists(),
                    )
                    self._audit.record_no_key(
                        "all", f"Failed to load API keys after {max_attempts} attempts: {e}"
                    )
        return None

    def _parse_providers(self, data: dict) -> None:
        """Parse provider data from decrypted YAML into _api_keys dict.

        Handles both canonical format (provider.keys[]) and legacy list format.

        Args:
            data: Decrypted YAML data containing a "providers" key.
        """
        providers = data.get("providers", {}) or {}
        if not isinstance(providers, dict):
            providers = {}

        for provider, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                # Legacy format: provider_config is a list of keys directly
                # e.g., providers.tavily = [{id: "...", key: "..."}, ...]
                if isinstance(provider, str) and provider not in ("version",):
                    self._load_keys_from_list(provider, provider_config)
                continue

            # Canonical format: provider_config has "keys" list
            raw_keys = provider_config.get("keys", [])
            if not isinstance(raw_keys, list):
                # Fallback: also accept direct list under provider name
                self._load_keys_from_list(provider, provider_config)
                continue

            normalized: list[dict[str, str | int | None]] = []
            for item in raw_keys:
                if not isinstance(item, dict):
                    continue
                key_id = str(item.get("key_id") or "").strip()
                key_value = item.get("key") or item.get("api_key") or item.get("token")
                if not key_id or not isinstance(key_value, str):
                    continue
                normalized.append(
                    {
                        "key_id": key_id,
                        "key": key_value,
                        "credits_total": (
                            int(item["credits_total"])
                            if item.get("credits_total") is not None
                            else None
                        ),
                    }
                )

            self._api_keys[provider] = normalized

    def _get_key(self, provider: str, key_id: str) -> SecretStr | None:
        """Get decrypted key value from storage."""
        provider_keys = self._api_keys.get(provider, [])
        for item in provider_keys:
            if str(item.get("key_id")) == key_id and isinstance(item.get("key"), str):
                return SecretStr(str(item["key"]))
        return None

    # === API Key Rotation ===

    async def acquire(
        self,
        provider: str,
        strategy: Literal["least_used", "round_robin", "failover"] | None = None,
    ) -> KeyInfo | None:
        """Acquire an API key for a provider.

        Args:
            provider: Provider name (e.g., "tavily", "firecrawl")
            strategy: Optional rotation strategy override

        Returns:
            KeyInfo with key details, or None if no keys available
        """
        key_info = await self._rotator.acquire(provider, strategy)

        if key_info:
            # Load actual key value
            actual_key = self._get_key(provider, key_info.key_id)
            if not actual_key:
                self._audit.record_no_key(
                    provider, f"Missing decrypted value for key_id={key_info.key_id}"
                )
                return None
            key_info.key = actual_key

            # Record audit
            self._audit.record_acquire(
                provider=provider,
                key_id=key_info.key_id,
                result="ok",
                credits_remaining=key_info.credits_remaining,
            )
        else:
            # No key available
            self._audit.record_no_key(provider, "No available keys")

        return key_info

    async def report_success(
        self,
        provider: str,
        key_id: str,
        credits_used: int = 1,
    ) -> None:
        """Report successful API call.

        Args:
            provider: Provider name
            key_id: Key identifier
            credits_used: Number of credits consumed
        """
        await self._rotator.report_success(provider, key_id, credits_used)
        self._audit.record_success(provider, key_id, credits_used)

    async def report_failure(
        self,
        provider: str,
        key_id: str,
        reason: str,
        retry_after: int | None = None,
    ) -> None:
        """Report failed API call.

        Args:
            provider: Provider name
            key_id: Key identifier
            reason: Error description
            retry_after: Optional retry-after value (seconds)
        """
        await self._rotator.report_failure(provider, key_id, reason, retry_after)
        self._audit.record_failure(provider, key_id, reason, cooldown=retry_after)

    def status(self, provider: str | None = None) -> dict:
        """Get credential status for provider(s).

        Args:
            provider: Optional specific provider, or None for all

        Returns:
            Dict with per-provider status
        """
        return self._rotator.status(provider)

    # === OAuth Operations ===

    def get_oauth(self, service: str, account: str = "primary") -> OAuthBundle | None:
        """Get OAuth credentials for a service.

        Args:
            service: Service name (e.g., "google_workspace")
            account: Account name (default: "primary")

        Returns:
            OAuthBundle or None if not found
        """
        token = self._keyring.get_oauth(service, account)
        if token:
            return OAuthBundle(service=service, account=account, refresh_token=token)
        return None

    def put_oauth(self, service: str, account: str, refresh_token: str) -> None:
        """Store OAuth refresh token.

        Args:
            service: Service name
            account: Account name
            refresh_token: OAuth refresh token
        """
        self._keyring.put_oauth(service, account, refresh_token)
        self._audit.record(
            provider=f"oauth:{service}",
            op="put_oauth",
            key_id=account,
            result="ok",
        )

    def revoke_oauth(self, service: str, account: str) -> None:
        """Revoke/delete OAuth credentials.

        Args:
            service: Service name
            account: Account name
        """
        deleted = self._keyring.delete_oauth(service, account)
        self._audit.record(
            provider=f"oauth:{service}",
            op="revoke_oauth",
            key_id=account,
            result="ok" if deleted else "not_found",
        )

    # === Utilities ===

    async def flush(self) -> None:
        """Flush runtime state to disk."""
        await self._rotator.flush()

    def reload(self) -> None:
        """Reload API keys from encrypted storage."""
        self._load_api_keys()


# === Exports ===

__all__ = [
    "CredentialManager",
    "OAuthBundle",
    "CircuitState",
    "KeyInfo",
]
