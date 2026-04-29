# Research Routing — Tier Policy

**Last Updated**: 2026-04-29T10:41 (v3 Implementata — Reddit keyless live, OAuth wrapper rimosso)
**Status**: ✅ **7 provider attivi** (searxng, tavily, exa, brave, pubmed, scientific_papers, **reddit-keyless**) + Reddit da OAuth-gated a **keyless attivo**. Vedi § v3 Implementation.

## Purpose

This page documents the canonical provider routing policy for research operations. All references (blueprint, skill, agent, code) must align with this policy.

## REGOLA FISSA — Dual Tier 1 (v3)

**searxng** + **reddit-search** sono SEMPRE tier 1 per TUTTI gli intent eccetto deep_scrape.
Entrambi sono gratuiti e illimitati — **non passare mai a provider a pagamento senza prima aver tentato entrambi.**

| Provider | Tipo | Costo | Limiti | Note |
|----------|------|-------|--------|------|
| searxng | Self-hosted meta-search | Zero | Illimitato | Privacy-first, Docker su 8888 |
| reddit | Keyless scraper (eliasbiondo) | Zero | Illimitato | 6 MCP tool: search, search_subreddit, get_post, get_subreddit_posts, get_user, get_user_posts |

## Provider Tier Matrix v3

| Intent | 1a 🆓 | 1b 🆓 | 2 | 3 | 4 | 5 | 6 | 7 |
|--------|-------|-------|---|---|---|---|---|---|
| `general/news` | **searxng** | **reddit** | **tavily** | **exa** | **brave** | **fetch** | — | — |
| `academic` | **searxng** | **reddit** | **pubmed** | **scientific_papers** | **tavily** | **exa** | **brave** | **fetch** |
| `social` | **reddit** | **searxng** | **tavily** | **brave** | — | — | — | — |
| `deep_scrape` | **fetch** | **webfetch** | — | — | — | — | — | — |

### Tier Definitions

| Provider | Type | Key Required | Cost | Tier | Notes |
|----------|------|--------------|------|------|-------|
| `searxng` | Self-hosted meta-search | No | Zero (infra only) | **1a** | Privacy-first; Docker su 8888; illimitato |
| `reddit` | Keyless scraper (eliasbiondo) | **No** | **Zero** | **1b** | **REGOLA FISSA v3**: sempre tier 1 con searxng. 6 MCP tool (search, search_subreddit, get_post, get_subreddit_posts, get_user, get_user_posts). Illimitato. |
| `tavily` | Commercial LLM-ready API | Yes | 1000 req/mo free, poi $0.008/req | 2 | 8 chiavi multi-account rotazione `least_used` |
| `exa` | Commercial semantic search | Yes | 1000 req/mo free, poi $0.007/req | 3 | 1 chiave |
| `brave` | Commercial search API | Yes | $5/mo free credits | 4 | 1 chiave; env var = `BRAVE_API_KEY` (no `_ACTIVE`) |
| `pubmed` | Accademico biomedico (NCBI E-utilities) | Opt (10 req/s con chiave) | Free | academic 2 | 9 MCP tool; `NCBI_API_KEY` opzionale via SOPS+CredentialManager |
| `scientific_papers` | Accademico multi-source (arXiv, Europe PMC, OpenAlex, etc.) | No | Gratuito (rate limit: 10 req/min Europe PMC) | academic 3 | 6 sorgenti; keyless; npm: `@futurelab-studio/latest-science-mcp` |
| `fetch` | HTTP fetch (readabilipy) | No | Zero | 5+ | Fallback finale |
| ~~`firecrawl`~~ | ~~Commercial scraping API~~ | ~~Yes~~ | **REMOVED** | — | ~~6 chiavi~~ — vedi Removed Providers |

### Rationale (v3 — Dual Tier 1 gratuito)

