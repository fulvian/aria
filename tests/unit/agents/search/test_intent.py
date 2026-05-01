# Tests for intent classification

from __future__ import annotations

from aria.agents.search.intent import (
    DEFAULT_INTENT,
    INTENT_KEYWORDS,
    classify_intent,
    get_intent_keywords,
)
from aria.agents.search.router import Intent


class TestClassifyIntent:
    """Test intent classification from query strings."""

    def test_news_keywords(self):
        """Keywords: news -> GENERAL_NEWS"""
        assert classify_intent("latest news about AI") == Intent.GENERAL_NEWS
        assert classify_intent("breaking news on tech") == Intent.GENERAL_NEWS
        assert classify_intent("current events today") == Intent.GENERAL_NEWS

    def test_news_italian(self):
        """Italian keywords: notizie, ultime -> GENERAL_NEWS"""
        assert classify_intent("ultime notizie suAI") == Intent.GENERAL_NEWS
        assert classify_intent("notizie di oggi") == Intent.GENERAL_NEWS

    def test_academic_keywords(self):
        """Keywords: research, paper, journal -> ACADEMIC"""
        assert classify_intent("research paper on machine learning") == Intent.ACADEMIC
        assert classify_intent("journal article about climate") == Intent.ACADEMIC
        assert classify_intent("academic study on blockchain") == Intent.ACADEMIC

    def test_academic_italian(self):
        """Italian: ricerca, pubblicazione -> ACADEMIC"""
        assert classify_intent("ricerca su intelligenza artificiale") == Intent.ACADEMIC
        assert classify_intent("pubblicazione scientifica") == Intent.ACADEMIC

    def test_deep_scrape_keywords(self):
        """Keywords: deep, scrape, crawl -> DEEP_SCRAPE"""
        assert classify_intent("deep scrape this website") == Intent.DEEP_SCRAPE
        assert classify_intent("extract all pages from site") == Intent.DEEP_SCRAPE
        assert classify_intent("crawl entire website") == Intent.DEEP_SCRAPE

    def test_deep_scrape_italian(self):
        """Italian: deep scrape, estrai -> DEEP_SCRAPE"""
        assert classify_intent("deep scrape del sito") == Intent.DEEP_SCRAPE
        assert classify_intent("estrai tutte le pagine") == Intent.DEEP_SCRAPE

    def test_no_keywords_defaults_to_general_news(self):
        """Query with no keywords defaults to GENERAL_NEWS"""
        assert classify_intent("tell me about something") == Intent.GENERAL_NEWS
        assert classify_intent("random query xyz") == Intent.GENERAL_NEWS

    def test_empty_query_defaults_to_general_news(self):
        """Empty query defaults to GENERAL_NEWS"""
        assert classify_intent("") == Intent.GENERAL_NEWS

    def test_multiple_keywords_highest_score_wins(self):
        """Multiple keywords - highest score wins"""
        # "deep research paper" has both DEEP_SCRAPE and ACADEMIC keywords
        # DEEP_SCRAPE has 1 ("deep"), ACADEMIC has 1 ("research")
        # Tie goes to whichever is first in scoring order (general_news by default)
        result = classify_intent("research deep paper")
        assert result in (Intent.ACADEMIC, Intent.DEEP_SCRAPE)

    def test_case_insensitive(self):
        """Keyword matching is case insensitive"""
        assert classify_intent("NEWS about AI") == Intent.GENERAL_NEWS
        assert classify_intent("Research PAPER") == Intent.ACADEMIC
        assert classify_intent("DEEP SCRAPE") == Intent.DEEP_SCRAPE


class TestGetIntentKeywords:
    """Test keyword retrieval for debugging/testing."""

    def test_returns_frozenset(self):
        """Returns frozenset for immutability"""
        keywords = get_intent_keywords(Intent.GENERAL_NEWS)
        assert isinstance(keywords, frozenset)

    def test_all_intents_have_keywords(self):
        """All intents have keyword sets"""
        for intent in Intent:
            if intent != Intent.UNKNOWN:
                keywords = get_intent_keywords(intent)
                assert len(keywords) > 0


class TestIntentKeywords:
    """Test INTENT_KEYWORDS dictionary structure."""

    def test_has_general_news_keywords(self):
        assert Intent.GENERAL_NEWS in INTENT_KEYWORDS
        assert "news" in INTENT_KEYWORDS[Intent.GENERAL_NEWS]

    def test_has_academic_keywords(self):
        assert Intent.ACADEMIC in INTENT_KEYWORDS
        assert "research" in INTENT_KEYWORDS[Intent.ACADEMIC]

    def test_has_deep_scrape_keywords(self):
        assert Intent.DEEP_SCRAPE in INTENT_KEYWORDS
        assert "deep" in INTENT_KEYWORDS[Intent.DEEP_SCRAPE]

    def test_unknown_not_in_keywords(self):
        """UNKNOWN intent has no keywords (handled by default)"""
        assert Intent.UNKNOWN not in INTENT_KEYWORDS


class TestDefaultIntent:
    """Test default intent constant."""

    def test_default_is_general_news(self):
        """DEFAULT_INTENT is GENERAL_NEWS"""
        assert DEFAULT_INTENT == Intent.GENERAL_NEWS
