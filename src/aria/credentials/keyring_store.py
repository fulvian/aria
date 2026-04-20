# Keyring Store for ARIA Credentials
#
# Persistent storage for OAuth refresh tokens via OS keyring (Secret Service on Linux).
# Per blueprint §13.3 and sprint plan W1.1.D.
#
# Features:
# - Store OAuth tokens per service/account
# - Fallback to age-encrypted files when Secret Service unavailable
# - Service name format: {prefix}.{service} (e.g., "aria.google_workspace")
#
# Usage:
#   from aria.credentials.keyring_store import KeyringStore
#
#   store = KeyringStore()
#   store.put_oauth("google_workspace", "primary", "refresh_token_value")
#   token = store.get_oauth("google_workspace", "primary")

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import keyring
import keyring.backends.fail
from keyring.errors import KeyringError

# === KeyringStore ===


class KeyringStore:
    """OAuth token storage using OS keyring.

    Tries Secret Service (Linux) first, falls back to age-encrypted files
    if keyring backend is not available.
    """

    # Default service prefix
    DEFAULT_PREFIX = "aria"

    def __init__(self, service_prefix: str = DEFAULT_PREFIX) -> None:
        """Initialize keyring store.

        Args:
            service_prefix: Prefix for service names (default: "aria")
        """
        self.service_prefix = service_prefix
        self._backend_name = self._detect_backend()
        self._log_backend()

    def _service_name(self, service: str) -> str:
        """Build full service name."""
        return f"{self.service_prefix}.{service}"

    def _detect_backend(self) -> str:
        """Detect which keyring backend is available.

        Returns:
            Backend name string for logging
        """
        backend = keyring.get_keyring()

        if isinstance(backend, keyring.backends.fail.Keyring):
            return "fail (no Secret Service)"
        elif "secret_service" in type(backend).__module__.lower():
            return "SecretService"
        elif "gnome" in type(backend).__module__.lower():
            return "GNOME Keyring"
        elif "kwallet" in type(backend).__module__.lower():
            return "KDE Wallet"
        else:
            return type(backend).__name__

    def _log_backend(self) -> None:
        """Log the detected backend (called once at init)."""
        from aria.utils.logging import get_logger, log_event

        logger = get_logger("aria.credentials.keyring_store")
        log_event(logger, 20, "keyring_backend", backend=self._backend_name)  # 20 = INFO

    def _get_fallback_key_path(self) -> Path | None:
        """Get path to fallback encryption key, or None if not configured."""
        fallback_key = Path(os.environ.get("ARIA_KEYRING_FALLBACK_KEY", "")).expanduser()
        if fallback_key.exists():
            return fallback_key
        # Also check default location
        default_key = Path("~/.config/sops/age/keyring_fallback.txt").expanduser()
        if default_key.exists():
            return default_key
        return None

    def _fallback_dir(self) -> Path:
        """Get the fallback directory for encrypted tokens."""
        credentials_root = Path(
            os.environ.get("ARIA_CREDENTIALS", "/home/fulvio/coding/aria/.aria/credentials")
        ).expanduser()
        return credentials_root / "keyring-fallback"

    def _age_recipient_from_key(self, key_path: Path) -> str:
        """Derive public recipient from an age private key file."""
        result = subprocess.run(
            ["age-keygen", "-y", str(key_path)],
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        )
        recipient = result.stdout.strip()
        if not recipient.startswith("age1"):
            raise RuntimeError("Invalid age recipient derived for keyring fallback")
        return recipient

    def _encrypt_age(self, data: str, key_path: Path) -> bytes:
        """Encrypt data with age CLI tool."""
        recipient = self._age_recipient_from_key(key_path)
        result = subprocess.run(
            ["age", "--encrypt", "-r", recipient, "-o", "-"],
            input=data.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=10,
        )
        return result.stdout

    def _decrypt_age(self, data: bytes, key_path: Path) -> str:
        """Decrypt data with age CLI tool using private key file."""
        result = subprocess.run(
            ["age", "--decrypt", "-i", str(key_path)],
            input=data,
            capture_output=True,
            check=True,
            timeout=10,
        )
        return result.stdout.decode("utf-8")

    # === OAuth operations ===

    def put_oauth(self, service: str, account: str, refresh_token: str) -> None:
        """Store OAuth refresh token.

        Args:
            service: Service name (e.g., "google_workspace")
            account: Account name (e.g., "primary")
            refresh_token: OAuth refresh token value

        Raises:
            RuntimeError: if both keyring and fallback unavailable
        """
        service_name = self._service_name(service)
        username = f"{self.service_prefix}.{account}"

        # Try keyring first
        backend = keyring.get_keyring()
        if not isinstance(backend, keyring.backends.fail.Keyring):
            try:
                keyring.set_password(service_name, username, refresh_token)
                return
            except KeyringError as e:
                # Log but continue to fallback
                from aria.utils.logging import get_logger, log_event

                logger = get_logger("aria.credentials.keyring_store")
                log_event(
                    logger, 30, "keyring_set_failed", service=service, error=str(e)
                )  # 30 = WARNING

        # Fallback to age-encrypted file
        fallback_key = self._get_fallback_key_path()
        if fallback_key is None:
            raise RuntimeError(
                f"No fallback keyring available for {service}/{account}. "
                "Set ARIA_KEYRING_FALLBACK_KEY or ensure Secret Service is installed."
            )

        # Ensure fallback directory exists
        fallback_dir = self._fallback_dir()
        fallback_dir.mkdir(parents=True, exist_ok=True)

        # Store encrypted
        filename = f"{service}-{account}.age"
        filepath = fallback_dir / filename

        encrypted = self._encrypt_age(refresh_token, fallback_key)
        filepath.write_bytes(encrypted)
        filepath.chmod(0o600)

    def get_oauth(self, service: str, account: str) -> str | None:
        """Retrieve OAuth refresh token.

        Args:
            service: Service name
            account: Account name

        Returns:
            Refresh token or None if not found
        """
        service_name = self._service_name(service)
        username = f"{self.service_prefix}.{account}"

        # Try keyring first
        backend = keyring.get_keyring()
        if not isinstance(backend, keyring.backends.fail.Keyring):
            try:
                token = keyring.get_password(service_name, username)
                if token is not None:
                    return token
            except KeyringError:
                pass  # Fall through to fallback

        # Try fallback file
        filename = f"{service}-{account}.age"
        filepath = self._fallback_dir() / filename

        if filepath.exists():
            fallback_key = self._get_fallback_key_path()
            if fallback_key is None:
                return None

            try:
                encrypted = filepath.read_bytes()
                return self._decrypt_age(encrypted, fallback_key)
            except Exception:
                return None

        return None

    def delete_oauth(self, service: str, account: str) -> bool:
        """Delete OAuth refresh token.

        Args:
            service: Service name
            account: Account name

        Returns:
            True if deleted, False if not found
        """
        service_name = self._service_name(service)
        username = f"{self.service_prefix}.{account}"

        deleted = False

        # Try keyring first
        backend = keyring.get_keyring()
        if not isinstance(backend, keyring.backends.fail.Keyring):
            try:
                keyring.delete_password(service_name, username)
                deleted = True
            except KeyringError:
                pass  # Fall through to fallback

        # Try fallback file
        filename = f"{service}-{account}.age"
        filepath = self._fallback_dir() / filename

        if filepath.exists():
            filepath.unlink()
            deleted = True

        return deleted

    def list_accounts(self, service: str) -> list[str]:
        """List account names for a service.

        Note: Not all backends support enumeration. Returns best-effort.

        Args:
            service: Service name

        Returns:
            List of account names (may be empty if enumeration not supported)
        """
        accounts: list[str] = []

        # Check fallback directory
        prefix = f"{service}-"
        fallback_dir = self._fallback_dir()
        if fallback_dir.exists():
            for f in fallback_dir.iterdir():
                if f.name.startswith(prefix) and f.suffix == ".age":
                    account = f.name[len(prefix) : -4]  # Remove prefix and .age
                    accounts.append(account)

        return accounts


# === CLI Entry Point ===


def main() -> int:  # pragma: no cover - developer utility CLI
    """CLI for keyring operations (testing/dev only)."""
    import argparse

    parser = argparse.ArgumentParser(description="Keyring store CLI")
    parser.add_argument("action", choices=["get", "put", "delete", "list"])
    parser.add_argument("service")
    parser.add_argument("account", nargs="?", default="primary")
    parser.add_argument("--token", help="Token value for put action")

    args = parser.parse_args()

    store = KeyringStore()

    try:
        if args.action == "get":
            token = store.get_oauth(args.service, args.account)
            if token:
                pass
            else:
                pass
        elif args.action == "put":
            if not args.token:
                return 1
            store.put_oauth(args.service, args.account, args.token)
        elif args.action == "delete":
            store.delete_oauth(args.service, args.account)
        elif args.action == "list":
            store.list_accounts(args.service)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
