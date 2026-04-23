"""
Reciprocal Rank Fusion (RRF) for multi-provider result merging per
Searcher Optimizer Plan §5.5.

Implements RRF with configurable rank_constant and window_size.
RRF formula: rrf_score(d) = sum over providers of 1 / (k + rank_i(d))
where k is the rank_constant (default 60, industry baseline).
"""

import logging

from pydantic import BaseModel, Field

from aria.agents.search.schema import SearchHit

logger = logging.getLogger(__name__)


class RRFConfig(BaseModel):
    """Configuration for Reciprocal Rank Fusion.

    Attributes:
        rank_constant: RRF rank constant k (default 60, industry baseline).
            Higher values dampen the effect of individual rankings.
        window_size: Maximum number of results per provider to consider.
            Limits latency by capping the fusion window.
    """

    rank_constant: int = Field(default=60, ge=1, description="RRF k parameter")
    window_size: int = Field(
        default=40,
        ge=1,
        le=100,
        description="Max results per provider in fusion window",
    )


class FusionResult(BaseModel):
    """Result of RRF fusion operation.

    Attributes:
        hits: Fused and ranked search hits.
        provider_count: Number of providers contributing results.
        total_input_hits: Total hits before fusion.
        fused_count: Hits after fusion.
    """

    hits: list[SearchHit]
    provider_count: int
    total_input_hits: int
    fused_count: int


def reciprocal_rank_fusion(
    provider_results: dict[str, list[SearchHit]],
    config: RRFConfig | None = None,
) -> FusionResult:
    """Apply Reciprocal Rank Fusion to results from multiple providers.

    Each provider's results are ranked by their position (1-indexed).
    The RRF score for each document is the sum of 1/(k + rank) across
    all providers that returned it.

    Documents are identified by their canonical URL for dedup.

    Args:
        provider_results: Dict mapping provider name to its result list.
        config: RRF configuration (uses defaults if None).

    Returns:
        FusionResult with fused and ranked hits.
    """
    if config is None:
        config = RRFConfig()

    k = config.rank_constant
    window = config.window_size

    # Track rrf scores per URL and keep the best SearchHit per URL
    url_scores: dict[str, float] = {}
    url_hits: dict[str, SearchHit] = {}
    total_input = 0
    contributing_providers = 0

    for _provider_name, hits in provider_results.items():
        if not hits:
            continue
        contributing_providers += 1

        # Only consider top-N results per provider (window_size)
        for rank_idx, hit in enumerate(hits[:window]):
            rank = rank_idx + 1  # 1-indexed
            total_input += 1

            # Use URL as document identifier
            url_key = str(hit.url).lower().strip().rstrip("/")

            # Accumulate RRF score
            contribution = 1.0 / (k + rank)
            url_scores[url_key] = url_scores.get(url_key, 0.0) + contribution

            # Keep the hit with the highest individual score per URL
            if url_key not in url_hits or hit.score > url_hits[url_key].score:
                url_hits[url_key] = hit

    # Sort by RRF score descending
    sorted_urls = sorted(url_scores.keys(), key=lambda u: url_scores[u], reverse=True)

    # Build final hit list with RRF scores
    fused_hits: list[SearchHit] = []
    for url_key in sorted_urls:
        hit = url_hits[url_key]
        # Update score to RRF score (normalized to 0-1 range)
        rrf_score = url_scores[url_key]
        # Normalize: max possible score from a single provider at rank 1 = 1/(k+1)
        # We use raw score but cap at 1.0 for compatibility
        normalized_score = min(1.0, rrf_score)
        fused_hits.append(
            SearchHit(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                published_at=hit.published_at,
                score=normalized_score,
                provider=hit.provider,
                provider_raw=hit.provider_raw,
            )
        )

    result = FusionResult(
        hits=fused_hits,
        provider_count=contributing_providers,
        total_input_hits=total_input,
        fused_count=len(fused_hits),
    )

    logger.debug(
        "RRF fusion: %d providers, %d input → %d fused (k=%d, window=%d)",
        contributing_providers,
        total_input,
        len(fused_hits),
        k,
        window,
    )

    return result
