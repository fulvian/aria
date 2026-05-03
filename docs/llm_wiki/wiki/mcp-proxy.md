# MCP Proxy (aria-mcp-proxy)

**Last Updated**: 2026-05-03T17:04+02:00
**Status**: Active ✅ — naming convention unified to single underscore `server_tool` (v7.0)
**Source**: `src/aria/mcp/proxy/`, `.aria/config/proxy.yaml`, `.aria/kilocode/mcp.json`, `.aria/config/agent_capability_matrix.yaml`, `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`, `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`, `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`

## Purpose

A FastMCP-native multi-server proxy that exposes `search_tools` and `call_tool`
synthetic tools to KiloCode. It replaced the static `lazy_loader.py` path and
reduced the MCP surface presented to KiloCode to a stable 2-entry runtime:
`aria-memory` + `aria-mcp-proxy`.

## Components

| File | Responsibility |
|---|---|
| `src/aria/mcp/proxy/server.py` | wires catalog + broker + transform + middleware |
| `src/aria/mcp/proxy/broker.py` | lazy backend session management + catalog tool metadata |
| `src/aria/mcp/proxy/catalog.py` | loads `mcp_catalog.yaml`, yields `BackendSpec`s |
| `src/aria/mcp/proxy/credential.py` | resolves `${VAR}` placeholders via `CredentialManager` |
| `src/aria/mcp/proxy/config.py` | `ProxyConfig` pydantic model (search/embedding/cache config) |
| `src/aria/mcp/proxy/middleware.py` | per-agent allowed-tools enforcement (`_caller_id`) |
| `src/aria/mcp/proxy/transforms/hybrid.py` | BM25 + mxbai-embed-large-v1 blend |
| `src/aria/mcp/proxy/transforms/lmstudio_embedder.py` | HTTP client for LM Studio embeddings |

## ✅ Correct naming pattern (single underscore)

**Tutti i tool name MCP devono usare il singolo underscore `_` come separatore tra server name e tool name.**

| Pattern | Esempio | Stato |
|---------|---------|-------|
| `server_tool` | `aria-mcp-proxy_search_tools` | ✅ **Standard** |
| `server_*` (wildcard) | `google_workspace_*` | ✅ **Standard** |
| `server__tool` (double underscore) | `aria-mcp-proxy__search_tools` | ❌ Deprecato |
| `server/tool` (slash) | `google_workspace/create_event` | ❌ Deprecato |

Utilizzare sempre il singolo underscore in:
- Capability matrix (`agent_capability_matrix.yaml`) → `google_workspace_*`
- Agent prompts (`allowed-tools` frontmatter) → `aria-mcp-proxy_search_tools`
- Skill files (SKILL.md) → `aria-mcp-proxy_search_tools`, `server_tool`
- Test assertion → `"tavily-mcp_search"`

---

## Operational baseline

- `mcp.json`: **2 live entries** (`aria-memory`, `aria-mcp-proxy`)
- Proxy synthetic entrypoints exposed to KiloCode: `search_tools`, `call_tool`
- Agent-facing canonical prompt tool names: `aria-mcp-proxy_search_tools`, `aria-mcp-proxy_call_tool` (single underscore `_` separator)
- Emergency rollback path: `bin/aria start --emergency-direct`
- Backend boot filtering: when `ARIA_CALLER_ID` is set, proxy boot loads only backend servers referenced by that agent's `allowed_tools`; `aria-memory` stays out-of-proxy and remains a separate MCP dependency
- **Catalog-driven discovery** (since F9): `search_tools` indexes `expected_tools` metadata from `mcp_catalog.yaml` without contacting any live backend; actual backend sessions are created on demand by `LazyBackendBroker` only when `call_tool` is invoked
- Embeddings cache: `.aria/runtime/proxy/embeddings/`
- Metrics namespace: `aria_proxy_*`
- Proxy events: `proxy.start`, `proxy.shutdown`, `proxy.backend_quarantine`, `proxy.cutover`, `proxy.emergency_rollback`, `proxy.caller_anomaly`

## Canonical contract (post-remediation)

### 1. Discovery and execution model
- Agents do **not** expose backend MCP wildcards in frontmatter anymore.
- Agents expose only the proxy synthetic tools plus direct non-proxy tools (memory, sequential-thinking, spawn-subagent, HITL where needed).
- Every proxy call must include `_caller_id` in the arguments.
- Canonical pattern:
  1. discovery via `aria-mcp-proxy_search_tools`
  2. execution via `aria-mcp-proxy_call_tool`

