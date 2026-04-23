---
title: Search Agent
sources:
  - docs/foundation/aria_foundation_blueprint.md §11
  - src/aria/agents/search/providers/_http.py
  - src/aria/agents/search/schema.py
  - src/aria/tools/tavily/mcp_server.py
  - src/aria/tools/exa/mcp_server.py
  - src/aria/tools/firecrawl/mcp_server.py
  - src/aria/tools/searxng/mcp_server.py
  - .aria/kilocode/agents/search-agent.md
last_updated: 2026-04-23
tier: 1
---

# Search Agent — Sub-Agent di Ricerca Web

## Architettura a 3 Layer

Il search subsystem ha 3 layer separati, ciascuno con responsabilità distinta:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Search-Agent (LLM sub-agent)              │
│  .aria/kilocode/agents/search-agent.md              │
│  - Classifica intent, sceglie tool MCP              │
│  - Fallback tra provider su isError: true            │
├─────────────────────────────────────────────────────┤
│  Layer 2: MCP Servers (FastMCP, stdio transport)    │
│  src/aria/tools/{tavily,exa,firecrawl,searxng}/     │
│  - Key rotation loop (max 5 attempts)                │
│  - CredentialManager acquire/report                  │
│  - ToolError → isError: true al LLM                  │
├─────────────────────────────────────────────────────┤
│  Layer 3: Provider Adapters (Python async)           │
│  src/aria/agents/search/providers/                   │
│  - HTTP retry con tenacity                           │
│  - KeyExhaustedError → ProviderError propagation     │
│  - Normalizzazione in SearchHit                      │
└─────────────────────────────────────────────────────┘
```

*source: `src/aria/tools/*/mcp_server.py`, `src/aria/agents/search/providers/*.py`*

---

## Provider Status (2026-04-23)

| Provider | Tier gratuito | Forte su | Costo | Stato | Tool MCP |
|----------|---------------|----------|-------|-------|----------|
| **Exa** | 1.000 req/mese | Semantic search, academic | $0.007/req | ✅ Primario (1/1 key) | `exa-script_search` |
| **Tavily** | 1.000 req/mese | LLM-ready synthesis, news | $0.008/req | ✅ Secondario (7/8 key) | `tavily-mcp_search` |
| **SearXNG** | Self-hosted, illimitato | Meta-search privacy | Zero | ✅ Fallback (Docker) | `searxng-script_search` |
| **Brave** | $5/mese free credits | Privacy, volume | $0.005/web | ⚠️ Da verificare npm | `brave-mcp_brave_web_search` |
| **Firecrawl** | 500 credits lifetime | Deep scraping, extract AI | ~$0.01/page | ❌ Credits esauriti (0/7) | `firecrawl-mcp_search/scrape/extract` |
| **SerpAPI** | 100 req/mese | Fallback ultima istanza | $5/1k | Non configurato | N/A |

*source: `docs/foundation/aria_foundation_blueprint.md` §11.1, verificato via E2E test 2026-04-23*

---

## MCP Tool Registry

Ogni provider è esposto come tool MCP via FastMCP. KiloCode risolve il tool ID come
`<server_name>_<tool_name>` dove `server_name` è il nome passato a `FastMCP()`.

### Exa — `exa-script_search`

| Proprietà | Valore |
|-----------|--------|
| **Server** | `FastMCP("exa-script")` |
| **Tool** | `search(query: str, top_k: int = 10) → dict` |
| **Wrapper** | `scripts/wrappers/exa-wrapper.sh` |
| **Config kilo.json** | `exa-script` → `command: [exa-wrapper.sh]` |
| **API key** | Via CredentialManager (`cm.acquire("exa")`) |
| **Key rotation** | Sì — max 5 tentativi |
| **Endpoint** | `POST https://api.exa.ai/search` |
| **Max results** | 25 |

### Tavily — `tavily-mcp_search`

| Proprietà | Valore |
|-----------|--------|
| **Server** | `FastMCP("tavily-mcp")` |
| **Tool** | `search(query: str, top_k: int = 10) → dict` |
| **Wrapper** | `scripts/wrappers/tavily-wrapper.sh` |
| **Config kilo.json** | `tavily-mcp` → `command: [tavily-wrapper.sh]` |
| **API key** | Via CredentialManager (`cm.acquire("tavily")`) |
| **Key rotation** | Sì — max 5 tentativi |
| **Endpoint** | `POST https://api.tavily.com/search` |
| **Max results** | 20 |
| **Extra** | Include `published_at` nei risultati |

### Firecrawl — `firecrawl-mcp_search`, `firecrawl-mcp_scrape`, `firecrawl-mcp_extract`

| Proprietà | Valore |
|-----------|--------|
| **Server** | `FastMCP("firecrawl-mcp")` |
| **Tools** | 3 tool esposti (vedi sotto) |
| **Wrapper** | `scripts/wrappers/firecrawl-wrapper.sh` |
| **Config kilo.json** | `firecrawl-mcp` → `command: [firecrawl-wrapper.sh]` |
| **API key** | Via CredentialManager (`cm.acquire("firecrawl")`) |
| **Key rotation** | Sì — max 5 tentativi (search), single-key (scrape/extract) |
| **Endpoint search** | `POST https://api.firecrawl.dev/v1/search` |
| **Endpoint scrape** | `POST https://api.firecrawl.dev/v1/scrape` |
| **Endpoint extract** | `POST https://api.firecrawl.dev/v1/extract` |

**Tool dettaglio:**

1. **`search(query, top_k=10)`** — Web search con key rotation loop completo
2. **`scrape(url)`** — Estrazione markdown da singolo URL. Usa `_acquire_working_provider()` (single key, no rotation loop)
3. **`extract(url, prompt, schema?)`** — Estrazione strutturata AI. Stesso pattern di scrape

### SearXNG — `searxng-script_search`

| Proprietà | Valore |
|-----------|--------|
| **Server** | `FastMCP("searxng-script")` |
| **Tool** | `search(query: str, top_k: int = 10) → dict` |
| **Wrapper** | `scripts/wrappers/searxng-wrapper.sh` |
| **Config kilo.json** | `searxng-script` → env: `ARIA_SEARCH_SEARXNG_URL=http://localhost:8888` |
| **API key** | **Nessuna** — self-hosted |
| **Key rotation** | Non necessaria (no API key) |
| **Endpoint** | `GET http://localhost:8888/search?format=json&q=...` |
| **Motori** | Google, DuckDuckGo, Bing |
| **Docker** | `searxng/searxng:latest`, restart: `unless-stopped`, port `127.0.0.1:8888→8080` |
| **Provider init** | Lazy singleton (`_provider` globale), disabled se `ARIA_SEARCH_SEARXNG_URL` vuoto |

### Brave — `brave-mcp_brave_web_search`

| Proprietà | Valore |
|-----------|--------|
| **Server** | npm package `@brave/brave-search-mcp-server` |
| **Wrapper** | `scripts/wrappers/brave-wrapper.sh` |
| **API key** | Da env `BRAVE_API_KEY_ACTIVE` |
| **Stato** | Da verificare E2E — wrapper esiste, npm package resolution da confermare |

*source: `src/aria/tools/*/mcp_server.py`, `.aria/kilocode/kilo.json`, `scripts/wrappers/*-wrapper.sh`*

---

## Output Format (comune a tutti i provider)

Ogni tool MCP restituisce un dict JSON con questa struttura:

```json
{
  "success": true,
  "results": [
    {
      "title": "Page Title",
      "url": "https://example.com/page",
      "snippet": "Extracted or generated snippet text...",
      "published_at": "2026-04-23T10:00:00+00:00",
      "score": 0.85,
      "provider": "exa"
    }
  ]
}
```

**In caso di errore** il tool solleva `ToolError` → FastMCP restituisce `isError: true` al LLM.
Il LLM **non** riceve un JSON `{"success": false, ...}` — riceve un errore strutturato.

*source: `src/aria/tools/*/mcp_server.py`, `src/aria/agents/search/schema.py` SearchHit model*

---

## Key Rotation — Come Funziona

I provider a pagamento (Tavily, Exa, Firecrawl) usano questo flusso per ogni chiamata:

```
search(query)
  │
  ├─ for attempt in range(5):
  │     │
  │     ├─ cm.acquire("provider") → KeyInfo o None
  │     │     └─ None → raise ToolError("no available keys")
  │     │
  │     ├─ provider = Provider(api_key=key_info.key)
  │     │
  │     ├─ try: hits = provider.search(query)
  │     │     ├─ Success → cm.report_success(key_id, credits=1)
  │     │     │           → return {"success": True, "results": [...]}
  │     │     │
  │     │     ├─ ProviderError → cm.report_failure(key_id, reason)
  │     │     │                  → provider.close()
  │     │     │                  → continue (next key)
  │     │     │
  │     │     └─ Exception → provider.close()
  │     │                    → continue (next key)
  │     │
  │     └─ end for
  │
  └─ raise ToolError("all 5 key attempts failed")
