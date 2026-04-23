---
title: Search Agent
sources:
  - docs/foundation/aria_foundation_blueprint.md §11
last_updated: 2026-04-23
tier: 1
---

# Search Agent — Sub-Agent di Ricerca Web

## Provider Supportati (MVP)

| Provider | Tier gratuito | Forte su | Costo incremento | Stato (2026-04-23) |
|----------|---------------|----------|------------------|--------------------|
| **Exa** | 1.000 req/mese | Semantic search academic | $0.007/req | ✅ Attivo (primario) |
| **Tavily** | 1.000 req/mese | LLM-ready synthesis, news | $0.008/req | ✅ Attivo (7/8 key, rotation) |
| **Firecrawl** | 500 credits lifetime | Deep scraping, extract AI | ~$0.005–0.015/page | ❌ Credits esauriti |
| **Brave** | $5/mese free credits | Privacy, volume (50 req/s) | $0.005/web | ⚠️ Da verificare npm |
| **SearXNG** | Self-hosted, illimitato | Meta, privacy totale | Zero (solo infra) | ✅ localhost:8888, Docker |
| **SerpAPI** | 100 req/mese | Fallback ultima istanza | $5/1k | Non configurato |

*source: `docs/foundation/aria_foundation_blueprint.md` §11.1*

## Key Rotation Automatica

Ogni MCP server implementa key rotation:
1. Acquisisce key da `CredentialManager.acquire(provider)`
2. Esegue la chiamata API
3. Se `ProviderError(credits_exhausted)` → `cm.report_failure()` → prova key successiva
4. Max 5 tentativi per request
5. Se tutti falliscono → `raise ToolError(...)` → FastMCP segnala `isError: true`

*source: `src/aria/tools/*/mcp_server.py`*

## Intent-Aware Routing

Il router Python (`src/aria/agents/search/router.py`) classifica l'intent e seleziona provider:

```python
INTENT_ROUTING = {
    "news":         ["tavily", "brave_news"],
    "academic":     ["exa", "tavily"],
    "deep_scrape":  ["firecrawl_extract", "firecrawl_scrape"],
    "general":      ["exa", "tavily"],       # Exa primario per general
    "privacy":      ["searxng", "brave"],
    "fallback":     ["serpapi"],
}
```

*source: `docs/foundation/aria_foundation_blueprint.md` §11.2*

## Error Handling (post-fix 2026-04-23)

- `ProviderError` con `reason`, `status_code`, `retryable` propagato da ogni provider
- `KeyExhaustedError` per HTTP 401/402/403/432 → non ritentabile con stessa key
- FastMCP `ToolError` per segnalare `isError: true` al LLM
- Il LLM può distinguere "nessun risultato" (success) da "provider rotto" (isError)

## API Key Rotation con Circuit Breaker

### Stato per-chiave

Persistito in `.aria/runtime/credentials/providers_state.enc.yaml` (cifrato):

```yaml
providers:
  tavily:
    keys:
      - key_id: tvly-1
        credits_total: 1000
        credits_used: 0
        circuit_state: closed    # closed|open|half_open
        failure_count: 0
        cooldown_until: null
    rotation_strategy: least_used   # round_robin | least_used | failover
```

*source: `docs/foundation/aria_foundation_blueprint.md` §11.3*

## Deduplicazione e Ranking

`src/aria/agents/search/dedup.py`:

1. URL canonicalization (rimozione utm_, query params non significativi)
2. Fuzzy match titoli con Levenshtein (ratio ≥ 0.85 = duplicato)
3. Score aggregato: `score = provider_weight × relevance × recency_decay`

*source: `docs/foundation/aria_foundation_blueprint.md` §11.4*

## Caching

- Cache query→results in memoria episodica tagged `search_cache` con TTL default 6h
- Hit ratio atteso ≥ 20%
- `aria search --no-cache` per bypass

*source: `docs/foundation/aria_foundation_blueprint.md` §11.5*

## Provider Exhaustion e Graceful Degradation

Runbook deterministico:

1. Health-check provider ogni 5 minuti
2. Fallback tree per intent:
   - `news/general`: Exa → Tavily → Brave → SearXNG → cache stale
   - `deep_scrape`: Firecrawl → fetch+readability → solo metadata
   - `academic`: Exa → Tavily → Brave web
3. Se tutti esterni down → modalità `local-only` (cache + SearXNG)
4. Notifica `system_event` + report giornaliero

*source: `docs/foundation/aria_foundation_blueprint.md` §11.6, `docs/operations/provider_exhaustion.md`*

## Implementazione Codice

```
src/aria/tools/
├── tavily/mcp_server.py    # FastMCP + key rotation loop
├── firecrawl/mcp_server.py # FastMCP + key rotation loop
├── exa/mcp_server.py       # FastMCP + key rotation loop
└── searxng/mcp_server.py   # FastMCP + ToolError

src/aria/agents/search/
├── router.py               # Intent-aware routing
├── dedup.py                # URL dedup + ranking
├── schema.py               # SearchHit, ProviderError, Intent
└── providers/
    ├── _http.py             # Shared retry + KeyExhaustedError
    ├── tavily.py            # TavilyProvider
    ├── firecrawl.py         # FirecrawlProvider
    ├── exa.py               # ExaProvider
    ├── searxng.py           # SearXNGProvider
    ├── brave.py             # BraveProvider
    └── serpapi.py           # SerpAPIProvider
```

## Vedi anche

- [[credentials]] — Rotation e circuit breaker
- [[tools-mcp]] — MCP server search providers
- [[skills-layer]] — deep-research skill
