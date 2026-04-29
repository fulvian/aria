"""Email-draft style analyzer — dynamic style discovery per Q7.

Analizza runtime le conversazioni Gmail con un recipient per derivare
un profilo di stile (saluto, chiusura, pronome, registro). Il profilo
è transitorio (per-session, mai salvato in wiki).

Q7 mandate: NO lesson statica, NO bootstrap utente.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)

# Type alias for workspace delegate callable
WorkspaceDelegate = Callable[..., Any]

Pronoun = Literal["tu", "lei", "voi", "you"]
Register = Literal["formal", "cordial", "concise", "technical", "neutral"]

# Common greeting patterns (first line of body)
GREETING_RE = re.compile(
    r"^(?:Egregio|Gentile|Spett\.?le|Ciao|Buongiorno|Buonasera|Salve|Hi|Hello|Dear|Hey)"
    r"(?:[^,])*?,\s*",
    re.MULTILINE,
)

# Closing patterns (last line before signature)
CLOSING_RE = re.compile(
    r"(?:"
    r"Cordiali saluti|Distinti saluti|A presto|A dopo|A piu tardi|"
    r"Grazie mille|Grazie|"
    r"Best|Best regards|Thanks|Thank you|Cheers|Sincerely|Regards"
    r")\s*,?\s*$",
    re.MULTILINE,
)

# Pronoun markers
PRONOUN_MARKERS: dict[Pronoun, list[str]] = {
    "lei": ["la ringrazio", "le allego", "la sua", "le invio", "la prego", "la saluto"],
    "tu": [
        "ti ringrazio",
        "ti allego",
        "ti invio",
        "ti confermo",
        "ti aggiorno",
        "ti mando",
        "ti scrivo",
        "ti chiedo",
        "ti dico",
        "ti faccio",
        "tuo",
        "tua",
        "tuoi",
        "tue",
        "come stai",
    ],
    "voi": ["vi ringrazio", "vi allego", "vi invio", "vostro", "vostra", "come state"],
    "you": ["thank you", "you", "your", "please", "thanks"],
}

# Register heuristics
REGISTER_MARKERS: dict[Register, list[str]] = {
    "formal": [
        "la ringrazio",
        "cordiali saluti",
        "distinti saluti",
        "egregio",
        "gentile",
        "spettabile",
        "a disposizione",
        "sua risposta",
    ],
    "cordial": [
        "ciao",
        "a presto",
        "fammi sapere",
        "grazie mille",
        "come promesso",
        "ti invio",
        "perfetto",
    ],
    "concise": [
        "done",
        "merged",
        "deploy",
        "eod",
        "wip",
        "fyi",
        "asap",
        "tbd",
        "n/a",
    ],
    "technical": [
        "api",
        "endpoint",
        "schema",
        "json",
        "response",
        "payload",
        "status",
        "deploy",
        "merge",
        "commit",
        "branch",
        "config",
        "error",
        "debug",
    ],
}


@dataclass
class StyleProfile:
    """Derived communication style for a specific recipient.

    Built at runtime per-recipient, never persisted to wiki (Q7).
    """

    recipient: str
    sample_count: int
    greeting: str | None = None
    closing: str | None = None
    pronoun: Pronoun = "you"
    register: Register = "neutral"
    avg_sentence_len_words: int = 0
    confidence: float = 0.0
    signature: str = ""


async def derive_style(
    recipient: str,
    workspace_delegate: WorkspaceDelegate,
    lookback_days: int = 365,
    min_samples: int = 3,
) -> StyleProfile:
    """Derive a communication style profile for a recipient.

    Searches Gmail for recent conversations with the recipient,
    extracts style markers, and builds a :class:`StyleProfile`.

    Args:
        recipient: Email address of the recipient.
        workspace_delegate: Callable that proxies workspace-agent.
        lookback_days: Days to look back for conversations (default 365).
        min_samples: Minimum thread count for high confidence (default 3).

    Returns:
        A :class:`StyleProfile` with style markers and confidence score.
    """
    try:
        result = await workspace_delegate(
            "gmail.search",
            query=f"to:{recipient} OR from:{recipient}",
            lookback_days=lookback_days,
        )
        threads = result.get("threads", [])
    except Exception as e:
        logger.warning("Failed to search email for %s: %s", recipient, e)
        threads = []

    if not threads:
        return StyleProfile(
            recipient=recipient,
            sample_count=0,
            confidence=0.0,
        )

    profile = _build_style_profile(recipient, threads)

    # Adjust confidence based on sample count
    if profile.sample_count >= min_samples:
        profile.confidence = min(0.9, profile.confidence)
    else:
        profile.confidence = min(0.4, profile.confidence)

    return profile


async def draft_email(
    recipient: str,
    subject: str,
    objective: str,
    workspace_delegate: WorkspaceDelegate,
    thread_id: str | None = None,
) -> str:
    """Draft an email body matching the discovered style for a recipient.

    This function is designed to be called from the ``email-draft`` skill.
    It returns the email body text; the skill is responsible for HITL
    confirmation and Gmail draft creation via workspace-agent.

    Args:
        recipient: Email address of the recipient.
        subject: Email subject line.
        objective: Purpose or context for the email.
        workspace_delegate: Callable that proxies workspace-agent.
        thread_id: Optional thread ID for replies.

    Returns:
        Draft email body as a string.
    """
    # Discover style
    profile = await derive_style(recipient, workspace_delegate)

    # Build context-aware body
    body_lines: list[str] = []

    if profile.sample_count == 0:
        # No history — neutral cordial default
        greeting = "Ciao"
        closing = "A presto"
        pronoun_hint = "tu"
    else:
        greeting = profile.greeting or "Ciao"
        closing = profile.closing or "A presto"
        pronoun_hint = profile.pronoun

    # Compose context-aware body
    context = _build_context_message(objective, pronoun_hint)
    body_lines.append(context)

    return _format_draft_body(
        greeting=greeting,
        body_text=" ".join(body_lines),
        closing=closing,
        signature="",
    )


def _build_style_profile(recipient: str, threads: list[dict]) -> StyleProfile:
    """Build a StyleProfile from a list of thread dicts."""
    greetings: list[str] = []
    closings: list[str] = []
    pronouns: list[str] = []
    registers: list[str] = []
    sentence_lengths: list[int] = []

    for thread in threads:
        messages = thread.get("messages", [])
        for msg in messages:
            if msg.get("from", "").startswith("fulvio"):
                body = msg.get("body", "")

                greeting = _extract_greeting(body)
                if greeting:
                    greetings.append(greeting)

                closing = _extract_closing(body)
                if closing:
                    closings.append(closing)

                pronouns.append(_infer_pronoun(body))
                registers.append(_infer_register(body))

                sl = _avg_sentence_length(body)
                if sl > 0:
                    sentence_lengths.append(sl)

    if not greetings and not closings:
        return StyleProfile(recipient=recipient, sample_count=len(threads))

    # Take most common greeting/closing
    most_common_greeting = _most_common(greetings) if greetings else None
    most_common_closing = _most_common(closings) if closings else None
    most_common_pronoun = _most_common(pronouns) if pronouns else "you"
    most_common_register = _most_common(registers) if registers else "neutral"

    avg_sl = int(sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0

    # Confidence based on consistency and sample count
    consistency = _compute_consistency(pronouns, registers)
    confidence = min(0.8, 0.3 + (len(threads) / 10) + consistency)

    return StyleProfile(
        recipient=recipient,
        sample_count=len(threads),
        greeting=most_common_greeting,
        closing=most_common_closing,
        pronoun=cast("Pronoun", most_common_pronoun),
        register=cast("Register", most_common_register),
        avg_sentence_len_words=avg_sl,
        confidence=round(confidence, 2),
    )


def _extract_greeting(body: str) -> str | None:
    """Extract the greeting line from an email body."""
    if not body:
        return None
    match = GREETING_RE.search(body)
    if match:
        greeting = match.group(0).strip().rstrip(",").strip()
        return greeting if greeting else None
    return None


def _extract_closing(body: str) -> str | None:
    """Extract the closing phrase from an email body."""
    if not body:
        return None
    match = CLOSING_RE.search(body)
    if match:
        return match.group(0).strip().rstrip(",").strip()
    return None


def _infer_pronoun(body: str) -> Pronoun:
    """Infer pronoun usage from email body text."""
    body_lower = body.lower()

    # Check in priority order: lei, voi, tu, you
    for marker in PRONOUN_MARKERS["lei"]:
        if marker in body_lower:
            return "lei"

    for marker in PRONOUN_MARKERS["voi"]:
        if marker in body_lower:
            return "voi"

    for marker in PRONOUN_MARKERS["tu"]:
        if marker in body_lower:
            return "tu"

    # Default to 'you' for English or unknown
    return "you"


def _infer_register(body: str) -> Register:
    """Infer communication register from email body text."""
    body_lower = body.lower()

    # Score each register
    scores: dict[Register, int] = {
        "formal": 0,
        "cordial": 0,
        "concise": 0,
        "technical": 0,
        "neutral": 1,  # default bias
    }

    for register, markers in REGISTER_MARKERS.items():
        for marker in markers:
            if marker in body_lower:
                scores[register] += 1

    return max(scores, key=scores.__getitem__)


def _avg_sentence_length(text: str) -> int:
    """Calculate average sentence length in words."""
    if not text.strip():
        return 0

    # Split on sentence boundaries
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return 0

    total_words = sum(len(s.split()) for s in sentences)
    return int(total_words / len(sentences))


def _most_common(items: list[str]) -> str:
    """Return the most common item in a list."""
    if not items:
        return ""
    return max(set(items), key=items.count)


def _compute_consistency(pronouns: list[str], registers: list[str]) -> float:
    """Compute style consistency score (0.0-0.3) based on agreement."""
    score = 0.0
    if pronouns:
        most_common_pronoun = _most_common(pronouns)
        pronoun_consistency = pronouns.count(most_common_pronoun) / len(pronouns)
        score += pronoun_consistency * 0.15

    if registers:
        most_common_reg = _most_common(registers)
        reg_consistency = registers.count(most_common_reg) / len(registers)
        score += reg_consistency * 0.15

    return min(0.3, round(score, 2))


def _build_context_message(objective: str, pronoun_hint: str) -> str:
    """Build a context-aware body message from the objective."""
    # Simple heuristic: use objective as body, adapted for pronoun
    if pronoun_hint == "lei":
        return f"in merito a {objective.lower()}, Le scrivo per..."
    elif pronoun_hint == "voi":
        return f"in merito a {objective.lower()}, Vi scrivo per..."
    else:
        return f"in merito a {objective.lower()}, ti scrivo per..."


def _format_draft_body(
    greeting: str | None,
    body_text: str,
    closing: str,
    signature: str,
) -> str:
    """Format a complete email body from components.

    Args:
        greeting: Greeting line (e.g. "Ciao Mario"). May be None.
        body_text: Main body content.
        closing: Closing phrase (e.g. "A presto").
        signature: Signature line (e.g. "Fulvio").

    Returns:
        Formatted email body string.
    """
    parts: list[str] = []
    if greeting:
        parts.append(f"{greeting},")
        parts.append("")

    parts.append(body_text)
    parts.append("")

    if closing:
        parts.append(f"{closing},")
    if signature:
        parts.append(signature)

    return "\n".join(parts)
