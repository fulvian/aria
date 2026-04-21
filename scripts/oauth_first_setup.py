#!/usr/bin/env python3
"""
ARIA OAuth First-Time Setup Script

Performs Google's OAuth 2.0 PKCE flow for first-time authorization.
Stores the refresh_token in the OS keyring via aria.credentials.KeyringStore.

Usage:
    python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,calendar.events,drive.file,documents,spreadsheets" --account primary [--client-secret-prompt]

Exit codes:
    0 - Success
    1 - Configuration error
    2 - Timeout or user abort
    3 - Token exchange failed
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode

# === Add src to path for imports ===
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from aria.config import get_config
from aria.credentials.keyring_store import KeyringStore

# === Constants ===

GOOGLE_OAUTH_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
DEFAULT_REDIRECT_URI = "http://localhost:8080/callback"
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes
MIN_CODE_VERIFIER_LENGTH = 43
MAX_CODE_VERIFIER_LENGTH = 128
GOOGLE_SCOPE_PREFIX = "https://www.googleapis.com/auth/"


# === Exceptions ===


class OAuthSetupError(Exception):
    """Base exception for OAuth setup errors."""

    pass


class ConfigurationError(OAuthSetupError):
    """Missing required configuration."""

    pass


class TimeoutError(OAuthSetupError):
    """User did not complete consent in time."""

    pass


class StateMismatchError(OAuthSetupError):
    """CSRF state mismatch after callback."""

    pass


class TokenExchangeError(OAuthSetupError):
    """Failed to exchange code for tokens."""

    pass


# === PKCE Helpers ===


def generate_code_verifier(length: int = 64) -> str:
    """Generate a PKCE code_verifier (43-128 chars, URL-safe random).

    Args:
        length: Length of the random bytes (will be base64url encoded)

    Returns:
        Code verifier string
    """
    if length < 43 or length > 128:
        raise ValueError("code_verifier length must be 43-128")
    # RFC 7636 unreserved charset
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_code_challenge(code_verifier: str) -> str:
    """Generate PKCE code_challenge from code_verifier using S256.

    Args:
        code_verifier: The code_verifier string

    Returns:
        Base64url-encoded SHA256 hash without padding
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def normalize_scope(scope: str) -> str:
    """Normalize shorthand scope names to full Google scope URLs."""
    scope = scope.strip()
    if not scope:
        return scope
    if scope.startswith("https://"):
        return scope
    return f"{GOOGLE_SCOPE_PREFIX}{scope}"


# === OAuth Server Handler ===


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that intercepts the OAuth callback."""

    protocol_version = "HTTP/1.1"

    def __init__(self, request: socket.socket, *args, **kwargs) -> None:
        # Store these as instance attributes before calling super()
        self.timeout_seconds: int = kwargs.pop("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        self.expected_state: str = kwargs.pop("expected_state", "")
        self.code_verifier: str = kwargs.pop("code_verifier", "")
        self.result_container: dict = kwargs.pop("result_container", {})
        super().__init__(request, *args, **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET request to /callback."""
        from urllib.parse import parse_qs

        # Parse query string
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        params = parse_qs(query)

        code = params.get("code", [""])[0]
        state = params.get("state", [""])[0]
        error = params.get("error", [""])[0]

        if error:
            self.result_container["error"] = error
            self.send_error(400, f"OAuth error: {error}")
            return

        # Verify state (CSRF protection)
        if state != self.expected_state:
            self.result_container["error"] = "state_mismatch"
            self.send_error(400, "State mismatch - possible CSRF")
            return

        # Store code for later token exchange
        self.result_container["code"] = code
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>ARIA OAuth Setup Complete</h1>"
            b"<p>You can close this window and return to the terminal.</p>"
            b"</body></html>"
        )

        # Signal server to stop
        self.server.shutdown_flag = True  # type: ignore[attr-defined]

    def do_POST(self) -> None:  # noqa: N802
        """Reject POST requests."""
        self.send_error(405, "Method not allowed")


# === OAuth Setup Class ===


