"""Unit tests for email-draft style analyzer (email_style.py)."""

from __future__ import annotations

import pytest

from aria.agents.productivity.email_style import (
    StyleProfile,
    _avg_sentence_length,
    _build_style_profile,
    _extract_closing,
    _extract_greeting,
    _format_draft_body,
    _infer_pronoun,
    _infer_register,
    derive_style,
    draft_email,
)

# ─── Fixtures: sample thread data ───────────────────────────────────────────


@pytest.fixture
def formal_threads() -> list[dict]:
    """Sample threads with formal Italian style."""
    return [
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Egregio Dott. Rossi,\n\nLa ringrazio per la tempestiva risposta. "
                    "Rimango a disposizione per chiarimenti.\n\nCordiali saluti,\nFulvio",
                },
                {
                    "from": "mario@acme.com",
                    "body": "Grazie a lei. A presto.",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Gentile Dott. Rossi,\n\nLe allego i documenti richiesti. "
                    "Resto in attesa di un suo riscontro.\n\nDistinti saluti,\nFulvio",
                },
            ]
        },
    ]


@pytest.fixture
def cordial_threads() -> list[dict]:
    """Sample threads with cordial Italian style."""
    return [
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Ciao Mario,\n\ncome promesso ti invio il report "
                    "aggiornato. Fammi sapere se serve altro.\n\nA presto,\nFulvio",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Ciao Mario,\n\nsì, perfetto. Ti confermo l'appuntamento "
                    "per giovedì.\n\nA presto,\nFulvio",
                },
            ]
        },
    ]


@pytest.fixture
def technical_threads() -> list[dict]:
    """Sample threads with concise technical English style."""
    return [
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Hi Anna,\n\nThe API response format changed in v2. "
                    "Check the updated schema.\n\nBest,\nFulvio",
                },
            ]
        },
        {
            "messages": [
                {
                    "from": "fulvio@example.com",
                    "body": "Hi Anna,\n\nPR is merged. Deployment scheduled for "
                    "EOD.\n\nBest,\nFulvio",
                },
            ]
        },
    ]


class MockWorkspaceDelegate:
    """Mock workspace-agent for email style discovery."""

    def __init__(self, threads: list[dict] | None = None) -> None:
        self.threads = threads or []
        self.call_count = 0

    async def __call__(self, action: str, **kwargs: dict) -> dict:
        self.call_count += 1
        if action == "gmail.search":
            return {"threads": self.threads}
        if action == "gmail.get_thread":
            return {"messages": []}
        if action == "gmail.draft_create":
            return {"draft_id": "draft_mock_001", "status": "created"}
        return {}


# ─── Tests: style extraction helpers ────────────────────────────────────────


class TestExtractGreeting:
    def test_formal_greeting(self) -> None:
        body = "Egregio Dott. Rossi,\n\nLa ringrazio..."
        assert _extract_greeting(body) == "Egregio Dott. Rossi"

    def test_cordial_greeting(self) -> None:
        body = "Ciao Mario,\n\ncome promesso..."
        assert _extract_greeting(body) == "Ciao Mario"

    def test_english_greeting(self) -> None:
        body = "Hi Anna,\n\nThe API response..."
        assert _extract_greeting(body) == "Hi Anna"

    def test_no_greeting(self) -> None:
        body = "This is just a message without greeting."
        assert _extract_greeting(body) is None

    def test_empty_body(self) -> None:
        assert _extract_greeting("") is None


class TestExtractClosing:
    def test_formal_closing(self) -> None:
        body = "...Rimango a disposizione.\n\nCordiali saluti,\nFulvio"
        assert _extract_closing(body) == "Cordiali saluti"

    def test_cordial_closing(self) -> None:
        body = "...Fammi sapere.\n\nA presto,\nFulvio"
        assert _extract_closing(body) == "A presto"

    def test_english_closing(self) -> None:
        body = "...Check the schema.\n\nBest,\nFulvio"
        assert _extract_closing(body) == "Best"

    def test_no_closing(self) -> None:
        body = "Short message without closing."
        assert _extract_closing(body) is None


class TestInferPronoun:
    def test_formal_lei(self) -> None:
        body = "La ringrazio per la sua risposta. Le allego i documenti."
        assert _infer_pronoun(body) == "lei"

    def test_informal_tu(self) -> None:
        body = "Ciao, come stai? Ti invio il report."
        assert _infer_pronoun(body) == "tu"

    def test_english_you(self) -> None:
        body = "Hi, thank you for your reply."
        assert _infer_pronoun(body) == "you"

    def test_voi_form(self) -> None:
        body = "Vi ringrazio per la vostra collaborazione. Come vi avevo anticipato..."
        assert _infer_pronoun(body) == "voi"

    def test_empty(self) -> None:
        assert _infer_pronoun("") == "you"


