"""Query Preprocessor Centralizzato — Academic Intent Query Normalization.

Centralizza le regole di preprocessing query per intent accademici,
attualmente sparse nei wrapper shell di scientific-papers-mcp.

Bug risolti (da scientific-papers-wrapper.sh):
  BUG 1: arXiv driver — query wrappata in doppi apici (frase esatta)
  BUG 2: EuropePMC driver — stessa cosa + sort=relevance rompe API
  BUG 3: search-papers.js — nessuna pre-elaborazione query centralizzata

Usage:
    from aria.agents.search.query_preprocessor import preprocess_query

    processed = preprocess_query('"state space model" Mamba', source="arxiv")
    # -> 'all:"state space model" AND all:Mamba AND all:efficient'
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

# ─── Configurazione ──────────────────────────────────────────────────────────

# Sorgenti supportate dal preprocessor
# pubmed REMOVED 2026-04-30: scientific-papers-mcp covers PubMed via source="europepmc"
ACADEMIC_SOURCES: Final[set[str]] = {
    "arxiv",
    "europepmc",
    "openalex",
    "core",
    "biorxiv",
    "generic",
}

# Pattern per identificare termini quotati (es. "deep learning")
QUOTED_PHRASE_PATTERN: Final[re.Pattern[str]] = re.compile(r'"([^"]+)"')

# Pattern per whitespace multiplo
MULTI_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"\s+")


# ─── Preprocessor core ───────────────────────────────────────────────────────


def _normalize_whitespace(query: str) -> str:
    """Normalizza spazi bianchi: multi-spazio → singolo, trim.

    Esempio: "  hello   world  " → "hello world"
    """
    return MULTI_WHITESPACE.sub(" ", query).strip()


def _strip_outer_quotes(query: str) -> str:
    """Rimuove eventuali doppi apici esterni che wrappano l'intera query.

    Esempio: '"state space model"' → 'state space model'
    """
    s = query.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].strip()
    return s


def _extract_quoted_terms(query: str) -> list[str]:
    """Estrae le frasi quotate dalla query.

    Esempio: '"deep learning" transformer' → ['deep learning']
    """
    return QUOTED_PHRASE_PATTERN.findall(query)


def _split_unquoted_terms(query: str) -> list[str]:
    """Divide la query in termini non quotati, rimuovendo le frasi quotate.

    Esempio: '"deep learning" transformer attention' → ['transformer', 'attention']
    """
    # Rimuovi frasi quotate
    without_quoted = QUOTED_PHRASE_PATTERN.sub("", query)
    # Splitta e filtra vuoti
    return [t for t in without_quoted.split() if t.strip()]


def _remove_quotes_from_query(query: str) -> str:
    """Rimuove TUTTI i doppi apici dalla query (per sorgenti che non li supportano).

    Esempio: '"state space model" Mamba' → 'state space model Mamba'
    """
    return query.replace('"', "").strip()


# ─── Source-specific formatters ──────────────────────────────────────────────


def _format_arxiv_query(query: str) -> str:
    """Formatta query per arXiv API (Boolean AND search).

    Trasforma termini non quotati in `all:term AND ...` preservando
    le frasi quotate come `all:"frase esatta"`.

    Esempio:
      Input:  '"state space model" Mamba efficient'
      Output: 'all:"state space model" AND all:Mamba AND all:efficient'
    """
    quoted = _extract_quoted_terms(query)
    unquoted = _split_unquoted_terms(query)

    terms: list[str] = []

    # Frasi quotate → all:"frase" (ricerca esatta)
    for q in quoted:
        terms.append(f'all:"{q}"')

    # Termini singoli → all:term (ricerca generica)
    for t in unquoted:
        terms.append(f"all:{t}")

    if not terms:
        return query

    return " AND ".join(terms)


def _format_europepmc_query(query: str) -> str:
    """Formatta query per Europe PMC REST API.

    A differenza di arXiv, EuropePMC NON accetta sort=relevance esplicito.
    Non usa prefisso field (la API fa search su tutti i campi).

    Esempio:
      Input:  '"machine learning" protein folding'
      Output: '"machine learning" protein folding'
          (le frasi quotate sono supportate da EuropePMC API)
    """
    # EuropePMC API supporta le frasi quotate cosi' come sono
    return _normalize_whitespace(query)


def _format_openalex_query(query: str) -> str:
    """Formatta query per OpenAlex API.

    OpenAlex usa search parameter che funziona bene con query naturali.

    Esempio:
      Input:  '"state space model" transformer'
      Output: '"state space model" transformer'
    """
    return _strip_outer_quotes(_normalize_whitespace(query))


def _format_biorxiv_query(query: str) -> str:
    """Formatta query per bioRxiv/medRxiv API.

    API semplice, query naturale.
    """
    return _normalize_whitespace(query)


def _format_core_query(query: str) -> str:
    """Formatta query per CORE API.

    CORE accetta query naturali con operatori boolean.
    """
    return _normalize_whitespace(query)


def _format_generic_query(query: str) -> str:
    """Formatta query generica: normalize + strip outer quotes."""
    return _strip_outer_quotes(_normalize_whitespace(query))


# ─── Registry ────────────────────────────────────────────────────────────────

SOURCE_FORMATTERS: dict[str, Callable[[str], str]] = {
    "arxiv": _format_arxiv_query,
    "europepmc": _format_europepmc_query,
    "openalex": _format_openalex_query,
    "biorxiv": _format_biorxiv_query,
    "core": _format_core_query,
    "generic": _format_generic_query,
}


# ─── Public API ──────────────────────────────────────────────────────────────


def preprocess_query(query: str, source: str = "generic") -> str:
    """Preprocessa una query per una specifica sorgente accademica.

    1. Normalizza whitespace
    2. Applica regole source-specifiche
    3. Se la sorgente non e' riconosciuta, usa regole generiche

    Args:
        query: Query da preprocessare.
        source: Sorgente target (arxiv, europepmc, pubmed, openalex, biorxiv, core, generic).

    Returns:
        Query preprocessata per la sorgente specificata.

    Example:
        >>> preprocess_query('"state space model" Mamba', source="arxiv")
        'all:"state space model" AND all:Mamba'
        >>> preprocess_query('"machine learning" protein folding', source="europepmc")
        '"machine learning" protein folding'
    """
    if not query or not query.strip():
        return query

    # Step 1: normalize whitespace always
    normalized = _normalize_whitespace(query)

    # Step 2: source-specific formatting
    if source in SOURCE_FORMATTERS:
        return SOURCE_FORMATTERS[source](normalized)
    return _format_generic_query(normalized)


def get_available_sources() -> set[str]:
    """Restituisce le sorgenti supportate dal preprocessor."""
    return ACADEMIC_SOURCES


# ─── Exports ─────────────────────────────────────────────────────────────────

__all__ = [
    "ACADEMIC_SOURCES",
    "SOURCE_FORMATTERS",
    "get_available_sources",
    "preprocess_query",
]
