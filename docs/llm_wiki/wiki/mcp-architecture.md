# MCP Architecture

**Last Updated**: 2026-05-03T18:35+02:00  
**Status**: Active ✅ — proxy-native architecture is now the runtime baseline  
**Primary sources**: `.aria/kilocode/mcp.json`, `.aria/config/mcp_catalog.yaml`, `.aria/config/agent_capability_matrix.yaml`, `src/aria/mcp/proxy/`, `docs/foundation/aria_foundation_blueprint.md`, `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`

## Current state

ARIA no longer runs a flat many-server MCP runtime inside KiloCode. The active
runtime baseline is now:

- `aria-memory` as a dedicated MCP server
- `aria-mcp-proxy` as the single MCP aggregation/search/execution surface for the
  rest of the tool ecosystem

### Inventory observed on 2026-05-03
- Runtime entries in `.aria/kilocode/mcp.json`: **2**
- Catalog-governed backend inventory: **16 servers** (14 pre-esistenti + context7 + github-discovery credentials cablati)
- Live architectural split:
  - **out of proxy**: `aria-memory`
  - **behind proxy**: search, productivity, system, finance, **development-research** backends from the catalog
  - **HTTP backends with headers**: `context7` (new v7.3), `helium-mcp` (pre-existing, now with proper transport support)

## Structural properties

- Core orchestration remains delegated: conductor still does not directly use
  search/workspace/productivity operational tools.
- Tool access is now governed in two layers:
  1. prompt/frontmatter baseline exposure
  2. proxy runtime enforcement via capability matrix + `_caller_id`
- Runtime still depends on stdio/wrapper processes for backend servers, but Kilo
  itself now sees a compressed MCP surface.
- MCP governance is now catalog-driven and policy-aware.

## What changed from the refoundation era

### Before
- Flat MCP exposure with many server entries visible to KiloCode
- Tool ownership effectively coupled to agent boundaries
- Greater prompt drift risk because backend tool names leaked into prompts/skills

### After
- Proxy-native surface with synthetic `search_tools` / `call_tool`
- Capability matrix decides which backend operations each agent may reach
- Agent boundaries can now be driven by workflow/domain cohesion rather than hard
  MCP exclusivity

## Architecture snapshot

```text
KiloCode
 ├─ aria-memory            (direct MCP dependency)
 └─ aria-mcp-proxy         (synthetic surface)
      ├─ search_tools
      └─ call_tool
           ├─ search: searxng, tavily, exa, brave, reddit-search, scientific-papers-mcp, fetch
           ├─ development: context7 (HTTP + headers), github-discovery (stdio + env)
           ├─ finance: financekit-mcp, mcp-fredapi, alpaca-mcp, helium-mcp (HTTP)
           ├─ productivity: google_workspace, markitdown-mcp
           └─ system: filesystem, sequential-thinking
```

## Governance model

### Prompt/frontmatter layer
- `search-agent` and `productivity-agent` expose only:
  - `aria-mcp-proxy__search_tools`
  - `aria-mcp-proxy__call_tool`
  - direct non-proxy tools they truly need (memory, sequential-thinking, spawn)
- `workspace-agent` follows the same contract but is transitional.

### Policy layer
- `.aria/config/agent_capability_matrix.yaml` is the effective source of truth for
  which backend families an agent can call.
- `productivity-agent` now includes `google_workspace__*`.
- `search-agent` includes search-domain providers plus `development`-oriented backends:
  - `github-discovery__*` (repo analysis)
  - `context7__*` (docs lookup)
- `trader-agent` includes finance backends (`financekit-mcp__*`, `mcp-fredapi__*`, `alpaca-mcp__*`, `helium-mcp__*`).

### Enforcement layer
- Missing caller identity on non-synthetic proxy calls is denied.
- Backend boot filtering may narrow loaded servers when `ARIA_CALLER_ID` is set.
- Legacy and runtime naming forms are normalized by middleware/registry helpers.

## Architectural consequence for agent boundaries

The architecture no longer assumes “one MCP belongs to one agent.” Instead:

- shared MCP access is allowed when domains are adjacent,
- active capabilities remain scoped per task/session,
- least privilege, HITL, and auditability remain mandatory.

This is the control-plane change that allowed convergence of Google Workspace
operations into `productivity-agent` while keeping `search-agent` separate.

## Known residual edges

1. `workspace-agent` still exists as compatibility-only prompt surface.
2. `ARIA_CALLER_ID` is still relevant for boot-time filtering, while `_caller_id`
   is the primary per-request enforcement mechanism.
3. Some historical wiki pages still describe pre-proxy or pre-convergence states
   and should be read through the lens of `mcp-proxy.md` and this page.

## Provenance

- Source: `.aria/kilocode/mcp.json` (read 2026-05-01)
- Source: `.aria/config/mcp_catalog.yaml` (read 2026-05-03 — 16 servers, context7 + github-discovery)
- Source: `.aria/config/agent_capability_matrix.yaml` (read 2026-05-03 — +development intent)
- Source: `src/aria/mcp/proxy/` (read 2026-05-03 — headers support in catalog/credential)
- Source: `docs/foundation/aria_foundation_blueprint.md` (updated 2026-05-01)
- Source: ADR-0015 + ADR-0008 amendment (read 2026-05-01)
- Source: ADR-0016 (read 2026-05-03 — proxy HTTP headers + code-discovery)
