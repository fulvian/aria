# Design: ARIA MCP Tool Search Proxy (FastMCP-native)

> **Date**: 2026-05-01
> **Author**: ARIA platform / Fulvio
> **Status**: Draft → in review
> **Branch**: TBD (proposed `feat/mcp-tool-search-proxy`)
> **Related plan**: `docs/plans/mcp_search_tool_plan_1.md` (to be written)
> **Supersedes**: `src/aria/launcher/lazy_loader.py` (static lazy bootstrap)

---

## 1. Problem statement

ARIA currently exposes 14 MCP servers (~100+ tool definitions) eagerly to KiloCode 7.2.x at boot. KiloCode loads every server, every tool definition contributing to context (~40K tokens, ~20% of 200K window). The current `lazy_loader.py` filters servers per intent tag at boot but is static, requires intent classification a priori, and only achieves a 30–50% reduction. It does not scale to the planned 30+ agents.

The Ten Commandments constraint **P9: Scoped Toolsets — no sub-agent sees more than 20 tools simultaneously** is enforced today via per-agent `allowed-tools` filtering in KiloCode prompts. With static MCP loading, this filtering is purely cosmetic: the LLM sees a reduced set, but the cost of every tool definition is still paid by KiloCode's runtime.

We need a **dynamic, server-side, scalable** mechanism for tool discovery and dispatch that:

1. Reduces context cost from ~40K tokens to <2K tokens at startup, regardless of N agents.
2. Makes scaling from 14 to 50+ MCP backends linear in cost (no fan-out per agent).
3. Preserves P9 by enforcing per-agent allowed-tools at proxy runtime, not at KiloCode display.
4. Integrates with ARIA's CredentialManager (rotation, SOPS+age decryption).
5. Remains fully reversible to the LKG baseline (rollback-first per Refoundation v2).

## 2. Decision: option C (FastMCP-native proxy)

After critical review of `docs/analysis/mcp_tool_search_analysis_1.md` (which compared `fussraider/tool-search-tools-mcp` and `rupinder2/mcp-orchestrator`), a third option was identified and selected: **build a thin proxy on FastMCP's native primitives**.

### 2.1 Why option C wins

The two candidates analysed reinvent features that FastMCP 3.2 (already a dependency of ARIA via `aria-memory`) provides natively:

| Capability | Option A (TS) | Option B (Python) | **Option C (FastMCP-native)** |
|---|---|---|---|
| Multi-server proxy | manual | manual + namespacing | `create_proxy(mcpServers)` native |
| Tool search algorithm | fuzzy + vector | BM25 + regex (whoosh dep) | `BM25SearchTransform` / `RegexSearchTransform` native |
| Per-agent visibility | none | partial (3 auth modes) | middleware `on_list_tools` / `on_call_tool` |
| Stack drift | Node 22+ runtime | Python (matches) | **none — already in repo** |
| Maintenance signal | 1★ solo-dev, last push 2026-04-06 | 2★ solo-dev, last push 2026-02-26 (3 mo stale) | PrefectHQ, in active production use |
| Forward-compat with Anthropic Tool Search Tool | no | partial | yes (synthetic tools mirror spec) |

Verified via Context7 (`/prefecthq/fastmcp`):