### 2. Enforcement model
- `on_call_tool`: **fail-closed** for non-synthetic calls when no caller identity is present.
- `on_list_tools`: synthetic tools are always visible; missing caller identity is logged as anomaly/warning.
- Capability matrix remains the source of truth for backend reachability.
- Search transforms improve discovery only; they are **not** factual validation controls.

### 3. Naming model
- The naming convention is uniformly single underscore `server_tool` (e.g., `aria-mcp-proxy_search_tools`, `google_workspace_search_gmail_messages`).
- Wildcards in matrix are server-scoped (`server_*`) to absorb upstream tool renames.
- No compatibility shims for legacy `server__tool` (double underscore) or `server/tool` (slash) forms remain — the migration is complete.

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
| F9 | ✅ | Catalog-driven search + lazy backend broker: `search_tools` uses catalog metadata only, `call_tool` creates single-backend sessions on demand |

## Known issues and fixes history

### F6 — server startup noise (2026-05-01)
**Problema**: Alcuni backend stampavano testo non-JSONRPC su stdout, rompendo la connessione MCP.

**Fix**: `scripts/mcp-stdio-filter.py` filtra stdout e inoltra solo payload JSONRPC validi.

### F6 — naming convention mismatch — resolved (2026-05-01 → 2026-05-03)
**Problema**: Il proxy esponeva nomi runtime `server_tool` (singolo underscore), mentre matrix e prompt usavano `server__tool` (doppio underscore).

**Fix (v6.0)**: `YamlCapabilityRegistry.is_tool_allowed()` e `CapabilityMatrixMiddleware._matches()` aggiungevano compatibility shim per gestire tutti e tre i formati (`__`, `_`, `/`).

**Risoluzione definitiva (2026-05-03)**: Tutti i riferimenti `server__tool` sono stati migrati al singolo underscore `server_tool`. I compatibility shim nelle funzioni `_matches()`, `is_tool_allowed()`, `resolve_server_from_tool()` e `_tool_server_name()` sono stati rimossi. Il formato singolo underscore è ora l'unico standard in tutto il codebase.

### F6 — wildcard capability matrix (2026-05-01)
**Problema**: La matrice elencava tool name troppo specifici e fragili.

**Fix**: sostituzione con wildcard `server_*`.

### F7 — caller-aware backend boot filtering (2026-05-01)
**Problema**: Il proxy bootava tutti i backend enabled anche in sessioni search-only, avviando server irrilevanti come `google_workspace`.

**Fix**: `build_proxy()` filtra i backend caricati quando `ARIA_CALLER_ID` è presente.

### F9 — catalog-driven search + lazy backend broker (2026-05-02)
**Problema**: `search_tools` enumerava tutti i backend live (tramite `create_proxy(all_backends)`), causando boot di server irrilevanti (google_workspace, filesystem) durante workflow trader-agent.

**Fix**:
- Rimosso `create_proxy(all_backends)` da `build_proxy()`.
- `search_tools` usa `LazyBackendBroker.catalog_tools()` — tool metadata da `mcp_catalog.yaml`, zero live backend.
- `call_tool` usa `LazyBackendBroker.call()` — singola sessione backend creata on demand e cachata.
- `resolve_server_from_tool()` gestisce tutti e tre i formati (double-underscore, single-underscore, slash) con longest-prefix matching per server con underscore nel nome (e.g. `google_workspace`).
- Nuovo modulo: `src/aria/mcp/proxy/broker.py`.

### F10 — Google Workspace contract reconciliation (2026-05-02)
**Problema**: prompt/skill/catalog usavano una combinazione incoerente di:
- invocazione errata dei tool sintetici (`call_tool("search_tools")`, `call_tool("call_tool")`)
- vecchi nomi `google_workspace` (`drive_list`, `gmail_search`, `docs_create`, ...)

**Fix**:
- prompt e runtime copy riallineati al pattern corretto:
  1. `aria-mcp-proxy_search_tools({...})`
  2. `aria-mcp-proxy_call_tool({...})`
- `mcp_catalog.yaml` ora usa i nomi canonici upstream di `workspace-mcp`
- `LazyBackendBroker` normalizza gli alias legacy `google_workspace` più comuni
  verso i nomi live backend per robustezza retrocompatibile
  (es. `drive_list` → `list_drive_items`, `gmail_search` → `search_gmail_messages`)

### F8 — remediation completed (2026-05-01)
**Runtime/policy hardening**
- `middleware.py`: `on_call_tool` è ora fail-closed quando manca il caller identity per tool non sintetici.
- `on_list_tools` emette warning strutturato quando il caller è assente.

