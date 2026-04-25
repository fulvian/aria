# Context Lifecycle Manager (CLM)
#
# Per blueprint §5.4 and sprint plan W1.1.K.
#
# In Sprint 1.1, implements ONLY extractive distillation WITHOUT LLM calls.
# Mock deterministic extractive baseline for distillation.
#
# Strategy:
# 1. Retrieve episodic entries for session/time range
# 2. Extract candidate chunks via rules:
#    - user_input with key verbs (ricorda, preferisco, voglio, deciso) → kind preference/decision
#    - Pattern <entita> <relazione> <valore> → kind fact
#    - Pattern "devo X", "ricordami di Y" → kind action_item
# 3. Generate SemanticChunk with source_episodic_ids
# 4. Aggregate actor via actor_aggregate
# 5. Confidence = actor_trust_score * keyword_match_ratio
#
# P5 rules: Never infer on tool_output without explicit confirmation.
#
# Usage:
#   from aria.memory.clm import CLM
#
#   clm = CLM(store, semantic_store)
#   chunks = await clm.distill_session(session_id)

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from aria.memory.actor_tagging import actor_trust_score
from aria.memory.schema import Actor, EpisodicEntry, SemanticChunk

if TYPE_CHECKING:
    from uuid import UUID

    from aria.memory.episodic import EpisodicStore
    from aria.memory.semantic import SemanticStore

# === Extractive Patterns ===

# Preference/decision keywords (Italian + English for MVP)
PREFERENCE_KEYWORDS = [
    "ricorda",
    "preferisco",
    "voglio",
    "deciso",
    "ho deciso",
    "ricordami",
    "mi piace",
    "non mi piace",
    "remember",
    "prefer",
    "want",
    "decided",
    "like",
    "dislike",
]

# Action item patterns
ACTION_ITEM_PATTERNS = [
    r"devo\s+",
    r"bisogna\s+",
    r"farò\s+",
    r"ricordami\s+di",
    r"mi serve\s+",
    r"ho bisogno\s+",
    r"need to\s+",
    r"must\s+",
    r"should\s+",
]

# Fact patterns: <entity> <relation> <value>
FACT_PATTERNS = [
    r"è\s+\w+\s+(di|che|a|in|per|con)",  # Entity is related to
    r"il\s+\w+\s+è\s+",
    r"la\s+\w+\s+è\s+",  # The X is Y
    r"si chiama\s+",
    r"ha\s+\d+\s+",  # Named / has N
]


# === CLM ===


