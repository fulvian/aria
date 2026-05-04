# ADR-0019: MCP Proxy Tier-based Architecture

**Status**: Accepted
**Date**: 2026-05-04
**Deciders**: Opus 4.7, User
**Tags**: proxy, tier, mcp, architecture, performance, reliability

## Context

The `TimeoutProxyProvider` (`src/aria/mcp/proxy/provider.py`) created a single
`ProxyClient` configured with `MCPConfig` multi-server containing 16 backends.
On `tools/list`, FastMCP executed `async with client:` opening all stdio sessions
in parallel. Slow backends (npx/uvx cold start, OAuth handshake) blocked the
entire operation. `asyncio.wait_for(20s)` did not guarantee a real constraint
because cancellation propagated through `__aexit__` which ran
`_terminate_process_tree` with a grace period on subprocesses.

Consequences:
- `tools/list` hung for tens of seconds.
- Dead backends rendered the entire proxy unusable.
- Upstream quota/rate-limiting could saturate under concurrent calls.
- No automatic recovery: a backend down at boot stayed down until manual restart.

## Decision

Replace `TimeoutProxyProvider` with a tier-based architecture that distinguishes
**warm** (always-on) vs **lazy** (on-demand) backends:

| Component | Responsibility |
|---|---|
| `TieredProxyProvider` | FastMCP Provider orchestrator — aggregates warm live tools + lazy cache |
| `BackendClient` | Mono-server wrapper around `fastmcp.Client` (1 stdio process per instance) |
| `WarmPool` | Always-on connections with healthcheck (30s interval) |
| `LazyRegistry` | On-demand spawn with idle TTL sweep (default 300s) |
| `Breaker` | Per-backend circuit breaker state machine |
| `ConcurrencyRegistry` | Per-backend `asyncio.Semaphore` with acquire timeout |
| `MetadataCache` | Persistent JSON tool cache on disk (atomic writes) |
| `RetryQueue` | Background retry with exponential backoff (max 10 attempts) |

Classification: 6 warm backends (high-frequency: filesystem, sequential-thinking,
aria-memory, fetch, searxng-script, reddit-search) + 12 lazy (quota-sensitive/paid:
brave-mcp, tavily-mcp, google_workspace, etc.)

## Alternatives Considered

1. **Lazy-only** — all backends on-demand, no warm pool. Pros: simpler. Cons: high
   latency for frequently-used backends, no healthcheck for system tools.

2. **Per-backend Provider** — one FastMCP Provider per backend. Pros: clean isolation.
   Cons: violates P2 (requires upstream FastMCP changes), complex wiring.

3. **Status quo** — keep `TimeoutProxyProvider` with minor fixes. Pros: minimal change.
   Cons: does not solve the fundamental architectural weakness (single multi-server client,
   no recovery, no backpressure).

## Consequences

### Positive
- `tools/list` cold < 1.5s (never opens stdio during request — warm pool live + metadata cache)
- `tools/list` warm < 300ms
- Backend down at boot does not block proxy start (auto-recovery via retry queue)
- Lazy backends incur cold start only on first use (idle TTL keeps warm between uses)
- Circuit breaker provides fail-fast on systemic errors (downstream outages degrade gracefully)
- Concurrency semaphore prevents resource exhaustion
- Metadata cache persists across proxy restarts
- 14 new typed events + 7 new Prometheus metrics for observability

### Negative
- More complex architecture (8 new modules vs 1 previous)
- Cold start for lazy backends can be up to 15s (documented in wiki)
- Metadata cache coordination requires catalog_hash tracking

### Compliance
- ✅ P2 (Upstream Invariance): no fork of FastMCP — pure subclassing/composition
- ✅ P8 (Tool Priority Ladder): maintains proxy architecture
- ✅ Backward compatible: synthetic tool schemas (`search_tools`, `call_tool`) unchanged
- ✅ `_caller_id` enforcement middleware unchanged

## Implementation

- **Branch**: `fix/proxy-tier-architecture`
- **Plan**: `docs/plans/ripristino_mcp-proxy_plan.md`
- **Quality gate**: ruff 0, mypy 0, 80 proxy tests PASS
- **Rollback**: `git revert` of merge commit

## References

- `docs/plans/ripristino_mcp-proxy_plan.md` — full implementation plan
- `docs/llm_wiki/wiki/mcp-proxy.md` — wiki with tier architecture section
- `docs/handoff/regressione_mcp-proxy_handoff.md` — original regression handoff
- `src/aria/mcp/proxy/tier/` — implementation modules
