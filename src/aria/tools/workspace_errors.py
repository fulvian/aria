"""
Google Workspace MCP Error Types and User-Facing Error Mapping

Provides structured error types and user-friendly error messages for
Google Workspace write operations.

Error categories:
- Auth errors: missing credentials, expired tokens, unauthenticated
- Scope errors: missing required OAuth scopes for write operations
- Quota errors: rate limits (429), API limits exceeded
- Mode errors: read-only mode, tool disabled
- Network errors: timeouts, connection failures

Usage:
    from aria.tools.workspace_errors import (
        WorkspaceError,
        AuthError,
        ScopeError,
        QuotaError,
        ModeError,
        format_workspace_error,
    )
"""

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(Enum):
    """Categories of workspace errors."""

    AUTH = "auth"
    SCOPE = "scope"
    QUOTA = "quota"
    MODE = "mode"
    NETWORK = "network"
    UNKNOWN = "unknown"


@dataclass
class WorkspaceError(Exception):
    """Base exception for Google Workspace errors."""

    category: ErrorCategory
    message: str
    tool_name: str | None = None
    doc_type: str | None = None
    http_status: int | None = None
    retry_after: int | None = None
    details: dict | None = None

    def __str__(self) -> str:
        return self.message


@dataclass
class AuthError(WorkspaceError):
    """Authentication failed or missing."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        http_status: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            category=ErrorCategory.AUTH,
            message=message,
            tool_name=tool_name,
            http_status=http_status,
            details=details,
        )


@dataclass
class ScopeError(WorkspaceError):
    """Missing required OAuth scopes."""

    missing_scopes: set[str] | None = None

    def __init__(
        self,
        message: str,
        missing_scopes: set[str] | None = None,
        tool_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            category=ErrorCategory.SCOPE,
            message=message,
            tool_name=tool_name,
            details=details,
        )
        self.missing_scopes = missing_scopes


@dataclass
class QuotaError(WorkspaceError):
    """Rate limit or quota exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        tool_name: str | None = None,
        http_status: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            category=ErrorCategory.QUOTA,
            message=message,
            tool_name=tool_name,
            http_status=http_status,
            retry_after=retry_after,
            details=details,
        )


@dataclass
class ModeError(WorkspaceError):
    """Operation not allowed in current mode (e.g., read-only)."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            category=ErrorCategory.MODE,
            message=message,
            tool_name=tool_name,
            details=details,
        )


@dataclass
class NetworkError(WorkspaceError):
    """Network connectivity or timeout issues."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            category=ErrorCategory.NETWORK,
            message=message,
            tool_name=tool_name,
            details=details,
        )


def map_http_status_to_error(
    status: int,
    tool_name: str | None = None,
    response_body: dict | None = None,
) -> WorkspaceError:
    """
    Map HTTP status code to appropriate workspace error.

    Args:
        status: HTTP status code
        tool_name: Name of the tool that failed
        response_body: Optional parsed response body

    Returns:
        Appropriate WorkspaceError subclass
    """
    if status == 401:
        return AuthError(
            message="Authentication failed. Token may be expired or invalid.",
            tool_name=tool_name,
            http_status=status,
            details=response_body,
        )

    if status == 403:
        # Check for scope issues in response
        error_details = response_body.get("error", {}) if response_body else {}
        if "invalid_scope" in str(error_details):
            missing = set()
            if isinstance(error_details, dict):
                missing = set(error_details.get("invalid_scope", []))
            return ScopeError(
                message="Missing required OAuth scopes for this operation.",
                missing_scopes=missing,
                tool_name=tool_name,
                details=response_body,
            )
        return AuthError(
            message="Access forbidden. Check permissions and scopes.",
            tool_name=tool_name,
            http_status=status,
            details=response_body,
        )

    if status == 429:
        retry_after = response_body.get("retry_after") if response_body else None
        return QuotaError(
            message="Rate limit exceeded. Retry after backoff.",
            retry_after=retry_after,
            tool_name=tool_name,
            http_status=status,
            details=response_body,
        )

    if status >= 500:
        return QuotaError(
            message=f"Server error ({status}). Retry with backoff.",
            tool_name=tool_name,
            http_status=status,
            details=response_body,
        )

    return WorkspaceError(
        category=ErrorCategory.UNKNOWN,
        message=f"Unexpected error: HTTP {status}",
        tool_name=tool_name,
        http_status=status,
        details=response_body,
    )


def format_workspace_error(error: WorkspaceError) -> str:
    """
    Format workspace error as user-friendly message with remediation.

    Args:
        error: The workspace error

    Returns:
        Formatted error message with remediation hints
    """
    lines = [f"Error: {error.message}"]

    if error.tool_name:
        lines.append(f"  Tool: {error.tool_name}")

    if error.doc_type:
        lines.append(f"  Document type: {error.doc_type}")

    # Add category-specific remediation
    if error.category == ErrorCategory.AUTH:
        lines.append("")
        lines.append("Remediation:")
        lines.append("  1. Verify OAuth credentials are set correctly")
        lines.append("  2. Check if token has expired - re-run OAuth flow if needed")
        lines.append("  3. Ensure GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are set")

    elif error.category == ErrorCategory.SCOPE:
        lines.append("")
        lines.append("Remediation:")
        lines.append("  1. Revoke existing tokens: https://myaccount.google.com/permissions")
        lines.append("  2. Re-run OAuth setup with all required scopes")
        if isinstance(error, ScopeError) and error.missing_scopes:
            lines.append(f"  3. Required scopes: {', '.join(sorted(error.missing_scopes))}")

    elif error.category == ErrorCategory.QUOTA:
        lines.append("")
        lines.append("Remediation:")
        lines.append("  1. Wait for retry_after period if specified")
        lines.append("  2. Implement truncated exponential backoff with jitter")
        lines.append("  3. Consider batching requests to reduce quota usage")
        if error.retry_after:
            lines.append(f"  4. Retry after: {error.retry_after}s")

    elif error.category == ErrorCategory.MODE:
        lines.append("")
        lines.append("Remediation:")
        lines.append("  1. Check if google_workspace MCP server is in read-only mode")
        lines.append("  2. Verify server is enabled in .aria/kilocode/mcp.json")
        lines.append("  3. Ensure write tools are registered (not disabled)")

    elif error.category == ErrorCategory.NETWORK:
        lines.append("")
        lines.append("Remediation:")
        lines.append("  1. Check network connectivity")
        lines.append("  2. Verify Google APIs are reachable")
        lines.append("  3. Increase timeout values if persistent")

    return "\n".join(lines)