class GoogleOAuthSetup:
    """Handles Google's OAuth 2.0 PKCE flow for first-time setup."""

    def __init__(
        self,
        client_id: str,
        scopes: list[str],
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        client_secret: str | None = None,
    ) -> None:
        """Initialize OAuth setup.

        Args:
            client_id: Google OAuth client ID
            scopes: List of OAuth scopes to request
            redirect_uri: Redirect URI for callback
            timeout_seconds: Max time to wait for user consent
            client_secret: Optional client secret (discouraged per ADR-0003)
        """
        self.client_id = client_id
        self.scopes = scopes
        self.redirect_uri = redirect_uri
        self.timeout_seconds = timeout_seconds
        self.client_secret = client_secret

        # Generate PKCE parameters
        self.code_verifier = generate_code_verifier(64)
        self.code_challenge = generate_code_challenge(self.code_verifier)

        # Generate state for CSRF protection
        self.state = secrets.token_urlsafe(32)

        # Results from callback
        self.result_container: dict = {"code": None, "error": None}

    def _build_authorization_url(self) -> str:
        """Build the Google authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "state": self.state,
        }
        return f"{GOOGLE_OAUTH_AUTHORIZATION_URL}?{urlencode(params)}"

    def _start_server(self, server_address: tuple[str, int]) -> HTTPServer:
        """Start the local OAuth callback server."""
        handler = lambda *args, **kwargs: OAuthCallbackHandler(
            *args,
            timeout_seconds=self.timeout_seconds,
            expected_state=self.state,
            code_verifier=self.code_verifier,
            result_container=self.result_container,
            **kwargs,
        )
        httpd = HTTPServer(server_address, handler)
        return httpd

    def _wait_for_callback(
        self,
        httpd: HTTPServer,
        start_time: float,
        timeout_seconds: int,
    ) -> None:
        """Wait for callback with timeout."""
        while True:
            elapsed = time.time() - start_time
            remaining = timeout_seconds - elapsed

            if remaining <= 0:
                raise TimeoutError("Timeout waiting for OAuth consent")

            # Check if callback was received
            if self.result_container.get("code") or self.result_container.get("error"):
                return

            # Check server shutdown flag
            if getattr(httpd, "shutdown_flag", False):
                return

            # Sleep briefly
            time.sleep(0.1)

    def _exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        import httpx

        data = {
            "client_id": self.client_id,
            "code": code,
            "code_verifier": self.code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = httpx.post(
                GOOGLE_OAUTH_TOKEN_URL,
                data=data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise TokenExchangeError(f"Token exchange failed: {e}") from e

    def run(self) -> dict:
        """Run the complete OAuth flow.

        Returns:
            Dict with tokens: {access_token, refresh_token, expires_in, id_token}

        Raises:
            ConfigurationError: If client_id missing
            TimeoutError: If user doesn't complete in time
            StateMismatchError: If CSRF state doesn't match
            TokenExchangeError: If token exchange fails
        """
        if not self.client_id:
            raise ConfigurationError("GOOGLE_OAUTH_CLIENT_ID is required")

        # Build authorization URL
        auth_url = self._build_authorization_url()

        # Determine callback host/port from redirect_uri
        # Default localhost:8080 based on redirect_uri
        host, port = "localhost", 8080
        if self.redirect_uri.startswith("http://"):
            from urllib.parse import urlparse

            parsed = urlparse(self.redirect_uri)
            if parsed.hostname:
                host = parsed.hostname
            if parsed.port:
                port = parsed.port

        # Start local server
        server_address = (host, port)
        httpd = self._start_server(server_address)

        # Start server thread
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        start_time = time.time()

        try:
            # Open browser for consent
            print("\n" + "=" * 60)
            print("ARIA OAuth Setup")
            print("=" * 60)
            print("\nOpening browser for Google OAuth consent...")
            print(f"Scopes requested: {', '.join(self.scopes)}")
            print("\nIf browser doesn't open, navigate to:")
            print(f"\n  {auth_url}\n")
            webbrowser.open(auth_url)

            # Wait for callback
            self._wait_for_callback(httpd, start_time, self.timeout_seconds)

        finally:
            # Shutdown server
            httpd.shutdown()
            httpd.server_close()

        # Check for errors
        error = self.result_container.get("error")
        if error:
            if error == "state_mismatch":
                raise StateMismatchError("CSRF state mismatch - aborting")
            raise OAuthSetupError(f"OAuth error: {error}")

        # Get authorization code
        code = self.result_container.get("code")
        if not code:
            raise TimeoutError("No authorization code received")

        # Exchange code for tokens
        print("\nAuthorization received. Exchanging for tokens...")
        tokens = self._exchange_code_for_tokens(code)

        if "refresh_token" not in tokens:
            print("\nWARNING: No refresh_token returned.")
            print("This may happen if you already authorized the app.")
            print("Try revoking access at: https://myaccount.google.com/permissions")
            print("Then run this script again.\n")

        return tokens


# === Scopes File Helper ===


def save_scopes(scopes: list[str], account: str) -> Path:
    """Save granted scopes to runtime directory.

    Args:
        scopes: List of granted scopes
        account: Account name

    Returns:
        Path to the saved scopes file
    """
    config = get_config()
    runtime_dir = config.paths.runtime / "credentials"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    scopes_file = runtime_dir / f"google_workspace_scopes_{account}.json"
    data = {
        "scopes": scopes,
        "account": account,
        "saved_at": time.time(),
    }
    scopes_file.write_text(json.dumps(data, indent=2))
    return scopes_file


# === CLI Entry Point ===


def main() -> int:
    """Main entry point for oauth_first_setup.py."""
    parser = argparse.ArgumentParser(
        description="ARIA OAuth 2.0 PKCE first-time setup for Google Workspace"
    )
    parser.add_argument(
        "--scopes",
        required=True,
        help="Comma-separated list of OAuth scopes",
    )
    parser.add_argument(
        "--account",
        default="primary",
        help="Account name (default: primary)",
    )
    parser.add_argument(
        "--client-secret-prompt",
        action="store_true",
        help="Prompt for client secret (discouraged, PKCE is preferred)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )

    args = parser.parse_args()

    # Parse scopes
    scopes = [normalize_scope(s) for s in args.scopes.split(",") if s.strip()]

    # Get client ID from environment
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not client_id:
        print("ERROR: GOOGLE_OAUTH_CLIENT_ID environment variable is not set.", file=sys.stderr)
        print("\nTo set it, run:")
        print("  export GOOGLE_OAUTH_CLIENT_ID='your-client-id.apps.googleusercontent.com'\n")
        return 1

    # Optional client secret
    client_secret: str | None = None
    if args.client_secret_prompt:
        import getpass

        client_secret = getpass.getpass("Client secret (optional, press Enter to skip): ").strip()
        if not client_secret:
            client_secret = None

    # Build KeyringStore
    keyring_store = KeyringStore()

    print("\n" + "=" * 60)
    print("ARIA Google Workspace OAuth Setup")
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Open browser for Google OAuth consent")
    print("  2. Exchange authorization code for tokens")
    print("  3. Store refresh_token in OS keyring")
    print("  4. Save granted scopes to runtime")
    print("\nScopes: " + ", ".join(scopes))
    print(f"Account: {args.account}")
    print(f"Timeout: {args.timeout}s")
    print("-" * 60 + "\n")

    try:
        # Run OAuth flow
        setup = GoogleOAuthSetup(
            client_id=client_id,
            scopes=scopes,
            timeout_seconds=args.timeout,
            client_secret=client_secret,
        )
        tokens = setup.run()

        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")
        expires_in = tokens.get("expires_in", 0)

        # Store refresh token in keyring
        if refresh_token:
            keyring_store.put_oauth("google_workspace", args.account, refresh_token)
            print(f"\nrefresh_token stored in keyring (aria.google_workspace/{args.account})")
        else:
            print("\nWARNING: No refresh_token to store!", file=sys.stderr)
            return 3

        # Save scopes
        scopes_file = save_scopes(scopes, args.account)
        print(f"Scopes saved to: {scopes_file}")

        # Verify keyring storage
        stored = keyring_store.get_oauth("google_workspace", args.account)
        if stored:
            print("\nKeyring verification: OK")
        else:
            print("\nWARNING: Keyring verification failed!", file=sys.stderr)
            return 3

        print("\n" + "=" * 60)
        print("OAuth Setup Complete!")
        print("=" * 60)
        print(f"\nAccess token: {'received' if access_token else 'NOT received'}")
        print(f"Refresh token: {'stored in keyring' if refresh_token else 'NOT received'}")
        print(f"Expires in: {expires_in}s")
        print("\nNext step: Enable google_workspace MCP in .aria/kilocode/mcp.json")
        print("          Then run: aria repl\n")

        return 0

    except ConfigurationError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1
    except TimeoutError as e:
        print(f"\nABORT: {e}", file=sys.stderr)
        print(
            "Please run the script again and complete consent within the timeout.", file=sys.stderr
        )
        return 2
    except StateMismatchError as e:
        print(f"\nABORT: {e}", file=sys.stderr)
        print("Please run the script again.", file=sys.stderr)
        return 2
    except TokenExchangeError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 3
    except OAuthSetupError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
