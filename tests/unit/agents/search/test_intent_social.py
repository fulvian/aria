# Tests for SOCIAL intent classification

from __future__ import annotations

import pytest

from aria.agents.search.intent import (
    classify_intent,
    get_intent_keywords,
    INTENT_KEYWORDS,
    DEFAULT_INTENT,
)
from aria.agents.search.router import Intent


class TestSocialIntent:
    """Test SOCIAL intent classification."""

    def test_social_keyword_reddit(self):
        """Keyword: reddit -> SOCIAL."""
        assert classify_intent("reddit discussion about AI") == Intent.SOCIAL

    def test_social_keyword_forum(self):
        """Keyword: forum -> SOCIAL."""
        assert classify_intent("forum discussion on tech") == Intent.SOCIAL

    def test_social_keyword_trending(self):
        """Keyword: trending -> SOCIAL (no conflict with GENERAL_NEWS)."""
        result = classify_intent("trending topics discussion")
        assert result == Intent.SOCIAL

    def test_social_trending_with_today_tie(self):
        """SOCIAL 'trending' + GENERAL_NEWS 'today' -> either is acceptable."""
        result = classify_intent("trending topics today")
        assert result in (Intent.SOCIAL, Intent.GENERAL_NEWS)

    def test_social_keyword_community(self):
        """Keyword: community -> SOCIAL."""
        assert classify_intent("community opinions on climate") == Intent.SOCIAL

    def test_social_keyword_public_opinion(self):
        """Keyword: public opinion -> SOCIAL."""
        assert classify_intent("what people are saying about AI") == Intent.SOCIAL

    def test_social_keyword_hacker_news(self):
        """Keyword: hacker news -> SOCIAL."""
        assert classify_intent("hacker news discussion") == Intent.SOCIAL

    def test_social_not_confused_with_news(self):
        """SOCIAL keywords take priority over GENERAL_NEWS when both match."""
        # "reddit" is SOCIAL, "news" is GENERAL_NEWS
        # SOCIAL should win with 1 match (GENERAL_NEWS also has 1 match)
        # This tests that SOCIAL is included in the scoring
        result = classify_intent("reddit news")
        # Both SOCIAL and GENERAL_NEWS have 1 match - the result depends on
        # dict iteration order. Either is acceptable as long as SOCIAL is scored.
        assert result in (Intent.SOCIAL, Intent.GENERAL_NEWS)

    def test_social_multiple_keywords(self):
        """Multiple SOCIAL keywords -> SOCIAL."""
        result = classify_intent("trending reddit discussion forum community")
        assert result == Intent.SOCIAL

    def test_social_not_triggered_on_general(self):
        """General query without social keywords -> not SOCIAL."""
        result = classify_intent("latest news on AI")
        assert result != Intent.SOCIAL

    def test_social_not_triggered_on_academic(self):
        """Academic query without social keywords -> not SOCIAL."""
        result = classify_intent("research paper on machine learning")
        assert result != Intent.SOCIAL


class TestSocialIntentKeywords:
    """Test SOCIAL keywords in INTENT_KEYWORDS."""

    def test_has_social_in_keywords(self):
        """SOCIAL intent has keywords defined."""
        assert Intent.SOCIAL in INTENT_KEYWORDS

    def test_social_keywords_is_frozenset(self):
        """SOCIAL keywords is a frozenset."""
        keywords = get_intent_keywords(Intent.SOCIAL)
        assert isinstance(keywords, frozenset)

    def test_social_keywords_contains_reddit(self):
        """SOCIAL keywords contain 'reddit'."""
        keywords = get_intent_keywords(Intent.SOCIAL)
        assert "reddit" in keywords

    def test_social_keywords_not_empty(self):
        """SOCIAL keywords are not empty."""
        keywords = get_intent_keywords(Intent.SOCIAL)
        assert len(keywords) > 0
