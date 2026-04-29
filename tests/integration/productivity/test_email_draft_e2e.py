"""E2E integration tests for email-draft workflow with mock workspace-agent.

Tests the full flow: gmail.search → style discovery → draft body → HITL
approval pattern → gmail.draft_create.
"""

from __future__ import annotations

import pytest

from aria.agents.productivity.email_style import (
    StyleProfile,
    derive_style,
    draft_email,
)


@pytest.fixture
def mock_formal_threads() -> list[dict]:
    """Cordiali thread con stile formale italiano."""
    return [
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Egregio Dott. Bianchi,\n\nLa ringrazio per la tempestiva "
                    "risposta. Rimango a disposizione per eventuali chiarimenti.\n\n"
                    "Cordiali saluti,\nFulvio",
                },
                {
                    "from": "luigi@acme.com",
                    "body": "Grazie a lei. Procediamo come concordato.",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Gentile Dott. Bianchi,\n\nLe allego i documenti richiesti. "
                    "Resto in attesa di un suo gentile riscontro.\n\nDistinti saluti,\nFulvio",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Egregio Dott. Bianchi,\n\nla ringrazio per l'aggiornamento. "
                    "Confermo la ricezione.\n\nCordiali saluti,\nFulvio",
                },
            ]
        },
    ]


@pytest.fixture
def mock_cordial_threads() -> list[dict]:
    """Thread con stile cordiale italiano."""
    return [
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Ciao Luca,\n\ncome promesso ti invio la documentazione "
                    "aggiornata. Fammi sapere se hai domande.\n\nA presto,\nFulvio",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Ciao Luca,\n\nti confermo l'appuntamento per giovedì "
                    "alle 15:00. A presto!\n\nA presto,\nFulvio",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Ciao Luca,\n\ngrazie mille per il feedback. Ti aggiorno "
                    "appena ho novità.\n\nA presto,\nFulvio",
                },
            ]
        },
    ]


class MockWorkspaceDelegate:
    """Mock workspace-agent for E2E email-draft testing.

    Simulates gmail.search, gmail.get_thread, gmail.draft_create.
    Records calls for assertions.
    """

    def __init__(self, threads: list[dict]) -> None:
        self.threads = threads
        self.calls: list[tuple[str, dict]] = []
        self.draft_created = False
        self.last_draft_args: dict = {}

    async def __call__(self, action: str, **kwargs: dict) -> dict:
        self.calls.append((action, kwargs))
        if action == "gmail.search":
            return {"threads": self.threads}
        if action == "gmail.get_thread":
            return self.threads[0] if self.threads else {}
        if action == "gmail.draft_create":
            self.draft_created = True
            self.last_draft_args = kwargs
            return {"draft_id": "draft_e2e_001", "status": "created", "id": "draft_e2e_001"}
        return {}


class TestEmailDraftE2E:
    """E2E tests simulating real email-draft flow."""

    @pytest.mark.asyncio
    async def test_formal_recipient_draft(self, mock_formal_threads: list[dict]) -> None:
        """Verify formal style is correctly detected and applied."""
        delegate = MockWorkspaceDelegate(threads=mock_formal_threads)

        # Step 1: Derive style
        profile = await derive_style("luigi@acme.com", delegate, min_samples=2)
        assert isinstance(profile, StyleProfile)
        assert profile.register == "formal"
        assert profile.pronoun == "lei"
        assert profile.sample_count >= 2

        # Step 2: Generate draft with discovered style
        draft = await draft_email(
            recipient="luigi@acme.com",
            subject="Proposta collaborazione Q3",
            objective="Proporre revisione contratto trimestrale",
            workspace_delegate=delegate,
        )
        assert isinstance(draft, str)
        assert len(draft) > 30

        # Verify draft matches formal style
        assert "Egregio" in draft or "Gentile" in draft, "Formal greeting expected"

    @pytest.mark.asyncio
    async def test_cordial_recipient_draft(self, mock_cordial_threads: list[dict]) -> None:
        """Verify cordial style is correctly detected and applied."""
        delegate = MockWorkspaceDelegate(threads=mock_cordial_threads)

        profile = await derive_style("luca@example.com", delegate, min_samples=2)
        assert profile.register == "cordial"
        assert profile.pronoun == "tu"

        draft = await draft_email(
            recipient="luca@example.com",
            subject="Aggiornamento progetto",
            objective="Fornire aggiornamento sullo stato del progetto",
            workspace_delegate=delegate,
        )
        assert isinstance(draft, str)
        assert "Ciao" in draft or "ciao" in draft.lower(), "Cordial greeting expected"

    @pytest.mark.asyncio
    async def test_unknown_recipient_fallback(self) -> None:
        """Verify unknown recipient gets neutral cordial fallback."""
        delegate = MockWorkspaceDelegate(threads=[])

        profile = await derive_style("unknown@example.com", delegate)
        assert profile.sample_count == 0
        assert profile.confidence < 0.5
        assert profile.register == "neutral"

        draft = await draft_email(
            recipient="unknown@example.com",
            subject="Introduction",
            objective="Introducing myself and our services",
            workspace_delegate=delegate,
        )
        assert isinstance(draft, str)
        assert len(draft) > 20

    @pytest.mark.asyncio
    async def test_draft_create_flow(self, mock_formal_threads: list[dict]) -> None:
        """Verify full flow: style → draft → workspace-agent draft_create."""
        delegate = MockWorkspaceDelegate(threads=mock_formal_threads)

        # Derive style
        profile = await derive_style("luigi@acme.com", delegate, min_samples=2)
        assert profile.register == "formal"

        # Generate draft
        draft_body = await draft_email(
            recipient="luigi@acme.com",
            subject="Q3 Planning",
            objective="Discuss Q3 planning and milestones",
            workspace_delegate=delegate,
        )

        # Simulate HITL approval and draft creation via workspace-agent
        draft_result = await delegate(
            "gmail.draft_create",
            to="luigi@acme.com",
            subject="Q3 Planning",
            body=draft_body,
        )
        assert delegate.draft_created
        assert draft_result.get("draft_id") == "draft_e2e_001"
        assert draft_result.get("status") == "created"

        # Verify workspace-agent was called in correct sequence
        actions = [call[0] for call in delegate.calls]
        assert actions[0] == "gmail.search", "First call should be style discovery"
        assert actions[-1] == "gmail.draft_create", "Last call should create draft"

    @pytest.mark.asyncio
    async def test_style_profile_not_persisted(self) -> None:
        """Verify style profile is NOT saved to wiki (Q7 mandate)."""
        delegate = MockWorkspaceDelegate(threads=[])
        profile = await derive_style("test@example.com", delegate)
        # The profile is in-memory only, no wiki write
        assert isinstance(profile, StyleProfile)
        # No wiki recall/update calls were made
        assert len(delegate.calls) > 0, "Should have called workspace-agent"
        # Only gmail.search call, no wiki_update
        actions = [call[0] for call in delegate.calls]
        assert all("wiki" not in a for a in actions), (
            "Style profile should not involve wiki operations"
        )
