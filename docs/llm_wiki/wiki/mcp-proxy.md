# MCP Proxy (aria-mcp-proxy)

**Last Updated**: 2026-05-04T09:15+02:00
**Status**: Active ✅ — caller contamination root-caused and shared-proxy fallback hardened
**Source**: `src/aria/mcp/proxy/`, `.aria/config/proxy.yaml`, `.aria/kilocode/mcp.json`, `.aria/config/agent_capability_matrix.yaml`, `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`, `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`, `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`

## Purpose

A FastMCP-native multi-server proxy that exposes `search_tools` and `call_tool`
synthetic tools to KiloCode. It replaced the static `lazy_loader.py` path and
reduced the MCP surface presented to KiloCode to a stable 2-entry runtime:
`aria-memory` + `aria-mcp-proxy`.

## Components

| File | Responsibility |
|---|---|
| `src/aria/mcp/proxy/server.py` | wires catalog + transform + middleware |
| `src/aria/mcp/proxy/catalog.py` | loads `mcp_catalog.yaml`, yields `BackendSpec`s |
| `src/aria/mcp/proxy/credential.py` | resolves `${VAR}` placeholders via `CredentialManager` |
| `src/aria/mcp/proxy/config.py` | `ProxyConfig` pydantic model (search/embedding/cache config) |
| `src/aria/mcp/proxy/middleware.py` | per-agent allowed-tools enforcement (`_caller_id`) |
| `src/aria/mcp/proxy/transforms/hybrid.py` | BM25 + mxbai-embed-large-v1 blend |
| `src/aria/mcp/proxy/transforms/lmstudio_embedder.py` | HTTP client for LM Studio embeddings |

## Operational baseline

- `mcp.json`: **2 live entries** (`aria-memory`, `aria-mcp-proxy`)
- Proxy synthetic entrypoints exposed to KiloCode: `search_tools`, `call_tool`
- Agent-facing canonical prompt tool names: `aria-mcp-proxy__search_tools`, `aria-mcp-proxy__call_tool`
- Emergency rollback path: `bin/aria start --emergency-direct`
- Backend boot filtering: manual single-agent filtering is now opt-in via `ARIA_PROXY_BOOT_CALLER_ID`; legacy ambient `ARIA_CALLER_ID` is ignored by default in shared ARIA sessions
- Embeddings cache: `.aria/runtime/proxy/embeddings/`
- Metrics namespace: `aria_proxy_*`
- Proxy events: `proxy.start`, `proxy.shutdown`, `proxy.backend_quarantine`, `proxy.cutover`, `proxy.emergency_rollback`, `proxy.caller_anomaly`

## Canonical contract (post-remediation)

### 1. Discovery and execution model
- Agents do **not** expose backend MCP wildcards in frontmatter anymore.
- Agents expose only the proxy synthetic tools plus direct non-proxy tools (memory, sequential-thinking, spawn-subagent, HITL where needed).
- Every proxy call must include `_caller_id` in the arguments.
- Discovery examples should include `_caller_id` too, even if the underlying schema only requires `query`.
- Canonical pattern:
  1. discovery via `aria-mcp-proxy__search_tools`
  2. execution via `aria-mcp-proxy__call_tool`

### 2. Enforcement model
- `on_call_tool`: **fail-closed** for non-synthetic calls when no caller identity is present.
- `call_tool` must carry an explicit per-request `_caller_id`; it must not inherit a shared ambient agent identity.
- `on_list_tools`: synthetic tools are always visible; missing caller identity is logged as anomaly/warning.
- Capability matrix remains the source of truth for backend reachability.
- Search transforms improve discovery only; they are **not** factual validation controls.

### 3. Naming model
- Prompts and matrix use the logical `server__tool` form.
- Middleware/registry compatibility layer also accepts:
  - legacy `server/tool`
  - runtime single-underscore `server_tool`
- Wildcards in matrix are server-scoped (`server__*`) to absorb upstream tool renames.

### 4. Agent-boundary model
- `search-agent` remains a separate research-domain agent.
- `productivity-agent` is now the unified work-domain agent for:
  - local filesystem
  - office ingestion
  - Google Workspace
  - meeting prep / email drafting
- `workspace-agent` remains transitional/compatibility-only.

## Implementation phases

| Phase | Status | Description |
|---|---|---|
| F0 | ✅ | Smoke — FastMCP proxy stdio verified |
| F1 | ✅ | Core — all proxy modules with unit + integration tests |
| F2 | ✅ | Shadow — proxy entry alongside existing MCP servers |
| F3 | ✅ | Cutover — mcp.json → 2 entries, agent prompts namespaced, tag `proxy-cutover-v1` |
| F4 | ✅ | `lazy_loader.py` removed, `mcp_catalog.yaml` stripped of `lazy_load`/`intent_tags`, ADR-0015 |
| F5 | ✅ | Observability (`proxy.*` events + `aria_proxy_*` metrics), skills namespaced, wiki finalized |
| F6 | ✅ | Debug & stabilizzazione: stdio filter, naming fix (single/double underscore), wildcard matrix |
| F7 | ✅ | Search-flow stabilization: caller-aware backend boot filtering |
| F8 | ✅ | Remediation: fail-closed middleware, canonical proxy contract, productivity/workspace convergence |

