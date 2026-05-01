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

## Spec & ADR

- Design: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`