class CLM:
    """Context Lifecycle Manager.

    Distills episodic entries into semantic chunks using extractive rules.
    Does NOT make LLM calls in Sprint 1.1.
    """

    def __init__(self, store: EpisodicStore, semantic: SemanticStore) -> None:
        """Initialize CLM.

        Args:
            store: EpisodicStore (T0)
            semantic: SemanticStore (T1)
        """
        self._store = store
        self._semantic = semantic

    async def distill_session(
        self,
        session_id: UUID,
        force: bool = False,
    ) -> list[SemanticChunk]:
        """Distill a session's episodic entries into semantic chunks.

        Args:
            session_id: Session to distill
            force: If True, re-process even if already distilled

        Returns:
            List of new SemanticChunk
        """
        # Get all episodic entries for session
        entries = await self._store.list_by_session(session_id, limit=500)

        if not entries:
            return []

        # Check for existing chunks (skip if not forcing)
        if not force:
            existing = await self._semantic.list_by_session(session_id, limit=1)
            if existing:
                # Already distilled
                return []

        # Distill entries
        chunks = self._distill_entries(entries)

        # Insert into semantic store
        if chunks:
            await self._semantic.insert_many(chunks)

        return chunks

    async def distill_range(
        self,
        since: datetime,
        until: datetime,
    ) -> list[SemanticChunk]:
        """Distill entries in a time range.

        Args:
            since: Start time
            until: End time

        Returns:
            List of new SemanticChunk
        """
        entries = await self._store.list_by_time_range(since, until, limit=500)

        if not entries:
            return []

        chunks = self._distill_entries(entries)

        if chunks:
            await self._semantic.insert_many(chunks)

        return chunks

    async def promote(self, chunk_id: UUID) -> None:
        """Promote a chunk (HITL approved → confidence=1.0).

        Args:
            chunk_id: Chunk to promote
        """
        await self._semantic.promote(chunk_id)

    async def demote(self, chunk_id: UUID) -> None:
        """Demote a chunk (error flagged → confidence-=0.3).

        Args:
            chunk_id: Chunk to demote
        """
        await self._semantic.demote(chunk_id)

    # === Private Extractives ===

    def _distill_entries(self, entries: list[EpisodicEntry]) -> list[SemanticChunk]:
        """Distill episodic entries into semantic chunks.

        Extracts chunks using rule-based patterns per sprint plan.

        Args:
            entries: Episodic entries to process

        Returns:
            List of SemanticChunk
        """
        chunks: list[SemanticChunk] = []
        now = datetime.now(UTC)

        # Group by session for context
        by_session: dict[UUID, list[EpisodicEntry]] = {}
        for entry in entries:
            if entry.session_id not in by_session:
                by_session[entry.session_id] = []
            by_session[entry.session_id].append(entry)

        for _session_id, session_entries in by_session.items():
            # Process in chronological order
            session_entries.sort(key=lambda e: e.ts)

            for entry in session_entries:
                # Only process USER_INPUT for preferences/decisions per P5
                if entry.actor != Actor.USER_INPUT:
                    continue

                entry_chunks = self._extract_from_entry(entry, now)
                chunks.extend(entry_chunks)

        # Deduplicate by source_episodic_ids + text
        seen: set[tuple[str, str]] = set()
        unique_chunks: list[SemanticChunk] = []
        for chunk in chunks:
            key = (
                str(chunk.source_episodic_ids[0]) if chunk.source_episodic_ids else "",
                chunk.text[:50],
            )
            if key not in seen:
                seen.add(key)
                unique_chunks.append(chunk)

        return unique_chunks

    def _extract_from_entry(
        self,
        entry: EpisodicEntry,
        now: datetime,
    ) -> list[SemanticChunk]:
        """Extract semantic chunks from a single entry.

        Args:
            entry: EpisodicEntry to process
            now: Current timestamp

        Returns:
            List of SemanticChunk (may be empty)
        """
        chunks: list[SemanticChunk] = []
        content_lower = entry.content.lower()

        # Check for action items
        for pattern in ACTION_ITEM_PATTERNS:
            if re.search(pattern, content_lower):
                chunks.append(
                    self._make_chunk(
                        source_ids=[entry.id],
                        actor=entry.actor,
                        kind="action_item",
                        text=entry.content,
                        now=now,
                    )
                )
                break  # One chunk per entry for action items

        # Check for preference/decision keywords
        for keyword in PREFERENCE_KEYWORDS:
            if keyword in content_lower:
                kind: Literal["preference", "decision"] = "preference"
                if "deciso" in content_lower or "decided" in content_lower:
                    kind = "decision"

                chunks.append(
                    self._make_chunk(
                        source_ids=[entry.id],
                        actor=entry.actor,
                        kind=kind,
                        text=entry.content,
                        now=now,
                    )
                )
                break

        # Check for fact patterns
        for pattern in FACT_PATTERNS:
            if re.search(pattern, content_lower):
                chunks.append(
                    self._make_chunk(
                        source_ids=[entry.id],
                        actor=entry.actor,
                        kind="fact",
                        text=entry.content,
                        now=now,
                    )
                )
                break

        return chunks

    def _make_chunk(
        self,
        source_ids: list[UUID],
        actor: Actor,
        kind: Literal["fact", "preference", "decision", "action_item", "concept"],
        text: str,
        now: datetime,
    ) -> SemanticChunk:
        """Create a SemanticChunk with computed confidence.

        Confidence = actor_trust_score * keyword_match_ratio

        Args:
            source_ids: Source T0 entry IDs
            actor: Actor for this chunk
            kind: Chunk type
            text: Distilled text
            now: Current timestamp

        Returns:
            SemanticChunk with confidence
        """
        # Calculate keyword match ratio
        content_lower = text.lower()
        keyword_matches = sum(1 for kw in PREFERENCE_KEYWORDS if kw in content_lower)
        match_ratio = min(1.0, keyword_matches / 3)  # normalize to 0-1

        # Base confidence from actor trust
        base_confidence = actor_trust_score(actor)

        # Combined confidence
        confidence = base_confidence * (0.5 + 0.5 * match_ratio)  # 0.5-1.0 range

        return SemanticChunk(
            source_episodic_ids=source_ids,
            actor=actor,
            kind=kind,
            text=text,
            keywords=self._extract_keywords(text),
            confidence=confidence,
            first_seen=now,
            last_seen=now,
        )

    def _extract_keywords(self, text: str, max_kw: int = 5) -> list[str]:
        """Extract keywords from text (simple rule-based).

        Args:
            text: Text to extract from
            max_kw: Maximum keywords to return

        Returns:
            List of keywords
        """
        # Simple extraction: words > 4 chars, not stopwords
        stopwords = {
            "il",
            "la",
            "lo",
            "gli",
            "le",
            "un",
            "una",
            "di",
            "a",
            "da",
            "è",
            "sono",
            "era",
            "eri",
            "eravamo",
            "e",
            "o",
            "ma",
            "perché",
            "che",
            "con",
            "in",
            "su",
            "questo",
            "quello",
            "mia",
            "mio",
            "the",
            "an",
            "and",
            "or",
            "but",
            "on",
            "at",
            "to",
        }

        words = re.findall(r"\b\w{5,}\b", text.lower())
        return [w for w in words if w not in stopwords][:max_kw]
