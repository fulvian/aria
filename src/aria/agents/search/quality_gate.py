"""
Quality gate evaluation for search results per Searcher Optimizer Plan §5.3.

Evaluates whether search results meet minimum quality thresholds before
deciding whether to escalate to higher-cost providers.
"""

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from aria.agents.search.schema import Intent, SearchHit

logger = logging.getLogger(__name__)


class QualityThresholds(BaseModel):
    """Configurable quality thresholds for gate evaluation.

    Attributes:
        min_unique_results: Minimum number of unique results.
        min_distinct_domains: Minimum number of distinct domains.
        min_recency_ratio: Minimum ratio of recent results (for news intent).
        recency_window_days: Days window for recency calculation.
        min_top3_score_mean: Minimum mean score of top 3 results.
    """

    min_unique_results: int = Field(default=6, ge=0)
    min_distinct_domains: int = Field(default=4, ge=0)
    min_recency_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    recency_window_days: int = Field(default=7, ge=1)
    min_top3_score_mean: float = Field(default=0.65, ge=0.0, le=1.0)


class QualityReport(BaseModel):
    """Quality evaluation report for a set of search results.

    Attributes:
        total_results: Total number of results evaluated.
        unique_results: Number of unique results (after dedup).
        distinct_domains: Number of distinct domains.
        recency_ratio: Ratio of results within recency window.
        top3_score_mean: Mean score of top 3 results.
        passed: Whether all gates passed.
        failed_gates: List of failed gate names.
    """

    total_results: int
    unique_results: int
    distinct_domains: int
    recency_ratio: float
    top3_score_mean: float
    passed: bool
    failed_gates: list[str] = Field(default_factory=list)


# Intent-specific threshold overrides
INTENT_THRESHOLDS: dict[Intent, QualityThresholds] = {
    Intent.NEWS: QualityThresholds(
        min_unique_results=5,
        min_distinct_domains=3,
        min_recency_ratio=0.4,
        recency_window_days=3,
        min_top3_score_mean=0.6,
    ),
    Intent.ACADEMIC: QualityThresholds(
        min_unique_results=4,
        min_distinct_domains=3,
        min_recency_ratio=0.2,
        recency_window_days=365,
        min_top3_score_mean=0.7,
    ),
    Intent.GENERAL: QualityThresholds(
        min_unique_results=6,
        min_distinct_domains=4,
        min_recency_ratio=0.3,
        recency_window_days=30,
        min_top3_score_mean=0.65,
    ),
    Intent.DEEP_SCRAPE: QualityThresholds(
        min_unique_results=1,
        min_distinct_domains=1,
        min_recency_ratio=0.0,
        recency_window_days=365,
        min_top3_score_mean=0.5,
    ),
    Intent.PRIVACY: QualityThresholds(
        min_unique_results=5,
        min_distinct_domains=3,
        min_recency_ratio=0.3,
        recency_window_days=30,
        min_top3_score_mean=0.6,
    ),
    Intent.FALLBACK: QualityThresholds(
        min_unique_results=3,
        min_distinct_domains=2,
        min_recency_ratio=0.2,
        recency_window_days=30,
        min_top3_score_mean=0.5,
    ),
}

DEFAULT_THRESHOLDS = QualityThresholds()


class QualityGate:
    """Evaluates search result quality against configurable thresholds.

    Used by the economic router to decide whether results from a low-cost
    provider are sufficient or if escalation to a higher-cost provider is needed.
    """

    def __init__(
        self,
        thresholds: dict[Intent, QualityThresholds] | None = None,
    ) -> None:
        """Initialize with optional custom thresholds.

        Args:
            thresholds: Custom per-intent thresholds. Merged with defaults.
        """
        self._thresholds = dict(INTENT_THRESHOLDS)
        if thresholds:
            self._thresholds.update(thresholds)

    def _get_thresholds(self, intent: Intent) -> QualityThresholds:
        """Get thresholds for a specific intent.

        Args:
            intent: Query intent.

        Returns:
            QualityThresholds for the intent.
        """
        return self._thresholds.get(intent, DEFAULT_THRESHOLDS)

    def evaluate(
        self,
        hits: list[SearchHit],
        intent: Intent,
        now: datetime | None = None,
    ) -> QualityReport:
        """Evaluate search results against quality gates.

        Args:
            hits: List of search hits to evaluate.
            intent: Query intent (used for threshold selection).
            now: Reference time (default: UTC now).

        Returns:
            QualityReport with evaluation results.
        """
        if now is None:
            now = datetime.now(UTC)

        thresholds = self._get_thresholds(intent)

        total = len(hits)
        unique = len(hits)  # Assumes hits are already deduplicated

        # Count distinct domains
        domains: set[str] = set()
        for hit in hits:
            try:
                parsed = urlparse(str(hit.url))
                domains.add(parsed.netloc.lower())
            except Exception:
                pass
        distinct_domains = len(domains)

        # Calculate recency ratio
        cutoff = now - timedelta(days=thresholds.recency_window_days)
        recent_count = 0
        for hit in hits:
            if hit.published_at is not None:
                pub = hit.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=UTC)
                if pub >= cutoff:
                    recent_count += 1
        recency_ratio = recent_count / total if total > 0 else 0.0

        # Calculate top-3 score mean
        sorted_hits = sorted(hits, key=lambda h: h.score, reverse=True)
        top3 = sorted_hits[:3]
        top3_mean = sum(h.score for h in top3) / len(top3) if top3 else 0.0

        # Evaluate gates
        failed_gates: list[str] = []

        if unique < thresholds.min_unique_results:
            failed_gates.append("unique_results")

        if distinct_domains < thresholds.min_distinct_domains:
            failed_gates.append("distinct_domains")

        if recency_ratio < thresholds.min_recency_ratio:
            failed_gates.append("recency_ratio")

        if top3_mean < thresholds.min_top3_score_mean:
            failed_gates.append("top3_score_mean")

        passed = len(failed_gates) == 0

        report = QualityReport(
            total_results=total,
            unique_results=unique,
            distinct_domains=distinct_domains,
            recency_ratio=round(recency_ratio, 3),
            top3_score_mean=round(top3_mean, 3),
            passed=passed,
            failed_gates=failed_gates,
        )

        if not passed:
            logger.debug(
                "Quality gate FAILED for intent=%s: %s "
                "(total=%d, domains=%d, recency=%.2f, top3=%.2f)",
                intent.value,
                failed_gates,
                total,
                distinct_domains,
                recency_ratio,
                top3_mean,
            )

        return report
