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
    """Fixture with all providers in tier order."""
    return [
        Provider.SEARXNG,
        Provider.TAVILY,
        Provider.FIRECRAWL_EXTRACT,
        Provider.EXA,
        Provider.BRAVE,
    ]


@pytest.fixture
def deep_scrape_providers():
    """Fixture for deep_scrape tier list."""
    return [
        Provider.FIRECRAWL_EXTRACT,
        Provider.FIRECRAWL_SCRAPE,
        Provider.FETCH,
    ]