class TestInferRegister:
    def test_formal(self) -> None:
        body = "La ringrazio per la tempestiva risposta. Resto a disposizione."
        assert _infer_register(body) == "formal"

    def test_cordial(self) -> None:
        body = "Ciao, come promesso ti invio il report. Fammi sapere!"
        assert _infer_register(body) == "cordial"

    def test_concise(self) -> None:
        body = "Done. Merged. Deploy EOD."
        assert _infer_register(body) == "concise"

    def test_technical(self) -> None:
        body = "The API endpoint returns 200 OK with JSON payload. Schema:"
        assert _infer_register(body) == "technical"

    def test_neutral_default(self) -> None:
        body = "Hi, here is the file. Let me know if you need anything."
        assert _infer_register(body) == "neutral"


class TestAvgSentenceLength:
    def test_short_sentences(self) -> None:
        text = "How are you? I am fine."
        assert _avg_sentence_length(text) == 3

    def test_long_sentences(self) -> None:
        text = "La ringrazio per la tempestiva risposta e resto a disposizione."
        result = _avg_sentence_length(text)
        assert result >= 5

    def test_empty(self) -> None:
        assert _avg_sentence_length("") == 0


# ─── Tests: StyleProfile building ──────────────────────────────────────────


class TestBuildStyleProfile:
    def test_formal_profile(self, formal_threads: list[dict]) -> None:
        profile = _build_style_profile("mario@acme.com", formal_threads)
        assert profile.recipient == "mario@acme.com"
        assert profile.sample_count == 2
        assert profile.register == "formal"
        assert profile.pronoun == "lei"
        assert profile.greeting is not None

    def test_cordial_profile(self, cordial_threads: list[dict]) -> None:
        profile = _build_style_profile("mario@acme.com", cordial_threads)
        assert profile.register == "cordial"
        assert profile.pronoun == "tu"

    def test_technical_profile(self, technical_threads: list[dict]) -> None:
        profile = _build_style_profile("anna@acme.com", technical_threads)
        assert profile.register == "technical"
        assert profile.pronoun == "you"

    def test_no_samples(self) -> None:
        profile = _build_style_profile("unknown@example.com", [])
        assert profile.sample_count == 0
        assert profile.register == "neutral"
        assert profile.pronoun == "you"
        assert profile.confidence < 0.5


# ─── Tests: derive_style ──────────────────────────────────────────────────


class TestDeriveStyle:
    @pytest.mark.asyncio
    async def test_derive_formal(self, formal_threads: list[dict]) -> None:
        delegate = MockWorkspaceDelegate(threads=formal_threads)
        profile = await derive_style("mario@acme.com", delegate, min_samples=2)
        assert isinstance(profile, StyleProfile)
        assert profile.recipient == "mario@acme.com"
        assert profile.register == "formal"
        assert profile.confidence >= 0.3

    @pytest.mark.asyncio
    async def test_derive_no_history(self) -> None:
        delegate = MockWorkspaceDelegate(threads=[])
        profile = await derive_style("unknown@example.com", delegate)
        assert profile.confidence < 0.5
        assert profile.register == "neutral"

    @pytest.mark.asyncio
    async def test_derive_below_min_samples(self) -> None:
        # Only 1 thread — below min_samples=3
        one_thread = [
            {
                "messages": [
                    {
                        "from": "fulvio@example.com",
                        "body": "Ciao,\n\nGrazie.\n\nA presto,\nFulvio",
                    }
                ]
            }
        ]
        delegate = MockWorkspaceDelegate(threads=one_thread)
        profile = await derive_style("mario@acme.com", delegate, min_samples=3)
        assert profile.confidence < 0.5


# ─── Tests: draft_email ────────────────────────────────────────────────────


class TestDraftEmail:
    @pytest.mark.asyncio
    async def test_draft_reply(self, formal_threads: list[dict]) -> None:
        delegate = MockWorkspaceDelegate(threads=formal_threads)
        draft = await draft_email(
            recipient="mario@acme.com",
            subject="Re: Q1 Budget Review",
            objective="Confermare ricezione documenti e proporre call",
            thread_id="thread_001",
            workspace_delegate=delegate,
        )
        assert isinstance(draft, str)
        assert len(draft) > 20
        # Should contain greeting
        assert any(g in draft for g in ["Egregio", "Gentile", "Ciao"])

    @pytest.mark.asyncio
    async def test_draft_new_email(self, cordial_threads: list[dict]) -> None:
        delegate = MockWorkspaceDelegate(threads=cordial_threads)
        draft = await draft_email(
            recipient="mario@acme.com",
            subject="Proposta collaborazione Q3",
            objective="Proporre nuova collaborazione trimestrale",
            thread_id=None,
            workspace_delegate=delegate,
        )
        assert isinstance(draft, str)
        assert len(draft) > 20


class TestFormatDraftBody:
    def test_format_with_greeting(self) -> None:
        body = _format_draft_body(
            greeting="Ciao Mario",
            body_text="come promesso ti invio il report aggiornato.",
            closing="A presto",
            signature="Fulvio",
        )
        assert body.startswith("Ciao Mario")
        assert "come promesso" in body
        assert "A presto" in body
        assert "Fulvio" in body

    def test_format_no_greeting(self) -> None:
        body = _format_draft_body(
            greeting=None,
            body_text="Here is the report.",
            closing="Best",
            signature="Fulvio",
        )
        assert body.startswith("Here is the report.")
        assert "Best" in body
