---
adr: ADR-0005
title: Memory v3 Cutover — Deprecate Legacy Persistence Tools
status: accepted
date_created: 2026-04-27
date_accepted: 2026-04-27
author: ARIA Chief Architect
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0005: Memory v3 Cutover — Deprecate Legacy Persistence Tools

## Status

**Accepted** — 2026-04-27

## Context

ARIA Memory v3 (Phases A–C) replaced the legacy persistence stack with a wiki-based
knowledge system:

| Legacy Tool | Replacement | Phase |
|-------------|-------------|-------|
| `remember` | `wiki_update` | A |
| `complete_turn` | `wiki_update` (end-of-turn) | A |
| `recall` | `wiki_recall` (FTS5) | A |
| `recall_episodic` | `wiki_recall` (FTS5) | A |
| `distill` | `wiki_update` (end-of-turn reflection) | A |
| `curate` | `wiki_update` + HITL tools | A |

The wiki module has been running alongside the legacy tools since Phase A
(belt+suspenders). With 315 unit tests passing and all quality gates green,
the legacy tools are now redundant.

Per blueprint P10 (Self-Documenting Evolution), Phase D requires an ADR
documenting the deprecation before removal.

## Decision

### Tools Removed (6)

1. `remember` — episodic T0 write (replaced by `wiki_update`)
2. `complete_turn` — turn-finalizer (replaced by `wiki_update` end-of-turn)
3. `recall` — semantic/T0 search (replaced by `wiki_recall`)
4. `recall_episodic` — chronological recall (replaced by `wiki_recall`)
5. `distill` — CLM distillation trigger (replaced by conductor end-of-turn reflection)
6. `curate` — HITL-gated promote/demote/forget (replaced by `wiki_update` + HITL tools)

### Tools Retained (4)

1. `forget` — HITL-gated soft delete (bridge to wiki tombstone in Phase E)
2. `stats` — memory telemetry (extended to include wiki stats)
3. `hitl_ask` — queue HITL approval
4. `hitl_list_pending` — list pending approvals
5. `hitl_cancel` — cancel pending request
6. `hitl_approve` — approve and execute

### Wiki Tools (4)

1. `wiki_update` — end-of-turn structured patch
2. `wiki_recall` — FTS5 search
3. `wiki_show` — get page by kind+slug
4. `wiki_list` — list pages by kind

### Net MCP Tool Count: 10

(4 wiki + 2 legacy bridge + 4 HITL)

### Modules Frozen (Not Deleted)

- `src/aria/memory/episodic.py` — frozen, kept for forensic read
- `src/aria/memory/semantic.py` — frozen, kept for forensic read
- `src/aria/memory/clm.py` — frozen, kept for forensic read

Phase E will hard-delete these after 30 days of stable wiki-only operation.

### Scheduler Changes

- `memory-distill` cron seed removed (CLM is frozen)
- `memory-wal-checkpoint` retained (still needed for episodic.db)
- `memory-watchdog` retained (wiki gap detection)

## Consequences

### Positive

- Simpler MCP surface (11 → 10 tools)
- Single persistence path (wiki.db) instead of dual-write
- No more CLM regex distillation (conductor LLM does reflection)
- Reduced cognitive load for conductor agent

### Negative

- Existing episodic.db data not automatically migrated to wiki.db
- Forensic access to episodic data requires frozen modules
- `forget` tool still uses episodic HITL queue (Phase E will migrate)

### Migration Path

No data migration required. wiki.db has been accumulating data since Phase A.
The legacy stores remain readable via frozen modules.

## Rollback Plan

1. Revert `mcp_server.py` — restore 6 removed tool registrations
2. Revert conductor template — restore old tool instructions
3. Revert scheduler `daemon.py` — restore `memory-distill` seed
4. Legacy modules remain in tree (frozen, not deleted)

Rollback is low-risk because no data is destroyed — only tool registrations
are removed from the MCP surface.

## Timeline

- **2026-04-27**: Phase D — deprecation (this ADR)
- **2026-05-27**: Phase E — hard delete frozen modules (after 30 days stable)
