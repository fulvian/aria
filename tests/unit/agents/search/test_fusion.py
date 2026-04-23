"""Unit tests for fusion module (Reciprocal Rank Fusion)."""

import pytest

from aria.agents.search.fusion import RRFConfig, reciprocal_rank_fusion
from aria.agents.search.schema import SearchHit


def _make_hit(
    title: str = "Test",
    url: str = "https://example.com/page",
    score: float = 0.8,
    provider: str = "searxng",
) -> SearchHit:
    """Create a test SearchHit."""
    return SearchHit(
        title=title,
        url=url,
        snippet="Test snippet",
        score=score,
        provider=provider,
    )


class TestReciprocalRankFusion:
    """Tests for RRF fusion."""

    def test_single_provider_passthrough(self):
        """Single provider results pass through unchanged."""
        hits = [
            _make_hit(title="A", url="https://a.com", score=0.9, provider="searxng"),
            _make_hit(title="B", url="https://b.com", score=0.8, provider="searxng"),
        ]
        result = reciprocal_rank_fusion({"searxng": hits})
        assert result.fused_count == 2
        assert result.provider_count == 1

    def test_two_providers_dedup(self):
        """Same URL from two providers gets merged via RRF."""
        provider_a = [
            _make_hit(
                title="Result A", url="https://shared.com/page", score=0.7, provider="searxng"
            )
        ]
        provider_b = [
            _make_hit(title="Result B", url="https://shared.com/page", score=0.9, provider="tavily")
        ]

        result = reciprocal_rank_fusion({"searxng": provider_a, "tavily": provider_b})
        assert result.fused_count == 1  # deduplicated
        assert result.total_input_hits == 2

    def test_two_providers_unique_results(self):
        """Different URLs from two providers are all kept."""
        provider_a = [_make_hit(title="A1", url="https://a.com/1", provider="searxng")]
        provider_b = [_make_hit(title="B1", url="https://b.com/1", provider="tavily")]

        result = reciprocal_rank_fusion({"searxng": provider_a, "tavily": provider_b})
        assert result.fused_count == 2

    def test_empty_provider_skipped(self):
        """Empty provider lists are skipped."""
        hits = [_make_hit(title="A", url="https://a.com", provider="searxng")]
        result = reciprocal_rank_fusion({"searxng": hits, "tavily": []})
        assert result.provider_count == 1
        assert result.fused_count == 1

    def test_empty_input(self):
        """Empty input returns empty result."""
        result = reciprocal_rank_fusion({})
        assert result.fused_count == 0
        assert result.provider_count == 0

    def test_rank_constant_effect(self):
        """Higher rank_constant dampens individual rankings more."""
        hits_a = [
            _make_hit(title=f"A{i}", url=f"https://a.com/{i}", provider="searxng") for i in range(5)
        ]
        hits_b = [
            _make_hit(title=f"B{i}", url=f"https://b.com/{i}", provider="tavily") for i in range(5)
        ]

        # Small k: more weight on individual rankings
        result_small_k = reciprocal_rank_fusion(
            {"searxng": hits_a, "tavily": hits_b},
            config=RRFConfig(rank_constant=1),
        )
        # Large k: more uniform scores
        result_large_k = reciprocal_rank_fusion(
            {"searxng": hits_a, "tavily": hits_b},
            config=RRFConfig(rank_constant=1000),
        )

        assert result_small_k.fused_count == 10
        assert result_large_k.fused_count == 10

    def test_window_size_limits_input(self):
        """Window size limits per-provider results in fusion."""
        hits = [
            _make_hit(title=f"H{i}", url=f"https://h.com/{i}", provider="searxng")
            for i in range(20)
        ]
        result = reciprocal_rank_fusion(
            {"searxng": hits},
            config=RRFConfig(window_size=5),
        )
        assert result.total_input_hits == 5  # only 5 considered from the 20

    def test_shared_url_gets_higher_score(self):
        """URL appearing in multiple providers gets higher RRF score."""
        shared_url = "https://shared.com/article"
        provider_a = [_make_hit(title="A", url=shared_url, provider="searxng")]
        provider_b = [_make_hit(title="B", url=shared_url, provider="tavily")]
        unique_hit = [_make_hit(title="C", url="https://unique.com/page", provider="searxng")]

        result = reciprocal_rank_fusion(
            {
                "searxng": provider_a + unique_hit,
                "tavily": provider_b,
            }
        )
        # Shared URL should rank first due to accumulated RRF score
        assert str(result.hits[0].url) == shared_url
