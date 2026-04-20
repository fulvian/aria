# Credential Rotator with Circuit Breaker
#
# Manages API key rotation, credits tracking, and circuit breaker state.
# Per blueprint §13.5 and sprint plan W1.1.E.
#
# Circuit breaker parameters:
# - OPEN after 3 consecutive failures in 5 minutes
# - cooldown_until = now + 30 minutes
# - HALF_OPEN on first acquire after cooldown: 1 probe; success→CLOSED, failure→OPEN (cooldown doubled, max 2h)
# - credits_remaining == 0 → key implicitly skipped
#
# Usage:
#   from aria.credentials.rotator import Rotator, CircuitState, KeyInfo
#
#   rotator = Rotator(sops_adapter, state_path)
#   key = rotator.acquire("tavily", strategy="least_used")
#   rotator.report_success("tavily", key.key_id, credits_used=5)
#   rotator.report_failure("tavily", key.key_id, "rate_limit", retry_after=60)

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, SecretStr

from aria.credentials.sops import SopsAdapter, SopsError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# === Types ===


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class KeyInfo(BaseModel):
    """Information about an API key."""

    provider: str
    key_id: str
    key: SecretStr
    credits_remaining: int | None = None
    circuit_state: CircuitState = CircuitState.CLOSED

    class Config:
        # Allow SecretStr coercion from plain str
        arbitrary_types_allowed = True


class KeyState(BaseModel):
    """Runtime state for a single key."""

    key_id: str
    credits_total: int | None = None
    credits_used: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    cooldown_until: datetime | None = None
    last_used_at: datetime | None = None
    last_error: str | None = None
    last_failure_at: datetime | None = None

    @property
    def credits_remaining(self) -> int | None:
        """Calculate remaining credits."""
        if self.credits_total is None:
            return None
        return self.credits_total - self.credits_used


class ProviderState(BaseModel):
    """Runtime state for a provider."""

    rotation_strategy: Literal["least_used", "round_robin", "failover"] = "least_used"
    keys: dict[str, KeyState] = Field(default_factory=dict)


class ProvidersRuntime(BaseModel):
    """Root runtime state for all providers."""

    providers: dict[str, ProviderState] = Field(default_factory=dict)


# === Rotator ===


