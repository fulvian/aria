#!/usr/bin/env python3
"""
Google Workspace OAuth Scope Verification Utility

Provides functions to verify OAuth tokens have the correct scopes for
Google Workspace MCP write operations.

Scope Requirements:
- Docs write: https://www.googleapis.com/auth/documents
- Sheets write: https://www.googleapis.com/auth/spreadsheets
- Slides write: https://www.googleapis.com/auth/presentations
- Drive file: https://www.googleapis.com/auth/drive.file

Usage:
    from workspace_auth import verify_write_scopes, ScopeCheckResult

    result = verify_write_scopes(access_token)
    if not result.write_ready:
        print(f"Missing scopes: {result.missing_scopes}")
"""

from dataclasses import dataclass
from enum import Enum

import httpx


class Service(Enum):
    """Google Workspace services that require write scopes."""

    DOCS = "docs"
    SHEETS = "sheets"
    SLIDES = "slides"
    DRIVE = "drive"


# Minimum write scopes for each service
WRITE_SCOPES: dict[Service, str] = {
    Service.DOCS: "https://www.googleapis.com/auth/documents",
    Service.SHEETS: "https://www.googleapis.com/auth/spreadsheets",
    Service.SLIDES: "https://www.googleapis.com/auth/presentations",
    Service.DRIVE: "https://www.googleapis.com/auth/drive.file",
}

# All scopes required for full write access
ALL_WRITE_SCOPES: set[str] = set(WRITE_SCOPES.values())


@dataclass
class ScopeCheckResult:
    """Result of OAuth scope verification."""

    token_info: dict
    granted_scopes: set[str]
    write_ready: bool
    missing_scopes: set[str]
    service_status: dict[Service, bool]

    def to_dict(self) -> dict:
        return {
            "write_ready": self.write_ready,
            "granted_scopes": list(self.granted_scopes),
            "missing_scopes": list(self.missing_scopes),
            "service_status": {s.value: status for s, status in self.service_status.items()},
        }


def get_token_info(access_token: str, timeout: float = 10.0) -> dict:
    """
    Get token info from Google's tokeninfo endpoint.

    Args:
        access_token: The OAuth access token to verify
        timeout: Request timeout in seconds

    Returns:
        Token info dict with 'scope' field containing space-separated scopes

    Raises:
        httpx.HTTPStatusError: If the request fails
    """
    response = httpx.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"access_token": access_token},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def parse_scopes(scope_string: str) -> set[str]:
    """
    Parse the scope string into a set of individual scopes.

    Args:
        scope_string: Space-separated scope string from token info

    Returns:
        Set of individual scope URLs
    """
    if not scope_string:
        return set()
    return set(scope_string.strip().split())


def check_service_scope(granted_scopes: set[str], service: Service) -> bool:
    """
    Check if a specific service has its write scope granted.

    Args:
        granted_scopes: Set of granted scope URLs
        service: The service to check

    Returns:
        True if the service's write scope is granted
    """
    required = WRITE_SCOPES.get(service)
    if required is None:
        return False
    return required in granted_scopes


def verify_write_scopes(
    access_token: str,
    required_services: set[Service] | None = None,
    timeout: float = 10.0,
) -> ScopeCheckResult:
    """
    Verify that an OAuth token has the required write scopes.

    Args:
        access_token: The OAuth access token to verify
        required_services: Set of services that must have write access
                           (defaults to all services if None)
        timeout: Request timeout in seconds

    Returns:
        ScopeCheckResult with detailed scope information

    Raises:
        httpx.HTTPStatusError: If the tokeninfo request fails
    """
    if required_services is None:
        required_services = set(Service)

    token_info = get_token_info(access_token, timeout=timeout)
    scope_string = token_info.get("scope", "")
    granted_scopes = parse_scopes(scope_string)

    # Check each required service
    service_status = {}
    missing_scopes = set()

    for service in required_services:
        required_scope = WRITE_SCOPES.get(service)
        if required_scope:
            has_scope = required_scope in granted_scopes
            service_status[service] = has_scope
            if not has_scope:
                missing_scopes.add(required_scope)
        else:
            service_status[service] = False

    # Write is ready only if all required services have their scopes
    write_ready = all(service_status.values()) if service_status else False

    return ScopeCheckResult(
        token_info=token_info,
        granted_scopes=granted_scopes,
        write_ready=write_ready,
        missing_scopes=missing_scopes,
        service_status=service_status,
    )


def format_scope_error(result: ScopeCheckResult) -> str:
    """
    Format a user-friendly error message for missing scopes.

    Args:
        result: The scope check result

    Returns:
        Formatted error message with remediation hints
    """
    if result.write_ready:
        return "All write scopes are granted."

    lines = [
        "ERROR: Missing required OAuth scopes for write operations:",
    ]

    service_names = {
        Service.DOCS: "Docs",
        Service.SHEETS: "Sheets",
        Service.SLIDES: "Slides",
        Service.DRIVE: "Drive",
    }

    for service, has_scope in result.service_status.items():
        if not has_scope:
            scope = WRITE_SCOPES[service]
            service_name = service_names.get(service, service.value)
            lines.append(f"  - {service_name}: {scope}")

    lines.append("")
    lines.append("Remediation:")
    lines.append("  1. Revoke existing tokens at: https://myaccount.google.com/permissions")
    lines.append("  2. Re-run OAuth setup with all required scopes")
    lines.append("  3. Verify token response includes all scopes above")

    return "\n".join(lines)


if __name__ == "__main__":
    import os
    import sys

    # CLI for testing: pass access token as argument or read from env
    access_token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GOOGLE_ACCESS_TOKEN")

    if not access_token:
        print("Usage: python workspace_auth.py <access_token>")
        print("   or: GOOGLE_ACCESS_TOKEN=<token> python workspace_auth.py")
        sys.exit(1)

    print(f"Verifying scopes for token: {access_token[:20]}...")

    try:
        result = verify_write_scopes(access_token)
        print(f"\nWrite Ready: {result.write_ready}")
        print(f"Granted Scopes ({len(result.granted_scopes)}):")
        for scope in sorted(result.granted_scopes):
            print(f"  + {scope}")

        if result.missing_scopes:
            print(f"\n{format_scope_error(result)}")
            sys.exit(1)
        else:
            print("\nAll required write scopes are granted.")
            sys.exit(0)

    except httpx.HTTPStatusError as e:
        print(f"Token verification failed: {e.response.status_code}")
        print(e.response.text[:200])
        sys.exit(1)
