# Research Routing — Tier Policy

**Last Updated**: 2026-04-27T17:30 (v2 Implementata — PubMed + Scientific Papers + SOCIAL intent live)
**Status**: ✅ 6 provider attivi (searxng, tavily, exa, brave, pubmed, scientific_papers) + reddit (OAuth gated). v2 Implementata.

## Purpose

This page documents the canonical provider routing policy for research operations. All references (blueprint, skill, agent, code) must align with this policy.

## Provider Tier Matrix v2

| Intent | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Tier 5 | Tier 6 | Tier 7 |
|--------|--------|--------|--------|--------|--------|--------|--------|
| `general/news` | **searxng** | **tavily** | **exa** | **brave** | **fetch** | — | — |
| `academic` | **searxng** | **pubmed** | **scientific_papers** | **tavily** | **exa** | **brave** | **fetch** |
| `deep_scrape` | **fetch** | **webfetch** | — | — | — | — | — |
| `social` | **reddit** (OAuth) | **searxng** | **tavily** | **brave** | — | — | — |

### Tier Definitions

| Provider | Type | Key Required | Cost | Notes |
|----------|------|--------------|------|-------|
| `searxng` | Self-hosted meta-search | No | Zero (infra only) | Tier 1; privacy-first; Docker su 8888 |
| `tavily` | Commercial LLM-ready API | Yes | 1000 req/mo free, poi $0.008/req | 8 chiavi multi-account rotazione `least_used` |
| `firecrawl` | ~~Commercial scraping API~~ | ~~Yes~~ | **REMOVED** (all 6 accounts exhausted) | ~~6 chiavi~~ — vedi Removed Providers |
| `exa` | Commercial semantic search | Yes | 1000 req/mo free, poi $0.007/req | 1 chiave |
| `brave` | Commercial search API | Yes | $5/mo free credits | 1 chiave; env var = `BRAVE_API_KEY` (no `_ACTIVE`) |
| `pubmed` | Accademico biomedico (NCBI E-utilities) | Opt (10 req/s con chiave) | Free | 9 MCP tool; `NCBI_API_KEY` opzionale via SOPS+CredentialManager |
| `scientific_papers` | Accademico multi-source (arXiv, Europe PMC, OpenAlex, etc.) | No | Gratuito (rate limit: 10 req/min Europe PMC) | 6 sorgenti; keyless; npm: `@futurelab-studio/latest-science-mcp` |
| `reddit` | Social/Discussioni (OAuth) | Sì (OAuth) | Gratuito | Solo read (Phase 1); HITL gate per setup OAuth |

### Rationale

Order follows "real API key availability to rotate" principle:
1. **SearXNG** — self-hosted, unlimited, no API key required; always attempted first
2. **Tavily** — has free tier, LLM-ready synthesis; 8 keys per multi-account
3. **Firecrawl** — credits limited; specialized for deep scrape; 6 keys
4. **Exa** — good for academic/semantic search
5. **Brave** — last fallback (has $5/mo free but lower priority for rotation)

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
| Search-Agent | `.aria/kilocode/agents/search-agent.md` | ✅ Tier ladder esplicito |
| Deep-Research Skill | `.aria/kilocode/skills/deep-research/SKILL.md` | ✅ Tier ladder già presente |
| MCP config | `.aria/kilocode/mcp.json` | ✅ All 5 provider enabled |

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
| **Reddit** (`jordanburke/reddit-mcp-server`) | Social/Discussioni | SOCIAL tier 1 | **OAuth obbligatorio** | ⏸️ Disabled — attesa HITL OAuth |
| **arXiv standalone** (`blazickjp/arxiv-mcp-server[pdf]`) | Accademico preprint (PDF read pipeline) | OPZIONALE Phase 2 | Nessuna | ⏸️ Conditional su necessità PDF |

### Cambi chiave v2 implementati

- Europe PMC: native Python provider RIMOSSO (violava P8). Sostituito da `scientific-papers-mcp` MCP.
- Reddit: claim "anonymous mode" UNVERIFIED su Context7 → OAuth obbligatorio.
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

- **`KEYLESS_PROVIDERS`** frozenset: searxng, fetch, webfetch, scientific_papers bypassano Rotator.
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