class Rotator:
    """Credential rotator with circuit breaker.

    Manages API key lifecycle: acquisition, success/failure reporting,
    automatic rotation based on strategy, and circuit breaker transitions.
    """

    # Circuit breaker thresholds (hardcoded per sprint plan)
    FAILURE_THRESHOLD = 3  # failures before OPEN
    FAILURE_WINDOW_MINUTES = 5  # time window for counting failures
    COOLDOWN_MINUTES = 30  # initial cooldown duration
    MAX_COOLDOWN_MINUTES = 120  # max cooldown (2 hours)
    HALF_OPEN_PROBES = 1  # probe requests in half_open state

    # Flush interval (opportunistic flush every 5s OR on failure state change)
    FLUSH_INTERVAL_SECONDS = 5.0

    def __init__(
        self,
        sops: SopsAdapter,
        state_path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize rotator.

        Args:
            sops: SOPS adapter for reading/writing encrypted state
            state_path: Path to providers_state.enc.yaml
            clock: Optional callable returning current datetime (for testing)
        """
        self.sops = sops
        self.state_path = state_path.resolve()
        self._clock = clock or (lambda: datetime.now(UTC))

        # In-memory state (synced to disk via SOPS)
        self._runtime: ProvidersRuntime = ProvidersRuntime()
        self._load_state()

        # Lock for concurrent access
        self._lock = asyncio.Lock()

        # Flush tracking
        self._last_flush = self._clock()
        self._dirty = False

    def _load_state(self) -> None:
        """Load state from SOPS-encrypted file."""
        if self.state_path.exists():
            try:
                data = self.sops.decrypt(self.state_path)
                # Backward compatibility: keys may be persisted as a list in YAML.
                providers = data.get("providers", {}) if isinstance(data, dict) else {}
                for provider_name, provider_data in providers.items():
                    keys_data = (
                        provider_data.get("keys", {}) if isinstance(provider_data, dict) else {}
                    )
                    if isinstance(keys_data, list):
                        provider_data["keys"] = {
                            key_item["key_id"]: key_item
                            for key_item in keys_data
                            if isinstance(key_item, dict) and "key_id" in key_item
                        }
                self._runtime = ProvidersRuntime(**data)
            except (SopsError, Exception) as e:
                # Log corruption and start fresh
                self.recover_from_corruption(str(e))
        else:
            # Initialize empty state
            self._runtime = ProvidersRuntime()

    def recover_from_corruption(self, error: str | None = None) -> None:
        """Recover from corrupted state file.

        Logs the error and reinitializes with empty providers.

        Args:
            error: Error description for logging
        """
        from aria.utils.logging import get_logger, log_event

        logger = get_logger("aria.credentials.rotator")
        log_event(
            logger,
            40,  # ERROR
            "rotator_state_corrupted",
            error=error or "unknown",
        )
        self._runtime = ProvidersRuntime()

    async def _flush(self) -> None:
        """Flush in-memory state to SOPS-encrypted file."""
        if not self._dirty:
            return

        try:
            data = self._runtime.model_dump(mode="json")
            # Persist keys as list to match blueprint runtime schema.
            for provider_data in data.get("providers", {}).values():
                keys_map = provider_data.get("keys", {})
                if isinstance(keys_map, dict):
                    provider_data["keys"] = list(keys_map.values())

            if self.state_path.exists():

                def mutate(_: dict[str, Any]) -> dict[str, Any]:
                    return data

                self.sops.edit_atomic(self.state_path, mutate)
            else:
                self.sops.encrypt_inplace(self.state_path, data)
            self._dirty = False
            self._last_flush = self._clock()
        except Exception as e:
            from aria.utils.logging import get_logger, log_event

            logger = get_logger("aria.credentials.rotator")
            log_event(logger, 40, "rotator_flush_failed", error=str(e))

    async def _mark_dirty(self) -> None:
        """Mark state as dirty and schedule flush."""
        self._dirty = True
        # Check if we should flush
        now = self._clock()
        elapsed = (now - self._last_flush).total_seconds()
        if elapsed >= self.FLUSH_INTERVAL_SECONDS:
            await self._flush()

    def _get_provider(self, provider: str) -> ProviderState:
        """Get or create provider state."""
        if provider not in self._runtime.providers:
            self._runtime.providers[provider] = ProviderState()
        return self._runtime.providers[provider]

    def sync_provider_keys(
        self,
        provider: str,
        keys: list[dict[str, Any]],
        strategy: Literal["least_used", "round_robin", "failover"] = "least_used",
    ) -> None:
        """Sync provider keys from decrypted api-keys config.

        Existing runtime counters are preserved when key_id already exists.
        """
        prov = self._get_provider(provider)
        prov.rotation_strategy = strategy

        synced: dict[str, KeyState] = {}
        for key_payload in keys:
            key_id = str(key_payload.get("key_id") or "").strip()
            if not key_id:
                continue
            existing = prov.keys.get(key_id, KeyState(key_id=key_id))
            existing.key_id = key_id
            if key_payload.get("credits_total") is not None:
                existing.credits_total = int(key_payload["credits_total"])
            synced[key_id] = existing

        prov.keys = synced
        self._dirty = True

    async def acquire(
        self,
        provider: str,
        strategy: Literal["least_used", "round_robin", "failover"] | None = None,
    ) -> KeyInfo | None:
        """Acquire an API key for a provider.

        Args:
            provider: Provider name (e.g., "tavily")
            strategy: Override rotation strategy (uses provider default if None)

        Returns:
            KeyInfo with key details, or None if no keys available
        """
        async with self._lock:
            prov = self._get_provider(provider)

            # Use provider's default strategy if not specified
            if strategy is None:
                strategy = prov.rotation_strategy

            # Find candidate keys
            candidates = []
            now = self._clock()

            for key_id, key_state in prov.keys.items():
                # Skip keys with no remaining credits
                if key_state.credits_remaining == 0:
                    continue

                # Handle circuit breaker state
                if key_state.circuit_state == CircuitState.OPEN:
                    # Check if cooldown has expired
                    if key_state.cooldown_until and now >= key_state.cooldown_until:
                        # Transition to HALF_OPEN
                        key_state.circuit_state = CircuitState.HALF_OPEN
                        key_state.failure_count = 0
                        await self._mark_dirty()
                    else:
                        # Still in cooldown
                        continue

                if key_state.circuit_state == CircuitState.HALF_OPEN:
                    # In half_open, only allow one probe (tracked by failure_count)
                    # We use failure_count to track probes in half_open
                    if key_state.failure_count >= self.HALF_OPEN_PROBES:
                        continue

                candidates.append((key_id, key_state))

            if not candidates:
                return None

            # Select based on strategy
            selected_key_id: str | None = None

            if strategy == "least_used":
                # Select key with most remaining credits (least used)
                candidates.sort(key=lambda x: x[1].credits_remaining or 0, reverse=True)
                selected_key_id = candidates[0][0]

            elif strategy == "round_robin":
                # Select key with oldest last_used_at
                candidates.sort(key=lambda x: x[1].last_used_at or now)
                selected_key_id = candidates[0][0]

            elif strategy == "failover":
                # For failover, try keys in order until one works
                # In acquire context, just return first available
                selected_key_id = candidates[0][0]

            else:
                # Default: least_used
                candidates.sort(key=lambda x: x[1].credits_remaining or 0, reverse=True)
                selected_key_id = candidates[0][0]

            if selected_key_id is None:
                return None

            # Update key state
            key_state = prov.keys[selected_key_id]
            key_state.last_used_at = now
            await self._mark_dirty()

            # Return key info (key value loaded separately from encrypted config)
            return KeyInfo(
                provider=provider,
                key_id=selected_key_id,
                key=SecretStr(""),  # Placeholder - actual key loaded from api-keys.enc.yaml
                credits_remaining=key_state.credits_remaining,
                circuit_state=key_state.circuit_state,
            )

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
        async with self._lock:
            prov = self._get_provider(provider)
            if key_id not in prov.keys:
                return

            key_state = prov.keys[key_id]
            key_state.credits_used += credits_used
            key_state.last_error = None

            # If in HALF_OPEN, transition to CLOSED on success
            if key_state.circuit_state == CircuitState.HALF_OPEN:
                key_state.circuit_state = CircuitState.CLOSED
                key_state.failure_count = 0
                key_state.cooldown_until = None

            await self._mark_dirty()

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
            retry_after: Optional retry-after header value (seconds)
        """
        async with self._lock:
            prov = self._get_provider(provider)
            if key_id not in prov.keys:
                return

            key_state = prov.keys[key_id]
            key_state.last_error = reason

            now = self._clock()

            if (
                key_state.last_failure_at is None
                or (now - key_state.last_failure_at).total_seconds()
                > self.FAILURE_WINDOW_MINUTES * 60
            ):
                key_state.failure_count = 0

            key_state.failure_count += 1
            key_state.last_failure_at = now

            # Determine new circuit state
            old_state = key_state.circuit_state
            changed = False

            if key_state.circuit_state == CircuitState.HALF_OPEN:
                # Failure in half_open → back to OPEN with doubled cooldown
                key_state.circuit_state = CircuitState.OPEN
                cooldown_mins = self.COOLDOWN_MINUTES * (2**key_state.failure_count)
                cooldown_mins = min(cooldown_mins, self.MAX_COOLDOWN_MINUTES)
                key_state.cooldown_until = datetime.fromtimestamp(
                    now.timestamp() + cooldown_mins * 60, tz=UTC
                )
                changed = True

            elif key_state.circuit_state == CircuitState.CLOSED:
                # Check if we should transition to OPEN
                if key_state.failure_count >= self.FAILURE_THRESHOLD:
                    key_state.circuit_state = CircuitState.OPEN
                    key_state.cooldown_until = datetime.fromtimestamp(
                        now.timestamp() + self.COOLDOWN_MINUTES * 60, tz=UTC
                    )
                    changed = True

            if changed or old_state != key_state.circuit_state:
                await self._mark_dirty()

    def status(self, provider: str | None = None) -> dict[str, Any]:
        """Get rotation status for provider(s).

        Args:
            provider: Optional specific provider, or None for all

        Returns:
            Dict with per-provider key status
        """
        if provider:
            prov = self._runtime.providers.get(provider)
            if not prov:
                return {"provider": provider, "keys": [], "error": "not configured"}
            return {
                "provider": provider,
                "strategy": prov.rotation_strategy,
                "keys": [
                    {
                        "key_id": k.key_id,
                        "circuit_state": k.circuit_state.value,
                        "credits_remaining": k.credits_remaining,
                        "failure_count": k.failure_count,
                        "cooldown_until": k.cooldown_until.isoformat()
                        if k.cooldown_until
                        else None,
                        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                        "last_error": k.last_error,
                    }
                    for k in prov.keys.values()
                ],
            }

        return {provider: self.status(provider) for provider in self._runtime.providers}

    async def flush(self) -> None:
        """Force flush of state to disk."""
        async with self._lock:
            await self._flush()
