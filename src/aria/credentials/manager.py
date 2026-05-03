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

from pathlib import Path
from typing import Literal

from pydantic import SecretStr

from aria.config import ARIAConfig, get_config
from aria.credentials.audit import get_audit_logger
from aria.credentials.keyring_store import KeyringStore
from aria.credentials.rotator import CircuitState, KeyInfo, Rotator
from aria.credentials.sops import SopsAdapter, SopsError

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
        self._secret_env_map: dict[str, str] = {}
        self._load_api_keys()

    def _load_api_keys(self) -> None:  # noqa: PLR0912
        """Load API keys from encrypted storage."""
        api_keys_path = self._config.paths.credentials / "secrets" / "api-keys.enc.yaml"
        self._api_keys = {}
        if api_keys_path.exists():
            try:
                data = self._sops.decrypt(api_keys_path)
                providers = data.get("providers", {}) or {}
                if not isinstance(providers, dict):
                    providers = {}

                for provider, provider_config in providers.items():
                    if not isinstance(provider_config, dict):
                        continue
                    raw_keys = provider_config.get("keys", [])
                    if not isinstance(raw_keys, list):
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
                                    else (
                                        int(item["free_tier_credits"])
                                        if item.get("free_tier_credits") is not None
                                        else None
                                    )
                                ),
                            }
                        )

                    for item in raw_keys:
                        if isinstance(item, dict):
                            key_value = item.get("key") or item.get("api_key") or item.get("token")
                            if isinstance(key_value, str) and key_value:
                                self._register_secret_aliases(
                                    provider.upper().replace("-", "_"),
                                    item,
                                    key_value,
                                )

                    self._api_keys[provider] = normalized
            except SopsError as e:
                # Log but don't fail - keys may be added later
                self._audit.record_no_key("all", f"Failed to load API keys: {e}")

        # Keep rotator state aligned with configured keys.
        for provider, keys in self._api_keys.items():
            self._rotator.sync_provider_keys(provider, keys)

    def _get_key(self, provider: str, key_id: str) -> SecretStr | None:
        """Get decrypted key value from storage."""
        provider_keys = self._api_keys.get(provider, [])
        for item in provider_keys:
            if str(item.get("key_id")) == key_id and isinstance(item.get("key"), str):
                return SecretStr(str(item["key"]))
        return None

    def _register_secret_aliases(
        self,
        provider_env_prefix: str,
        item: dict[str, object],
        normalized_key_value: str,
    ) -> None:
        """Register env-style aliases for decrypted provider secrets.

        The proxy catalog uses placeholders like ``${FRED_API_KEY}`` and
        ``${ALPACA_API_SECRET}``, while the encrypted credential file stores
        provider-centric records. This bridge keeps the credential storage model
        intact while exposing a simple ``get(VAR)`` lookup API for the proxy.
        """
        env_map = self._secret_env_map

        def _set(name: str, value: object | None) -> None:
            if isinstance(value, str) and value:
                env_map.setdefault(name, value)

        _set(f"{provider_env_prefix}_API_KEY", normalized_key_value)
        _set(f"{provider_env_prefix}_KEY", normalized_key_value)
        _set(f"{provider_env_prefix}_TOKEN", normalized_key_value)

        _set(f"{provider_env_prefix}_API_SECRET", item.get("secret"))
        _set(f"{provider_env_prefix}_SECRET", item.get("secret"))
        _set(f"{provider_env_prefix}_CLIENT_SECRET", item.get("client_secret"))

        # Support custom env_name override — if the key item specifies a
        # different env var name, register it directly.
        # Example: github-discovery backend expects GHDISC_GITHUB_TOKEN.
        custom_env = item.get("env_name")
        if isinstance(custom_env, str) and custom_env.strip():
            _set(custom_env.strip(), normalized_key_value)

    def get(self, key: str) -> str | None:
        """Return a decrypted secret by env-style key name.

        This supports proxy placeholder resolution for values like
        ``${FRED_API_KEY}`` and ``${ALPACA_API_SECRET}``.
        """
        return self._secret_env_map.get(key)

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