Order follows "free/unlimited first, key-based commercial fallback" principle:
1a. **SearXNG** — self-hosted, unlimited, no API key required; sempre primo tentativo
1b. **Reddit** — keyless scraper, unlimited, no API key required; secondo tentativo gratuito
2. **Tavily** — has free tier (1000 req/mo), LLM-ready synthesis; 8 keys
3. **Exa** — good for academic/semantic search
4. **Brave** — last fallback (has $5/mo free)
5. **Fetch** — HTTP fallback finale, zero cost

**REGOLA**: Non passare mai a provider a pagamento senza prima aver tentato searxng E reddit-search.

## Implementation

### Router Code

**File**: `src/aria/agents/search/router.py` — IMPLEMENTATO E TESTATO

```
ResearchRouter.route(query, intent) → (Provider, KeyInfo) | SearchResult(degraded=True)
ResearchRouter.fallback(provider, intent, reason) → Provider | None
```

Features:
- Per-intent tier list (`INTENT_TIERS` dict)
- Health check (ciclo 5 min)
- Circuit breaker check (salta provider `OPEN`)
- Degraded mode (tutti i tier esauriti → `SearchResult(degraded=True)`)
- Key acquisition via `Rotator.acquire()`
- SearXNG special case: self-hosted, no Rotator needed
- ~~Firecrawl composite names~~ (firecrawl **REMOVED**) — rotator_provider mappato direttamente; auth-free (SEARXNG, FETCH, WEBFETCH) bypassano il Rotator

**File**: `src/aria/agents/search/intent.py` — Classificatore keyword-based
- `classify_intent(query)` → `Intent.GENERAL_NEWS | ACADEMIC | DEEP_SCRAPE | SOCIAL`
- Keyword set: italiano + inglese + nuovi v2 (pubmed, pmid, europe pmc, biorxiv, reddit, forum, subreddit, trending, ecc.)
- Default: `GENERAL_NEWS`

### Fallback Behavior

When a provider fails with classified reason, the router advances to next tier consecutively:

| Failure Reason | Action |
|----------------|--------|
| `rate_limit` | Skip to next tier; log `provider_skipped` |
| `credits_exhausted` | Skip to next tier; mark provider exhausted |
| `circuit_open` | Skip to next tier; log circuit breaker state |
| `timeout` | Retry once, then fallback to next tier |
| `network_error` | Retry once, then fallback to next tier |

### Degraded Mode

If all tiers fail, the router enters `local-only` mode:
- Return cached results with `degraded` banner
- Log `degraded_mode_entered` event
- Notify via system_event

## Context7 Verification (2026-04-27)

| Provider | Context7 ID | Key verified |
|----------|-------------|-------------|
| Tavily MCP | `/tavily-ai/tavily-mcp` | `TAVILY_API_KEY` env var, `npx -y tavily-mcp@latest` |
| Firecrawl MCP Server | `/firecrawl/firecrawl-mcp-server` | `FIRECRAWL_API_KEY` env var | ❌ **REMOVED** (all accounts exhausted) |
| Exa MCP Server | `/exa-labs/exa-mcp-server` | `EXA_API_KEY` env var, `npx -y exa-mcp-server` |
| Brave Search MCP | `/brave/brave-search-mcp-server` | `BRAVE_API_KEY` env var, `--brave-api-key` CLI, **richiede chiave a startup** |

## Test Results (2026-04-27)

### Scenari verificati

```
searxng disponibile              → GENERAL_NEWS: searxng ✅ (tier 1, self-hosted)
searxng DOWN                     → tavily ✅ (fallback tier 1→2)
searxng + tavily DOWN            → exa ✅ (fallback tier 1→2→3)
DEEP_SCRAPE                      → fetch ✅ (tier 1, HTTP fetch)
Health check (5 provider)        → tutti available ✅
```

### Provider Keys (Rotator)

