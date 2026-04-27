# Research Routing — Tier Policy

**Last Updated**: 2026-04-27T15:36 (ripristino completato — tutti i 5 provider funzionanti con rotation multi-account, router testato con fallback)
**Status**: ✅ FULLY RESTORED — tutti i provider operativi, router funzionante

## Purpose

This page documents the canonical provider routing policy for research operations. All references (blueprint, skill, agent, code) must align with this policy.

## Provider Tier Matrix

| Intent | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Tier 5 |
|--------|--------|--------|--------|--------|--------|
| `general/news` | **searxng** | **tavily** | **exa** | **brave** | **fetch** |
| `academic` | **searxng** | **tavily** | **exa** | **brave** | **fetch** |
| `deep_scrape` | **fetch** | **webfetch** | — | — | — |

### Tier Definitions

| Provider | Type | Key Required | Cost | Notes |
|----------|------|--------------|------|-------|
| `searxng` | Self-hosted meta-search | No | Zero (infra only) | Tier 1; privacy-first; Docker su 8888 |
| `tavily` | Commercial LLM-ready API | Yes | 1000 req/mo free, poi $0.008/req | 8 chiavi multi-account rotazione `least_used` |
| `firecrawl` | Commercial scraping API | Yes | 500 credits lifetime, poi ~$0.005-0.015/page | 6 chiavi multi-account; `extract`/`scrape` specializzati |
| `exa` | Commercial semantic search | Yes | 1000 req/mo free, poi $0.007/req | 1 chiave |
| `brave` | Commercial search API | Yes | $5/mo free credits | 1 chiave; env var = `BRAVE_API_KEY` (no `_ACTIVE`) |

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
- Firecrawl composite names (`firecrawl_extract`, `firecrawl_scrape`) mapped to base `firecrawl`

**File**: `src/aria/agents/search/intent.py` — Classificatore keyword-based
- `classify_intent(query)` → `Intent.GENERAL_NEWS | ACADEMIC | DEEP_SCRAPE`
- Keyword set: italiano + inglese
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
| Firecrawl MCP Server | `/firecrawl/firecrawl-mcp-server` | `FIRECRAWL_API_KEY` env var, `npx -y firecrawl-mcp` |
| Exa MCP Server | `/exa-labs/exa-mcp-server` | `EXA_API_KEY` env var, `npx -y exa-mcp-server` |
| Brave Search MCP | `/brave/brave-search-mcp-server` | `BRAVE_API_KEY` env var, `--brave-api-key` CLI, **richiede chiave a startup** |

## Test Results (2026-04-27)

### Scenari verificati

```
searxng disponibile              → GENERAL_NEWS: searxng ✅ (tier 1, self-hosted)
searxng DOWN                     → tavily ✅ (fallback tier 1→2)
searxng + tavily DOWN            → firecrawl ✅ (fallback tier 1→2→3)
DEEP_SCRAPE                      → firecrawl_extract ✅ (mappato a firecrawl)
Health check (5 provider)        → tutti available ✅
```

### Provider Keys (Rotator)

| Provider | Keys | Stato |
|----------|------|-------|
| Tavily | 8 (multi-account) | 8/8 available (closed) |
| Firecrawl | 6 (multi-account) | 6/6 available (closed) |
| Brave | 1 | 1/1 available (closed) |
| Exa | 1 | 1/1 available (closed) |

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
3. `general/news`: tier 1+2 down → fallback to firecrawl (tier 3)
4. `deep_scrape`: firecrawl_extract failure → fallback to firecrawl_scrape (tier 2)
5. `deep_scrape`: firecrawl_scrape failure → fallback to fetch (tier 3)
6. All providers unavailable → explicit `local-only/degraded` response
7. ALL 5 PROD: `python -m aria.credentials status` → tutti `closed` con chiavi ✅