## Known issues and fixes history

### F6 — server startup noise (2026-05-01)
**Problema**: Alcuni backend stampavano testo non-JSONRPC su stdout, rompendo la connessione MCP.

**Fix**: `scripts/mcp-stdio-filter.py` filtra stdout e inoltra solo payload JSONRPC validi.

### F6 — naming convention mismatch (2026-05-01)
**Problema**: Il proxy esponeva nomi runtime `server_tool`, mentre matrix e prompt usavano `server__tool`.

**Fix**: `YamlCapabilityRegistry.is_tool_allowed()` e `CapabilityMatrixMiddleware._matches()` ora gestiscono `server__tool`, `server/tool` e `server_tool`.

### F6 — wildcard capability matrix (2026-05-01)
**Problema**: La matrice elencava tool name troppo specifici e fragili.

**Fix**: sostituzione con wildcard `server__*`.

### F7 — caller-aware backend boot filtering (2026-05-01)
**Problema**: Il proxy bootava tutti i backend enabled anche in sessioni search-only, avviando server irrilevanti come `google_workspace`.

**Fix**: `build_proxy()` filtra i backend caricati quando `ARIA_PROXY_BOOT_CALLER_ID` è presente.

### F8 — remediation completed (2026-05-01)
**Runtime/policy hardening**
- `middleware.py`: `on_call_tool` è ora fail-closed quando manca il caller identity per tool non sintetici.
- `on_list_tools` emette warning strutturato quando il caller è assente.

**Canonical proxy contract**
- `search-agent` e `productivity-agent` espongono solo i tool sintetici del proxy nel frontmatter.
- `workspace-agent` è ridotto a stub transitorio con lo stesso modello canonico.
- Le skill attive usano `_caller_id` e il pattern `search_tools` → `call_tool`.

**Productivity/workspace convergence**
- `productivity-agent` ha `google_workspace__*` nella capability matrix.
- `productivity-agent` è ora il work-domain agent principale.
- `workspace-agent` è dichiarato compatibilità/transitorio nei prompt e nella governance.

**Docs/governance**
- ADR-0008 è stato emendato.
- Blueprint P9 è stato formalmente riscritto come **Scoped Active Capabilities**.

## Residual caveats

1. In sessioni ARIA condivise non bisogna impostare globalmente `ARIA_CALLER_ID` nel `.env`; per boot filtering manuale usare `ARIA_PROXY_BOOT_CALLER_ID` e solo per debug one-agent.
2. `workspace-agent` esiste ancora per compatibilità; non è più il target architetturale di lungo periodo.
3. Futuri cleanup potranno rimuovere riferimenti residui a percorsi legacy collegati a `workspace-agent`.

## 2026-05-04 — Caller contamination remediation

**Problema**: una ricerca `search-agent` che menzionava Amadeus/Airbnb poteva vedere il proxy comportarsi come `traveller-agent`, con discovery travel-centric e errori del tipo `fetch__fetch not allowed for traveller-agent`.

**Root cause**:
- `.env` locale conteneva `ARIA_CALLER_ID=traveller-agent`
- `server.py` lo usava per boot-time backend filtering
- `middleware.py` lo riusava come fallback implicito per request prive di `_caller_id`

**Fix**:
- boot caller env rinominato a `ARIA_PROXY_BOOT_CALLER_ID`
- compatibilità legacy disponibile solo via opt-in esplicito
- `call_tool` non eredita più un caller ambientale implicito
- esempi prompt/skill aggiornati per includere `_caller_id` anche in discovery

**Runbook operativo**:
- In runtime ARIA condivisi lasciare **non impostati** `ARIA_CALLER_ID` e `ARIA_PROXY_REQUEST_CALLER_ID`.
- Per sessioni normali fare affidamento solo su `_caller_id` per request.
- Usare `ARIA_PROXY_BOOT_CALLER_ID` solo per debug/manual boot di un proxy dedicato a un singolo agente.
- Se ricompaiono denial incoerenti del tipo `tool X not allowed for traveller-agent` dentro sessioni `search-agent`, controllare prima l'ambiente del processo proxy e la presenza di `_caller_id` nella request reale.

## 2026-05-04 — Tier-based architecture v2 (proxy-tier)

**Problema risolto**: `TimeoutProxyProvider` creava un singolo `ProxyClient` multi-server con
16 backend. `tools/list` apriva in parallelo tutte le sessioni stdio. Backend lenti
bloccavano l'intera operazione. `asyncio.wait_for(20s)` non garantiva vincolo reale
perché la cancellazione propagava in `__aexit__`.