| Provider | Keys | Stato | Note |
|----------|------|-------|------|
| Tavily | 3 (multi-account) | 3/3 attive | 5 rimosse per esaurimento/disattivazione |
| Brave | 1 | 1/1 attiva | — |
| Exa | 1 | 1/1 attiva | — |
| SearXNG | 0 (self-hosted) | Docker 8888 | Nessuna chiave necessaria |
| ~~Firecrawl~~ | ~~6~~ | ~~RIMOSSO~~ | Tutti i crediti lifetime esauriti |

## Agent/Skill Prompts

| Source | Location | Alignment Status |
|--------|----------|------------------|
| Blueprint routing | `docs/foundation/aria_foundation_blueprint.md` §11.2 | ✅ Aligned |
| Blueprint fallback | `docs/foundation/aria_foundation_blueprint.md` §11.6 | ✅ Aligned |
| Search-Agent | `.aria/kilocode/agents/search-agent.md` | ✅ **v4.0**: 9 tool pubmed-mcp + 5 tool scientific-papers-mcp aggiunti a `allowed-tools` e `mcp-dependencies` |
| Deep-Research Skill | `.aria/kilocode/skills/deep-research/SKILL.md` | ✅ Tier ladder già presente |
| MCP config | `.aria/kilocode/mcp.json` | ✅ All provider enabled (pubmed-mcp, scientific-papers-mcp abilitati) |
| Conductor | `.aria/kilocode/agents/aria-conductor.md` | ✅ **v4.0**: productivity-agent nei sub-agenti con dispatch rules |
| PubMed wrapper | `scripts/wrappers/pubmed-wrapper.sh` | ✅ **v4.0**: fallback bunx→npx |
| Scientific Papers wrapper | `scripts/wrappers/scientific-papers-wrapper.sh` | ✅ **v4.0**: version pin 0.1.40, checksum guard, hard fail |

## Removed Providers

| Provider | Reason |
|----------|--------|
| `serpapi` | Not in `mcp.json`; redundant with defined 5-tier fallback chain |
| `firecrawl` | **REMOVED 2026-04-27**: all 6 accounts exhausted lifetime free credits (500 each). Credits are one-time allocation, not monthly. `disabled: true` in `mcp.json` pending credit reload. Tier 3 role replaced by `exa` (for academic) and `fetch`/`webfetch` (for deep scrape). |

## Verification Matrix

1. `general/news`: tier 1 healthy → uses searxng, no fallback
2. `general/news`: tier 1 quota exhausted → fallback to tavily (tier 2)
3. `general/news`: tier 1+2 down → fallback to exa (tier 3)
4. `deep_scrape`: fetch failure → fallback to webfetch (tier 2)
5. `all`: all tiers unavailable → explicit `local-only/degraded` response
6. All providers unavailable → explicit `local-only/degraded` response
7. ALL 5 PROD: `python -m aria.credentials status` → tutti `closed` con chiavi ✅

## v2 Implementation Complete (2026-04-27)

Piano v2 audit-corrected implementato: `docs/plans/research_academic_reddit_2.md` (sostituisce v1).
ADR: `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md`.
Tutti i test passano: 109/109 nei search tests.

### New Providers v2 — State

| Provider | Type | Intent/Tier | Auth | Status |
|----------|------|-------------|------|--------|
| **PubMed** (`@cyanheads/pubmed-mcp-server` v2.6.4) | Accademico biomedico | ACADEMIC tier 2 | `NCBI_API_KEY` (opt) via SOPS+CredentialManager | ✅ Implementato |
| **Scientific Papers** (`@futurelab-studio/latest-science-mcp`) | Accademico multi-source (arXiv + Europe PMC + OpenAlex + biorxiv + CORE + PMC) | ACADEMIC tier 3 | Nessuna (keyless) | ✅ Implementato |
| ~~**Reddit** (`jordanburke/reddit-mcp-server`)~~ | Social/Discussioni | SOCIAL tier 1 | ~~**OAuth obbligatorio**~~ | ❌ **RIMOSSO v3** — sostituito da keyless — vedi v3 Implementation |
| **Reddit Keyless** (`eliasbiondo/reddit-mcp-server`) | Social/Discussioni (scraping) | SOCIAL tier 1 | **Nessuna** | ✅ **KEYLESS ATTIVO v3** — 6 tool (search, search_subreddit, get_post, get_subreddit_posts, get_user, get_user_posts). PyPI: `reddit-no-auth-mcp-server`. MCP key: `reddit-search` |
| **arXiv standalone** (`blazickjp/arxiv-mcp-server[pdf]`) | Accademico preprint (PDF read pipeline) | OPZIONALE Phase 2 | Nessuna | ⏸️ Conditional su necessità PDF |

