# MCP Architecture

**Last Updated**: 2026-04-29  
**Status**: Active — rollback-first refoundation direction documented in v2  
**Primary sources**: `.aria/kilocode/mcp.json`, `docs/plans/gestione_mcp_refoundation_plan.md`, `docs/plans/gestione_mcp_refoundation_plan_v2.md`, `docs/analysis/analisi_sostenibilita_mcp_report.md`

## Current state

ARIA currently uses a predominantly flat MCP registry defined in `.aria/kilocode/mcp.json` and mirrored into the isolated runtime under `.aria/kilo-home/.kilo/` by `bin/aria`.

### Inventory observed on 2026-04-29
- Configured servers: 16
- Enabled servers: 15
- Domains present: core, search, workspace, productivity, experimental

### Structural properties
- Core orchestration remains delegated: conductor does not directly use search/workspace tools.
- Tool access is scoped via `allowed-tools` and `mcp-dependencies`.
- Runtime still depends on per-server stdio/wrapper processes.
- No canonical MCP catalog, no schema registry, and no gateway layer are currently active.

## Key issues

1. **Inventory drift**: sustainability analysis references 12 servers, live config has 16.
2. **Exposure drift**: some configured search servers are not consistently exposed in `search-agent` declarations.
3. **Config duplication**: source config and isolated runtime copy can drift.
4. **Flat governance**: no explicit domain/tier/lifecycle metadata in config.
5. **No schema snapshots**: `tools/list` drift is not tracked.

## Recommended direction

The working direction is now split across:

- `docs/plans/gestione_mcp_refoundation_plan.md` — governance/scaling v1
- `docs/plans/gestione_mcp_refoundation_plan_v2.md` — rollback-first hardening and cutover discipline

The recommended order is:

1. baseline authority;
2. rollback invariants;
3. drift elimination;
4. measured optimization;
5. selective gatewaying.

### Baseline / candidate / fallback path
- **Baseline**: the current direct MCP path is treated as last-known-good and must remain runnable.
- **Candidate**: new catalog-driven, lazy, or gateway-based paths can be enabled only behind explicit gates.
- **Fallback path**: any new path must preserve direct bypass to the existing provider/tool chain.

### Immediate priorities
- Freeze the current architecture as explicit LKG baseline.
- Introduce a canonical MCP catalog.
- Align config, prompts, agent exposure, and wiki.
- Add drift checks and schema snapshots.
- Measure startup/context/process baselines before adopting lazy loading or a gateway.
- Keep rollback in the config plane; avoid state migrations in `.aria/runtime` and `.aria/credentials`.

### Deferred priorities
- Tool search / lazy loading, only after capability probe and metadata cleanup.
- Search-domain gateway PoC, only if metrics justify it and bypass remains hard-wired.
- Code execution pattern, deferred to later ADR/R&D.

## Provenance
- Source: `.aria/kilocode/mcp.json` (read 2026-04-29)
- Source: `docs/plans/gestione_mcp_refoundation_plan.md` (created 2026-04-29)
- Source: `docs/plans/gestione_mcp_refoundation_plan_v2.md` (created 2026-04-29)
- Source: `docs/analysis/analisi_sostenibilita_mcp_report.md` (updated 2026-04-29)
- Source: Context7 `/metatool-ai/metamcp`, `/lastmile-ai/mcp-agent`, `/modelcontextprotocol/modelcontextprotocol` (queried 2026-04-29)
- Source: Anthropic Engineering and Cloudflare enterprise MCP articles (queried 2026-04-29)
