# Intent Classification — Deterministic Keyword-Based
#
# Per blueprint §11.2: classifier is a mini-skill based on keyword + (optional)
# zero-shot LLM call on Haiku 4.5. This module implements the keyword-based
# classification without LLM calls (deterministic, no external dependencies).
#
# Usage:
#   from aria.agents.search.intent import classify_intent
#   intent = classify_intent("latest news about AI")

from __future__ import annotations

from typing import Final

from aria.agents.search.router import Intent

# === Keyword Sets ===

INTENT_KEYWORDS: dict[Intent, frozenset[str]] = {
    Intent.DEEP_SCRAPE: frozenset(
        {
            "deep",
            "scrape",
            "crawl",
            "extract",
            "full page",
            "complete",
            "entire website",
            "all pages",
            "deep scrape",
            "scraping",
            "estrai",
        }
    ),
    Intent.ACADEMIC: frozenset(
        {
            "academic",
            "research",
            "paper",
            "journal",
            "article",
            "study",
            "scholar",
            "citation",
            "doi",
            "arxiv",
            "publication",
            "preprint",
            "conference",
            "proceedings",
            # Nuovi v2:
            "pubmed",
            "pmid",
            "europe pmc",
            "europepmc",
            "openalex",
            "biorxiv",
            "scientific",
            "experiment",
            "clinical trial",
            "abstract",
            "peer review",
            "literature review",
            "mesh",
            # IT esistenti:
            "ricerca",
            "pubblicazione",
            "studio",
            "articolo scientifico",
        }
    ),
    Intent.GENERAL_NEWS: frozenset(
        {
            "news",
            "latest",
            "current",
            "recent",
            "breaking",
            "today",
            "headline",
            "update",
            "notizie",
            "ultime",
            "attualità",
            "novità",
        }
    ),
    Intent.SOCIAL: frozenset(
        {
            "reddit",
            "social media",
            "forum",
            "discussion",
            "community",
            "subreddit",
            "trending",
            "viral",
            "what people are saying",
            "public opinion",
            "reddit discussion",
            "hacker news",
        }
    ),
}

# Default intent when no keywords match
DEFAULT_INTENT: Final[Intent] = Intent.GENERAL_NEWS


def classify_intent(query: str) -> Intent:
    """Classify intent from query keywords (deterministic, no LLM).

    Args:
        query: Search query string

    Returns:
        Classified Intent (default: GENERAL_NEWS if no keywords match)
    """
    query_lower = query.lower()
    scores: dict[Intent, int] = {
        Intent.GENERAL_NEWS: 0,
        Intent.ACADEMIC: 0,
        Intent.DEEP_SCRAPE: 0,
        Intent.SOCIAL: 0,  # NUOVO v2
    }

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                scores[intent] += 1

    max_score = max(scores.values(), default=0)
    if max_score == 0:
        return DEFAULT_INTENT

    return max(scores, key=lambda k: scores[k])


def get_intent_keywords(intent: Intent) -> frozenset[str]:
    """Get keywords for a specific intent (useful for debugging/testing)."""
    return INTENT_KEYWORDS.get(intent, frozenset())