### Cambi chiave v2 implementati

- Europe PMC: native Python provider RIMOSSO (violava P8). Sostituito da `scientific-papers-mcp` MCP.
- Reddit: claim "anonymous mode" UNVERIFIED su Context7 → OAuth obbligatorio (jordanburke/reddit-mcp-server).
- **2026-04-29**: github-discovery ha trovato alternativa **keyless** valida: `eliasbiondo/reddit-mcp-server` (PyPI: `reddit-no-auth-mcp-server`) — 6 tool MCP di ricerca, scraping old.reddit.com, nessuna API key. Report: `docs/analysis/report_gemme_reddit_mcp.md`.
- **2026-04-29 v3**: sostituzione completata — `reddit` aggiunto a `KEYLESS_PROVIDERS`, OAuth wrapper eliminato, test aggiornati (110/110 PASS).
- ADR-0006 creato (P10 compliance).
- arXiv: `[pdf]` extra confermato via Context7 per paper pre-2007 PDF-only.
- Pattern CredentialManager per NCBI key (non raw env var).
- `scientific-papers-mcp` npm package è `@futurelab-studio/latest-science-mcp` (verified on npm).

### New Intent: SOCIAL

```python
class Intent(StrEnum):
    GENERAL_NEWS = "general/news"
    ACADEMIC = "academic"
    DEEP_SCRAPE = "deep_scrape"
    SOCIAL = "social"        # NUOVO v2
    UNKNOWN = "unknown"
```

### Accompanied by:

- **`KEYLESS_PROVIDERS`** frozenset: searxng, fetch, webfetch, scientific_papers, **reddit** bypassano Rotator.
- **REGOLA FISSA v3**: searxng + reddit sono sempre tier 1 (entrambi gratuiti e illimitati). Mai passare a provider a pagamento senza prima aver tentato entrambi.
- **`test_provider_pubmed.py`**: 7 test (enum, tier, health).
- **`test_provider_scientific_papers.py`**: 8 test (enum, keyless, tier).
- **`test_provider_reddit.py`**: 6 test (enum, SOCIAL tier, fallback).
- **`test_intent_social.py`**: 13 test (SOCIAL keyword match, scoring).
- **`test_router_academic_tiers.py`**: 10 test (7-tier ladder, fallback chain).
- **`test_router_social_tiers.py`**: 12 test (REDDIT DOWN simulation, degraded mode).

### Context7 Verified Sources v2

| MCP Server | Context7 ID | Snippets | Benchmark | Verifica |
|------------|-------------|----------|-----------|----------|
| PubMed | `/cyanheads/pubmed-mcp-server` | 1053 | 83.7 | npx + `NCBI_API_KEY` + `UNPAYWALL_EMAIL` |
| Scientific Papers | `/benedict2310/scientific-papers-mcp` | 5319 | 67.0 | `search_papers(source=europepmc)` confermato; npm: `@futurelab-studio/latest-science-mcp` |
| arXiv standalone | `/blazickjp/arxiv-mcp-server` | 112 | 76.1 | `[pdf]` extra confermato |
| Reddit | `/jordanburke/reddit-mcp-server` | 39 | — | OAuth env vars **obbligatori** (no anonymous mode docs) |

## v3 Implementation — Reddit Keyless Live (2026-04-29)

