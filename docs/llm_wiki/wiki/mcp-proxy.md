# MCP Proxy (aria-mcp-proxy)

**Last Updated**: 2026-05-03T18:35+02:00
**Status**: Active ✅ — remediation complete; canonical proxy contract is now the live baseline
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
| `src/aria/mcp/proxy/credential.py` | resolves `${VAR}` placeholders in `env` and `headers` (v7.3 adds inline placeholder support) |
| `src/aria/mcp/proxy/config.py` | `ProxyConfig` pydantic model (search/embedding/cache config) |
| `src/aria/mcp/proxy/middleware.py` | per-agent allowed-tools enforcement (`_caller_id`) |
| `src/aria/mcp/proxy/transforms/hybrid.py` | BM25 + mxbai-embed-large-v1 blend |
| `src/aria/mcp/proxy/transforms/lmstudio_embedder.py` | HTTP client for LM Studio embeddings |

## Operational baseline

- `mcp.json`: **2 live entries** (`aria-memory`, `aria-mcp-proxy`)
- Proxy synthetic entrypoints exposed to KiloCode: `search_tools`, `call_tool`
- Agent-facing canonical prompt tool names: `aria-mcp-proxy__search_tools`, `aria-mcp-proxy__call_tool`
- Emergency rollback path: `bin/aria start --emergency-direct`
- Backend boot filtering: when `ARIA_CALLER_ID` is set, proxy boot loads only backend servers referenced by that agent's `allowed_tools`; `aria-memory` stays out-of-proxy and remains a separate MCP dependency
- Embeddings cache: `.aria/runtime/proxy/embeddings/`
- Metrics namespace: `aria_proxy_*`
- Proxy events: `proxy.start`, `proxy.shutdown`, `proxy.backend_quarantine`, `proxy.cutover`, `proxy.emergency_rollback`, `proxy.caller_anomaly`

## Canonical contract (post-remediation)

### 1. Discovery and execution model
- Agents do **not** expose backend MCP wildcards in frontmatter anymore.
- Agents expose only the proxy synthetic tools plus direct non-proxy tools (memory, sequential-thinking, spawn-subagent, HITL where needed).
- Every proxy call must include `_caller_id` in the arguments.
- Canonical pattern:
  1. discovery via `aria-mcp-proxy__search_tools`
  2. execution via `aria-mcp-proxy__call_tool`

### 2. Enforcement model
- `on_call_tool`: **fail-closed** for non-synthetic calls when no caller identity is present.
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
| F9 | ✅ | **HTTP Headers support**: `BackendSpec.headers`, inline `${VAR}` resolution in CredentialInjector, catalog parsing of headers from YAML, context7 + github-discovery ARIA integration, code-discovery skill |

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

**Fix**: `build_proxy()` filtra i backend caricati quando `ARIA_CALLER_ID` è presente.

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

### F9 — HTTP headers support for backend auth (2026-05-03)
**Problema**: Context7 (e altri HTTP MCP backend come Helium) richiedono un header `Authorization: Bearer <token>` per autenticazione, ma `BackendSpec` non supportava il campo `headers`.

**Fix**: 
- `BackendSpec` esteso con `headers: dict[str, str]`
- `to_mcp_entry()` include `headers` per backend HTTP/SSE
- `_parse_entry()` legge `headers` dal YAML
- `CredentialInjector.inject()` risolve `${VAR}` anche in `headers` (non solo `env`)
- `_resolve()` ora gestisce placeholder inline (`Bearer ${TOKEN}`)

**Backend integrati**:
- `github-discovery`: `env.GHDISC_GITHUB_TOKEN` cablato nel catalogo, SOPS credential store
- `context7`: nuova entry nel catalogo con `transport: http`, `url`, `headers.Authorization: Bearer ${CONTEXT7_API_KEY}`
- `code-discovery` skill creata per orchestrazione development-oriented

## Residual caveats

1. `ARIA_CALLER_ID` resta utile per boot-time backend filtering, ma il modello condiviso usa `_caller_id` come meccanismo primario di enforcement per request.
2. `workspace-agent` esiste ancora per compatibilità; non è più il target architetturale di lungo periodo.
3. Futuri cleanup potranno rimuovere riferimenti residui a percorsi legacy collegati a `workspace-agent`.

## Spec and ADR provenance

- Design: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`
- Boundary/governance amendment: `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`
- Runtime source: `src/aria/mcp/proxy/`
