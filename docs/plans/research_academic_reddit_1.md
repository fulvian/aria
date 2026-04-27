# Piano di Implementazione — Provider Accademici + Reddit per ARIA Research Agent

> **Documento**: `docs/plans/research_academic_reddit_1.md`  
> **Versione**: 1.0  
> **Data**: 2026-04-27  
> **Autore**: ARIA General Manager (Orchestrator)  
> **Analisi sorgente**: `docs/analysis/research_agent_enhancement.md`  
> **Blueprint rif.**: `docs/foundation/aria_foundation_blueprint.md` §11  
> **Stato**: DRAFT — Piano pre-implementazione  

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Assesment Stato Corrente](#2-assesment-stato-corrente)
3. [Provider Selezionati — Context7 Verified](#3-provider-selezionati--context7-verified)
4. [Strategia di Implementazione](#4-strategia-di-implementazione)
5. [Modifiche al Router](#5-modifiche-al-router)
6. [Modifiche a Intent Classifier](#6-modifiche-a-intent-classifier)
7. [Wrapper Script e mcp.json](#7-wrapper-script-e-mcpjson)
8. [Strategy di Test](#8-strategy-di-test)
9. [Pre-existing Issues da Risolvere](#9-pre-existing-issues-da-risolvere)
10. [Piano di Rollout](#10-piano-di-rollout)
11. [Analisi dei Rischi](#11-analisi-dei-rischi)
12. [Stima Effort](#12-stima-effort)
13. [Quality Gates](#13-quality-gates)
14. [Appendici](#14-appendici)

---

## 1. Executive Summary

Questo piano descrive l'integrazione di **4 nuovi provider** nel sub-agente di ricerca ARIA, espandendo le capacità di ricerca accademica e aggiungendo la ricerca su social media:

| Provider | Tipo | MCP Server | Auth | Costo | Priorità |
|----------|------|------------|------|-------|----------|
| **PubMed** | Accademico (biomedico) | `@cyanheads/pubmed-mcp-server` v2.6.4 | API key gratuita | $0 | 🔴 P0 |
| **arXiv** | Accademico (preprint) | `blazickjp/arxiv-mcp-server` (PyPI) | Nessuna | $0 | 🔴 P0 |
| **Europe PMC** | Accademico (biomedico EU) | Provider Python nativo | Nessuna | $0 | 🔴 P0 |
| **Reddit** | Social/Discussioni | `jordanburke/reddit-mcp-server` | Nessuna (anonimo) | $0 | 🟡 P1 |

**Costo totale aggiuntivo: €0/mese.**

Tutti i provider sono stati verificati tramite **Context7** per confermare disponibilità di MCP server, API signature, e pattern di configurazione aggiornati al 2026-04-27.

### Raccomandazioni chiave

1. **PubMed**: Usare `@cyanheads/pubmed-mcp-server` (NON `@iflow-mcp` come riportato nell'analisi) — 9 tools, Apache 2.0, 1053 snippet Context7, manutenzione attiva, public hosted instance disponibile
2. **arXiv**: Usare `blazickjp/arxiv-mcp-server` via `uv tool run` (4 tools: search_papers, download_paper, list_papers, read_paper)
3. **Europe PMC**: Implementare come **provider Python nativo** (YAGNI: non serve un mega-MCP con 6 fonti quando ci serve solo Europe PMC)
4. **Reddit**: Usare `jordanburke/reddit-mcp-server` in modalità anonima (11 tools read/write, zero-config)
5. **Nuovo Intent `SOCIAL`**: Creare un nuovo intent dedicato per Reddit e ricerche social

---

## 2. Assesment Stato Corrente

### 2.1 Architettura attuale (verificata sul codice)

```
Provider enum (router.py):
  SEARXNG, TAVILY, EXA, BRAVE, FETCH, WEBFETCH

Intent enum (router.py):
  GENERAL_NEWS, ACADEMIC, DEEP_SCRAPE, UNKNOWN

INTENT_TIERS (router.py):
  GENERAL_NEWS: SEARXNG > TAVILY > EXA > BRAVE > FETCH
  ACADEMIC:     SEARXNG > TAVILY > EXA > BRAVE > FETCH  ← uguale a GENERAL!
  DEEP_SCRAPE:  FETCH > WEBFETCH

Health check (router.py):
  Keyless providers: searxng, fetch, webfetch → sempre AVAILABLE
  Key-based providers: tavily, exa, brave → controllati via Rotator

mcp.json (.aria/kilocode/):
  11 server: filesystem, git, github, sequential-thinking, fetch, aria-memory,
             tavily-mcp, brave-mcp, exa-script, searxng-script, google_workspace,
             playwright (disabled)

Wrapper scripts (scripts/wrappers/):
  tavily-wrapper.sh, brave-wrapper.sh, exa-wrapper.sh,
  searxng-wrapper.sh, google-workspace-wrapper.sh
```

### 2.2 Problemi identificati

| # | Problema | Severità | File |
|---|----------|----------|------|
| **P1** | `ACADEMIC` usa la stessa ladder di `GENERAL_NEWS` — nessuna specializzazione accademica | Alta | `router.py:106-125` |
| **P2** | Test e conftest.py referenziano `FIRECRAWL_EXTRACT` e `FIRECRAWL_SCRAPE` che non esistono più nel `Provider` enum | Alta | `test_router.py`, `test_router_integration.py`, `conftest.py` |
| **P3** | `Intent.SOCIAL` non esiste — Reddit dovrebbe instradare via `GENERAL_NEWS` o nuovo intent | Media | `router.py:80-86` |
| **P4** | `INTENT_KEYWORDS` non include keyword PubMed, Europe PMC, Reddit | Media | `intent.py:19-70` |
| **P5** | `_refresh_health` non conosce i nuovi provider keyless (arxiv, europe_pmc, reddit) | Bassa | `router.py:319-344` |
| **P6** | `route()` restituisce `(provider, None)` per keyless — funziona ma va esteso per i nuovi | Bassa | `router.py:226-227` |

### 2.3 Pattern di integrazione consolidato

Il pattern ARIA per aggiungere un provider è:

```
1. Identificare MCP server (Context7 verification)
2. Creare wrapper script in scripts/wrappers/<provider>-wrapper.sh
3. Registrare in .aria/kilocode/mcp.json
4. Aggiungere Provider enum in router.py
5. Aggiornare INTENT_TIERS in router.py
6. Aggiornare INTENT_KEYWORDS in intent.py
7. Aggiornare _refresh_health in router.py
8. Aggiungere test
9. Aggiornare .env.example
10. Aggiornare LLM Wiki (research-routing.md)
```

---

## 3. Provider Selezionati — Context7 Verified

### 3.1 PubMed — `@cyanheads/pubmed-mcp-server`

**Context7 ID**: `/cyanheads/pubmed-mcp-server` | **Snippets**: 1053 | **Benchmark**: 83.7 | **License**: Apache 2.0

| Caratteristica | Valore |
|----------------|--------|
| Versione | 2.6.4 |
| N° tools | 9 |
| Installazione | `npx -y @cyanheads/pubmed-mcp-server@latest` |
| Configurazione env | `NCBI_API_KEY`, `NCBI_ADMIN_EMAIL`, `MCP_TRANSPORT_TYPE=stdio` |
| Public hosted | `https://pubmed.caseyjhand.com/mcp` (fallback) |

**Tools disponibili**:

| Tool | Descrizione |
|------|-------------|
| `pubmed_search_articles` | Ricerca PubMed con query syntax, filtri, paginazione |
| `pubmed_fetch_articles` | Fetch metadati completi per PMIDs (max 200) |
| `pubmed_fetch_fulltext` | Full-text da PMC + Unpaywall fallback |
| `pubmed_format_citations` | Citazioni in APA, MLA, BibTeX, RIS |
| `pubmed_find_related` | Articoli correlati, citanti, references |
| `pubmed_spell_check` | Spell-check query biomediche |
| `pubmed_lookup_mesh` | Esplora vocabolario MeSH |
| `pubmed_lookup_citation` | Risolvi riferimenti parziali → PMID |
| `pubmed_convert_ids` | Converti tra DOI, PMID, PMCID |

**Perché `@cyanheads` e NON `@iflow-mcp`**: L'analisi originale raccomandava `@iflow-mcp/pubmed-mcp-server`, ma Context7 mostra che `@cyanheads/pubmed-mcp-server` ha 1053 snippet (vs 0 per `@iflow-mcp`), benchmark 83.7, 9 tool, public hosted instance, e manutenzione attiva. La scelta è basata su evidenza Context7, non su preferenza soggettiva.

### 3.2 arXiv — `blazickjp/arxiv-mcp-server`

**Context7 ID**: `/blazickjp/arxiv-mcp-server` | **Snippets**: 112 | **Benchmark**: 76.1 | **License**: Apache 2.0

| Caratteristica | Valore |
|----------------|--------|
| Installazione | `uv tool install arxiv-mcp-server` |
| Avvio | `uv tool run arxiv-mcp-server --storage-path <path>` |
| API key | Nessuna richiesta |
| Rate limit | Gestito automaticamente dal server |

**Tools disponibili**:

| Tool | Descrizione |
|------|-------------|
| `search_papers` | Cerca arXiv per query, date range, categorie (cs.AI, cs.LG, etc.) |
| `download_paper` | Scarica paper per ID (HTML → PDF fallback) |
| `list_papers` | Elenca paper scaricati localmente |
| `read_paper` | Leggi contenuto paper scaricato |

### 3.3 Europe PMC — Provider Python Nativo

**Endpoint**: `https://www.ebi.ac.uk/europepmc/webservices/rest` | **Costo**: $0 | **API Key**: Nessuna

| Caratteristica | Valore |
|----------------|--------|
| Formato risposta | JSON |
| Rate limit | ~10 req/sec (500 req/min) |
| Paginazione | Cursor-based (`cursorMark`) |
| Page size max | 1000 |

**Perché provider nativo e non MCP**: 
- Lo Scientific Papers MCP (`benedict2310/scientific-papers-mcp`) include 6 fonti (arXiv, PubMed, Europe PMC, OpenAlex, bioRxiv, CORE) — ma noi implementiamo già arXiv e PubMed separatamente con MCP dedicati. Usare un mega-MCP violerebbe YAGNI
- L'API REST di Europe PMC è semplice (1 endpoint principale: `GET /search`)
- Un provider nativo Python (~80 LOC) dà controllo completo su timeout, error handling, e formato risposta
- Evita dipendenze da MCP server esterni non necessari

**Implementazione minima**:

```python
# src/aria/agents/search/providers/europepmc.py
import httpx
from typing import Any

class EuropePMCProvider:
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, session: httpx.AsyncClient | None = None):
        self._session = session or httpx.AsyncClient(timeout=30)

    async def search(self, query: str, page_size: int = 10) -> list[dict[str, Any]]:
        resp = await self._session.get(
            f"{self.BASE_URL}/search",
            params={
                "query": query, "format": "json",
                "resultType": "core", "pageSize": page_size,
            },
        )
        resp.raise_for_status()
        return resp.json().get("resultList", {}).get("result", [])
```

### 3.4 Reddit — `jordanburke/reddit-mcp-server`

**Context7 ID**: `/jordanburke/reddit-mcp-server` | **Snippets**: 39 | **License**: MIT

| Caratteristica | Valore |
|----------------|--------|
| Installazione | `npx reddit-mcp-server` |
| Modalità anonima | 10 req/min, nessuna configurazione |
| Modalità OAuth | 60-100 req/min (richiede `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`) |

**Tools disponibili**:

| Tool | Descrizione |
|------|-------------|
| `get_reddit_post` | Fetch post specifico |
| `get_top_posts` | Top posts da subreddit |
| `get_user_info` | Info utente Reddit |
| `get_subreddit_info` | Info subreddit |
| `get_trending_subreddits` | Subreddit trending |
| `search_reddit` | Cerca post su Reddit |
| `get_post_comments` | Commenti di un post |
| `get_user_posts` | Posts di un utente |
| `get_user_comments` | Commenti di un utente |
| `create_post` | Crea post (write) |
| `reply_to_post` | Rispondi a post (write) |

---

## 4. Strategia di Implementazione

### 4.1 Ordine di implementazione

```
Fase 1 (core):   PubMed + arXiv + Europe PMC → router + intent [P0]
Fase 2 (social): Reddit → nuovo intent SOCIAL [P1]
Fase 3 (fix):    Pre-existing test issues (FIRECRAWL references) [P0]
Fase 4 (qa):     Test completi + quality gates [P0]
Fase 5 (docs):   Wiki update + .env.example [P1]
```

### 4.2 Step per ogni provider

#### PubMed

1. Registrare NCBI API key (gratuita): https://www.ncbi.nlm.nih.gov/account/settings/
2. Aggiungere a `.env`: `NCBI_API_KEY=<key>`, `NCBI_ADMIN_EMAIL=fulviold@gmail.com`
3. Creare `scripts/wrappers/pubmed-wrapper.sh`
4. Aggiungere `pubmed` in `.aria/kilocode/mcp.json`
5. Aggiungere `Provider.PUBMED` in `router.py`
6. Aggiornare `INTENT_TIERS[Intent.ACADEMIC]`

**Wrapper script**:

```bash
#!/usr/bin/env bash
# scripts/wrappers/pubmed-wrapper.sh
set -euo pipefail

if [[ -z "${NCBI_API_KEY:-}" ]]; then
  echo "WARN: NCBI_API_KEY missing; PubMed rate limit will be 3 req/s" >&2
fi

export MCP_TRANSPORT_TYPE="${MCP_TRANSPORT_TYPE:-stdio}"
export MCP_LOG_LEVEL="${MCP_LOG_LEVEL:-info}"

exec npx -y @cyanheads/pubmed-mcp-server@latest
```

**mcp.json entry**:

```json
"pubmed-mcp": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/pubmed-wrapper.sh",
  "disabled": false,
  "env": {
    "NCBI_API_KEY": "${NCBI_API_KEY}",
    "NCBI_ADMIN_EMAIL": "${NCBI_ADMIN_EMAIL}",
    "MCP_TRANSPORT_TYPE": "stdio"
  }
}
```

#### arXiv

1. Nessuna API key richiesta
2. Installare: `uv tool install arxiv-mcp-server`
3. Creare `scripts/wrappers/arxiv-wrapper.sh`
4. Aggiungere `arxiv` in `.aria/kilocode/mcp.json`
5. Aggiungere `Provider.ARXIV` in `router.py`

**Wrapper script**:

```bash
#!/usr/bin/env bash
# scripts/wrappers/arxiv-wrapper.sh
set -euo pipefail

STORAGE_PATH="${ARXIV_STORAGE_PATH:-/home/fulvio/coding/aria/.aria/cache/arxiv}"
mkdir -p "$STORAGE_PATH"

exec uv tool run arxiv-mcp-server --storage-path "$STORAGE_PATH"
```

**mcp.json entry**:

```json
"arxiv-mcp": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/arxiv-wrapper.sh",
  "disabled": false,
  "env": {
    "ARXIV_STORAGE_PATH": "/home/fulvio/coding/aria/.aria/cache/arxiv"
  }
}
```

#### Europe PMC (Provider Python Nativo)

1. Creare `src/aria/agents/search/providers/europepmc.py`
2. Registrare in `providers/__init__.py`
3. Aggiungere `Provider.EUROPE_PMC` in `router.py`
4. Il provider viene chiamato direttamente dal search agent (non è un MCP server)

**Nota**: Poiché Europe PMC NON è un MCP server ma un provider nativo, il search agent dovrà importarlo e chiamarlo direttamente. Questo è diverso dal pattern MCP, ma appropriato per API REST semplici.

#### Reddit

1. Nessuna API key per modalità anonima
2. Aggiungere `reddit` in `.aria/kilocode/mcp.json` (no wrapper necessario)
3. Aggiungere `Provider.REDDIT` in `router.py`
4. Aggiungere `Intent.SOCIAL` in `router.py`
5. Aggiornare `INTENT_TIERS[Intent.SOCIAL]`

**mcp.json entry**:

```json
"reddit-mcp": {
  "command": "npx",
  "args": ["reddit-mcp-server"],
  "disabled": false
}
```

**Opzionale — OAuth per rate limit più alti**:
```json
"reddit-mcp": {
  "command": "npx",
  "args": ["reddit-mcp-server"],
  "disabled": false,
  "env": {
    "REDDIT_CLIENT_ID": "${REDDIT_CLIENT_ID}",
    "REDDIT_CLIENT_SECRET": "${REDDIT_CLIENT_SECRET}"
  }
}
```

---

## 5. Modifiche al Router

### 5.1 Provider Enum Esteso

```python
class Provider(StrEnum):
    # Provider esistenti
    SEARXNG = "searxng"
    TAVILY = "tavily"
    EXA = "exa"
    BRAVE = "brave"
    FETCH = "fetch"
    WEBFETCH = "webfetch"

    # Nuovi provider accademici
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    EUROPE_PMC = "europe_pmc"

    # Nuovo provider social
    REDDIT = "reddit"
```

### 5.2 Intent Enum Esteso

```python
class Intent(StrEnum):
    GENERAL_NEWS = "general/news"
    ACADEMIC = "academic"
    DEEP_SCRAPE = "deep_scrape"
    SOCIAL = "social"        # NUOVO
    UNKNOWN = "unknown"
```

### 5.3 INTENT_TIERS Ridisegnato

```python
INTENT_TIERS: dict[Intent, tuple[Provider, ...]] = {
    Intent.GENERAL_NEWS: (
        Provider.SEARXNG,   # tier 1 — self-hosted, privacy-first
        Provider.TAVILY,    # tier 2 — commercial, LLM-ready
        Provider.EXA,       # tier 3 — semantic search
        Provider.BRAVE,     # tier 4 — commercial web search
        Provider.FETCH,     # tier 5 — HTTP fallback
    ),
    Intent.ACADEMIC: (
        Provider.SEARXNG,      # tier 1 — self-hosted (cerca anche accademico)
        Provider.PUBMED,       # tier 2 — PubMed biomedico (API key opt.)
        Provider.ARXIV,        # tier 3 — arXiv preprint CS/ML/Physics
        Provider.EUROPE_PMC,   # tier 4 — Europe PMC biomedico EU (gratuito)
        Provider.TAVILY,       # tier 5 — fallback generalistico
        Provider.EXA,          # tier 6 — semantic search
        Provider.BRAVE,        # tier 7 — fallback
        Provider.FETCH,        # tier 8 — HTTP fallback
    ),
    Intent.DEEP_SCRAPE: (
        Provider.FETCH,     # tier 1 — HTTP fetch
        Provider.WEBFETCH,  # tier 2 — web fetch fallback
    ),
    Intent.SOCIAL: (
        Provider.REDDIT,       # tier 1 — Reddit (MCP, anonimo)
        Provider.SEARXNG,      # tier 2 — SearXNG fallback (engine reddit)
        Provider.TAVILY,       # tier 3 — generalistico
        Provider.BRAVE,        # tier 4 — fallback
    ),
}
```

### 5.4 Modifiche a `route()` per provider keyless

I nuovi provider `arxiv`, `europe_pmc`, e `reddit` (in modalità anonima) sono keyless e devono essere trattati come `searxng`/`fetch`/`webfetch`. Modificare il blocco:

```python
# Prima (riga 226-227):
if rotator_provider in ("searxng", "fetch", "webfetch"):
    return provider, None

# Dopo:
if rotator_provider in ("searxng", "fetch", "webfetch", "arxiv", "europe_pmc", "reddit"):
    return provider, None
```

### 5.5 Modifiche a `_refresh_health()`

```python
async def _refresh_health(self, provider: str) -> None:
    # Keyless providers: always AVAILABLE
    if provider in ("searxng", "fetch", "webfetch", "arxiv", "europe_pmc", "reddit"):
        self._health[provider] = HealthState.AVAILABLE
        return
    # ... existing logic unchanged
```

---

## 6. Modifiche a Intent Classifier

### 6.1 INTENT_KEYWORDS Esteso

```python
INTENT_KEYWORDS: dict[Intent, frozenset[str]] = {
    Intent.DEEP_SCRAPE: frozenset({
        "deep", "scrape", "crawl", "extract",
        "full page", "complete", "entire website",
        "all pages", "deep scrape", "scraping", "estrai",
    }),
    Intent.ACADEMIC: frozenset({
        "academic", "research", "paper", "journal", "article",
        "study", "scholar", "citation", "doi", "arxiv",
        "publication", "preprint", "conference", "proceedings",
        "pubmed", "pmid", "europe pmc", "europepmc",          # NUOVI
        "scientific", "experiment", "clinical trial",
        "abstract", "peer review", "literature review",
        "ricerca", "pubblicazione", "studio", "articolo scientifico",
    }),
    Intent.GENERAL_NEWS: frozenset({
        "news", "latest", "current", "recent", "breaking",
        "today", "headline", "update",
        "notizie", "ultime", "attualità", "novità",
    }),
    Intent.SOCIAL: frozenset({                                 # NUOVO
        "reddit", "social media", "forum", "discussion",
        "community", "subreddit", "trending", "viral",
        "what people are saying", "public opinion",
        "reddit discussion", "hacker news",
    }),
}
```

### 6.2 Modifica `classify_intent()` per supportare SOCIAL

```python
def classify_intent(query: str) -> Intent:
    query_lower = query.lower()
    scores: dict[Intent, int] = {
        Intent.GENERAL_NEWS: 0,
        Intent.ACADEMIC: 0,
        Intent.DEEP_SCRAPE: 0,
        Intent.SOCIAL: 0,       # NUOVO
    }
    # ... existing logic unchanged
```

---

## 7. Wrapper Script e mcp.json

### 7.1 Nuovi wrapper scripts

| Script | Provider | Complessità |
|--------|----------|-------------|
| `scripts/wrappers/pubmed-wrapper.sh` | PubMed | Media (API key) |
| `scripts/wrappers/arxiv-wrapper.sh` | arXiv | Bassa (storage path) |
| `scripts/wrappers/reddit-wrapper.sh` | Reddit (OAuth) | Opzionale, solo se OAuth |

### 7.2 mcp.json — entries complete

```json
{
  "mcpServers": {
    "... existing servers ...": {},
    
    "pubmed-mcp": {
      "command": "/home/fulvio/coding/aria/scripts/wrappers/pubmed-wrapper.sh",
      "disabled": false,
      "env": {
        "NCBI_API_KEY": "${NCBI_API_KEY}",
        "NCBI_ADMIN_EMAIL": "${NCBI_ADMIN_EMAIL}",
        "MCP_TRANSPORT_TYPE": "stdio"
      }
    },
    "arxiv-mcp": {
      "command": "/home/fulvio/coding/aria/scripts/wrappers/arxiv-wrapper.sh",
      "disabled": false,
      "env": {
        "ARXIV_STORAGE_PATH": "/home/fulvio/coding/aria/.aria/cache/arxiv"
      }
    },
    "reddit-mcp": {
      "command": "npx",
      "args": ["reddit-mcp-server"],
      "disabled": false
    }
  }
}
```

### 7.3 .env.example — nuove variabili

```bash
# === PubMed / NCBI ===
# NCBI_API_KEY=your-32-char-key-here
# NCBI_ADMIN_EMAIL=fulviold@gmail.com

# === Reddit (opzionale, per OAuth) ===
# REDDIT_CLIENT_ID=your-client-id
# REDDIT_CLIENT_SECRET=your-client-secret
```

---

## 8. Strategy di Test

### 8.1 Nuovi test da creare

| Test file | Cosa testa | Tipo |
|-----------|------------|------|
| `tests/unit/agents/search/test_provider_pubmed.py` | PubMed provider registration, enum, tier | Unit |
| `tests/unit/agents/search/test_provider_arxiv.py` | arXiv provider registration, enum, tier | Unit |
| `tests/unit/agents/search/test_provider_europepmc.py` | Europe PMC provider search(), error handling | Unit |
| `tests/unit/agents/search/test_intent_social.py` | SOCIAL intent classification keywords | Unit |
| `tests/unit/agents/search/test_router_academic_tiers.py` | ACADEMIC intent: PubMed > arXiv > Europe PMC order | Unit |
| `tests/unit/agents/search/test_router_social_tiers.py` | SOCIAL intent: Reddit > SearXNG > Tavily order | Unit |
| `tests/unit/agents/search/test_providers/test_europepmc.py` | EuropePMCProvider.search() integration | Integration |

### 8.2 Test esistenti da aggiornare

| Test file | Modifica necessaria |
|-----------|---------------------|
| `tests/unit/agents/search/test_router.py` | Rimuovere riferimenti a `FIRECRAWL_EXTRACT`, `FIRECRAWL_SCRAPE` |
| `tests/unit/agents/search/test_router_integration.py` | Rimuovere riferimenti a Firecrawl; aggiungere test nuovi provider |
| `tests/unit/agents/search/conftest.py` | Rimuovere `FIRECRAWL_EXTRACT`/`FIRECRAWL_SCRAPE` fixtures |
| `tests/unit/agents/search/test_intent.py` | Aggiungere test per keyword SOCIAL, PubMed, Europe PMC |

### 8.3 Commands per eseguire i test

```bash
# Prima delle modifiche (baseline)
pytest tests/unit/agents/search/ -q

# Dopo le modifiche
pytest tests/unit/agents/search/ -q -x --tb=short

# Solo test nuovi
pytest tests/unit/agents/search/test_intent_social.py -q
pytest tests/unit/agents/search/test_router_academic_tiers.py -q
```

---

## 9. Pre-existing Issues da Risolvere

### 9.1 FIRECRAWL references in test code

**Problema**: I test e conftest.py referenziano `Provider.FIRECRAWL_EXTRACT` e `Provider.FIRECRAWL_SCRAPE`, che sono stati rimossi dal `Provider` enum nel commit di ripristino (2026-04-27). Questo causa `AttributeError` se i test vengono eseguiti.

**File affetti**:
- `tests/unit/agents/search/test_router.py:23-24` — `test_provider_values` si aspetta `FIRECRAWL_EXTRACT` e `FIRECRAWL_SCRAPE`
- `tests/unit/agents/search/test_router.py:30-31` — `test_all_providers_unique` conta providers inclusi i rimossi
- `tests/unit/agents/search/conftest.py:34-35` — `all_providers` fixture include `FIRECRAWL_EXTRACT`
- `tests/unit/agents/search/conftest.py:44-45` — `deep_scrape_providers` include `FIRECRAWL_EXTRACT` e `FIRECRAWL_SCRAPE`
- `tests/unit/agents/search/test_router_integration.py:88,116,189-211` — vari test usano provider Firecrawl

**Fix**: Aggiornare i test per riflettere il `Provider` enum corrente. Questa è una pre-condizione per far passare i nuovi test.

### 9.2 Disallineamento INTENT_TIERS nei test

I test di integrazione (`test_router_integration.py`) verificano un `INTENT_TIERS` che include Firecrawl, ma il `INTENT_TIERS` reale nel codice non lo include più. I test devono essere allineati.

---

## 10. Piano di Rollout

### Fase 1: Fix pre-existing issues (30 min)
- [ ] Aggiornare `test_router.py`, `test_router_integration.py`, `conftest.py` per rimuovere riferimenti Firecrawl
- [ ] Verificare che i test passino con `Provider` enum corrente
- [ ] Commit: `fix(search): remove stale FIRECRAWL references from tests`

### Fase 2: PubMed + arXiv MCP (1h)
- [ ] Registrare NCBI API key (HITL: serve browser)
- [ ] Creare `scripts/wrappers/pubmed-wrapper.sh`
- [ ] Creare `scripts/wrappers/arxiv-wrapper.sh`
- [ ] Aggiungere `pubmed-mcp` e `arxiv-mcp` in `mcp.json`
- [ ] Aggiornare `.env` e `.env.example`
- [ ] Verificare startup MCP server (`/mcps` nel REPL)
- [ ] Commit: `feat(search): add PubMed and arXiv MCP providers`

### Fase 3: Europe PMC provider nativo (1h)
- [ ] Creare `src/aria/agents/search/providers/europepmc.py`
- [ ] Aggiornare `providers/__init__.py`
- [ ] Commit: `feat(search): add Europe PMC native provider`

### Fase 4: Router + Intent update (1h)
- [ ] Aggiungere `Provider.PUBMED`, `Provider.ARXIV`, `Provider.EUROPE_PMC`, `Provider.REDDIT`
- [ ] Aggiungere `Intent.SOCIAL`
- [ ] Aggiornare `INTENT_TIERS` per tutti gli intent
- [ ] Aggiornare `route()` keyless providers list
- [ ] Aggiornare `_refresh_health()` keyless providers list
- [ ] Aggiornare `INTENT_KEYWORDS` con nuove keyword
- [ ] Aggiornare `classify_intent()` per `SOCIAL`
- [ ] Commit: `feat(search): expand router with academic and social providers`

### Fase 5: Reddit MCP (30 min)
- [ ] Aggiungere `reddit-mcp` in `mcp.json` (modalità anonima)
- [ ] Verificare startup
- [ ] Commit: `feat(search): add Reddit MCP provider`

### Fase 6: Test (1.5h)
- [ ] Scrivere test per nuovi provider
- [ ] Scrivere test per nuovo intent `SOCIAL`
- [ ] Scrivere test per nuovi tier accademici
- [ ] Eseguire quality gates: `ruff check .`, `mypy src`, `pytest -q`
- [ ] Commit: `test(search): add tests for academic and social providers`

### Fase 7: Documentazione (30 min)
- [ ] Aggiornare `docs/llm_wiki/wiki/research-routing.md`
- [ ] Aggiornare `docs/llm_wiki/wiki/index.md`
- [ ] Aggiungere entry in `docs/llm_wiki/wiki/log.md`
- [ ] Commit: `docs(search): update research routing wiki for new providers`

---

## 11. Analisi dei Rischi

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| **PubMed MCP non si avvia senza API key** | Bassa | Medio | L'MCP server funziona senza key (solo rate limit ridotto). Wrapper emette WARN. |
| **arXiv MCP richiede `uv tool install`** | Media | Basso | Aggiungere `uv tool install arxiv-mcp-server` nel wrapper se necessario |
| **Europe PMC downtime** | Bassa | Medio | Fallback a PubMed per biomedico, a Tavily/Exa per generale |
| **Reddit blocca accesso anonimo** | Media | Alto | Piano B: SearXNG engine reddit; Piano C: Redlib self-hosted |
| **PubMed MCP (@cyanheads) richiede Bun?** | Bassa | Bassa | Il README menziona Bun ma supporta anche `npx`. Verificare. |
| **Aumento risorse per 4 nuovi MCP** | Media | Bassa | ~100MB RAM totali stimati. Accettabile per MVP. |
| **Rate limit Reddit anonimo (10 req/min)** | Media | Medio | OAuth se necessario (richiede RBP approval). Il tier SOCIAL ha fallback a SearXNG. |

---

## 12. Stima Effort

| Task | Effort | Dipendenze |
|------|--------|------------|
| Fix test Firecrawl references | 30 min | Nessuna |
| PubMed wrapper + mcp.json | 30 min | NCBI API key (HITL) |
| arXiv wrapper + mcp.json | 30 min | `uv tool install` |
| Europe PMC provider nativo | 1h | Nessuna |
| Router update (Provider, Intent, INTENT_TIERS) | 45 min | Provider definiti |
| Intent classifier update | 30 min | Intent SOCIAL definito |
| Reddit mcp.json | 15 min | Nessuna |
| Test nuovi provider | 1h | Router + Intent completi |
| Test fix + allineamento | 30 min | Fix Firecrawl references |
| Documentazione wiki | 30 min | Implementazione completa |
| **Totale** | **~6h** | |

---

## 13. Quality Gates

Prima di considerare completata l'implementazione, devono passare:

| Gate | Comando | Criterio |
|------|---------|----------|
| Lint | `ruff check .` | 0 errori |
| Format | `ruff format --check .` | 0 differenze |
| Type check | `mypy src/aria/agents/search/` | 0 errori |
| Unit tests | `pytest tests/unit/agents/search/ -q` | Tutti passano |
| MCP startup | `/mcps` nel REPL | pubmed-mcp, arxiv-mcp, reddit-mcp connessi |

---

## 14. Appendici

### A. Context7 Verification Log

| Provider | Context7 ID | Snippets | Benchmark | Reputation | Verified |
|----------|-------------|----------|-----------|------------|----------|
| PubMed | `/cyanheads/pubmed-mcp-server` | 1053 | 83.7 | High | ✅ 2026-04-27 |
| arXiv | `/blazickjp/arxiv-mcp-server` | 112 | 76.1 | High | ✅ 2026-04-27 |
| Scientific Papers | `/benedict2310/scientific-papers-mcp` | 5319 | 67.0 | Medium | ✅ (escluso per YAGNI) |
| Reddit | `/jordanburke/reddit-mcp-server` | 39 | — | Medium | ✅ 2026-04-27 |

### B. Architettura Finale

```
                        ┌─ Intent ─┐
                        │ GENERAL  │
                        │ ACADEMIC │
                        │ SOCIAL   │  ← NUOVO
                        │ DEEP_SCR │
                        └────┬─────┘
                             │ classify_intent()
                             ▼
                   ┌─────────────────┐
                   │ ResearchRouter  │
                   │ route(intent)   │
                   └──┬──┬──┬──┬──┬──┘
                      │  │  │  │  │
        ┌─────────────┘  │  │  │  └──────────────┐
        │                │  │  │                  │
        ▼                ▼  ▼  ▼                  ▼
 ┌──────────┐   ┌──────┐ ┌───┐ ┌───┐   ┌──────────┐
 │ SEARXNG  │   │TAVILY│ │EXA│ │...│   │  REDDIT  │  ← NUOVO
 │(self-host)│   │(MCP) │ │MCP│ │   │   │(MCP anon)│
 └──────────┘   └──────┘ └───┘ └───┘   └──────────┘
        │              │     │              │
        ▼              ▼     ▼              ▼
 ┌──────────┐   ┌──────┐ ┌──────┐   ┌──────────┐
 │  PUBMED  │   │ARXIV │ │EUROPE│   │  FETCH   │
 │  (MCP)   │   │(MCP) │ │ PMC  │   │ (scrape) │
 └──────────┘   └──────┘ │(nativo)│  └──────────┘
                         └──────┘
   ↑ NUOVI ↑              ↑ NUOVO ↑
```

### C. Decisioni Architetturali

| Decisione | Motivazione |
|-----------|-------------|
| `@cyanheads/pubmed-mcp-server` anziché `@iflow-mcp` | Context7: 1053 snippet vs 0, benchmark 83.7, 9 tool, public hosted instance |
| Provider Python nativo per Europe PMC | YAGNI: non serve un mega-MCP 6-fonti; API REST semplice (~80 LOC) |
| `blazickjp/arxiv-mcp-server` via `uv tool` | Confermato Context7 (112 snippet, benchmark 76.1), PyPI, 4 tool |
| `jordanburke/reddit-mcp-server` anonimo | Zero-config, 10 req/min sufficienti per MVP; OAuth futuro se necessario |
| Nuovo `Intent.SOCIAL` (non routing dentro `GENERAL_NEWS`) | Separa semanticamente le ricerche social; permette tier dedicato (Reddit > SearXNG > Tavily) |
| PubMed TIER 2 in ACADEMIC (dopo SearXNG) | PubMed è specializzato biomedico; SearXNG è privacy-first e copre anche accademico generale |
| arXiv TIER 3 in ACADEMIC | arXiv è specializzato preprint CS/ML/Physics; complementare a PubMed |

### D. Riferimenti

| Risorsa | URL |
|---------|-----|
| Analisi origine | `docs/analysis/research_agent_enhancement.md` |
| Blueprint §11 | `docs/foundation/aria_foundation_blueprint.md` |
| Wiki research-routing | `docs/llm_wiki/wiki/research-routing.md` |
| PubMed MCP (Context7) | https://context7.com/cyanheads/pubmed-mcp-server/llms.txt |
| arXiv MCP (Context7) | https://context7.com/blazickjp/arxiv-mcp-server/llms.txt |
| Reddit MCP (Context7) | https://context7.com/jordanburke/reddit-mcp-server/llms.txt |
| PubMed MCP (npm) | https://www.npmjs.com/package/@cyanheads/pubmed-mcp-server |
| arXiv MCP (PyPI) | https://github.com/blazickjp/arxiv-mcp-server |
| Reddit MCP (GitHub) | https://github.com/jordanburke/reddit-mcp-server |
| NCBI API Key | https://www.ncbi.nlm.nih.gov/account/settings/ |
| Europe PMC API | https://europepmc.org/RestfulWebService |

---

> **Fine del piano.** Questo documento è il punto di riferimento unico per l'implementazione.  
> Dopo approvazione dell'utente (HITL Milestone 2 — Technical Design), procedere con la Fase 1.
