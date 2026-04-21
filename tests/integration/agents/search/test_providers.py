"""Integration tests for search providers with respx mocking."""

from datetime import UTC, datetime
from typing import Any

import httpx
import respx
import pytest

from aria.agents.search.providers.tavily import TavilyProvider
from aria.agents.search.providers.firecrawl import FirecrawlProvider
from aria.agents.search.providers.brave import BraveProvider
from aria.agents.search.providers.exa import ExaProvider
from aria.agents.search.schema import ProviderStatus


class TestTavilyProvider:
    """Integration tests for TavilyProvider."""

    @respx.mock
    async def test_search_returns_normalized_hits(self):
        """Test that Tavily search returns properly normalized SearchHit."""
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://example.com/article",
                            "title": "Test Article",
                            "content": "This is the article content.",
                            "published_date": "2024-01-15T10:30:00Z",
                            "score": 0.95,
                        },
                        {
                            "url": "https://example.com/second",
                            "title": "Second Article",
                            "content": "More content here.",
                            "published_date": None,
                            "score": 0.85,
                        },
                    ]
                },
            )
        )

        provider = TavilyProvider(api_key="test-key")
        hits = await provider.search("test query", top_k=10)

        assert len(hits) == 2
        assert hits[0].title == "Test Article"
        assert str(hits[0].url) == "https://example.com/article"
        assert hits[0].snippet == "This is the article content."
        assert hits[0].provider == "tavily"
        assert hits[0].score == 0.95
        assert hits[1].title == "Second Article"
        assert hits[1].published_at is None
        await provider.close()

    @respx.mock
    async def test_search_empty_results(self):
        """Test handling of empty results."""
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        provider = TavilyProvider(api_key="test-key")
        hits = await provider.search("nothing found", top_k=10)

        assert len(hits) == 0
        await provider.close()

    @respx.mock
    async def test_search_http_error_returns_empty(self):
        """Test that HTTP errors are handled gracefully."""
        route = respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(500))

        provider = TavilyProvider(api_key="test-key")
        hits = await provider.search("error test", top_k=10)

        assert hits == []
        await provider.close()

    @respx.mock
    async def test_health_check_available(self):
        """Test health check when API is healthy."""
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        provider = TavilyProvider(api_key="test-key")
        status = await provider.health_check()

        assert status == ProviderStatus.AVAILABLE
        await provider.close()

    @respx.mock
    async def test_health_check_credits_exhausted(self):
        """Test health check when credits are exhausted."""
        route = respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(429))

        provider = TavilyProvider(api_key="test-key")
        status = await provider.health_check()

        assert status == ProviderStatus.CREDITS_EXHAUSTED
        await provider.close()


class TestFirecrawlProvider:
    """Integration tests for FirecrawlProvider."""

    @respx.mock
    async def test_search_returns_hits(self):
        """Test Firecrawl search returns normalized hits."""
        route = respx.post("https://api.firecrawl.dev/v1/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "url": "https://firecrawl-test.com/page",
                            "title": "Firecrawl Test Page",
                            "description": "A test page for firecrawl.",
                            "published_date": "2024-02-20",
                        },
                    ]
                },
            )
        )

        provider = FirecrawlProvider(api_key="test-key")
        hits = await provider.search("firecrawl test", top_k=5)

        assert len(hits) == 1
        assert hits[0].title == "Firecrawl Test Page"
        assert str(hits[0].url) == "https://firecrawl-test.com/page"
        assert hits[0].provider == "firecrawl"
        await provider.close()

    @respx.mock
    async def test_scrape_returns_content(self):
        """Test Firecrawl scrape returns full page content."""
        route = respx.post("https://api.firecrawl.dev/v1/scrape").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "markdown": "# Page Title\n\nThis is the full content.",
                        "metadata": {"title": "Scrape Test"},
                    },
                },
            )
        )

        provider = FirecrawlProvider(api_key="test-key")
        hit = await provider.scrape("https://example.com/full-page")

        assert hit is not None
        assert hit.title == "Scrape Test"
        assert "Page Title" in hit.snippet
        assert hit.provider == "firecrawl"
        await provider.close()

    @respx.mock
    async def test_scrape_failure_returns_none(self):
        """Test that scrape failures return None gracefully."""
        route = respx.post("https://api.firecrawl.dev/v1/scrape").mock(
            return_value=httpx.Response(500)
        )

        provider = FirecrawlProvider(api_key="test-key")
        hit = await provider.scrape("https://example.com/error")

        assert hit is None
        await provider.close()

    @respx.mock
    async def test_extract_returns_structured_payload(self):
        """Test Firecrawl extract endpoint wrapper."""
        respx.post("https://api.firecrawl.dev/v1/extract").mock(
            return_value=httpx.Response(
                200,
                json={"success": True, "data": [{"field": "value"}]},
            )
        )

        provider = FirecrawlProvider(api_key="test-key")
        data = await provider.extract(
            url="https://example.com",
            prompt="Extract key fields",
            schema={"type": "object"},
        )

        assert data["success"] is True
        await provider.close()


class TestBraveProvider:
    """Integration tests for BraveProvider."""

    @respx.mock
    async def test_search_returns_hits(self):
        """Test Brave search returns normalized hits."""
        route = respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "web": {
                        "results": [
                            {
                                "url": "https://brave-test.com/result",
                                "title": "Brave Result",
                                "description": "A brave search result.",
                            },
                        ]
                    }
                },
            )
        )

        provider = BraveProvider(api_key="test-brave-key")
        hits = await provider.search("brave test", top_k=5)

        assert len(hits) == 1
        assert hits[0].title == "Brave Result"
        assert str(hits[0].url) == "https://brave-test.com/result"
        assert hits[0].provider == "brave"
        await provider.close()


class TestExaProvider:
    """Integration tests for ExaProvider."""

    @respx.mock
    async def test_search_with_highlights(self):
        """Test Exa search extracts highlights properly."""
        route = respx.post("https://api.exa.ai/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://exa-test.com/academic",
                            "title": "Exa Academic Paper",
                            "highlights": ["This is a key finding from the paper."],
                            "published_date": "2024-03-01",
                            "score": 0.92,
                        },
                    ]
                },
            )
        )

        provider = ExaProvider(api_key="test-exa-key")
        hits = await provider.search("academic paper test", top_k=5)

        assert len(hits) == 1
        assert hits[0].title == "Exa Academic Paper"
        assert "key finding" in hits[0].snippet
        assert hits[0].provider == "exa"
        await provider.close()

    @respx.mock
    async def test_search_fallback_to_text(self):
        """Test Exa falls back to text snippet when no highlights."""
        route = respx.post("https://api.exa.ai/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://exa-test.com/article",
                            "title": "Exa Article",
                            "highlights": [],
                            "text": "This is the article body text.",
                            "published_date": None,
                            "score": 0.80,
                        },
                    ]
                },
            )
        )

        provider = ExaProvider(api_key="test-exa-key")
        hits = await provider.search("article test", top_k=5)

        assert len(hits) == 1
        assert "article body text" in hits[0].snippet
        await provider.close()


class TestProviderHealth:
    """Integration tests for ProviderHealth."""

    @respx.mock
    async def test_probe_all_returns_status_dict(self):
        """Test that probe_all returns status for all providers."""
        from aria.agents.search.health import ProviderHealth
        from aria.agents.search.providers.tavily import TavilyProvider

        respx.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        provider = TavilyProvider(api_key="test-key")
        health = ProviderHealth(providers={"tavily": provider})

        results = await health.probe_all()

        assert "tavily" in results
        assert results["tavily"] == ProviderStatus.AVAILABLE

        await provider.close()
