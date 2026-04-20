"""Tests for search schema models."""

from datetime import datetime, timezone

import pytest

from aria.agents.search.schema import (
    Intent,
    SearchHit,
    INTENT_ROUTING,
    PROVIDER_WEIGHTS,
)
from aria.agents.search.router import IntentClassifier


class TestIntentClassifier:
    """Tests for intent classification."""

    def setup_method(self):
        self.classifier = IntentClassifier()

    def test_news_intent(self):
        assert self.classifier.classify("notizie di oggi") == Intent.NEWS
        assert self.classifier.classify("breaking news") == Intent.NEWS
        assert self.classifier.classify("ultime notizie") == Intent.NEWS

    def test_academic_intent(self):
        assert self.classifier.classify("paper on machine learning") == Intent.ACADEMIC
        assert self.classifier.classify("arxiv publication") == Intent.ACADEMIC
        assert self.classifier.classify("research study on AI") == Intent.ACADEMIC

    def test_deep_scrape_intent(self):
        assert self.classifier.classify("https://example.com") == Intent.DEEP_SCRAPE
        assert self.classifier.classify("scrape https://test.com") == Intent.DEEP_SCRAPE

    def test_privacy_intent(self):
        assert self.classifier.classify("privacy policy analysis") == Intent.PRIVACY
        assert self.classifier.classify("tracking cookies review") == Intent.PRIVACY

    def test_general_intent_default(self):
        assert self.classifier.classify("what is python") == Intent.GENERAL
        assert self.classifier.classify("best restaurants in Rome") == Intent.GENERAL


class TestSearchHit:
    """Tests for SearchHit model."""

    def test_create_minimal_hit(self):
        hit = SearchHit(title="Test", url="https://test.com", snippet="content", provider="tavily")
        assert hit.title == "Test"
        assert hit.url == "https://test.com"
        assert hit.score == 0.0
        assert hit.provider == "tavily"
        assert hit.provider_raw == {}

    def test_create_full_hit(self):
        now = datetime.now(timezone.utc)
        hit = SearchHit(
            title="Full Hit",
            url="https://full.com",
            snippet="content",
            published_at=now,
            score=0.95,
            provider="tavily",
            provider_raw={"raw": "data"},
        )
        assert hit.title == "Full Hit"
        assert hit.score == 0.95
        assert hit.published_at == now
        assert hit.provider_raw == {"raw": "data"}

    def test_hit_defaults(self):
        hit = SearchHit(title="A", url="https://a.com", snippet="", provider="tavily")
        assert hit.score == 0.0
        assert hit.published_at is None
        assert hit.provider_raw == {}


class TestIntentRouting:
    """Tests for INTENT_ROUTING table."""

    def test_all_intents_have_providers(self):
        for intent in Intent:
            providers = INTENT_ROUTING[intent]
            assert isinstance(providers, list)
            assert len(providers) > 0

    def test_news_routing(self):
        providers = INTENT_ROUTING[Intent.NEWS]
        assert "tavily" in providers
        assert "brave_news" in providers


class TestProviderWeights:
    """Tests for PROVIDER_WEIGHTS."""

    def test_all_providers_have_weights(self):
        for provider in PROVIDER_WEIGHTS:
            weight = PROVIDER_WEIGHTS[provider]
            assert 0.0 <= weight <= 1.0

    def test_tavily_is_primary(self):
        assert PROVIDER_WEIGHTS["tavily"] == 1.0
