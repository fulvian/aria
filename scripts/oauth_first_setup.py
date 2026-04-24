#!/usr/bin/env python3
"""
OAuth 2.0 PKCE Utility Functions for Google Workspace MCP

Provides code verifier and challenge generation for OAuth authorization flows.
This module is used by wrapper scripts to perform OAuth setup for the Google Workspace MCP server.

Usage:
    from oauth_first_setup import generate_code_verifier, generate_code_challenge

    cv = generate_code_verifier(64)  # 64-byte random string
    cc = generate_code_challenge(cv)  # S256 hash
"""

import base64
import hashlib
import secrets


def generate_code_verifier(length: int = 64) -> str:
    """
    Generate a random code verifier for PKCE.

    Args:
        length: Length of the random bytes (default 64)

    Returns:
        URL-safe base64-encoded random string

    Note:
        RFC 7636 recommends code verifier length between 43-128 characters
        when using 256-bit SHA256 challenge. We use 64 bytes which produces
        an 88-character base64 string.
    """
    code_verifier = secrets.token_bytes(length)
    return base64.urlsafe_b64encode(code_verifier).decode("utf-8").rstrip("=")


def generate_code_challenge(code_verifier: str) -> str:
    """
    Generate S256 code challenge from code verifier.

    Args:
        code_verifier: The code verifier string from generate_code_verifier()

    Returns:
        URL-safe base64-encoded SHA256 hash of the verifier
    """
    code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(code_challenge).decode("utf-8").rstrip("=")


def generate_state(length: int = 32) -> str:
    """
    Generate a random state parameter for CSRF protection.

    Args:
        length: Length of random bytes (default 32)

    Returns:
        URL-safe base64-encoded random string
    """
    state = secrets.token_bytes(length)
    return base64.urlsafe_b64encode(state).decode("utf-8").rstrip("=")