**Canonical proxy contract**
- `search-agent` e `productivity-agent` espongono solo i tool sintetici del proxy nel frontmatter.
- `workspace-agent` è ridotto a stub transitorio con lo stesso modello canonico.
- Le skill attive usano `_caller_id` e il pattern `search_tools` → `call_tool`.

**Productivity/workspace convergence**
- `productivity-agent` ha `google_workspace_*` nella capability matrix.
- `productivity-agent` è ora il work-domain agent principale.
- `workspace-agent` è dichiarato compatibilità/transitorio nei prompt e nella governance.

**Docs/governance**
- ADR-0008 è stato emendato.
- Blueprint P9 è stato formalmente riscritto come **Scoped Active Capabilities**.

## Fixed Bugs (2026-05-03)

### ~~B1 — `BackendSpec.to_mcp_entry()` ignora `transport` field~~ ✅ FIXED

**File**: `catalog.py:40-51`
**Fix PR**: branch `fix/trader-agent-recovery`

`to_mcp_entry()` ora produce formato corretto in base al transport:
- HTTP/SSE: `{"url": self.url, "transport": self.transport}`
- stdio: `{"command": self.command, "args": list(self.args)}`

`BackendSpec` ha un nuovo campo `url: str = ""`. `_parse_entry()` auto-rileva URL per HTTP backends da `source_of_truth` (se inizia con `http`) o dal campo esplicito `url` nello YAML.

**Context7 verificato**: FastMCP `create_proxy` supporta nativamente `{"url": ..., "transport": "http"}`.

**Helium MCP** ora abilitato (9 tool). FMP richiede ancora server lifecycle management.

### ~~B2 — `_tool_server_name()` split errato per underscore~~ ✅ FIXED

**File**: `server.py:210-227`
**Fix PR**: branch `fix/trader-agent-recovery`

`_tool_server_name()` ora accetta `known_servers: set[str] | None` e usa right-to-left longest-prefix matching. Per `google_workspace_search_gmail`, cerca ogni prefisso separato da `_` da destra verso sinistra finché non trova una corrispondenza in `known_servers`.

`_filter_backends_for_caller()` passa `known_servers` a `_allowed_server_names()` → `_tool_server_name()`.

**Test**: 12 nuovi test per B1 (5) + B2 (7). 959 totali pass.

### ~~B3 — _caller_id non passato dal client MCP~~ ✅ FIXED (99b3f37)

**File**: `server.py:116-128`, `middleware.py:74-134`

**Problema**: `_call_tool(name, arguments)` e `_search_tools(query)` dichiaravano
solo `name`/`arguments`/`query`. FastMCP `Tool.from_function()` genera lo schema
MCP esclusivamente dai parametri della funzione. Client MCP strict scartano
`_caller_id` perché non nello schema → middleware fail-chiudeva per TUTTI gli agenti.

**Fix**: Aggiunto `_caller_id: str | None = None` come parametro esplicito in entrambe
le funzioni. Il parametro è ignorato dal corpo ma incluso nello schema MCP.
Prompt trader-agent aggiornato: `_caller_id` va come parametro separato.

### ~~C1-C2 — Catalog/backend tool mismatches~~ ✅ FIXED (d559451)

**File**: `.aria/config/mcp_catalog.yaml`

`financekit-mcp`: 6 tool names errati rimossi, 12 tool mancanti aggiunti (17 totali).
`mcp-fredapi`: 2 tool inesistenti (`get_fred_series_info`, `get_fred_series_search`) rimossi.

### ~~C3 — search_tools max_results=5 nascondeva 143/148 tool~~ ✅ FIXED

**File**: `transforms/hybrid.py`

`HybridSearchTransform._search()` in discovery mode (query vuota) restituisce
l'intero catalogo invece di troncare a 5. Verificato: `search_tools(query="")` → 148 tool.

### ~~C4 — broker.call() errore opaco~~ ✅ FIXED

**File**: `broker.py`

Cattura `Unknown tool` e restituisce backend name + lista tool disponibili + hint
`search_tools`. Evita loop di retry dell'agente.

## Residual caveats
2. `workspace-agent` esiste ancora per compatibilità; non è più il target architetturale di lungo periodo.
3. Futuri cleanup potranno rimuovere riferimenti residui a percorsi legacy collegati a `workspace-agent`.
4. Catalog-driven tool descriptions derivano da `expected_tools` + `notes` in `mcp_catalog.yaml`; i tool description specifici per tool (parametri, ecc.) sono disponibili solo dopo la prima chiamata al backend.

## Spec and ADR provenance

- Design: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`
- Boundary/governance amendment: `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`
- Runtime source: `src/aria/mcp/proxy/`
