"""
Deduplication and ranking for search results per blueprint §11.4.

Uses URL canonicalization and fuzzy title matching (rapidfuzz) per §11.4.
Ranking: score = provider_weight × relevance × recency_decay.
"""

import urllib.parse
from datetime import UTC, datetime
from math import exp

from rapidfuzz import fuzz

from aria.agents.search.schema import SearchHit


def canonicalize_url(url: str) -> str:
    """Canonicalize URL for deduplication per blueprint §11.4.

    Removes tracking parameters (utm_*, fbclid, gclid) and normalizes URL.

    Args:
        url: Raw URL string.

    Returns:
        Canonical URL string.
    """
    if not url:
        return ""

    try:
        parsed = urllib.parse.urlparse(url)
        # Normalize: lowercase scheme and host, remove trailing slash
        scheme = parsed.scheme.lower() if parsed.scheme else "https"
        netloc = parsed.netloc.lower()

        # Remove www. prefix
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Remove tracking query params
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "msclkid",
            "dclid",
            "_ga",
            "ref",
            "source",
        }
        query_params = []
        for key, value in urllib.parse.parse_qsl(parsed.query):
            if key.lower() not in tracking_params:
                query_params.append((key, value))

        query = urllib.parse.urlencode(sorted(query_params))

        # Reconstruct
        return urllib.parse.urlunparse((scheme, netloc, parsed.path.rstrip("/"), "", query, ""))
    except Exception:
        # Fallback: return lowercased stripped URL
        return url.strip().lower()


def title_similarity(a: str, b: str) -> float:
    """Calculate Levenshtein similarity ratio between two titles.

    Args:
        a: First title.
        b: Second title.

    Returns:
        Similarity score 0.0-1.0 (1.0 = identical).
    """
    if not a or not b:
        return 0.0
    # rapidfuzz ratio returns 0-100, normalize to 0-1
    return fuzz.ratio(a, b) / 100.0


def dedup_hits(hits: list[SearchHit], title_threshold: float = 0.85) -> list[SearchHit]:
    """Deduplicate search hits based on URL canonicalization and title similarity.

    Algorithm:
    1. Group by canonical URL.
    2. For each group with same URL, keep highest-scoring hit.
    3. Then apply fuzzy title matching to catch near-duplicates with
       different URLs (e.g. same article on different mirrors).

    Args:
        hits: List of search hits.
        title_threshold: Title similarity threshold for dedup (default 0.85).

    Returns:
        Deduplicated list of hits preserving original order.
    """
    if not hits:
        return []

    # Step 1: dedup by canonical URL
    url_map: dict[str, SearchHit] = {}
    for hit in hits:
        canonical = canonicalize_url(hit.url)
        if canonical not in url_map or hit.score > url_map[canonical].score:
            url_map[canonical] = hit

    # Step 2: dedup by title similarity
    unique_hits: list[SearchHit] = []
    seen_titles: list[str] = []

    for hit in url_map.values():
        is_duplicate = False
        for seen_title in seen_titles:
            if title_similarity(hit.title, seen_title) >= title_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_hits.append(hit)
            seen_titles.append(hit.title)

    return unique_hits


def recency_decay(
    published_at: datetime | None,
    now: datetime | None = None,
    half_life_days: float = 30.0,
) -> float:
    """Calculate recency decay factor per blueprint §11.4.

    Uses exponential decay with configurable half-life.

    Args:
        published_at: Publication date of the hit.
        now: Reference time (default: now UTC).
        half_life_days: Days until score is halved.

    Returns:
        Decay factor between 0.0 and 1.0.
    """
    if published_at is None:
        return 0.5  # Unknown date gets neutral score

    if now is None:
        now = datetime.now(UTC)

    # Make published_at timezone-aware if needed
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)

    age_days = (now - published_at).total_seconds() / 86400.0
    if age_days < 0:
        age_days = 0.0

    # Exponential decay: score = exp(-lambda * age)
    # half_life: score(half_life_days) = 0.5
    # exp(-lambda * half_life) = 0.5 => lambda = ln(2) / half_life
    decay_factor = exp(-0.6931471805599453 * age_days / half_life_days)
    return max(0.1, min(1.0, decay_factor))


def rank_hits(
    hits: list[SearchHit],
    provider_weights: dict[str, float] | None = None,
    now: datetime | None = None,
) -> list[SearchHit]:
    """Rank hits by score = provider_weight × recency_decay.

    Args:
        hits: List of hits to rank.
        provider_weights: Dict mapping provider name to weight.
        now: Reference time for recency calculation.

    Returns:
        Sorted list of hits (highest score first).
    """
    if provider_weights is None:
        provider_weights = {}

    def composite_score(hit: SearchHit) -> float:
        weight = provider_weights.get(hit.provider, 0.5)
        decay = recency_decay(hit.published_at, now)
        return weight * (hit.score or 0.5) * decay

    return sorted(hits, key=composite_score, reverse=True)
