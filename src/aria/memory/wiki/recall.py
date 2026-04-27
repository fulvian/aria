# ARIA Memory Wiki — FTS5 Recall Engine
#
# Per docs/plans/auto_persistence_echo.md §6.2.
#
# FTS5 search with score thresholding for wiki page recall.
# Returns scored results capped by token budget.
#
# Usage:
#   from aria.memory.wiki.recall import WikiRecallEngine
#   engine = WikiRecallEngine(store)
#   results = await engine.recall("memory system design", max_pages=5, min_score=0.3)

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aria.memory.wiki.schema import Page, PageKind

if TYPE_CHECKING:
    from aria.memory.wiki.db import WikiStore

logger = logging.getLogger(__name__)

# === Token estimation ===

_APPROX_CHARS_PER_TOKEN = 4  # Conservative estimate for English text
_DEFAULT_MAX_BODY_CHARS = 500  # First paragraph / excerpt


@dataclass
class RecallResult:
    """A single recall result with relevance score."""

    kind: PageKind
    slug: str
    title: str
    body_excerpt: str
    score: float
    page_id: str = ""

    @property
    def estimated_tokens(self) -> int:
        """Estimate token count for this result."""
        total_chars = len(self.title) + len(self.body_excerpt) + len(self.slug)
        return max(1, total_chars // _APPROX_CHARS_PER_TOKEN)


class WikiRecallEngine:
    """FTS5-based recall engine for wiki pages.

    Per plan §6.2: FTS5 against user message, returns scored pages
    capped by token budget.
    """

    def __init__(self, store: WikiStore) -> None:
        """Initialize recall engine.

        Args:
            store: WikiStore instance for database access.
        """
        self._store = store

    async def recall(
        self,
        query: str,
        max_pages: int = 5,
        min_score: float = 0.3,
        max_tokens: int = 2000,
        kind_filter: PageKind | None = None,
    ) -> list[RecallResult]:
        """Search wiki pages using FTS5.

        Args:
            query: Search query (user message or topic).
            max_pages: Maximum number of pages to return.
            min_score: Minimum FTS5 rank score (normalized 0-1).
            max_tokens: Total token budget for results.
            kind_filter: Optional filter by page kind.

        Returns:
            List of RecallResult sorted by score descending.
        """
        conn = await self._store._ensure_connected()

        # Build FTS5 query
        fts_query = self._sanitize_fts_query(query)
        if not fts_query:
            return []

        # Execute FTS5 search with ranking
        sql = """
            SELECT p.id, p.kind, p.slug, p.title, p.body_md,
                   bm25(page_fts) as rank
            FROM page_fts
            JOIN page p ON page_fts.slug = p.slug AND page_fts.kind = p.kind
            WHERE page_fts MATCH ?
        """
        params: list[object] = [fts_query]

        if kind_filter:
            sql += " AND p.kind = ?"
            params.append(kind_filter.value)

        sql += " ORDER BY rank LIMIT ?"
        params.append(max_pages * 2)  # Fetch extra for score filtering

        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
        except Exception as exc:
            logger.warning("FTS5 search failed: %s", exc)
            return []

        if not rows:
            return []

        # Normalize scores: bm25 returns negative values (more negative = better match)
        # Convert to 0-1 range where 1 = best match
        raw_scores = [row["rank"] for row in rows]
        if not raw_scores:
            return []

        best_score = min(raw_scores)  # Most negative = best
        worst_score = max(raw_scores)  # Least negative = worst
        score_range = worst_score - best_score if worst_score != best_score else 1.0

        results: list[RecallResult] = []
        total_tokens = 0

        for row in rows:
            # Normalize: 1.0 for best, 0.0 for worst
            if score_range == 0:
                normalized = 1.0
            else:
                normalized = (row["rank"] - worst_score) / score_range
                # Invert since bm25 negative: more negative = better
                normalized = abs(normalized)
                normalized = round(normalized, 3)

            if normalized < min_score:
                continue

            # Create excerpt from body
            body = row["body_md"] or ""
            excerpt = self._truncate_to_excerpt(body)

            result = RecallResult(
                kind=PageKind(row["kind"]),
                slug=row["slug"],
                title=row["title"],
                body_excerpt=excerpt,
                score=normalized,
                page_id=row["id"],
            )

            # Check token budget
            estimated = result.estimated_tokens
            if total_tokens + estimated > max_tokens:
                # Try truncating further
                if total_tokens < max_tokens:
                    remaining = max_tokens - total_tokens
                    max_chars = remaining * _APPROX_CHARS_PER_TOKEN
                    result.body_excerpt = result.body_excerpt[:max_chars] + "..."
                    results.append(result)
                break

            results.append(result)
            total_tokens += estimated

        return results

    async def get_profile(self) -> Page | None:
        """Get the user profile page.

        Per plan §6.1: profile is always-on, auto-injected into conductor prompt.
        """
        return await self._store.get_page(PageKind.PROFILE, "profile")

    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize a query string for FTS5 MATCH.

        FTS5 has special syntax. We strip dangerous characters but
        preserve quoted phrases and basic operators.

        Args:
            query: Raw search query.

        Returns:
            Sanitized FTS5 query string.
        """
        if not query or not query.strip():
            return ""

        # Strip control characters
        cleaned = query.strip()

        # Remove characters that could break FTS5 syntax
        # Keep: alphanumeric, spaces, quotes, asterisks, hyphens, underscores
        import re

        cleaned = re.sub(r"[^\w\s*\"'-]", " ", cleaned)

        # Split into tokens and rejoin with OR (match any word)
        tokens = cleaned.split()
        if not tokens:
            return ""

        # Simple: join tokens with OR for broad matching
        return " OR ".join(f'"{t}"' for t in tokens[:20])  # Cap at 20 terms

    def _truncate_to_excerpt(self, body: str) -> str:
        """Truncate body to a reasonable excerpt.

        Returns first paragraph up to DEFAULT_MAX_BODY_CHARS.
        """
        if not body:
            return ""

        # Find first paragraph break
        paragraphs = body.split("\n\n")
        first_para = paragraphs[0] if paragraphs else body

        if len(first_para) > _DEFAULT_MAX_BODY_CHARS:
            return first_para[:_DEFAULT_MAX_BODY_CHARS] + "..."

        return first_para
