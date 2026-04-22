# Google Workspace OAuth Helper
#
# Runtime helper for managing OAuth tokens at runtime.
# Called by google_workspace_mcp wrapper or ARIA code for token refresh.
# Per blueprint §12.1 and sprint plan W1.4.B.
#
# Features:
# - Ensure refresh_token is available from keyring
# - Read granted scopes from runtime credentials
# - Revoke tokens and clear keyring
#
# Usage:
#   from aria.agents.workspace.oauth_helper import GoogleOAuthHelper
#
#   helper = GoogleOAuthHelper(cm)
#   token = helper.ensure_refresh_token("primary")  # raises if missing
#   scopes = helper.get_scopes("primary")

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    from aria.config import ARIAConfig

from aria.credentials import CredentialManager
from aria.credentials.keyring_store import KeyringStore

# === Exceptions ===


class OAuthSetupRequiredError(Exception):
    """Raised when no refresh token is available in keyring."""

    def __init__(self, account: str = "primary") -> None:
        self.account = account
        super().__init__(
            f"No refresh token found for account '{account}'. "
            "Run 'python scripts/oauth_first_setup.py' first."
        )


class OAuthError(Exception):
    """General OAuth error."""

    pass


# === Google OAuth Helper ===


class GoogleOAuthHelper:
    """Runtime helper for Google Workspace OAuth operations.

    Provides a clean API for:
    - Ensuring refresh_token is available (raises OAuthSetupRequiredError if not)
    - Getting granted scopes
    - Revoking tokens
    """

    # Service name used in keyring
    SERVICE_NAME = "google_workspace"

    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        config: ARIAConfig | None = None,
    ) -> None:
        """Initialize OAuth helper.

        Args:
            credential_manager: Optional CredentialManager instance
            config: Optional ARIAConfig instance
        """
        self._cm = credential_manager or CredentialManager()
        self._keyring = KeyringStore()
        self._config = config

    def _scopes_file_path(self, account: str) -> Path:
        """Get path to scopes file for account."""
        # Lazy import to avoid circular reference
        from aria.config import get_config

        config = self._config or get_config()
        runtime_dir = config.paths.runtime / "credentials"
        return runtime_dir / f"google_workspace_scopes_{account}.json"

    def _runtime_credentials_dir(self) -> Path:
        """Get path to runtime credentials directory for workspace-mcp.

        This is where the wrapper creates <email>.json files.
        Path: .aria/runtime/credentials/google_workspace_mcp/
        """
        # Lazy import to avoid circular reference
        from aria.config import get_config

        config = self._config or get_config()
        return config.paths.runtime / "credentials" / "google_workspace_mcp"

    def ensure_refresh_token(self, account: str = "primary") -> str:
        """Get refresh token, raising if missing.

        Args:
            account: Account name (default: "primary")

        Returns:
            Refresh token string

        Raises:
            OAuthSetupRequiredError: If no token in keyring
        """
        token = self._keyring.get_oauth(self.SERVICE_NAME, account)

        if not token:
            raise OAuthSetupRequiredError(account)

        return token

    def get_scopes(self, account: str = "primary") -> list[str]:
        """Get granted scopes for account.

        Args:
            account: Account name (default: "primary")

        Returns:
            List of granted scope strings (empty if not set up)
        """
        scopes_file = self._scopes_file_path(account)

        if not scopes_file.exists():
            return []

        try:
            data: dict[str, object] = json.loads(scopes_file.read_text())
            scopes_data = data.get("scopes", [])
            return cast("list[str]", scopes_data)
        except (json.JSONDecodeError, OSError):
            return []

    def revoke(self, account: str = "primary") -> None:
        """Revoke OAuth tokens and clear keyring.

        This method:
        1. Revokes the refresh token at Google
        2. Clears the keyring
        3. Deletes the runtime credentials file created by the wrapper
        4. Deletes the scopes file

        Args:
            account: Account name (default: "primary")

        Raises:
            OAuthError: If revocation fails
        """

        import httpx

        # Get current token
        refresh_token = self._keyring.get_oauth(self.SERVICE_NAME, account)
        if not refresh_token:
            # Already gone
            return

        # Revoke at Google
        revoke_url = "https://oauth2.googleapis.com/revoke"
        try:
            response = httpx.post(
                revoke_url,
                data={"token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            # 200 = success, 400 = unknown token (already revoked?)
            if response.status_code not in (200, 400):
                response.raise_for_status()
        except httpx.HTTPError as e:
            raise OAuthError(f"Failed to revoke token: {e}") from e
        finally:
            # Always clear keyring, even if revocation fails
            self._keyring.delete_oauth(self.SERVICE_NAME, account)

        # Clear runtime credentials file (created by google-workspace-wrapper.sh)
        # File is at WORKSPACE_MCP_CREDENTIALS_DIR/<safe_email>.json
        try:
            runtime_dir = self._runtime_credentials_dir()
            if runtime_dir.exists():
                # Find and delete all <email>.json files in the directory
                for creds_file in runtime_dir.glob("*.json"):
                    creds_file.unlink()
        except Exception:
            # Best effort cleanup - don't fail if this fails
            pass

        # Clear scopes file
        scopes_file = self._scopes_file_path(account)
        if scopes_file.exists():
            scopes_file.unlink()

    def is_configured(self, account: str = "primary") -> bool:
        """Check if OAuth is configured for account.

        Args:
            account: Account name (default: "primary")

        Returns:
            True if refresh token exists in keyring
        """
        return self._keyring.get_oauth(self.SERVICE_NAME, account) is not None


# === Exports ===

__all__ = [
    "GoogleOAuthHelper",
    "OAuthSetupRequiredError",
    "OAuthError",
]