**Soluzione**: Architettura tier-based con 7 nuovi componenti in `src/aria/mcp/proxy/tier/`:

| Componente | File | Responsabilità |
|---|---|---|
| `TieredProxyProvider` | `tiered_provider.py` | Orchestratore FastMCP Provider — sostituisce `TimeoutProxyProvider` |
| `BackendClient` | `backend_client.py` | Wrapper mono-server attorno a `fastmcp.Client` (1 stdio process per istanza) |
| `WarmPool` | `warm_pool.py` | Sempre-on connessioni per backend ad alta frequenza (healthcheck 30s) |
| `LazyRegistry` | `lazy_registry.py` | On-demand backend spawn con idle TTL sweep |
| `Breaker` | `breaker.py` | Per-backend circuit breaker state machine (closed/open/half_open) |
| `ConcurrencyRegistry` | `semaphore.py` | Per-backend `asyncio.Semaphore` con acquire timeout |
| `MetadataCache` | `metadata_cache.py` | JSON persistente su disk per discovery senza cold start |
| `RetryQueue` | `retry_queue.py` | Background retry con exponential backoff |

**Classificazione tier iniziale**:
- **Warm** (6): `filesystem`, `sequential-thinking`, `aria-memory`, `fetch`, `searxng-script`, `reddit-search`
- **Lazy** (12): `scientific-papers-mcp`, `brave-mcp`, `exa-script`, `tavily-mcp`, `google_workspace`,
  `markitdown-mcp`, `github-discovery`, `airbnb`, `osm-mcp`, `aria-amadeus-mcp`, `booking`

**Pipeline `tools/list` post-fix**:
```
Kilo → tools/list → Provider.list_tools (TieredProxyProvider)
  → warm_tools: live query con timeout 3s per backend (cache fallback)
  → lazy_tools: tutti da metadata cache (nessuna connessione stdio)
  → merge + transform → middleware filter → client
```
Garanzia: `tools/list` NON apre mai connessioni stdio durante la request.

**Nuovi eventi observability** (14 tipi):
`proxy.backend_warm_pool_demote`, `proxy.backend_circuit_open/closed/half_open`,
`proxy.backend_lazy_spawn`, `proxy.backend_idle_shutdown`, `proxy.backend_backpressure`,
`proxy.backend_quarantine`, `proxy.metadata_cache_hit/miss`,
`proxy.list_tools_latency_ms`, `proxy.call_tool_queued`, `proxy.tier_recovery_attempt`

**Nuove metriche Prometheus**:
`aria_proxy_circuit_open_total`, `aria_proxy_lazy_spawn_total`,
`aria_proxy_idle_shutdown_total`, `aria_proxy_list_tools_latency_seconds`,
`aria_proxy_call_tool_queue_wait_seconds`, gauge `aria_proxy_warm_pool_size`,
gauge `aria_proxy_lazy_pool_size`

**File modificati**:
- `src/aria/mcp/proxy/catalog.py` — `BackendSpec` esteso con campi `proxy_lifecycle`, `proxy_concurrency`, `proxy_idle_ttl_s`, `proxy_breaker_threshold`, `proxy_breaker_cooldown_s`
- `src/aria/mcp/proxy/config.py` — `ProxyConfig` esteso con `TierConfig` (default globali tier)
- `src/aria/mcp/proxy/server.py` — usa `TieredProxyProvider` invece di `TimeoutProxyProvider`
- `src/aria/mcp/proxy/provider.py` — **RIMOSSO**
- `.aria/config/proxy.yaml` — aggiunta sezione `tier:`
- `.aria/config/mcp_catalog.yaml` — aggiunto `proxy_lifecycle` per ogni server
- `src/aria/observability/events.py` — aggiunto `ProxyTierEventKind` con 14 valori
- `src/aria/observability/metrics.py` — aggiunte 7 nuove metriche tier

**File creati** (8 nuovi):
`tier/__init__.py`, `tier/tiered_provider.py`, `tier/backend_client.py`, `tier/warm_pool.py`,
`tier/lazy_registry.py`, `tier/breaker.py`, `tier/semaphore.py`, `tier/metadata_cache.py`,
`tier/retry_queue.py`

**Quality gate**: ruff 0 errori, mypy 0 errori, 80 proxy test PASS (49 legacy + 31 nuovi),
803/836 test totali pass (33 preesistenti traveller-agent)

## Spec and ADR provenance

- Design: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`
- ADR: `docs/foundation/decisions/ADR-0019-mcp-proxy-tier-architecture.md`
- Boundary/governance amendment: `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`
- Piano esecuzione: `docs/plans/ripristino_mcp-proxy_plan.md`
- Runtime source: `src/aria/mcp/proxy/`
