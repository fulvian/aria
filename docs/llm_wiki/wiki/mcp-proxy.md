# MCP Proxy (aria-mcp-proxy)

**Last Updated**: 2026-05-01
**Status**: Active (F1 — Core implementation complete)
**Source**: `src/aria/mcp/proxy/`, `.aria/config/proxy.yaml`,
`docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`

## Purpose

A FastMCP-native multi-server proxy that exposes `search_tools` and
`call_tool` synthetic tools to KiloCode. Replaces the static
`lazy_loader.py` and removes per-server tool-definition cost from the
KiloCode startup context.

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

## Operational

- mcp.json: 2 entries (`aria-memory`, `aria-mcp-proxy`) — planned for F3
- Emergency rollback: `bin/aria start --emergency-direct` — planned for F3
- Backend boot filtering: when `ARIA_CALLER_ID` is set, proxy boot loads only
  backend servers referenced by that agent's `allowed_tools`; `aria-memory`
  stays out-of-proxy and remains a separate MCP dependency.
- Embeddings cache: `.aria/runtime/proxy/embeddings/`
- Metrics: `aria_proxy_*` (Prometheus) — planned for F5
- Events: `proxy.start`, `proxy.shutdown`, `proxy.backend_quarantine`,
  `proxy.cutover`, `proxy.emergency_rollback`, `proxy.caller_anomaly` — planned for F5

## Implementation Phases

| Phase | Status | Description |
|---|---|---|
| F0 | ✅ | Smoke — FastMCP proxy stdio verified |
| F1 | ✅ | Core — all proxy modules with unit + integration tests |
| F2 | ✅ | Shadow — proxy entry alongside existing MCP servers |
| F3 | ✅ | Cutover — mcp.json → 2 entries, agent prompts namespaced, tag `proxy-cutover-v1` |
| F4 | ✅ | `lazy_loader.py` removed, `mcp_catalog.yaml` stripped of `lazy_load`/`intent_tags`, ADR-0015 |
| F5 | ✅ | Observability (`proxy.*` events + `aria_proxy_*` metrics), skills namespaced, wiki finalized |
| **F6** | ✅ | **Debug & stabilizzazione**: stdio filter per server rumorosi, naming fix (single/double underscore), wildcard matrix |

## Known Issues & Fixes

### F6 — server startup noise (2026-05-01)
**Problema**: I server SearXNG, Scientific Papers, Tavily e Google Workspace stampano
testo di startup non-JSONRPC su stdout (`"SearXNG MCP server is running..."`,
`"info: Starting SciHarvester..."`, banner FastMCP, ecc.). FastMCP interpreta ogni
linea stdout come JSONRPC e fallisce, rompendo la connessione MCP.

**Fix**: `scripts/mcp-stdio-filter.py` — relay bidirezionale che filtra stdout
passando solo messaggi JSONRPC validi e reindirizzando il resto a stderr.
Applicato ai 4 wrapper scripts via `exec uv run mcp-stdio-filter.py -- <cmd>`.

### F6 — naming convention mismatch (2026-05-01)
**Problema**: Il proxy espone tool con singolo underscore (`server_tool`) dovuto
al `Namespace` transform di FastMCP, ma la capability matrix e gli agent prompts
usavano doppio underscore (`server__tool`). Il middleware bloccava chiamate
legittime per mancato matching.

**Fix**: `YamlCapabilityRegistry.is_tool_allowed()` e
`CapabilityMatrixMiddleware._matches()` ora gestiscono 3 forme:
- `server__tool` (convenzione matrix/prompts)
- `server/tool` (legacy pre-F3)
- `server_tool` (nome reale dal proxy, singolo underscore)

### F6 — wildcard capability matrix (2026-05-01)
**Problema**: La matrice elencava nomi di tool specifici che non corrispondevano
ai nomi reali del proxy (es. `searxng-script__search` vs `searxng-script_search_web`).

**Fix**: Sostituiti tutti i nomi esatti con wildcard per server (`server__*`),
molto più resilienti a cambiamenti dei nomi dei tool nei backend upstream.

### F7 — caller-aware backend boot filtering (2026-05-01)
**Problema**: Il proxy bootava tutti i backend enabled dal catalogo anche in
 sessioni search-only. Durante il caso cinema del 2026-05-01 questo avviava
 backend irrilevanti come `google_workspace`, causando rumore JSONRPC e conflitti
 OAuth/porta inutili.

**Fix**: `build_proxy()` ora deriva i backend ammessi dai prefissi `server__*`
 presenti in `allowed_tools` del caller (`ARIA_CALLER_ID`), esclude i server non
 pertinenti e mantiene `aria-memory` separato dal proxy. Verifica FastMCP:
 le search transforms limitano discovery/listing, non validano l'output fattuale
 dei tool; il filtering va quindi applicato al boot dei backend e alla middleware.

## Spec & ADR

- Design: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`
- Fixes branch: `feat/mcp-tool-search-proxy` (commit `d08b57b`+)
