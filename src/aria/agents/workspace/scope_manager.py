# Scope Manager for Google Workspace OAuth
#
# Manages OAuth scopes with escalation control per blueprint §12.2 and ADR-0003.
# Enforces minimal scopes and prevents broad scope usage without ADR.
#
# Features:
# - Define and enforce minimal scopes
# - Request scope escalation with ADR reference
# - Check current granted scopes
#
# Usage:
#   from aria.agents.workspace.scope_manager import ScopeManager
#
#   sm = ScopeManager(oauth_helper)
#   current = sm.current("primary")
#   if needs_new_scope(current, new_requested):
#       ticket = sm.request_escalation(new_scopes, "reason for needing")

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.agents.workspace.oauth_helper import GoogleOAuthHelper

# === Constants ===

# Baseline scopes per blueprint §12.2 (read-first)
MINIMAL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations.readonly",
]

# Broad scopes that require explicit ADR
BROAD_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail",  # full gmail
    "https://www.googleapis.com/auth/calendar",  # full calendar
    "https://www.googleapis.com/auth/drive",  # full drive
    "https://www.googleapis.com/auth/presentations",  # full Slides read/write
]

_BROAD_SCOPE_SET = set(BROAD_SCOPES)


# === Exceptions ===


class ScopeEscalationError(Exception):
    """Raised when scope escalation is attempted without proper ADR."""

    pass


class UnauthorizedScopeError(Exception):
    """Raised when an unauthorized broad scope is detected."""

    pass


class ScopeCoherenceError(Exception):
    """Raised when runtime scopes don't match required scopes for enabled tools."""

    pass


# === Escalation Ticket ===


@dataclass
class EscalationTicket:
    """Represents a scope escalation request."""

    current_scopes: list[str]
    requested_scopes: list[str]
    reason: str
    adr_ref: str | None  # Must be set before proceeding
    approved: bool = False

    def requires_adr(self) -> bool:
        """Check if escalation requires an ADR."""
        return any(scope in _BROAD_SCOPE_SET for scope in self.requested_scopes)


# === Scope Manager ===


class ScopeManager:
    """Manages OAuth scope enforcement and escalation.

    Key rules per ADR-0003:
    - No broad scopes without explicit ADR reference
    - Scope escalation requires re-running oauth_first_setup.py
    - All scope grants are logged (not sensitive)
    """

    # Minimal scopes that can be used without escalation
    MINIMAL = MINIMAL_SCOPES

    def __init__(self, oauth_helper: GoogleOAuthHelper) -> None:
        """Initialize scope manager.

        Args:
            oauth_helper: GoogleOAuthHelper instance for token/scope operations
        """
        self._helper = oauth_helper

    def current(self, account: str = "primary") -> list[str]:
        """Get current granted scopes for account.

        Args:
            account: Account name (default: "primary")

        Returns:
            List of currently granted scope strings
        """
        return self._helper.get_scopes(account)

    def is_scope_broad(self, scope: str) -> bool:
        """Check if a scope is considered broad.

        Args:
            scope: Full OAuth scope URL

        Returns:
            True if scope is broad and requires ADR
        """
        return scope in _BROAD_SCOPE_SET

    def validate_scopes(self, scopes: list[str]) -> None:
        """Validate that scopes don't include unauthorized broad scopes.

        Args:
            scopes: List of scope URLs to validate

        Raises:
            UnauthorizedScopeError: If any scope is broad without ADR
        """
        for scope in scopes:
            if self.is_scope_broad(scope):
                raise UnauthorizedScopeError(
                    f"Broad scope '{scope}' requires explicit ADR approval. "
                    f"Use minimal scopes or request escalation via ScopeManager."
                )

    def request_escalation(
        self,
        new_scopes: list[str],
        reason: str,
        adr_ref: str | None = None,
        account: str = "primary",
    ) -> EscalationTicket:
        """Create an escalation ticket for new scopes.

        Args:
            new_scopes: List of scopes being requested
            reason: Business justification for the escalation
            adr_ref: Optional ADR reference (required for broad scopes)

        Returns:
            EscalationTicket (must have adr_ref set for broad scopes)

        Raises:
            ScopeEscalationError: If broad scopes without ADR reference
        """
        ticket = EscalationTicket(
            current_scopes=self.current(account),
            requested_scopes=new_scopes,
            reason=reason,
            adr_ref=adr_ref,
        )

        if ticket.requires_adr() and not adr_ref:
            raise ScopeEscalationError(
                f"Scope escalation requires ADR reference. "
                f"Requested scopes: {new_scopes}. "
                f"Create an ADR and pass adr_ref='ADR-XXXX' to request_escalation."
            )

        return ticket

    def check_or_raise(self, account: str = "primary") -> list[str]:
        """Get current scopes, raising if unauthorized broad scopes found.

        Args:
            account: Account name (default: "primary")

        Returns:
            Current scopes list

        Raises:
            UnauthorizedScopeError: If any granted scope is broad without ADR
        """
        scopes = self.current(account)
        self.validate_scopes(scopes)
        return scopes

    def check_scope_coherence(
        self,
        required_scopes: list[str],
        account: str = "primary",
    ) -> None:
        """Verify runtime scopes cover the required scopes for enabled tools.

        This check ensures that if a tool is enabled (via governance matrix),
        the runtime has the necessary OAuth scopes granted.

        Args:
            required_scopes: List of scopes required by enabled tools
            account: Account name (default: "primary")

        Raises:
            ScopeCoherenceError: If runtime scopes are missing required scopes

        Example:
            >>> sm = ScopeManager(oauth_helper)
            >>> required = [
            ...     "https://www.googleapis.com/auth/gmail.readonly",
            ...     "https://www.googleapis.com/auth/calendar.events",
            ... ]
            >>> sm.check_scope_coherence(required)
            # Raises ScopeCoherenceError if missing scopes
        """
        granted = set(self.current(account))
        required = set(required_scopes)

        missing = sorted(required - granted)
        if missing:
            raise ScopeCoherenceError(
                f"Missing OAuth scopes for enabled toolset: {', '.join(missing)}\n"
                f"Required scopes: {', '.join(sorted(required))}\n"
                f"Granted scopes: {', '.join(sorted(granted))}\n"
                f"To fix: Run 'python scripts/oauth_first_setup.py' to re-consent with new scopes."
            )


# === Exports ===

__all__ = [
    "ScopeManager",
    "ScopeEscalationError",
    "UnauthorizedScopeError",
    "ScopeCoherenceError",
    "EscalationTicket",
    "MINIMAL_SCOPES",
    "BROAD_SCOPES",
]
