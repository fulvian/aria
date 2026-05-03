# ADR-0017: Traveller-Agent — Travel Domain Sub-Agent Introduction

**Status**: Implemented (F1-F7)
**Date**: 2026-05-03
**Authors**: fulvio
**Related**: ADR-0018 (aria-amadeus-mcp), ADR-0015 (proxy), ADR-0012 (cutover/rollback)

## Context

ARIA requires domain-specific sub-agents for specialized tasks. The existing
`search-agent` (general research), `productivity-agent` (office domain), and
`trader-agent` (finance domain) each cover distinct domains. Travel planning
— encompassing destination research, transport, accommodation, activities,
itineraries, and budget — was an uncovered domain.

Initial analysis considered three approaches:

1. **Extend `search-agent`** with travel intent. Rejected: search-agent lacks
   travel semantics (dates, geocoding, multi-OTA comparison, waypoint
   optimization, accommodation-specific tools).
2. **Create a skill only**. Rejected: a skill cannot bring its own capability
   scope, HITL triggers, or intent categories. The travel domain is large and
   autonomous enough to justify a full sub-agent.
3. **Create a new sub-agent**. Selected: `traveller-agent` (domain-primary,
   category: `travel`).

### LangGraph evaluation

The preliminary research recommended a LangGraph hub-and-spoke architecture
(Ctrip pattern). This was **explicitly rejected** during design because:

- ARIA already has a hub-and-spoke pattern (conductor → spawn-subagent →
  sub-agent → skill → proxy → MCP backend). Adding LangGraph creates a
  parallel orchestration runtime (architectural drift).
- ARIA HITL is `hitl-queue__ask` (real audit gate, persistent). LangGraph
  `interrupt()` is a runtime mechanism that doesn't integrate with the
  gateway/scheduler.
- Capability enforcement is via proxy + `_caller_id`, not in-process state
  graphs.

## Decision

Introduce `traveller-agent` as a new domain-primary sub-agent (type: subagent,
category: travel) following the canonical ARIA pattern established by
`trader-agent`:

- **Prompt**: `.aria/kilocode/agents/traveller-agent.md` (modelled on trader-agent)
- **Capability matrix**: entry in `.aria/config/agent_capability_matrix.yaml`
- **Conductor dispatch**: routing rules with 30+ Italian travel keywords,
  7 intent categories, explicit guard against routing travel to search-agent
- **Backend MCP**: 4 servers registered in `.aria/config/mcp_catalog.yaml`
  (airbnb, osm-mcp, aria-amadeus-mcp, booking)
- **Skills**: 6 skill files in `.aria/kilocode/skills/` (destination-research,
  accommodation-comparison, transport-planning, activity-planning,
  itinerary-building, budget-analysis)
- **Delegation**: traveller-agent → productivity-agent (export),
  traveller-agent → search-agent (context, max depth 1)
- **HITL**: all external writes via `hitl-queue__ask` (delegated to
  productivity-agent)
- **No LangGraph runtime**: pure ARIA-native orchestration

## Rationale

1. **Domain autonomy**: Travel planning is a self-contained domain with
   distinct semantics (dates, addresses, geocoding, multi-OTA comparison).
   No existing agent covers it.
2. **Pattern consistency**: Follows the exact same architecture as
   trader-agent (capability matrix, proxy canonical, conductor dispatch).
3. **No new infrastructure**: Uses existing ARIA primitives (spawn-subagent,
   hitl-queue__ask, aria-memory, aria-mcp-proxy). No new runtimes.
4. **HITL safety**: Write operations (Drive/Calendar/email) are delegated
   to productivity-agent which enforces HITL via hitl-queue__ask.
   Booking write operations are out-of-scope in MVP.

## Consequences

### Positive

- Clean separation of travel domain from general search/office/finance
- 124+ unit/integration tests covering prompt, capability matrix, conductor
  dispatch, catalog, MCP server, skills, anti-drift
- All 6 travel skills are documented and independently testable
- Cost circuit breaker for Amadeus free tier (2K/month)

### Negative

- 4 new backend MCP servers to maintain (airbnb, osm-mcp, aria-amadeus-mcp,
  booking)
- Booking MCP is gated (lifecycle: shadow) due to Playwright fragility
- No live booking capability in MVP (future ADR required)

### Mitigations

- osm-mcp replaces Google Maps (rejected due to billing requirements)
- aria-amadeus-mcp has quota monitoring + auto-quarantine
- booking is lifecycle: shadow until stability verified
- All backends support degraded mode (single backend failure doesn't
  block the entire agent)

## Implementation

Implementation in 7 phases on branch `feature/traveller-agent-f1`:

| Phase | Scope | Commit |
|-------|-------|--------|
| F1 | Foundation (prompt + matrix + conductor) | `e9eac37` |
| F2 | Backend MCP catalog | `d462ff9` |
| F3 | aria-amadeus-mcp FastMCP server | `a8f8d07` |
| F4 | Skill core (3 skill) | `7a65b09` |
| F5 | Skill complementari + booking gated | `4d1857c` |
| F6 | Export handoff chain | `33dfb8a` |
| F7 | Observability + anti-drift | `9301a40` |

Total: 7 commits, 24 files, ~2200 lines added.

## References

- `docs/plans/agents/traveller_agent_plan.md` — foundation plan
- `.aria/kilocode/agents/traveller-agent.md` — canonical prompt
- `.aria/config/agent_capability_matrix.yaml` — capability matrix
- `.aria/kilocode/agents/aria-conductor.md` — conductor dispatch
- `.aria/config/mcp_catalog.yaml` — backend catalog
- `src/aria/tools/amadeus/mcp_server.py` — FastMCP server
- `src/aria/observability/events.py` — traveller event types
