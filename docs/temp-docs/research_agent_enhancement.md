# Research Agent Enhancement — Analisi e Previsione di Integrazione

> **Data**: 2026-04-27  
> **Versione**: 1.0  
> **Autore**: ARIA ARIA-Conductor  
> **Stato**: Draft — Analisi tecnica pre-implementazione  
> **Blueprint rif.**: `docs/foundation/aria_foundation_blueprint.md` §11

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Architettura Provider di Ricerca ARIA — Stato Attuale](#2-architettura-provider-di-ricerca-aria--stato-attuale)
3. [Provider Accademici](#3-provider-accademici)
   - 3.1 [PubMed (NCBI E-utilities)](#31-pubmed-ncbi-e-utilities)
   - 3.2 [Europe PMC (EuroSearch)](#32-europe-pmc-eurosearch)
   - 3.3 [arXiv](#33-arxiv)
4. [Provider Generalistico — Reddit](#4-provider-generalistico--reddit)
5. [Analisi Comparativa e Raccomandazioni](#5-analisi-comparativa-e-raccomandazioni)
6. [Piano di Integrazione](#6-piano-di-integrazione)
7. [Modifiche al Router](#7-modifiche-al-router)
8. [Costi e API Key](#8-costi-e-api-key)
9. [Rischi e Mitigazioni](#9-rischi-e-mitigazioni)

---

## 1. Executive Summary

Questo report analizza l'integrazione di **4 nuovi provider** per il sub-agente di ricerca di ARIA:

| Provider | Tipo | API Key? | Costo | MCP esistente | Priorità |
|----------|------|----------|-------|---------------|----------|
| **PubMed** | Accademico | Opzionale (raccomandata) | Gratuito | ✅ `@iflow-mcp/pubmed-mcp-server` | Alta |
| **Europe PMC** | Accademico | No | Gratuito | ✅ Incluso in `scientific-papers-mcp` | Alta |
| **arXiv** | Accademico | No | Gratuito | ✅ `arxiv-mcp-server` (blazickjp) | Alta |
| **Reddit** | Generalistico | Opzionale (per OAuth) | Gratuito (MCP anonimo) | ✅ `reddit-mcp-server` (jordanburke) | Media |

**Raccomandazione chiave**: Seguire il pattern già consolidato in ARIA per l'integrazione dei provider:
1. Ogni provider come **MCP server** registrato in `mcp.json`
2. **Wrapper script** in `scripts/wrappers/` per gestire credenziali e configurazione
3. **Nuovo intent** `SOCIAL` nel router per Reddit (o routing dentro `general/news`)
4. **Nuovo intent** `ACADEMIC` già esiste — espandere con PubMed, Europe PMC, arXiv

---

## 2. Architettura Provider di Ricerca ARIA — Stato Attuale

### 2.1 Provider esistenti

| Provider | Tipo | Meccanismo | Intent coperti | Tier |
|----------|------|------------|----------------|------|
| **SearXNG** | Generalistico | MCP (`searxng-mcp`) via wrapper | general/news, academic | 1 |
| **Tavily** | Generalistico | MCP (`tavily-mcp`) via wrapper + credential rotation | general/news, academic | 2 |
| **Exa** | Generalistico/Semantico | MCP (`exa-mcp-server`) via wrapper | general/news, academic | 3 |
| **Brave** | Generalistico | MCP (`brave-search-mcp-server`) via wrapper | general/news, academic | 4 |
| **Fetch** | Deep scrape | MCP (`mcp-server-fetch`) via uvx | deep_scrape | 5 |
| **WebFetch** | Deep scrape | Locale (webfetch) | deep_scrape | 6 |

### 2.2 Pattern di integrazione (consolidato)

```
┌──────────────────────────────────────────────────────┐
│  .kilo/mcp.json                                      │
│  {                                                   │
│    "mcpServers": {                                   │
│      "tavily":   { "command": "scripts/wrappers/..." }│
│      "brave":    { "command": "npx ..." }             │
│      ...                                              │
│    }                                                  │
│  }                                                    │
├──────────────────────────────────────────────────────┤
│  scripts/wrappers/<provider>-wrapper.sh               │
│  ├── Auto-acquire API key da CredentialManager         │
│  ├── Pre-verify chiave (per wrapper Tavily)            │
│  └── exec npx -y <mcp-server>                         │
├──────────────────────────────────────────────────────┤
│  src/aria/agents/search/router.py                     │
│  ├── Provider enum                                    │
│  ├── INTENT_TIERS dict                                │
│  ├── route() → tier fallback                          │
│  └── Health check + circuit breaker                   │
├──────────────────────────────────────────────────────┤
│  src/aria/agents/search/intent.py                     │
│  └── classify_intent() → keyword-based                │
├──────────────────────────────────────────────────────┤
│  src/aria/credentials/manager.py                      │
│  └── CredentialManager.acquire(provider)              │
└──────────────────────────────────────────────────────┘
```

### 2.3 Schema di routing attuale

```python
INTENT_TIERS = {
    Intent.GENERAL_NEWS: (SEARXNG, TAVILY, EXA, BRAVE, FETCH),
    Intent.ACADEMIC:     (SEARXNG, TAVILY, EXA, BRAVE, FETCH),  # stesso!
    Intent.DEEP_SCRAPE:  (FETCH, WEBFETCH),
}
```

**Problema rilevato**: I provider accademici non hanno un intent dedicato — `ACADEMIC` usa la stessa ladder di `GENERAL_NEWS`. I nuovi provider accademici (PubMed, Europe PMC, arXiv) dovrebbero entrare nella ladder `ACADEMIC`, preferibilmente **prima** dei provider generalistici.

---

## 3. Provider Accademici

### 3.1 PubMed (NCBI E-utilities)

#### Panoramica

PubMed è il database di letteratura biomedica più vasto al mondo, gestito dal **National Center for Biotechnology Information (NCBI)**. L'accesso programmatico avviene tramite le **E-utilities** (Entrez Programming Utilities).

| Caratteristica | Valore |
|----------------|--------|
| **URL Base** | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` |
| **Protocollo** | HTTPS |
| **Formati risposta** | JSON (ESearch, ESummary), XML e Text (EFetch) |
| **Copertura** | 36M+ citazioni, articoli biomedici dal 1940 |
| **Costo** | Gratuito |
| **API Key** | Opzionale ma raccomandata (gratuita da registrare) |
| **Rate limit senza key** | 3 req/sec per IP |
| **Rate limit con key** | 10 req/sec per API key |
| **Max risultati per search** | 10.000 (PubMed) |
| **Autenticazione** | Parametro `api_key` nella query string + `email` obbligatorio |

#### API Endpoints principali

| Utility | Endpoint | Funzione |
|---------|----------|----------|
| **ESearch** | `esearch.fcgi` | Ricerca testuale → lista PMIDs |
| **ESummary** | `esummary.fcgi` | Metadati veloci per PMIDs (titolo, autori, journal, DOI) |
| **EFetch** | `efetch.fcgi` | Record completi (abstract, MeSH, references) |
| **ELink** | `elink.fcgi` | Collegamenti a full-text e database correlati |

#### Query Fields (PubMed)

| Tag | Descrizione | Esempio |
|-----|-------------|---------|
| `[Title]` | Titolo articolo | `cancer[Title]` |
| `[Author]` | Autore | `Smith[Author]` |
| `[Journal]` | Rivista | `Nature[Journal]` |
| `[MeSH Terms]` | Termini MeSH | `neoplasms[MeSH]` |
| `[Abstract]` | Abstract | `gene[Abstract]` |
| `[Affiliation]` | Affiliazione | `Harvard[Affil]` |
| `[pdat]` | Data pubblicazione | `2020[pdat]` |

#### MCP Server esistenti

Esistono **almeno 7 MCP server** per PubMed:

| Server | URL | Note |
|--------|-----|------|
| `@iflow-mcp/pubmed-mcp-server` | [npm](https://www.npmjs.com/package/@iflow-mcp/pubmed-mcp-server) | **Raccomandato** — MIT, tools: search, fetch_summary, get_full_text |
| `ncukondo/pubmed-mcp` | [GitHub](https://github.com/ncukondo/pubmed-mcp) | MIT, config: `PUBMED_EMAIL`, `PUBMED_API_KEY` |
| Augmented-Nature/PubMed-MCP-Server | [GitHub](https://github.com/Augmented-Nature/PubMed-MCP-Server) | Python, 16 tools specializzati |
| openpharma-org/pubmed-mcp | [GitHub](https://github.com/openpharma-org/pubmed-mcp) | Tools: search_keywords, search_advanced, get_article_metadata |

**Raccomandazione**: Usare `@iflow-mcp/pubmed-mcp-server` come MCP esterno (pattern npx), con wrapper bash per gestire `NCBI_API_KEY` e `PUBMED_EMAIL`.

#### Modalità di integrazione in ARIA

**Opzione A — MCP Server (Raccomandata)**:
```
.kilo/mcp.json → pubmed-mcp → wrapper → npx
```

**Opzione B — Provider Python nativo**:
```
src/aria/agents/search/providers/pubmed.py → chiama E-utilities REST
```

**Opzione A è preferita** perché:
- Segue il pattern consolidato degli altri provider
- L'MCP server gestisce già rate limiting e formati
- Minimo codice da scrivere e mantenere

#### Wrapper script proposto

```bash
#!/usr/bin/env bash
# scripts/wrappers/pubmed-wrapper.sh
set -euo pipefail

# Configura credenziali NCBI
if [[ -z "${NCBI_API_KEY:-}" ]]; then
  # Fallback: estrai da environment o credenziali cifrate
  echo "WARN: NCBI_API_KEY missing; rate limit will be 3 req/sec" >&2
fi

if [[ -z "${PUBMED_EMAIL:-}" ]]; then
  # Fallback: usa email utente
  export PUBMED_EMAIL="fulviold@gmail.com"
fi

exec npx -y @iflow-mcp/pubmed-mcp-server
```

---

### 3.2 Europe PMC (EuroSearch)

#### Panoramica

Il termine **"EuroSearch"** non corrisponde a un servizio attuale con questo nome. L'analisi ha identificato **Europe PMC** (Europe PubMed Central) come il candidato più probabile:

- Repository **europeo** di letteratura biomedica e scientifica
- Gestito da **EMBL-EBI** (European Bioinformatics Institute)
- **42M+ articoli**, preprint, brevetti, linee guida cliniche
- API REST completamente gratuita senza API key

| Caratteristica | Valore |
|----------------|--------|
| **URL Base** | `https://www.ebi.ac.uk/europepmc/webservices/rest` |
| **Protocollo** | HTTPS |
| **Formati** | JSON, XML, Dublin Core |
| **Costo** | Gratuito |
| **API Key** | **Non richiesta** per uso base |
| **Rate limit** | ~10 req/sec (500 req/min) |
| **Paginazione** | Cursor-based (`cursorMark`) |
| **Page size max** | 1000 (default 25) |

#### Endpoint API

| Endpoint | Descrizione |
|----------|-------------|
| `GET /search?query=...&format=json` | Ricerca articoli |
| `GET /search?query=...&cursorMark=*&pageSize=25` | Ricerca con cursore |
| `GET /{source}/{id}/citations` | Citazioni |
| `GET /{source}/{id}/references` | Riferimenti bibliografici |
| `GET /{source}/{id}/fullTextXML` | Full text XML |
| `GET /{source}/{id}/links` | Dati correlati |

**Formato risposta JSON**:
```json
{
  "hitCount": 12345,
  "nextCursorMark": "AoIIP4j6gSg1NTMz...",
  "resultList": {
    "result": [
      {
        "id": "PMC1234567",
        "source": "PMC",
        "title": "CRISPR-Cas9 in cancer therapy...",
        "authorString": "Smith J, Brown A...",
        "journalTitle": "Nature",
        "pubYear": "2024",
        "doi": "10.1038/...",
        "abstractText": "...",
        "firstPublicationDate": "2024-01-15"
      }
    ]
  }
}
```

#### MCP Server esistenti

| Nome | Inclusione | URL |
|------|-----------|-----|
| **Scientific Paper Harvester** | arXiv, OpenAlex, PMC, Europe PMC, bioRxiv, CORE | [GitHub](https://github.com/benedict2310/Scientific-Papers-MCP) |
| **Paper Search MCP** | arXiv, PubMed, Google Scholar, Europe PMC, DOAJ | [GitHub](https://github.com/openags/paper-search-mcp) |
| **PubMed Search MCP** | PubMed, Europe PMC, CORE, OpenAlex, NCBI (40 tools) | [GitHub](https://github.com/u9401066/pubmed-search-mcp) |
| **Europe PMC Literature Search MCP** | Solo Europe PMC (FastMCP) | [lobehub.com](https://lobehub.com/mcp/gqy20-article-mcp) |

**Raccomandazione**: Due opzioni:

1. **Usare `scientific-papers-mcp`** (copre Europe PMC + arXiv + PubMed in un solo server) — **Raccomandato per efficienza**
2. **Implementare provider Python nativo** chiamando `api.europepmc.org` — più leggero se vogliamo solo Europe PMC

#### Libreria Python helper

```bash
pip install pyeuropepmc
```

```python
from pyeuropepmc import SearchEngine

engine = SearchEngine()
results = engine.search(query="CRISPR AND cancer", limit=10)
for paper in results:
    print(f"{paper.title} ({paper.pubYear}) - {paper.doi}")
```

#### Oppure REST diretta:

```python
import requests

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

def search_europepmc(query: str, page_size: int = 10) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/search",
        params={"query": query, "format": "json", "resultType": "core", "pageSize": page_size}
    )
    resp.raise_for_status()
    return resp.json()["resultList"]["result"]
```

---

### 3.3 arXiv

#### Panoramica

arXiv è il repository di preprint più importante per Fisica, Matematica, Computer Science, Biologia Quantitativa e Statistica. Gestito dalla **Cornell University Library**.

| Caratteristica | Valore |
|----------------|--------|
| **Endpoint** | `http://export.arxiv.org/api/query` (HTTP, non HTTPS!) |
| **Formato risposta** | Atom 1.0 (XML) |
| **Costo** | Gratuito |
| **API Key** | Non richiesta |
| **Rate limit** | 1 req ogni 3 secondi (raccomandato), max 4 req/sec burst |
| **Max risultati** | 2.000 per call, 30.000 totali |
| **Paginazione** | `start` + `max_results` (offset-based) |

#### Parametri di Ricerca

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `search_query` | — | Query con field prefixes |
| `id_list` | — | Lista arXiv ID (es. `2301.08276`) |
| `start` | 0 | Indice di partenza |
| `max_results` | 10 | Max risultati (≤ 2.000) |
| `sortBy` | `relevance` | `relevance`, `lastUpdatedDate`, `submittedDate` |
| `sortOrder` | — | `ascending`, `descending` |

#### Field Prefixes

| Prefix | Campo | Esempio |
|--------|-------|---------|
| `ti:` | Title | `ti:transformer` |
| `au:` | Author | `au:hinton` |
| `abs:` | Abstract | `abs:reinforcement+learning` |
| `cat:` | Category | `cat:cs.AI` |
| `all:` | All fields | `all:quantum+computing` |

#### Categorie arXiv più rilevanti per ARIA

| Codice | Categoria |
|--------|-----------|
| `cs.AI` | Artificial Intelligence |
| `cs.LG` | Machine Learning |
| `cs.CL` | Computation and Language (NLP) |
| `cs.CV` | Computer Vision |
| `cs.IR` | Information Retrieval |
| `cs.SE` | Software Engineering |
| `cs.MA` | Multiagent Systems |
| `stat.ML` | Machine Learning (Statistics) |
| `cs.RO` | Robotics |

#### MCP Server esistenti

| Server | Stelle | URL |
|--------|--------|-----|
| **blazickjp/arxiv-mcp-server** | ~28 ⭐ | [GitHub](https://github.com/blazickjp/arxiv-mcp-server) |
| juananpe/arxiv-research-server-mcp | — | [GitHub](https://github.com/juananpe/arxiv-research-server-mcp) |
| 1Dark134/arxiv-mcp-server (fork) | — | [GitHub](https://github.com/1Dark134/arxiv-mcp-server) |

**Raccomandazione**: Usare `arxiv-mcp-server` (blazickjp) — ha search_papers con filtri, download PDF, storage locale. Installabile via `uv tool install arxiv-mcp-server`.

#### Esempio di query diretta

```
http://export.arxiv.org/api/query?search_query=cat:cs.LG+AND+abs:transformer&start=0&max_results=10
```

#### Wrapper script proposto

```bash
# scripts/wrappers/arxiv-wrapper.sh
# arXiv API non richiede chiavi — solo rate limiting
exec uv tool run arxiv-mcp-server --storage-path /home/fulvio/coding/aria/.aria/cache/arxiv
```

#### Libreria Python alternativa

Libreria `arxiv` su PyPI (MIT):
```python
import arxiv

search = arxiv.Search(
    query="transformer attention",
    max_results=10,
    sort_by=arxiv.SortCriterion.Relevance,
)

for paper in search.results():
    print(f"{paper.title} ({paper.primary_category})")
```

---

## 4. Provider Generalistico — Reddit

### 4.1 Stato dell'API Reddit (2026)

La situazione dell'API Reddit è complessa a seguito dei cambiamenti del 2023-2025:

| Data | Evento |
|------|--------|
| **Giu 2023** | Nuovi rate limits e API a pagamento per uso commerciale |
| **Giu 2023** | 100 req/min con OAuth gratuito (free tier) |
| **Nov 2025** | **Responsible Builder Policy (RBP)** — pre-approvazione obbligatoria per TUTTI i nuovi accessi API, inclusi progetti personali |
| **2026** | Richiesta API è di fatto bloccata: l'approvazione non è garantita |

#### Rate Limits attuali

| Tipo | Limite | Note |
|------|--------|------|
| Anonimo (senza OAuth) | ~10 req/min | Effettivamente inutilizzabile |
| OAuth free tier | 100 req/min | Richiede approvazione RBP (non garantita) |
| Commerciale | Prezzi opachi | Migliaia di $ / mese |

### 4.2 Alternative disponibili

| Opzione | Affidabilità | Costo | API Key? | Rischio Blocco | Effort |
|---------|-------------|-------|----------|----------------|--------|
| **MCP: jordanburke/reddit-mcp-server** (anonimo) | Alta | Gratuito | No (opzionale) | Medio-Basso | **Ore** |
| **MCP: adhikasp/mcp-reddit** (PRAW) | Alta | Gratuito | Sì (OAuth) | Basso (se approvato) | Ore |
| **Redlib self-hosted** | Alta | Solo hosting | No | Medio | 1-2 gg |
| **Scraping .json** (old.reddit.com) | Media | 0 | No | Alto | 1 gg |
| **Pushshift dump** | Alta (statico) | Storage | No | Basso | 3-5 gg |
| **Apify Reddit MCP** | Alta | $49+/mese | No | Basso | Ore |

### 4.3 Raccomandazione: jordanburke/reddit-mcp-server

**Il MCP server `reddit-mcp-server` di Jordan Burke è la scelta ottimale** per ARIA:

- **Zero configurazione**: `npx reddit-mcp-server` funziona subito in modalità anonima (10 req/min)
- **Aggiornato**: v1.4.5 (aprile 2026), già conforme alla RBP
- **Read/write**: hot threads, search, post content, commenti
- **Safe mode**: evita spam detection, rate limiting intelligente
- **Tre modalità di autenticazione**:
  - `anonymous`: 10 rpm, no API key
  - `auto`: 10-100 rpm
  - `authenticated`: 60-100 rpm (con OAuth)

```json
{
  "mcpServers": {
    "reddit": {
      "command": "npx",
      "args": ["reddit-mcp-server"]
    }
  }
}
```

**Se la modalità anonima non basta**, si può aggiungere OAuth:
```json
{
  "mcpServers": {
    "reddit": {
      "command": "npx",
      "args": ["reddit-mcp-server", "--client-id", "...", "--client-secret", "..."],
      "env": {
        "REDDIT_CLIENT_ID": "${REDDIT_CLIENT_ID}",
        "REDDIT_CLIENT_SECRET": "${REDDIT_CLIENT_SECRET}"
      }
    }
  }
}
```

### 4.4 Considerazioni su SearXNG + Reddit

SearXNG può già cercare su Reddit tramite il suo engine integrato (`reddit` o `reddit.search`). Se SearXNG è già configurato, si può ottenere copertura Reddit **senza aggiungere un provider dedicato**. Tuttavia, un provider Reddit dedicato offre:
- Risultati più ricchi (commenti, voti, metadata)
- Nessuna dipendenza da SearXNG (che potrebbe essere down)
- Possibilità di fare ricerche specifiche (per autore, per subreddit, per periodo)

---

## 5. Analisi Comparativa e Raccomandazioni

### 5.1 Tabella comparativa completa

| Provider | Tipo | Auth | Costo | Maturità MCP | Rate Limit | Copertura | Priorità |
|----------|------|------|-------|-------------|------------|-----------|----------|
| **PubMed** | Accademico | API key opt. | Gratuito | Alta (7 server) | 10 req/s | 36M+ articoli biomedici | 🔴 P0 |
| **Europe PMC** | Accademico | Nessuna | Gratuito | Media (4 server) | 10 req/s | 42M+ articoli + preprint | 🔴 P0 |
| **arXiv** | Accademico | Nessuna | Gratuito | Alta (3+ server) | 1 req/3s | 2M+ preprint CS/ML/Physics | 🔴 P0 |
| **Reddit** | Social | Opzionale | Gratuito (anonimo) | Alta (3 server) | 10-100 rpm | Discussioni social | 🟡 P1 |

### 5.2 Raccomandazioni per modalità di integrazione

| Provider | Approccio consigliato | Dettaglio |
|----------|----------------------|-----------|
| **PubMed** | **MCP Server** (`@iflow-mcp/pubmed-mcp-server`) + wrapper bash | Pattern identico a Tavily/Exa |
| **Europe PMC** | **Provider Python nativo** o **Scientific Papers MCP** | Preferire provider nativo se vogliamo solo Europe PMC |
| **arXiv** | **MCP Server** (`blazickjp/arxiv-mcp-server`) via `uv tool` | Già disponibile su PyPI, zero-config |
| **Reddit** | **MCP Server** (`jordanburke/reddit-mcp-server`) in modalità anonima | Zero-config, npx diretto |

### 5.3 Priorità implementativa

```
Sprint corrente
├── [P0] PubMed  — MCP server + wrapper + router
├── [P0] arXiv   — MCP server + wrapper + router
├── [P0] Europe PMC — provider nativo OPPURE Scientific Papers MCP
└── [P1] Reddit  — MCP server (sprint successivo)
```

---

## 6. Piano di Integrazione

### 6.1 PubMed

#### Steps

1. **Registrare NCBI API key**:
   - Account: https://www.ncbi.nlm.nih.gov/account/
   - API key: https://www.ncbi.nlm.nih.gov/account/settings/
   - Aggiungere a `.env`: `NCBI_API_KEY=<key>` e `NCBI_EMAIL=fulviold@gmail.com`

2. **Creare wrapper script**:
   ```
   scripts/wrappers/pubmed-wrapper.sh
   ```
   - Legge `NCBI_API_KEY` e `NCBI_EMAIL` da env
   - Exec `npx @iflow-mcp/pubmed-mcp-server`

3. **Registrare in `mcp.json`**:
   ```json
   "pubmed": {
     "command": "scripts/wrappers/pubmed-wrapper.sh"
   }
   ```

4. **Aggiungere al Router** (`router.py`):
   ```python
   class Provider(StrEnum):
       PUBMED = "pubmed"
       # ...
   
   INTENT_TIERS[Intent.ACADEMIC] = (
       Provider.SEARXNG,
       Provider.PUBMED,     # TIER 2 — PubMed
       Provider.ARXIV,       # TIER 3 — arXiv
       Provider.EUROPE_PMC,  # TIER 4 — Europe PMC
       Provider.TAVILY,      # TIER 5 — fallback generalistico
       Provider.EXA,
       Provider.BRAVE,
       Provider.FETCH,
   )
   ```

#### Struttura file

```
src/aria/agents/search/providers/
└── pubmed.py              # (Opzionale: se si sceglie provider nativo invece di MCP)

scripts/wrappers/
└── pubmed-wrapper.sh      # Wrapper MCP

.kilo/mcp.json             # Registrazione pubmed

src/aria/agents/search/
├── router.py              # Provider.PUBMED, INTENT_TIERS update
├── intent.py              # Keyword PubMed aggiunte
```

### 6.2 Europe PMC

#### Steps

1. **Nessuna API key richiesta**
2. **Creare provider Python nativo** o **usare Scientific Papers MCP**

**Opzione A — Provider Python nativo (Raccomandata per controllo)**:
```
src/aria/agents/search/providers/europepmc.py
```

Implementazione minima:

```python
import httpx
from typing import Any


class EuropePMCProvider:
    """Europe PMC REST API provider."""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, session: httpx.AsyncClient | None = None):
        self._session = session or httpx.AsyncClient(timeout=30)

    async def search(self, query: str, page_size: int = 10) -> list[dict[str, Any]]:
        resp = await self._session.get(
            f"{self.BASE_URL}/search",
            params={"query": query, "format": "json", "resultType": "core", "pageSize": page_size},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("resultList", {}).get("result", [])
```

**Opzione B — Scientific Papers MCP**:
```json
{
  "mcpServers": {
    "scientific-papers": {
      "command": "npx",
      "args": ["-y", "scientific-papers-mcp"]
    }
  }
}
```

Questa opzione include anche arXiv, PubMed, OpenAlex, bioRxiv in un unico server.

### 6.3 arXiv

#### Steps

1. **Nessuna API key richiesta**
2. **Creare wrapper script**:
   ```
   scripts/wrappers/arxiv-wrapper.sh
   ```
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   exec uv tool run arxiv-mcp-server --storage-path /home/fulvio/coding/aria/.aria/cache/arxiv
   ```

3. **Registrare in `mcp.json`**:
   ```json
   "arxiv": {
     "command": "scripts/wrappers/arxiv-wrapper.sh"
   }
   ```

4. **Aggiungere keyword arXiv alla classificazione** (`intent.py`):
   ```python
   Intent.ACADEMIC: frozenset({
       "academic", "research", "paper", "journal", "article",
       "study", "scholar", "citation", "doi", "arxiv",
       "publication", "preprint", "conference", "proceedings",
       "ricerca", "pubblicazione", "studio", "articolo scientifico",
       "pubmed", "pmid", "europe pmc",  # nuovi accademici
   }),
   ```

#### Attenzione: arXiv usa HTTP, non HTTPS

L'endpoint arXiv è `http://export.arxiv.org/api/query` (non HTTPS). Questo potrebbe causare warning di sicurezza. Verificare se l'MCP server `arxiv-mcp-server` usa l'endpoint corretto.

### 6.4 Reddit

#### Steps

1. **Nessuna API key** per modalità anonima (10 req/min)
2. **Registrare direttamente in `mcp.json`** — nessun wrapper necessario:
   ```json
   "reddit": {
     "command": "npx",
     "args": ["reddit-mcp-server"],
     "disabled": false
   }
   ```

3. **Opzionale: OAuth per 100 req/min**:
   - Registrare app: https://www.reddit.com/prefs/apps
   - Ottenere `client_id` e `client_secret`
   - Creare wrapper `scripts/wrappers/reddit-wrapper.sh` che passa credenziali

4. **Aggiungere nuovo Intent `SOCIAL`** o espandere `GENERAL_NEWS`:

**Opzione A — Nuovo Intent SOCIAL** (raccomandata):
```python
class Intent(StrEnum):
    GENERAL_NEWS = "general/news"
    ACADEMIC = "academic"
    DEEP_SCRAPE = "deep_scrape"
    SOCIAL = "social"        # NUOVO
    UNKNOWN = "unknown"

INTENT_KEYWORDS[Intent.SOCIAL] = frozenset({
    "reddit", "social", "forum", "discussion", "community",
    "news on reddit", "reddit says", "subreddit", "trending",
    "reddit discussion", "what people are saying",
})

INTENT_TIERS[Intent.SOCIAL] = (
    Provider.REDDIT,
    Provider.SEARXNG,
    Provider.TAVILY,
    ...
)
```

**Opzione B — Routing dentro GENERAL_NEWS** (minimo sforzo):
```python
INTENT_TIERS[Intent.GENERAL_NEWS] = (
    Provider.REDDIT,       # TIER 0 — Reddit per news sociali
    Provider.SEARXNG,
    Provider.TAVILY,
    ...
)
```

---

## 7. Modifiche al Router

### 7.1 Provider enum esteso

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
    EUROPE_PMC = "europe_pmc"
    ARXIV = "arxiv"

    # Nuovo provider social
    REDDIT = "reddit"
```

### 7.2 INTENT_TIERS ridisegnato

La matrice dei tier deve distinguere nettamente tra intenti accademici e generali:

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
        Provider.ARXIV,        # tier 3 — arXiv preprint (gratuito)
        Provider.EUROPE_PMC,   # tier 4 — Europe PMC (gratuito)
        Provider.TAVILY,       # tier 5 — fallback generalistico
        Provider.EXA,          # tier 6 — semantic search
        Provider.BRAVE,        # tier 7 — fallback
        Provider.FETCH,        # tier 8 — fallback HTTP
    ),
    Intent.DEEP_SCRAPE: (
        Provider.FETCH,
        Provider.WEBFETCH,
    ),
    Intent.SOCIAL: (            # NUOVO
        Provider.REDDIT,        # tier 1 — Reddit (MCP, anonimo)
        Provider.SEARXNG,       # tier 2 — SearXNG può averne
        Provider.TAVILY,        # tier 3 — fallback
        Provider.BRAVE,         # tier 4 — fallback
    ),
}
```

### 7.3 Health check per nuovi provider

Il metodo `_refresh_health` va esteso per gestire i nuovi provider. I provider senza chiave (arXiv, Europe PMC, Reddit in modalità anonima) vanno trattati come `searxng` (sempre available):

```python
async def _refresh_health(self, provider: str) -> None:
    if provider in ("searxng", "fetch", "webfetch", "arxiv", "europe_pmc", "reddit"):
        self._health[provider] = HealthState.AVAILABLE
        return
    # ... existing logic for key-based providers
```

### 7.4 Intent classification estesa

```python
INTENT_KEYWORDS: dict[Intent, frozenset[str]] = {
    Intent.GENERAL_NEWS: frozenset({
        "news", "latest", "current", "recent", "breaking",
        "today", "headline", "update", "notizie", "ultime",
        "attualità", "novità",
    }),
    Intent.ACADEMIC: frozenset({
        "academic", "research", "paper", "journal", "article",
        "study", "scholar", "citation", "doi", "arxiv",
        "publication", "preprint", "conference", "proceedings",
        "pubmed", "pmid", "europe pmc",  # NUOVI
        "scientific", "experiment", "clinical trial",
        "ricerca", "pubblicazione", "studio", "articolo scientifico",
        "abstract", "peer review", "literature review",
    }),
    Intent.SOCIAL: frozenset({   # NUOVO
        "reddit", "social media", "forum", "discussion",
        "community", "subreddit", "trending", "viral",
        "what people are saying", "public opinion",
        "reddit discussion", "hacker news",
    }),
    Intent.DEEP_SCRAPE: frozenset({
        "deep", "scrape", "crawl", "extract",
        "full page", "complete", "entire website",
        "all pages", "deep scrape", "scraping", "estrai",
    }),
}
```

---

## 8. Costi e API Key

### 8.1 Riepilogo costi

| Provider | Costo mensile base | Oneri nascosti | Soglia gratuita |
|----------|-------------------|----------------|-----------------|
| **PubMed** | 0 € | Nessuno | Illimitato (10 req/s con key) |
| **Europe PMC** | 0 € | Nessuno | Illimitato (10 req/s) |
| **arXiv** | 0 € | Nessuno | Illimitato (1 req/3s) |
| **Reddit** | 0 € | Nessuno (anonimo) oppure $0 (OAuth se approvato) | 10-100 req/min |

**Costo totale aggiuntivo per ARIA: 0 €/mese** per tutti e quattro i provider.

### 8.2 API Key necessarie

| Provider | Key necessaria? | Dove ottenerla | Variabile d'ambiente |
|----------|----------------|----------------|---------------------|
| **PubMed** | ✅ Raccomandata (gratuita) | https://www.ncbi.nlm.nih.gov/account/settings/ | `NCBI_API_KEY`, `PUBMED_EMAIL` |
| **Europe PMC** | ❌ No | — | — |
| **arXiv** | ❌ No | — | — |
| **Reddit** | ⬜ Opzionale | https://www.reddit.com/prefs/apps | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` |

### 8.3 Gestione credenziali

Seguire il pattern esistente:
- PubMed key → `CredentialManager.acquire("pubmed")` se vogliamo rotation
- In alternativa, env var semplice via wrapper bash come per Brave/Exa
- Aggiungere a `.env.example`:
  ```
  # PubMed / NCBI
  NCBI_API_KEY=
  NCBI_EMAIL=fulviold@gmail.com
  
  # Reddit (opzionale, per OAuth)
  REDDIT_CLIENT_ID=
  REDDIT_CLIENT_SECRET=
  ```

---

## 9. Rischi e Mitigazioni

### 9.1 Rischi tecnici

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| **arXiv usa HTTP** (non HTTPS) | Alta | Medio | Verificare se l'MCP server fa proxy sicuro; warning in sviluppo |
| **Reddit RBP blocca accesso** | Media | Alto | Piano B: Redlib self-hosted; Piano C: SearXNG engine reddit |
| **Rate limit PubMed senza key** | Certo (3 req/s) | Basso | Registrare API key gratuita (10 req/s) |
| **Europe PMC downtimes** | Bassa | Medio | Fallback a PubMed per biomedico, a Tavily/Exa per generale |
| **arXiv API non ufficiale: latenza** | Media | Basso | Cache query risultati 6h (già implementata) |
| **Reddit anonimo: 10 req/min insufficienti** | Media | Medio | Aggiungere OAuth se approvazione RBP ottenuta |

### 9.2 Rischi operativi

| Rischio | Mitigazione |
|---------|-------------|
| **Dipendenza da MCP esterni non mantenuti** | Preferire MCP con stelle GitHub e aggiornamenti recenti. PubMed: `@iflow-mcp` (npm, MIT); arXiv: `blazickjp` (PyPI, Apache 2.0); Reddit: `jordanburke` (npm, aggiornato apr 2026) |
| **MCP server aggiuntivi aumentano consumo risorse** | I 4 MCP server pesano ~100MB RAM totali (stimato). Accettabile per MVP |
| **Confusione nei tier di routing** | Documentare chiaramente nel wiki `research-routing.md` la nuova matrice |

---

## 10. Appendici

### A. URL documentazione ufficiale

| Provider | Risorsa | URL |
|----------|---------|-----|
| **PubMed** | NCBI E-utilities Home | https://www.ncbi.nlm.nih.gov/home/develop/api/ |
| **PubMed** | Manuale E-utilities | https://www.ncbi.nlm.nih.gov/books/NBK25501/ |
| **PubMed** | API Key | https://www.ncbi.nlm.nih.gov/account/settings/ |
| **PubMed** | MCP Server (npm) | https://www.npmjs.com/package/@iflow-mcp/pubmed-mcp-server |
| **Europe PMC** | REST API Reference | https://europepmc.org/RestfulWebService |
| **Europe PMC** | Swagger | https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=* |
| **Europe PMC** | pyeuropepmc (PyPI) | https://pypi.org/project/pyeuropepmc/ |
| **arXiv** | API Index | https://info.arxiv.org/help/api/index.html |
| **arXiv** | User Manual | https://info.arxiv.org/help/api/user-manual.html |
| **arXiv** | Terms of Use | https://info.arxiv.org/help/api/tou.html |
| **arXiv** | arxiv-mcp-server (PyPI) | https://github.com/blazickjp/arxiv-mcp-server |
| **arXiv** | arxiv.py (PyPI) | https://github.com/lukasschwab/arxiv.py |
| **Reddit** | API Reference | https://www.reddit.com/dev/api/ |
| **Reddit** | Data API Wiki | https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki |
| **Reddit** | Responsible Builder Policy | https://www.reddit.com/r/redditdev/comments/1oug31u/ |
| **Reddit** | reddit-mcp-server | https://github.com/jordanburke/reddit-mcp-server |

### B. Schema dell'architettura finale

```
                          ┌─ Intent ─┐
                          │ GENERAL  │
                          │ ACADEMIC │
                          │ SOCIAL   │
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
   │ SEARXNG  │   │TAVILY│ │EXA│ │...│   │  REDDIT  │
   │(self-host)│   │(MCP) │ │MCP│ │   │   │(MCP anon)│
   └──────────┘   └──────┘ └───┘ └───┘   └──────────┘
          │              │     │              │
          ▼              ▼     ▼              ▼
   ┌──────────┐   ┌──────┐ ┌──────┐   ┌──────────┐
   │  PUBMED  │   │ARXIV │ │EUROPE│   │  FETCH   │
   │ (MCP)   │   │(MCP) │ │ PMC  │   │ (scrape) │
   └──────────┘   └──────┘ └──────┘   └──────────┘
```

### C. Stima effort implementativo

| Task | Effort stimato | Dipende da |
|------|---------------|------------|
| PubMed wrapper + mcp.json | 1h | NCBI API key registration |
| arXiv wrapper + mcp.json | 30min | Nessuno |
| Europe PMC provider (nativo) | 2h | Nessuno |
| Reddit mcp.json | 15min | Nessuno |
| Router update (Provider, INTENT_TIERS, health) | 1h | Provider creati |
| Intent classification update | 30min | Nessuno |
| Test e validazione | 2h | Tutti i provider |
| Documentazione (wiki + diagrammi) | 1h | Implementazione |
| **Totale** | **~8h** | |

### D. Note su "EuroSearch"

La ricerca ha chiarito che **"EuroSearch" non esiste come servizio o API attuale**. Le possibili interpretazioni erano:

1. ⭐ **Europe PMC** (massima probabilità) — repository europeo di letteratura biomedica con REST API gratuita
2. ❌ **EuroSearch Project** (1998-1999) — progetto di ricerca ERCIM, defunto
3. ❌ **Eurosearch Consultants** — società di head hunting, irrilevante
4. ⬜ **EOSC / OpenAIRE** — infrastrutture europee di ricerca, ma non sono motori di ricerca testuale

**Raccomandazione**: Confermare con Fulvio che con "EuroSearch" intendesse **Europe PMC**. In caso di dubbio, implementare **Europe PMC** che è comunque il provider più utile per ricerche accademiche europee. In alternativa, considerare anche **OpenAlex** (474M+ pubblicazioni, no API key, API REST JSON) o **CORE** (300M+ articoli open access, API key gratuita).

---

> **Fine del report.** Questo documento serve come analisi pre-implementazione. Dopo approvazione, procedere con la creazione dei ticket/sottotask e l'implementazione seguendo l'ordine di priorità: PubMed → arXiv → Europe PMC → Reddit.
