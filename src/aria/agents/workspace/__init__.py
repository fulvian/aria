# ARIA workspace agents module

from aria.agents.workspace.oauth_helper import (
    GoogleOAuthHelper,
    OAuthError,
    OAuthSetupRequired,
)
from aria.agents.workspace.multi_account import MultiAccountRegistry, WorkspaceAccount
from aria.agents.workspace.scope_manager import (
    EscalationTicket,
    ScopeEscalationError,
    ScopeManager,
    UnauthorizedScopeError,
)

__all__ = [
    "GoogleOAuthHelper",
    "OAuthSetupRequired",
    "OAuthError",
    "WorkspaceAccount",
    "MultiAccountRegistry",
    "ScopeManager",
    "ScopeEscalationError",
    "UnauthorizedScopeError",
    "EscalationTicket",
]