- `fastmcp.server.create_proxy(config)` accepts `{"mcpServers": {...}}` (same shape as KiloCode's `mcp.json`).
- `BM25SearchTransform` auto-indexes tool name, description, and parameters; rebuilds on tool list change.
- Synthetic tools `search_tools` and `call_tool` are exposed to the client at the standard MCP protocol level — **no client-side support required**. KiloCode 7.2.x sees a normal stdio MCP server with two tools.
- `Middleware.on_list_tools` and `on_call_tool` hooks run inside the standard auth pipeline, so capability checks compose with existing FastMCP guarantees.

### 2.2 Trade-offs

- We give up Option A's TypeScript skills/macros YAML system. ARIA already has a Python skills system in `.aria/kilocode/skills/`; macros at the MCP layer would duplicate it.
- We give up Option B's Redis-backed persistent registry. Not needed — the MCP catalog YAML is the single source of truth and is loaded at startup; runtime state (warm embeddings) is cached on disk under `.aria/runtime/proxy/`.
- We accept that per-agent identity is propagated by convention (`_caller_id` argument injected by agent prompts) rather than by transport-level authentication. This matches ARIA's existing trust model (single-user, P1 isolation).

### 2.3 Rollout strategy

The user has selected rollout **A — total replacement of `lazy_loader.py`**. The proxy becomes the only path; the original direct-MCP `mcp.json` is retained only as an emergency rollback (`bin/aria start --emergency-direct`).

This respects the Stella Polare rollback-first culture: every phase F0–F5 has a documented rollback action with MTTR < 5 minutes.

## 3. Architecture

```
KiloCode 7.2.x (client)
  │
  │  .aria/kilocode/mcp.json — 2 entries:
  │    aria-memory   (direct, hot path for wiki_recall + HITL)
  │    aria-mcp-proxy (this design)
  ▼
aria-mcp-proxy (NEW, FastMCP server, stdio, single process)
  ├── BackendComposite (FastMCP create_proxy)
  │     mcpServers loaded from .aria/config/mcp_catalog.yaml
  │     auto-namespacing: <server>__<tool>
  │     14 backends today; 50+ at scale
  ├── HybridSearchTransform (NEW, extends BM25SearchTransform)
  │     exposes 2 synthetic tools: search_tools, call_tool
  │     hides backend tools from list_tools (still callable)
  │     blends BM25 score with mxbai-embed-large-v1 semantic similarity
  ├── CapabilityMatrixMiddleware (NEW)
  │     consumes _caller_id from arguments
  │     enforces agent_capability_matrix.yaml at on_call_tool
  │     filters at on_list_tools when caller is known
  └── CredentialInjector (NEW)
        SOPS+age unwrap on backend startup
        listens for rotation events from CredentialManager
        graceful backend restart on key change
```

### 3.1 Components

#### 3.1.1 Server — `src/aria/mcp/proxy/server.py` (~150 LOC)

Entry point. Loads catalog, builds backends config, wires transforms and middleware, runs stdio.

```python
import asyncio
from fastmcp import FastMCP
from fastmcp.server import create_proxy
from aria.mcp.proxy.catalog import load_backends_config
from aria.mcp.proxy.transforms.hybrid import HybridSearchTransform
from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware
from aria.agents.coordination.registry import AgentRegistry

def build_proxy() -> FastMCP:
    backends = load_backends_config(".aria/config/mcp_catalog.yaml")
    proxy = create_proxy(backends, name="aria-mcp-proxy")
    proxy.add_transform(HybridSearchTransform())
    proxy.add_middleware(CapabilityMatrixMiddleware(AgentRegistry()))
    return proxy

if __name__ == "__main__":
    asyncio.run(build_proxy().run_async(transport="stdio"))
```

#### 3.1.2 Catalog loader — `src/aria/mcp/proxy/catalog.py` (~80 LOC)

Reads `.aria/config/mcp_catalog.yaml`, filters `lifecycle: enabled`, converts to FastMCP `mcpServers` dict, calls `CredentialInjector` to expand `${VAR}` placeholders.

#### 3.1.3 Search transform — `src/aria/mcp/proxy/transforms/hybrid.py` (~120 LOC)

Subclass `BM25SearchTransform`. Adds semantic layer via LM Studio HTTP endpoint (mxbai-embed-large-v1 model already on disk). Graceful degrade to BM25-only if LM Studio is offline.

Configuration in `.aria/config/proxy.yaml`:

```yaml
search:
  transform: hybrid          # hybrid | bm25 | regex
  blend: 0.6                 # 60% BM25, 40% semantic
  embedding:
    provider: lmstudio
    endpoint: http://127.0.0.1:1234/v1/embeddings
    model: mxbai-embed-large-v1
    dim: 1024
    max_tokens: 512
    timeout_s: 5.0
    fallback: bm25
  cache:
    persist: true
    path: .aria/runtime/proxy/embeddings/
    invalidate_on: catalog_change
```

#### 3.1.4 Capability middleware — `src/aria/mcp/proxy/middleware.py` (~100 LOC)

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError
from aria.agents.coordination.registry import AgentRegistry

class CapabilityMatrixMiddleware(Middleware):
    def __init__(self, registry: AgentRegistry):
        self._registry = registry

    async def on_list_tools(self, ctx: MiddlewareContext, call_next):
        tools = await call_next(ctx)
        caller = self._resolve_caller(ctx)
        if not caller:
            return tools
        allowed = self._registry.get_allowed_tools(caller)
        return [t for t in tools if self._matches(t.name, allowed)]

    async def on_call_tool(self, ctx: MiddlewareContext, call_next):
        args = dict(ctx.message.arguments or {})
        caller = args.pop("_caller_id", None)
        ctx.message.arguments = args  # strip before forward
        if caller and not self._is_allowed(ctx.message.name, caller):
            raise ToolError(f"tool {ctx.message.name} not allowed for {caller}")
        return await call_next(ctx)
```

#### 3.1.5 Credential injector — `src/aria/mcp/proxy/credential.py` (~80 LOC)

Subscribes to `CredentialManager` rotation events. On rotation, restarts the affected backend by closing its `ProxyClient` and triggering a new `create_proxy` mount.

### 3.2 Data flow

End-to-end search-agent flow:

1. User query → KiloCode → conductor agent.
2. Conductor calls `aria-memory/wiki_recall_tool` (direct, not via proxy — hot path).
3. Conductor calls `spawn-subagent` → search-agent.
4. KiloCode connects search-agent to `aria-mcp-proxy` stdio (already warm via systemd).
5. KiloCode `tools/list` → returns 2 synthetic tools (`search_tools`, `call_tool`) plus any tools explicitly marked `always_visible=true`.
6. Search-agent reasons about query intent and calls `search_tools(pattern="academic papers", _caller_id="search-agent")`.
7. `HybridSearchTransform` returns top-K matching backend tools with full schemas.
8. Search-agent calls `call_tool(name="scientific-papers-mcp__search_papers", arguments={...}, _caller_id="search-agent")`.
9. `CapabilityMatrixMiddleware` validates: `scientific-papers-mcp/search_papers` ∈ allowed-tools[search-agent] → ✓.
10. Proxy forwards to the backend stdio process; result passes through unchanged.
11. Search-agent returns to conductor; conductor synthesises final answer.

### 3.3 Caller identity model

KiloCode shares a single MCP session across agent slots, so transport-level identity is not available. Identity is propagated by **convention**: each agent prompt instructs the LLM to include `_caller_id: "<agent-name>"` in every `search_tools` and `call_tool` invocation.

The middleware strips `_caller_id` before forwarding, so backends never see it.

This model is consistent with ARIA's existing trust boundary (single-user, P1 local isolation). Spoofing by an LLM is the same risk class as the LLM ignoring its `allowed-tools` directive today. A future hardening (Phase 2+) can move to MCP HTTP transport with per-agent bearer tokens; this requires KiloCode changes that conflict with P2 (Upstream Invariance) and is therefore out of scope here.

Audit trail: every `call_tool` without a `_caller_id`, or with a mismatch between the declared caller and the requested tool, increments `aria_proxy_caller_missing_total{reason}` and emits a `proxy.caller_anomaly` event.

### 3.4 Embedding model — mxbai-embed-large-v1 (local, existing)

Already present at `~/.lmstudio/models/mixedbread-ai/mxbai-embed-large-v1/mxbai-embed-large-v1-f16.gguf` (639 MB GGUF, BERT 1024-dim, max 512 tokens). LM Studio server is currently running on `127.0.0.1:1234` with an OpenAI-compatible endpoint.

Integration: HTTP via `httpx` (already an ARIA dependency). No new Python dependencies. Model lifecycle managed entirely by LM Studio.

```
POST http://127.0.0.1:1234/v1/embeddings
{
  "model": "mxbai-embed-large-v1",
  "input": ["text1", "text2"]
}
```

Indexing cost: ~15 ms / tool / call. 100 tools × 15 ms = 1.5 s one-shot at proxy boot. Persisted to `.aria/runtime/proxy/embeddings/{tool_namespaced}.npy`. Cold start after first run is ~50 ms (npy load only).

Fallback path: if `127.0.0.1:1234` is unreachable, the transform sets `_semantic_enabled = False` at boot and runs BM25-only. No user-visible failure.

## 4. Error handling

| Failure mode | Behaviour | Recovery / rollback |
|---|---|---|
| Backend MCP crash | Mark backend unhealthy, exclude from search index, log `proxy.backend_quarantine` | Health check every 30 s; auto-recover on next successful initialize |
| Search index corruption | Rebuild on next `tools/list` | Transparent |
| Backend timeout (>30 s) | Raise `ToolError("backend timeout: <server>")` on `call_tool` | Caller (agent) decides retry / fallback |
| Proxy process crash | systemd `Restart=on-failure`, max 3 / minute | KiloCode reconnects stdio automatically |
| Capability deny | `ToolError("tool <name> not allowed for <agent>")` | No retry; counted in `aria_proxy_tool_denied_total` |
| Credential rotation mid-call | Backend restart graceful; in-flight call fails with retryable error | `tenacity` retry × 3 inside CredentialInjector |
| LM Studio embeddings down | Degrade transform to BM25-only at boot or on next failure | Re-probe every 5 min; restore semantic layer when reachable |
| Catastrophic proxy unable to start | `bin/aria start --emergency-direct` restores original `mcp.json` from `baseline-LKG-v1` | MTTR < 2 min |

## 5. Observability

Metrics added to `src/aria/observability/metrics.py`:

- `aria_proxy_search_latency_seconds{agent}` — histogram
- `aria_proxy_tool_call_total{agent, tool, status}` — counter
- `aria_proxy_tool_denied_total{agent, tool, reason}` — counter
- `aria_proxy_backend_health{server}` — gauge (0 / 1)
- `aria_proxy_context_tokens_saved` — gauge (estimated reduction vs LKG baseline)
- `aria_proxy_caller_missing_total{reason}` — counter (audit anomaly)
- `aria_proxy_embedding_index_seconds` — histogram (boot / rebuild)

Typed events added to `src/aria/observability/events.py`:

- `proxy.start`, `proxy.shutdown`
- `proxy.backend_quarantine`, `proxy.backend_recovered`
- `proxy.cutover`, `proxy.emergency_rollback`
- `proxy.caller_anomaly`

## 6. Impact on agents and skills

### 6.1 Agent prompt updates

All four agent prompts (`.aria/kilocode/agents/*.md`) need:

1. `allowed-tools` rewritten with namespaced names (`tavily-mcp__search` instead of `tavily-mcp/search`).
2. `mcp-dependencies` field updated to a single entry: `aria-mcp-proxy` (plus `aria-memory` for direct callers).
3. New addendum (auto-injected by template):

> When invoking `search_tools` or `call_tool` on `aria-mcp-proxy`, ALWAYS include
> `_caller_id: "<this-agent-name>"` in the arguments. The proxy uses this to
> enforce per-agent capabilities. Calls without `_caller_id` fall back to a
> permissive but audited path.

### 6.2 Capability matrix update

`.aria/config/agent_capability_matrix.yaml` keys remain the canonical SoT but tool names change to namespaced form. The `AgentRegistry.get_allowed_tools()` loader handles backwards-compat by accepting both `server/tool` and `server__tool`.

### 6.3 Skills coordination impact

| Skill | Impact |
|---|---|
| `deep-research` | Update tool name references (e.g. `tavily-mcp__search`). Logic unchanged. |
| `planning-with-files` | No change (does not call MCP tools directly). |
| `triage-email` | No change (workspace-agent owns the call). |
| `calendar-orchestration` | No change. |
| `pdf-extract` | Update reference: `markitdown-mcp__convert_to_markdown`. |
| `office-ingest` | Update reference: `markitdown-mcp__convert_to_markdown`. |
| `doc-draft` | No change. |
| `hitl-queue` | No change (uses `aria-memory` direct, not via proxy). |
| `memory-distillation` | No change (direct). |
| `blueprint-keeper` | No change (direct). |
| `consultancy-brief` | Update tool name references. |
| `meeting-prep` | Update tool name references. |
| `email-draft` | No change. |
| `source-dedup` | Update tool name references. |

`aria-memory` and `hitl-queue` both remain on the direct path because they are hot paths invoked every turn by the conductor; routing them through the proxy adds latency that is not justified.

### 6.4 Drift validator

`scripts/check_mcp_drift.py` is updated to validate four cross-references:

1. `mcp_catalog.yaml` ↔ proxy `BackendComposite` mounted servers (single source of truth).
2. `agent_capability_matrix.yaml` ↔ proxy `Middleware` allowed-tool checks (no orphan permissions).
3. Agent prompts `allowed-tools` ↔ matrix entries (no drift).
4. `mcp.json` ↔ {aria-memory, aria-mcp-proxy} only.

## 7. Migration phases

Phases F0–F5 are described in detail in §3 of `docs/plans/mcp_search_tool_plan_1.md` (to be written). Summary:

| Phase | Goal | Duration | Reversible? |
|---|---|---|---|
| F0 | Smoke proxy with 1 backend, validate KiloCode 7.2.x sees 2 synthetic tools | 30 min | Trivially — no commit |
| F1 | Implement core (`src/aria/mcp/proxy/`), unit + integration tests | 4–5 days | git revert |
| F2 | Shadow mode — proxy runs alongside, no production traffic | 2 days | Remove mcp.json entry |
| F3 | Cutover — `mcp.json` reduced to 2 entries, prompts namespaced | 2 days | `git checkout baseline-LKG-v1 -- ...` (<5 min) |
| F4 | Remove `lazy_loader.py`, update catalog metadata, write ADR-0015 | 1 day | git revert |
| F5 | Observability + skill updates, wiki refresh | 1 day | git revert |

Total: ~10 working days, critical path on F1 implementation.

## 8. Testing strategy

### 8.1 Unit tests (`tests/unit/mcp/proxy/`)

| File | Scope | Min count |
|---|---|---|
| `test_proxy_server.py` | `create_proxy` with fixture `mcpServers`, namespacing, lifecycle | 8 |
| `test_capability_middleware.py` | `on_list_tools` filtering, `on_call_tool` deny, `_caller_id` strip | 10 |
| `test_hybrid_search.py` | BM25 score, mocked embed, blend, graceful degrade | 8 |
| `test_credential_inject.py` | SOPS unwrap, rotation event, backend restart | 6 |
| `test_catalog_loader.py` | YAML parse, missing fields, `lifecycle` filter | 6 |

LM Studio mocked via `respx` / `httpx_mock`. Total wall-clock < 5 s.

### 8.2 Integration tests (`tests/integration/mcp/proxy/`)

| File | Scope |
|---|---|
| `test_proxy_e2e_stdio.py` | spawn proxy stdio; `tools/list` returns 2 synthetic; `search_tools(pattern="memory")` finds wiki_recall |
| `test_call_tool_routing.py` | `call_tool(name="filesystem__read", ...)` reaches a real backend fixture |
| `test_capability_enforcement.py` | search-agent caller calls a workspace tool → `ToolError` |
| `test_hybrid_with_real_lms.py` | skip if LM Studio offline; otherwise verify embed roundtrip |
| `test_emergency_rollback.py` | `bin/aria start --emergency-direct` restores original mcp.json |

### 8.3 End-to-end / acceptance (`tests/e2e/mcp/proxy/`)

| File | Scope |
|---|---|
| `test_search_quality.py` | 20 real ARIA queries (search/productivity/memory mix), top-3 hit rate ≥ 85% — **F1 ship gate** |
| `test_full_session_kilocode.py` | KiloCode 7.2.x session: conductor → search-agent via proxy, real query, log final answer |
| `test_context_token_reduction.py` | measure total tool definition tokens at boot: < 2 K (vs ~40 K LKG). **Ship gate ≥ 80% reduction** |

### 8.4 Performance gates (block ship if exceeded)

- Cold start proxy > 3 s
- `search_tools` p95 latency > 200 ms
- `call_tool` overhead vs direct MCP > 50 ms
- Proxy memory > 200 MB with 100 indexed tools

### 8.5 Coverage

`src/aria/mcp/proxy/*` ≥ 85% (existing ARIA gate via `make quality`).

## 9. Security and safety

- All backends are subprocess MCP servers, isolated by Linux user (P1).
- Credentials injected only at backend startup, never logged.
- `_caller_id` is a soft authentication; trust boundary remains the single-user owner of the workstation. This is documented in ADR-0015.
- The proxy never exposes a network listener — stdio only. This preserves P4 (Local-First, Privacy-First).
- HITL triggers from `agent_capability_matrix.yaml` (`destructive`, `costly`, `oauth_consent`) remain in effect; the middleware refuses any tool flagged HITL when `_caller_id` is missing.
- Backend health checks do not call any backend tool; they invoke `initialize` only, so no side effects.

## 10. Open questions

These do not block the spec but should be resolved during F1 implementation:

1. **HTTP transport upgrade** for per-agent bearer-token authentication — deferred unless KiloCode upstream adopts it without breaking P2.
2. **Embedding cache invalidation policy** — currently catalog-hash-based. Should we also invalidate on FastMCP version change?
3. **Search index size budget** — at 100 tools the BM25 index is small; at 500+ tools we may need a background refresh rather than synchronous rebuild. Re-evaluate at F5 metrics review.
4. **Proxy as systemd vs on-demand stdio** — current default is on-demand spawn by KiloCode (matches all other MCP servers in `mcp.json`). systemd `aria-mcp-proxy.service` is optional for warm-start performance.

## 11. Acceptance criteria

The design is implemented when all the following are true:

- [ ] `src/aria/mcp/proxy/` package exists with the four components in §3.1.
- [ ] `.aria/kilocode/mcp.json` has exactly two entries: `aria-memory` and `aria-mcp-proxy`.
- [ ] `src/aria/launcher/lazy_loader.py` is removed; `mcp_catalog.yaml` no longer carries `lazy_load` / `intent_tags`.
- [ ] All four agent prompts and the capability matrix use namespaced tool names; the matrix loader accepts both legacy and namespaced forms during the transition.
- [ ] `make quality` is green: ruff, format, mypy, pytest including the new unit / integration / e2e suites.
- [ ] Token reduction measured: tool definitions visible to KiloCode at boot < 2 K tokens (vs ~40 K LKG baseline) — ≥ 80% reduction.
- [ ] Search quality gate: ≥ 85% top-3 hit rate on the 20 reference queries.
- [ ] Performance gates respected (§8.4).
- [ ] ADR-0015 written: "FastMCP-native MCP proxy replaces static lazy loader".
- [ ] Wiki updated: `mcp-architecture.md`, `mcp-refoundation.md`, new `mcp-proxy.md` page; index and log entries.
- [ ] Rollback drill rehearsed: `bin/aria start --emergency-direct` restores baseline-LKG-v1 in < 2 min.

---

*End of design document. Review feedback expected before writing the implementation plan at `docs/plans/mcp_search_tool_plan_1.md`.*