### Stato

| Azione | Dettaglio | Status |
|--------|-----------|--------|
| `mcp.json` | `reddit-mcp` (OAuth, disabled) → `reddit-search` (keyless, enabled) | ✅ Fatto |
| `scripts/wrappers/reddit-wrapper.sh` | Eliminato (non serve piu — keyless, nessuna gestione credenziali) | ✅ Rimosso |
| `router.py` | `"reddit"` aggiunto a `KEYLESS_PROVIDERS`; commenti aggiornati | ✅ Fatto |
| `test_provider_reddit.py` | `test_reddit_is_key_based` → `test_reddit_is_keyless` + `test_reddit_bypasses_rotator` | ✅ Aggiornato |
| `search-agent.md` | 6 tool reddit-search aggiunti ad `allowed-tools` e `mcp-dependencies`; tier ladder aggiornato | ✅ Fatto |
| `deep-research/SKILL.md` | Reddit integrato nel tier ladder social; procedure update | ✅ Fatto |
| Qualita | `ruff check` ✅ `mypy` ✅ `pytest` 110/110 PASS | ✅ Pass |

### Modifiche al Comportamento del Router

**Prima (v2)**: `SOCIAL` → REDDIT (OAuth-gated, DOWN senza client_id) → SEARXNG → TAVILY → BRAVE
**Dopo (v3)**: `SOCIAL` → REDDIT (keyless, sempre AVAILABLE) → SEARXNG → TAVILY → BRAVE

Reddit e ora un provider sempre disponibile, bypassando il Rotator (nessuna chiave da gestire).
Il vecchio wrapper OAuth e i file `reddit-wrapper.sh` sono stati eliminati definitivamente.

## Scientific Papers — Bug Fixes (2026-04-29)

### Problema

Il MCP server `@futurelab-studio/latest-science-mcp` v0.1.40 (`scientific-papers-mcp`)
restituiva 0 risultati su arXiv ed EuropePMC per query multi-termine.

### Root Cause: 3 Bug nel Driver npm

**BUG 1 — arXiv driver** (`arxiv-driver.js` searchPapers, field=all):
```javascript
// OLD: searchQuery = `all:"${query}"`;
// Trasformava: "state space model Mamba" → all:"state space model Mamba"
// Problema: frase ESATTA, non trova varianti
```

**BUG 2 — EuropePMC driver** (`europepmc-driver.js` searchPapers):
```javascript
// OLD: searchQuery = `"${query}"`;
// Stesso problema: query wrappata in doppi apici
// OLD: sort="relevance" — API EuropePMC REST NON accetta sort=relevance,
// restituisce solo {"version":"6.9"} senza risultati
// OLD: hasFullText==="Y" — il campo haFullText spesso è null/'?'
// filtrando tutti i risultati validi
```

**BUG 3 — Centralizzato** (`search-papers.js`):
Nessuna pre-elaborazione query prima di dispatch ai driver.

### Fix Applicati

Patch applicate al codice JS nella cache npx e salvate in `docs/patches/scientific-papers-mcp/`
per auto-restore. Il wrapper `scripts/wrappers/scientific-papers-wrapper.sh` applica
le patch automaticamente a ogni cache entry npx.

**Fix 1** (`arxiv-driver.js`):
```javascript
// NEW: parse query in termini + frasi quotate, join con AND
// Input: "state space model" Mamba efficient
// Output: all:"state space model" AND all:Mamba AND all:efficient
```

**Fix 2** (`europepmc-driver.js`):
```javascript
// NEW: stessi parse strategy
// NEW: sort=rimosso per default relevance (API non lo supporta)
// NEW: hasFullText !== "N" invece di === "Y"
```

**Fix 3** (`search-papers.js`):
```javascript
// NEW: preprocessQuery() strips outer quotes, normalizza whitespace
// Tutti i driver ricevono processedQuery invece di raw query
```

