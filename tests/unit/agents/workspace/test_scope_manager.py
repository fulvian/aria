from __future__ import annotations

from typing import Any

import pytest

from aria.agents.workspace.scope_manager import (
    ScopeCoherenceError,
    ScopeEscalationError,
    ScopeManager,
)


class _Helper:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_scopes(self, account: str = "primary") -> list[str]:
        self.calls.append(account)
        return ["https://www.googleapis.com/auth/gmail.readonly"]


def test_is_scope_broad_exact_match() -> None:
    helper: Any = _Helper()
    manager = ScopeManager(helper)

    assert manager.is_scope_broad("https://www.googleapis.com/auth/drive")
    assert not manager.is_scope_broad("https://www.googleapis.com/auth/drive.file")


def test_request_escalation_uses_account() -> None:
    helper: Any = _Helper()
    manager = ScopeManager(helper)

    manager.request_escalation(
        ["https://www.googleapis.com/auth/gmail.readonly"],
        reason="need read scope",
        account="team-a",
    )

    assert helper.calls == ["team-a"]


def test_request_escalation_broad_scope_requires_adr() -> None:
    helper: Any = _Helper()
    manager = ScopeManager(helper)

    with pytest.raises(ScopeEscalationError):
        manager.request_escalation(
            ["https://www.googleapis.com/auth/drive"],
            reason="need full drive",
        )


def test_check_scope_coherence_passes_when_required_scopes_granted() -> None:
    helper: Any = _Helper()
    manager = ScopeManager(helper)

    manager.check_scope_coherence(
        [
            "https://www.googleapis.com/auth/gmail.readonly",
        ]
    )


def test_check_scope_coherence_raises_on_missing_scopes() -> None:
    helper: Any = _Helper()
    manager = ScopeManager(helper)

    with pytest.raises(ScopeCoherenceError):
        manager.check_scope_coherence(
            [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/calendar.events",
            ]
        )
