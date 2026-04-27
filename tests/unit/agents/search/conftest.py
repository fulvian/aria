# Test fixtures for search agent tests

from __future__ import annotations

import pytest

from aria.agents.search.router import Intent, Provider


@pytest.fixture
def general_news_intent():
    """Fixture for general/news intent."""
    return Intent.GENERAL_NEWS


@pytest.fixture
def academic_intent():
    """Fixture for academic intent."""
    return Intent.ACADEMIC


@pytest.fixture
def deep_scrape_intent():
    """Fixture for deep_scrape intent."""
    return Intent.DEEP_SCRAPE


@pytest.fixture
def all_providers():
    """Fixture with all providers in tier order (post-FIRECRAWL)."""
    return [
        Provider.SEARXNG,
        Provider.TAVILY,
        Provider.EXA,
        Provider.BRAVE,
        Provider.FETCH,
    ]


@pytest.fixture
def deep_scrape_providers():
    """Fixture for deep_scrape tier list (post-FIRECRAWL)."""
    return [
        Provider.FETCH,
        Provider.WEBFETCH,
    ]
