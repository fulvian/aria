"""Unit tests for quality_gate module."""

from datetime import UTC, datetime, timedelta

import pytest

from aria.agents.search.quality_gate import QualityGate, QualityThresholds, QualityReport
from aria.agents.search.schema import Intent, SearchHit


def _make_hit(
    title: str = "Test Result",
    url: str = "https://example.com/page",
    score: float = 0.8,
    days_ago: int = 0,
    provider: str = "searxng",
) -> SearchHit:
    """Create a SearchHit for testing."""
    published = datetime.now(UTC) - timedelta(days=days_ago) if days_ago >= 0 else None
    return SearchHit(
        title=title,
        url=url,
        snippet="Test snippet",
        published_at=published,
        score=score,
        provider=provider,
    )


class TestQualityGate:
    """Tests for QualityGate."""

    def test_sufficient_results_pass(self):
        """Enough unique results from different domains should pass."""
        gate = QualityGate()
        hits = [
            _make_hit(title=f"Result {i}", url=f"https://domain{i}.com/page", score=0.8)
            for i in range(8)
        ]
        report = gate.evaluate(hits, Intent.GENERAL)
        assert report.passed
        assert report.unique_results == 8
        assert report.distinct_domains == 8

    def test_insufficient_results_fail(self):
        """Too few results should fail the unique_results gate."""
        gate = QualityGate()
        hits = [_make_hit(title="Only result", url="https://example.com/page")]
        report = gate.evaluate(hits, Intent.GENERAL)
        assert not report.passed
        assert "unique_results" in report.failed_gates

    def test_single_domain_fail(self):
        """All results from same domain should fail distinct_domains gate."""
        gate = QualityGate()
        hits = [
            _make_hit(title=f"Result {i}", url=f"https://same.com/page{i}", score=0.8)
            for i in range(10)
        ]
        report = gate.evaluate(hits, Intent.GENERAL)
        assert not report.passed
        assert "distinct_domains" in report.failed_gates

    def test_low_scores_fail(self):
        """Results with low scores should fail top3_score_mean gate."""
        gate = QualityGate()
        hits = [
            _make_hit(
                title=f"Result {i}",
                url=f"https://domain{i}.com/page",
                score=0.3,
            )
            for i in range(8)
        ]
        report = gate.evaluate(hits, Intent.GENERAL)
        assert not report.passed
        assert "top3_score_mean" in report.failed_gates

    def test_empty_hits_fail(self):
        """Empty results list should fail all gates."""
        gate = QualityGate()
        report = gate.evaluate([], Intent.GENERAL)
        assert not report.passed
        assert len(report.failed_gates) > 0

    def test_news_intent_recency_check(self):
        """News intent checks for recent results."""
        gate = QualityGate()
        # Mix of recent and old results
        hits = [
            _make_hit(title="Recent", url=f"https://r{i}.com/p", score=0.8, days_ago=1)
            for i in range(3)
        ] + [
            _make_hit(title="Old", url=f"https://o{i}.com/p", score=0.8, days_ago=30)
            for i in range(5)
        ]
        report = gate.evaluate(hits, Intent.NEWS)
        # 3 out of 8 recent within 3-day window = 0.375 ratio < 0.4 threshold
        assert not report.passed
        assert "recency_ratio" in report.failed_gates

    def test_deep_scrape_low_thresholds(self):
        """Deep scrape intent has very low thresholds (1 result sufficient)."""
        gate = QualityGate()
        hits = [_make_hit(title="Scraped page", url="https://target.com/page", score=0.5)]
        report = gate.evaluate(hits, Intent.DEEP_SCRAPE)
        assert report.passed

    def test_custom_thresholds_override(self):
        """Custom thresholds override defaults for specific intents."""
        custom = {Intent.GENERAL: QualityThresholds(min_unique_results=2)}
        gate = QualityGate(thresholds=custom)
        hits = [
            _make_hit(title="A", url="https://a.com/p", score=0.8),
            _make_hit(title="B", url="https://b.com/p", score=0.8),
        ]
        report = gate.evaluate(hits, Intent.GENERAL)
        # With custom threshold of 2, this should pass unique_results
        assert report.unique_results >= 2


class TestQualityReport:
    """Tests for QualityReport model."""

    def test_report_model(self):
        """QualityReport can be created with required fields."""
        report = QualityReport(
            total_results=10,
            unique_results=8,
            distinct_domains=5,
            recency_ratio=0.6,
            top3_score_mean=0.85,
            passed=True,
            failed_gates=[],
        )
        assert report.passed
        assert report.failed_gates == []
