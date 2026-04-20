"""Tests for dedup module."""

from datetime import datetime, timedelta, timezone

import pytest

from aria.agents.search.dedup import (
    canonicalize_url,
    title_similarity,
    dedup_hits,
    rank_hits,
    recency_decay,
)
from aria.agents.search.schema import SearchHit


class TestCanonicalizeUrl:
    """Tests for URL canonicalization."""

    def test_removes_utm_params(self):
        url = "https://example.com/page?utm_source=twitter&utm_medium=social"
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "example.com" in result

    def test_removes_fbclid(self):
        url = "https://example.com/?fbclid=abc123&content=page"
        result = canonicalize_url(url)
        assert "fbclid" not in result
        assert "content=page" in result

    def test_normalizes_www_prefix(self):
        url = "https://www.example.com/page"
        result = canonicalize_url(url)
        assert result.startswith("https://example.com")

    def test_removes_trailing_slash(self):
        url = "https://example.com/page/"
        result = canonicalize_url(url)
        assert not result.endswith("/")

    def test_lowercases_scheme_and_host(self):
        url = "HTTPS://WWW.EXAMPLE.COM/Page"
        result = canonicalize_url(url)
        assert "https" in result
        assert "example" in result

    def test_empty_url(self):
        assert canonicalize_url("") == ""
        assert canonicalize_url("   ") == "https://"  # normalize adds scheme


class TestTitleSimilarity:
    """Tests for title fuzzy matching."""

    def test_identical_titles(self):
        score = title_similarity("Hello World", "Hello World")
        assert score == 1.0

    def test_similar_titles(self):
        score = title_similarity("Hello World", "Hello World!")
        assert score > 0.8

    def test_different_titles(self):
        score = title_similarity("Hello", "Goodbye")
        assert score < 0.5

    def test_empty_titles(self):
        assert title_similarity("", "") == 0.0
        assert title_similarity("Hello", "") == 0.0
        assert title_similarity("", "World") == 0.0


class TestDedupHits:
    """Tests for search hit deduplication."""

    def test_dedups_same_url(self):
        hits = [
            SearchHit(title="A", url="https://ex.com/a", snippet="x", provider="tavily", score=0.9),
            SearchHit(title="B", url="https://ex.com/a", snippet="y", provider="tavily", score=0.8),
        ]
        result = dedup_hits(hits)
        assert len(result) == 1
        assert result[0].title == "A"  # Higher score kept

    def test_dedups_canonical_url(self):
        hits = [
            SearchHit(
                title="A", url="https://ex.com/a?utm_source=x", snippet="x", provider="tavily"
            ),
            SearchHit(title="B", url="https://ex.com/a", snippet="y", provider="tavily"),
        ]
        result = dedup_hits(hits)
        assert len(result) == 1

    def test_preserves_different_urls(self):
        hits = [
            SearchHit(title="A", url="https://ex.com/a", snippet="x", provider="tavily"),
            SearchHit(title="B", url="https://ex.com/b", snippet="y", provider="tavily"),
        ]
        result = dedup_hits(hits)
        assert len(result) == 2

    def test_empty_list(self):
        assert dedup_hits([]) == []

    def test_fuzzy_title_dedup(self):
        hits = [
            SearchHit(
                title="How to Learn Python", url="https://site.com/a", snippet="", provider="tavily"
            ),
            SearchHit(
                title="How to Learn Python - Complete Guide",
                url="https://site.com/b",
                snippet="",
                provider="brave",
            ),
        ]
        result = dedup_hits(hits, title_threshold=0.85)
        # High similarity should dedupe
        assert len(result) <= 2


class TestRecencyDecay:
    """Tests for recency decay."""

    def test_recent_hit_full_score(self):
        now = datetime.now(timezone.utc)
        hit_date = now
        decay = recency_decay(hit_date, now)
        assert decay == pytest.approx(1.0, abs=0.01)

    def test_old_hit_decays(self):
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=30)
        decay = recency_decay(old_date, now)
        assert 0.4 < decay < 0.6  # ~0.5 at half-life

    def test_none_date_gets_neutral(self):
        decay = recency_decay(None)
        assert decay == 0.5


class TestRankHits:
    """Tests for hit ranking."""

    def test_ranked_by_composite_score(self):
        hits = [
            SearchHit(title="A", url="https://a.com", snippet="", provider="tavily", score=0.5),
            SearchHit(title="B", url="https://b.com", snippet="", provider="brave", score=0.9),
        ]
        result = rank_hits(hits, provider_weights={"tavily": 1.0, "brave": 0.5})
        # tavily (1.0 * 0.5) = 0.5, brave (0.5 * 0.9) = 0.45
        assert result[0].title == "A"

    def test_empty_list(self):
        assert rank_hits([]) == []

    def test_unknown_provider_gets_default_weight(self):
        hits = [
            SearchHit(title="A", url="https://a.com", snippet="", provider="unknown", score=0.5),
        ]
        result = rank_hits(hits, provider_weights={})
        assert len(result) == 1