```

### Quali errori attivano la rotation

| Codice HTTP | Significato | Azione |
|-------------|-------------|--------|
| **401** | Unauthorized / key invalida | `report_failure` → next key |
| **402** | Payment required / credits esauriti | `report_failure` → next key |
| **403** | Forbidden | `report_failure` → next key |
| **432** | Tavily usage limit | `report_failure` → next key |
| **429** | Rate limit | Retry con backoff (stessa key) |
| **5xx** | Server error | Retry con backoff (stessa key, max 3) |

I codici 401/402/403/432 sollevano `KeyExhaustedError` nel layer HTTP (`_http.py`),
convertito in `ProviderError(reason="credits_exhausted", retryable=True)` nel provider adapter,
che il MCP server intercetta per ruotare la key.

I codici 429/5xx sollevano `RetryableProviderError` e vengono ritentati con tenacity
(exponential backoff, max 3 tentativi) **senza** rotation — si assume che la key sia valida
ma il server temporaneamente occupato.

*source: `src/aria/agents/search/providers/_http.py`, `src/aria/tools/*/mcp_server.py`*

---

## Error Classes (gerarchia)

```python
# _http.py — Layer HTTP
KeyExhaustedError(status_code, detail)
  → Sollevato per HTTP 401/402/403/432
  → Non ritentabile con stessa key

RetryableProviderError(message)
  → Sollevato per HTTP 429/5xx
  → Ritentato con tenacity (backoff, max 3)

# schema.py — Layer dominio
ProviderError(provider, reason, status_code, message, retryable)
  → reason: "credits_exhausted" | "request_failed"
  → retryable: True = prova altra key, False = non ritentare
  → Sollevato dai provider adapter, intercettato dai MCP server
```

*source: `src/aria/agents/search/providers/_http.py`, `src/aria/agents/search/schema.py`*

---

## SearXNG — Deployment Self-Hosted

### Infrastruttura Docker

```yaml
Container: searxng
Image: searxng/searxng:latest
Port: 127.0.0.1:8888 → 8080
Restart: unless-stopped
```

### Comportamento al riavvio

| Scenario | Risultato |
|----------|-----------|
| Container crash (OOM, errore) | Docker riavvia automaticamente |
| Spegnimento PC | Docker daemon si avvia al boot → container si riavvia |
| `docker stop searxng` | Resta fermo finché `docker start searxng` |
| `bin/aria repl` | Non tocca il container — sono indipendenti |

**Prerequisito**: Docker daemon deve essere abilitato al boot (`systemctl is-enabled docker` = `enabled`).

### Configurazione

- File: `.aria/runtime/searxng/settings.yml`
- Motori abilitati: Google, Bing, DuckDuckGo, Qwant, Brave
- Formato risposta: JSON
- Lingua: it-IT (default), en (secondaria)

### Disabilitazione

Se `ARIA_SEARCH_SEARXNG_URL` non è impostata (o vuota), il provider risulta `is_enabled = False`
e il tool `search()` solleva `ToolError("SearXNG disabled: set ARIA_SEARCH_SEARXNG_URL")`.

*source: `.aria/runtime/searxng/settings.yml`, `.aria/kilocode/kilo.json`, `src/aria/agents/search/providers/searxng.py`*

---

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

La classificazione è regex-based (no LLM): keyword come "oggi", "news", "paper", "arxiv" etc.

*source: `src/aria/agents/search/schema.py` INTENT_KEYWORDS, `docs/foundation/aria_foundation_blueprint.md` §11.2*

---

## Fallback Tree (per il Search-Agent LLM)

Il search-agent riceve le istruzioni di routing dal suo frontmatter (`search-agent.md`):

1. **Query fattuale / generale** → `exa-script_search` → `tavily-mcp_search` → `searxng-script_search`
2. **Query accademica** → `exa-script_search` → `tavily-mcp_search`
3. **URL specifico** → `firecrawl-mcp_scrape` → `fetch_fetch`
4. **Fallback privacy** → `searxng-script_search` → `brave-mcp_brave_web_search`

Il search-agent **non** implementa il fallback nel codice — è l'LLM stesso che, ricevendo
`isError: true` da un tool, decide di provare il successivo. Questo è il comportamento
naturale quando `ToolError` segnala correttamente l'errore.

*source: `.aria/kilocode/agents/search-agent.md`*

---

## Wrapper Scripts (environment isolation)

Ogni MCP server è avviato tramite un wrapper bash che resetta l'ambiente:

```bash
exec env -i \
    HOME="$HOME" \
    PATH="$PATH" \
    ARIA_HOME="$ARIA_HOME" \
    ARIA_RUNTIME="$ARIA_HOME/.aria/runtime" \
    ARIA_CREDENTIALS="$ARIA_HOME/.aria/credentials" \
    SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" \
    "$ARIA_HOME/.venv/bin/python" -m aria.tools.<provider>.mcp_server
```

Il wrapper SearXNG aggiunge `ARIA_SEARCH_SEARXNG_URL` all'environment isolato.

*source: `scripts/wrappers/*-wrapper.sh`*

---

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
    rotation_strategy: least_used
```

### Ciclo di vita circuit breaker

- **Closed** (normale) → errori rari tollerati
- **Open** → dopo 3 failure in 5min → cooldown 30min
- **Half-open** → dopo cooldown, 1 tentativo; se ok → closed, se fail → open esteso

*source: `src/aria/credentials/rotator.py`, `docs/foundation/aria_foundation_blueprint.md` §11.3*

---

## Deduplicazione e Ranking

`src/aria/agents/search/dedup.py`:

1. URL canonicalization (rimozione utm_, query params non significativi)
2. Fuzzy match titoli con Levenshtein (ratio ≥ 0.85 = duplicato)
3. Score aggregato: `score = provider_weight × relevance × recency_decay`

*source: `docs/foundation/aria_foundation_blueprint.md` §11.4*

---

## Caching

- Cache query→results in memoria episodica tagged `search_cache` con TTL default 6h
- Hit ratio atteso ≥ 20%
- `aria search --no-cache` per bypass

*source: `docs/foundation/aria_foundation_blueprint.md` §11.5*

---

## Implementazione Codice — Mappa Completa

```
src/aria/
├── agents/search/
│   ├── schema.py               # SearchHit, ProviderError, Intent, INTENT_ROUTING
│   ├── router.py               # Intent-aware routing (regex classifier)
│   ├── dedup.py                # URL dedup + ranking
│   └── providers/
│       ├── _http.py             # request_json_with_retry, KeyExhaustedError, RetryableProviderError
│       ├── tavily.py            # TavilyProvider — POST /search, key in params
│       ├── firecrawl.py         # FirecrawlProvider — search/scrape/extract
│       ├── exa.py               # ExaProvider — POST /search, Bearer auth
│       ├── searxng.py           # SearXNGProvider — GET /search?format=json, no key
│       ├── brave.py             # BraveProvider
│       └── serpapi.py           # SerpAPIProvider
├── tools/
│   ├── tavily/mcp_server.py     # FastMCP("tavily-mcp") — search + rotation loop
│   ├── exa/mcp_server.py        # FastMCP("exa-script") — search + rotation loop
│   ├── firecrawl/mcp_server.py  # FastMCP("firecrawl-mcp") — search/scrape/extract + rotation
│   └── searxng/mcp_server.py    # FastMCP("searxng-script") — search, no rotation needed
└── credentials/
    ├── manager.py               # CredentialManager.acquire/report_success/report_failure
    └── rotator.py               # Circuit breaker per-key state

scripts/wrappers/
├── tavily-wrapper.sh            # env isolation → python -m aria.tools.tavily.mcp_server
├── exa-wrapper.sh               # env isolation → python -m aria.tools.exa.mcp_server
├── firecrawl-wrapper.sh         # env isolation → python -m aria.tools.firecrawl.mcp_server
├── searxng-wrapper.sh           # env isolation + ARIA_SEARCH_SEARXNG_URL
└── brave-wrapper.sh             # npm wrapper per @brave/brave-search-mcp-server
```

*source: analisi struttura `src/aria/`*

---

## Vedi anche

- [[credentials]] — Rotation e circuit breaker dettaglio
- [[tools-mcp]] — MCP server ecosystem (tutti i server, non solo search)
- [[skills-layer]] — deep-research skill (orchestra multi-step search)
- [[ten-commandments]] — P8 (Tool Priority Ladder), P9 (Scoped Toolsets)