### Esiti Test (ARIA-isolated env, 2026-04-29)

| Sorgente | Query | Prima | Dopo |
|----------|-------|-------|------|
| arXiv | `Mamba state space model` | 0-2 risultati irrilevanti (fisica) | ✅ 5 paper pertinenti su SSM/Mamba |
| EuropePMC | `machine learning protein folding` | 0 risultati | ✅ 5 paper pertinenti |
| OpenAlex | `Mamba state space model` | ✅ funzionava già (API search param) | ✅ invariato (3 paper) |

### File Modificati

| File | Modifica |
|------|----------|
| `.aria/kilo-home/.npm/_npx/*/node_modules/@futurelab-studio/latest-science-mcp/dist/drivers/arxiv-driver.js` | `_parseArxivQuery()` + Boolean AND search |
| `.aria/kilo-home/.npm/_npx/*/node_modules/@futurelab-studio/latest-science-mcp/dist/drivers/europepmc-driver.js` | `_parseQuery()` + sort fix + hasFullText fix |
| `.aria/kilo-home/.npm/_npx/*/node_modules/@futurelab-studio/latest-science-mcp/dist/tools/search-papers.js` | `preprocessQuery()` + processedQuery dispatch |
| `scripts/wrappers/scientific-papers-wrapper.sh` | Auto-patching npx cache entries a startup |
| `docs/patches/scientific-papers-mcp/*.{js,original.js}` | Seed patches per auto-restore |
| `.aria/kilocode/agents/search-agent.md` | Sezione "Query Formulation per Scientific Papers" |

### Quality Gate

```
pytest tests/unit/agents/search/ -q  → 110 passed (era 109, +1 test per keyless)
ruff check src/aria/agents/search/   → All checks passed
mypy src/aria/agents/search/         → Success: no issues found
```

## Reddit — Alternative Keyless (LIVE in ARIA)

### Configurazione Attiva: eliasbiondo/reddit-mcp-server (KEYLESS)

MCP server keyless con 6 tool di ricerca. Usa scraping di `old.reddit.com`.
**ATTIVO in ARIA** dal 2026-04-29. Nessuna API key, nessun OAuth.

```json
{
  "mcpServers": {
    "reddit-search": {
      "command": "uvx",
      "args": ["reddit-no-auth-mcp-server"],
      "env": {},
      "disabled": false
    }
  }
}
```

**Tools**: `search`, `search_subreddit`, `get_post`, `get_subreddit_posts`, `get_user`, `get_user_posts`
**PyPI**: `reddit-no-auth-mcp-server`
**Repo**: https://github.com/eliasbiondo/reddit-mcp-server
**Report completo**: `docs/analysis/report_gemme_reddit_mcp.md`

### Opzione B: adhikasp/mcp-reddit (KEYLESS, solo hot threads)

MCP server popolare (398 ⭐) per hot threads, senza search.

```json
{
  "mcpServers": {
    "reddit-hot": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/adhikasp/mcp-reddit.git", "mcp-reddit"],
      "env": {}
    }
  }
}
```

### Opzione C (OAuth, solo se necessario per write)

Se in futuro servono write operations (postare, commentare), seguire questi passaggi:

1. Vai su https://www.reddit.com/prefs/apps
2. Clicca **"are you a developer? create an app..."**
3. Compila: name=`aria-reddit-reader`, type=`script`
4. Salva Client ID e Secret via CredentialManager:
   ```bash
   python -m aria.credentials add --provider reddit_client_id --id reddit-app --key <CLIENT_ID>
   python -m aria.credentials add --provider reddit_client_secret --id reddit-app --key <CLIENT_SECRET>
   ```
5. Abilitare `jordanburke/reddit-mcp-server` in `mcp.json`

### Fallback senza Reddit

Se Reddit non è configurato/raggiungibile, il router scala automaticamente:
`SOCIAL`: REDDIT (DOWN) → SEARXNG → TAVILY → BRAVE
