---
title: Search Agent
sources:
  - docs/foundation/aria_foundation_blueprint.md §11
last_updated: 2026-04-23
tier: 1
---

# Search Agent — Sub-Agent di Ricerca Web

## Provider Supportati (MVP)

| Provider | Tier gratuito | Forte su | Costo incremento |
|----------|---------------|----------|------------------|
| **Tavily** | 1.000 req/mese | LLM-ready synthesis, news | $0.008/req |
| **Firecrawl** | 500 credits lifetime | Deep scraping, extract AI | ~$0.005–0.015/page |
| **Brave** | $5/mese free credits | Privacy, volume (50 req/s) | $0.005/web, $0.004/ans |
| **Exa** | 1.000 req/mese | Semantic search academic | $0.007/req |
| **SearXNG** | Self-hosted, illimitato | Meta, privacy totale | Zero (solo infra) |
| **SerpAPI** | 100 req/mese | Fallback ultima istanza | $5/1k |

DuckDuckGo **esplicitamente escluso** (no API ufficiale, scraping fragile).

*source: `docs/foundation/aria_foundation_blueprint.md` §11.1*

## Intent-Aware Routing

Il router Python (`src/aria/agents/search/router.py`) classifica l'intent e seleziona provider:

```python
INTENT_ROUTING = {
    "news":         ["tavily", "brave_news"],
    "academic":     ["exa", "tavily"],
    "deep_scrape":  ["firecrawl_extract", "firecrawl_scrape"],
    "general":      ["brave", "tavily"],
    "privacy":      ["searxng", "brave"],
    "fallback":     ["serpapi"],
}
```

Classifier: mini-skill `intent-classifier` basata su keyword + (opzionale) zero-shot LLM call.

*source: `docs/foundation/aria_foundation_blueprint.md` §11.2*

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

### Pattern di utilizzo

```python
cm = CredentialManager()
key = cm.acquire("tavily", strategy="least_used")
response = call_api(key)
cm.report_success("tavily", key.id, credits_used=1)  # oppure
cm.report_failure("tavily", key.id, reason="rate_limit")
```

### Circuit breaker

- **Closed** (normale) → errori rari tollerati
- **Open** → dopo 3 failure in 5min → cooldown 30min
- **Half-open** → dopo cooldown, 1 tentativo; se ok → closed, se fail → open esteso

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
   - `news/general`: Tavily → Brave → SearXNG → cache stale
   - `deep_scrape`: Firecrawl → fetch+readability → solo metadata
   - `academic`: Exa → Tavily → Brave web
3. Se tutti esterni down → modalità `local-only` (cache + SearXNG)
4. Notifica `system_event` + report giornaliero

*source: `docs/foundation/aria_foundation_blueprint.md` §11.6, `docs/operations/provider_exhaustion.md`*

## Implementazione Codice

```
src/aria/agents/search/
├── __init__.py
├── router.py          # Intent-aware routing
├── dedup.py           # URL dedup + ranking
└── providers/
    └── (tavily, firecrawl, brave, exa, searxng, serpapi)
```

## Vedi anche

- [[credentials]] — Rotation e circuit breaker
- [[tools-mcp]] — MCP server search providers
- [[skills-layer]] — deep-research skill
