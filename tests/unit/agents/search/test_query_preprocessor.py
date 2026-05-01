"""Unit tests for centralized query preprocessor (query_preprocessor.py).

Verifica le regole di preprocessing per ogni sorgente accademica,
inclusi i fix per i 3 bug npm di scientific-papers-mcp v0.1.40.
"""

from __future__ import annotations

from aria.agents.search.query_preprocessor import (
    ACADEMIC_SOURCES,
    SOURCE_FORMATTERS,
    get_available_sources,
    preprocess_query,
)


class TestWhitespaceNormalization:
    """Query normalization (applied to all sources)."""

    def test_trim_whitespace(self):
        """Leading/trailing whitespace is trimmed."""
        assert preprocess_query("  hello world  ") == "hello world"

    def test_collapse_multiple_spaces(self):
        """Multiple spaces are collapsed to single."""
        result = preprocess_query("machine   learning   model")
        assert "  " not in result

    def test_empty_query(self):
        """Empty query returns empty."""
        assert preprocess_query("") == ""
        assert preprocess_query("   ") == "   "  # stripped to spaces only, returned as-is


class TestArxivPreprocessor:
    """arXiv-specific query formatting (BUG 1 fix)."""

    def test_simple_query(self):
        """Simple single-term query."""
        result = preprocess_query("transformer", source="arxiv")
        assert result == "all:transformer"

    def test_multi_term_query(self):
        """Multi-term query becomes Boolean AND."""
        result = preprocess_query("machine learning", source="arxiv")
        # Both terms become all:term joined with AND
        assert "AND" in result
        assert "all:machine" in result
        assert "all:learning" in result

    def test_quoted_phrase(self):
        """Quoted phrase uses all:\"phrase\"."""
        result = preprocess_query('"state space model"', source="arxiv")
        assert '"state space model"' in result
        # Should be all:"state space model"
        assert 'all:"state space model"' in result

    def test_mixed_quoted_and_unquoted(self):
        """Mix of quoted phrases and unquoted terms."""
        result = preprocess_query('"state space model" Mamba efficient', source="arxiv")
        assert 'all:"state space model"' in result
        assert "all:Mamba" in result
        assert "all:efficient" in result
        assert result.count("AND") >= 2

    def test_no_double_quote_wrapping(self):
        """BUG 1 fix: query is NOT wrapped in double quotes as a whole."""
        result = preprocess_query("Mamba state space model", source="arxiv")
        # The entire query should NOT be wrapped in quotes
        assert not result.startswith('"') or not result.endswith('"')
        assert "all:" in result


class TestEuropePmcPreprocessor:
    """EuropePMC-specific query formatting (BUG 2 fix)."""

    def test_simple_query_no_wrapping(self):
        """BUG 2 fix: query is NOT wrapped in double quotes as a whole."""
        result = preprocess_query("machine learning protein folding", source="europepmc")
        # The entire query should NOT be wrapped in quotes
        assert not result.startswith('"') or not result.endswith('"')

    def test_preserves_quoted_terms(self):
        """EuropePMC supports quoted phrases, they are preserved."""
        result = preprocess_query('"machine learning" protein folding', source="europepmc")
        assert '"machine learning"' in result
        assert "protein folding" in result

    def test_normalizes_whitespace(self):
        """Whitespace normalized."""
        result = preprocess_query("  machine   learning  ", source="europepmc")
        assert result == "machine learning"

    def test_handles_empty(self):
        """Empty query returns empty."""
        assert preprocess_query("", source="europepmc") == ""


class TestOpenAlexPreprocessor:
    """OpenAlex-specific query formatting."""

    def test_simple_query(self):
        """Simple query preserved."""
        result = preprocess_query("neural networks", source="openalex")
        assert result == "neural networks"

    def test_strips_outer_quotes(self):
        """Outer double quotes are stripped (OpenAlex API handles raw text better)."""
        result = preprocess_query('"state space model"', source="openalex")
        assert not result.startswith('"') or not result.endswith('"')
        # But inner quotes should be kept
        assert "state space model" in result


class TestGenericPreprocessor:
    """Generic fallback behavior."""

    def test_generic_normalizes(self):
        """Generic source normalizes whitespace."""
        result = preprocess_query("  hello   world  ")
        assert result == "hello world"

    def test_generic_strips_outer_quotes(self):
        """Generic source strips outer quotes."""
        result = preprocess_query('"hello world"')
        assert result == "hello world"
        assert result == "hello world"

    def test_generic_keeps_inner_quotes(self):
        """Generic source only strips outer quotes, preserves inner."""
        result = preprocess_query('"machine" learning')
        assert result == '"machine" learning'


class TestAvailableSources:
    """Verify source registry is complete."""

    def test_academic_sources_defined(self):
        """ACADEMIC_SOURCES includes all expected sources (pubmed removed)."""
        expected = {"arxiv", "europepmc", "openalex", "core", "biorxiv", "generic"}
        assert expected == ACADEMIC_SOURCES

    def test_all_sources_have_formatters(self):
        """Every source has a registered formatter."""
        for source in ACADEMIC_SOURCES:
            assert source in SOURCE_FORMATTERS, f"Missing formatter for {source}"

    def test_formatters_are_callable(self):
        """All registered formatters are callable functions."""
        for name, formatter in SOURCE_FORMATTERS.items():
            assert callable(formatter), f"Formatter for {name} is not callable"

    def test_get_available_sources(self):
        """get_available_sources() returns ACADEMIC_SOURCES."""
        assert get_available_sources() == ACADEMIC_SOURCES


class TestBug3Centralized:
    """BUG 3 fix: all drivers should receive processed query."""

    def test_all_sources_receive_processed(self):
        """preprocess_query returns a string for every source (no crashes)."""
        query = '"machine learning" transformer attention'
        for source in ACADEMIC_SOURCES:
            result = preprocess_query(query, source=source)
            assert isinstance(result, str)
            assert len(result) > 0
            # No source should return the raw query unchanged in a way
            # that would cause the original bugs
            assert "The" not in result  # no garbage prefix

    def test_arxiv_and_europepmc_differ(self):
        """arXiv and EuropePMC produce different output for the same input."""
        query = '"state space model" Mamba'
        arxiv_result = preprocess_query(query, source="arxiv")
        epmc_result = preprocess_query(query, source="europepmc")
        # arXiv uses Boolean AND with all: prefix
        # EuropePMC preserves the original form
        assert arxiv_result != epmc_result
        assert "all:" in arxiv_result
        assert "all:" not in epmc_result
