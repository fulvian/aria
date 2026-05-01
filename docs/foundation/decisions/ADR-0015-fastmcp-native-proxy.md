# ADR-0015: FastMCP-Native Multi-Server Proxy

**Status**: Implemented (F1-F3)
**Date**: 2026-05-01
**Authors**: fulvio
**Related**: ADR-0010 (lazy loading), ADR-0012 (cutover/rollback)

## Context

ARIA's initial MCP integration used a static multi-entry `mcp.json` with 16
server entries, each defining its own tool profile. Every KiloCode session
loaded the full 40K tokens of tool definitions into the LLM context window,
consuming ~80% of available context before any agent interaction began.

Two earlier attempts to mitigate this were:

1. **ADR-0010 (lazy loading)**: A bootstrap-per-intent strategy that filtered
   `mcp.json` entries by `intent_tags`. This reduced tool tokens but still
   required KiloCode to parse and validate the filtered JSON, and introduced
   YAML → JSON translation drift documented in `check_mcp_drift.py`.

2. **ADR-0012 (cutover/rollback)**: Provided a controlled cutover framework
   with rollback capability via `mcp.json.baseline`.

The fundamental problem remained: every backend MCP server contributed its own
tool definitions to KiloCode's initialization, and there was no intermediate
layer to aggregate, search, or filter tools at runtime.

## Decision

Replace the static multi-entry `mcp.json` with a FastMCP-native proxy server
(`src/aria/mcp/proxy/`) that:

1. Aggregates all backend MCP servers into a single stdio endpoint.
2. Exposes exactly two synthetic tools to KiloCode:
   - `search_tools(query)` — BM25 + semantic hybrid search over tool metadata.
   - `call_tool(name, arguments)` — routes calls to the correct backend.
3. Reduces startup tool-definition tokens from ~40K to < 2K.
4. Applies per-agent capability enforcement via `CapabilityMatrixMiddleware`
   using `_caller_id` convention and `agent_capability_matrix.yaml`.

## Architecture

```
KiloCode session
    │
    ├── aria-memory (direct — 12 tools/1.5K tokens)
    └── aria-mcp-proxy (proxy — 2 synthetic tools)
            │
            ├── filesystem (stdio)
            ├── tavily-mcp (stdio)
            ├── brave-mcp (stdio)
            ├── google_workspace (stdio)
            ├── ... (12 more backends)
            │
            └── HybridSearchTransform
                    ├── BM25 Okapi ranking
                    └── mxbai-embed-large-v1 semantic (1024d)
```

## Key Design Decisions

### 1. BM25+Semantic hybrid search (F1.7)
   - **BM25** provides fast keyword matching (inherited from FastMCP).
   - **Semantic** via LM Studio `mxbai-embed-large-v1` adds intent-aware ranking.
   - Blend parameter (`proxy.yaml: search.blend = 0.6`) controls weight.
   - Graceful degradation: if LM Studio is unavailable, falls back to pure BM25.

### 2. Per-agent capability enforcement (F1.8)
   - Agent prompts pass `_caller_id: "<agent>"` with every `call_tool` invocation.
   - `CapabilityMatrixMiddleware` checks `agent_capability_matrix.yaml` before
     forwarding the call.
   - Synthetic tools `search_tools` and `call_tool` are always visible.
   - When the proxy tool is `call_tool`, the middleware checks the *backend*
     tool name, not the proxy tool name.

### 3. Namespaced tool names (F3)
   - Tools are namespaced as `server__tool_name` (e.g., `tavily-mcp__search`).
   - The capability matrix uses the same `__` form.
   - Legacy `server/tool` form is supported during migration via fallback
     matching in `CapabilityMatrixMiddleware._matches()`.

### 4. Cutover strategy (F3)
   - Phase 1 (F2): Proxy added to `mcp.json` alongside existing 14 servers
     (shadow mode, no agent prompts use it).
   - Phase 2 (F3): `mcp.json` reduced to 2 entries (`aria-memory`,
     `aria-mcp-proxy`). Agent prompts updated with namespaced tools +
     `_caller_id` rule.
   - Emergency rollback: `mcp.json.baseline` preserved and
     `bin/aria start --emergency-direct` restores the original 16-entry config.

## Consequences

### Positive
- Tool-definition tokens reduced from ~40K to < 2K per session.
- Per-agent tool filtering without KiloCode-level restrictions.
- Embedding cache avoids repeated LM Studio calls for the same tool catalog.
- Clean on-call separation: backend servers are opaque to KiloCode.

### Negative
- Cold-start latency increased by ~300ms (BM25 indexing + optional embedding).
- LM Studio is a runtime dependency for semantic search; offline fallback
  is pure BM25, which is still functional but less accurate.
- Backend servers that emit non-JSON-RPC startup text (SearXNG, Google
  Workspace, Scientific Papers) cause `Failed to parse JSONRPC message`
  errors in the proxy's client. These are non-fatal (process still works)
  but noisy.

### Risks
- Proxy is a single point of failure: if `aria-mcp-proxy` crashes, all
  backend tools are unreachable. Mitigated by emergency rollback
  (`--emergency-direct`) and the plan to add systemd auto-restart.
- `_caller_id` is agent-provided (not cryptographically verified);
  agents could impersonate other agents. Risk is low because KiloCode
  controls agent execution.

## Related Documents

- Design spec: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- Implementation plan: `docs/plans/mcp_search_tool_plan_1.md`
- Proxy package: `src/aria/mcp/proxy/`
- Config: `.aria/config/proxy.yaml`
- Wiki: `docs/llm_wiki/wiki/mcp-proxy.md`
- Baseline snapshot: `.aria/kilocode/mcp.json.baseline`
