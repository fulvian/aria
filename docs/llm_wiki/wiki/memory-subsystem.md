# Memory Subsystem — Architecture, Gaps, and Tools

**Last Updated**: 2026-04-24
**Status**: OPERATIONAL — All 7 gaps closed
**Source**: `src/aria/memory/`, `docs/analysis/memory_subsystem_health_check_2026-04-24.md`

---

## Architecture Overview

The memory subsystem implements the 5D memory model per blueprint §5:

| Tier | Name | Storage | Purpose |
|------|------|---------|---------|
| T0 | Episodic | SQLite WAL (`episodic.db`) | Raw verbatim events |
| T1 | Semantic | SQLite FTS5 | Distilled facts, preferences, decisions |
| T2 | Conceptual | LanceDB (lazy) | Semantic embeddings |
| T3 | Associative | SQLite graph | Entity relationships (Fase 2) |
| T4 | Procedural | Filesystem SKILL.md | Workflows and procedures |

## Components

### EpisodicStore (`src/aria/memory/episodic.py`)
- **Role**: Tier 0 episodic memory with WAL mode and FTS5 full-text search
- **Key Methods**:
  - `insert(entry)` — Insert single episodic entry (P6: no UPDATE on content)
  - `insert_many(entries)` — Batch insert
  - `search_text(query, top_k)` — FTS5 full-text search
  - `get(entry_id)` — Retrieve by ID (excludes tombstoned)
  - `tombstone(entry_id, reason)` — Soft delete (P6 compliant)
  - `enqueue_hitl(...)` — Enqueue HITL request for approval
  - `list_hitl_pending(limit)` — List pending HITL requests
  - `vacuum_wal()` — Checkpoint WAL and VACUUM
  - `prune_old_entries(retention_days)` — Tombstone entries older than retention (new)
  - `stats()` — Return MemoryStats with counts

### SemanticStore (`src/aria/memory/semantic.py`)
- **Role**: Tier 1 semantic chunks with FTS5
- **Key Methods**:
  - `insert_chunk(chunk)` — Insert semantic chunk
  - `search(query, top_k)` — Search semantic chunks
  - `delete(chunk_id)` — Delete chunk

### CLM — Context Lifecycle Manager (`src/aria/memory/clm.py`)
- **Role**: Distills T0 episodic entries into T1 semantic chunks
- **Trigger**: Post-session via ConductorBridge hook, every 6h via scheduler
- **Key Methods**:
  - `distill_session(session_id)` — Distill all entries for a session
  - `distill_range(since, until)` — Distill entries in time range

### MCP Server (`src/aria/memory/mcp_server.py`)
- **Role**: FastMCP server exposing memory tools (11 tools total)
- **Tools**:
  1. `remember` — Write T0 episodic entry
  2. `recall` — Search semantic + episodic
  3. `recall_episodic` — Cronological episodic retrieval
  4. `distill` — Trigger CLM distillation on-demand
  5. `curate` — Promote/demote/forget with HITL
  6. `forget` — Soft delete + tombstone
  7. `stats` — Telemetry
  8. `hitl_list` — List pending HITL requests
  9. `hitl_cancel` — Cancel a pending HITL request
  10. `hitl_approve` — Approve and execute a pending HITL action (NEW — P7)
  11. `health` — Checkpoint FTS5 and return stats

## Gap Remediation Status

| Gap | Before | After | Evidence |
|-----|--------|-------|----------|
| CLM mai eseguito | ❌ CRITICO — 1005 T0 entries, 0 T1 chunks | ✅ post-session hook + 6h cron | ConductorBridge._distill_session_bg() + memory-distill task |
| HITL approval path inesistente | ❌ CRITICO — forget enqueued but never executed | ✅ hitl_approve tool | mcp_server.py:529 + test_mcp_server.py |
| Retention T0/T1 non applicata | ❌ CRITICO — 365gg config ignored | ✅ prune_old_entries() + Reaper | episodic.py:484 + reaper.py:69 |
| WAL episodic.db non checkpointato | ⚠️ MANCANTE — WAL grows unbounded | ✅ Reaper + memory-wal-checkpoint task | reaper.py:64 + scheduler daemon |
| Integration tests assenti | ⚠️ MANCANTE — 0 integration tests | ✅ 9 integration tests | tests/integration/memory/ (3 files) |
| Backup non schedulato | ⚠️ MANCANTE — scripts/backup.sh manual | ✅ aria-backup.timer | systemd/aria-backup.* |
| T1 compression 90gg | ⚠️ DEFERRED | ⚠️ DEFERRED | T1 now populated; re-evaluate after 30 days |

## CLM Trigger Paths

### Path 1: Post-Session (immediate)
```
User message → ConductorBridge.handle_user_message() 
→ _spawn_conductor() → response stored in episodic 
→ _distill_session_bg() [asyncio.create_task]
→ CLM.distill_session() → semantic chunks
```

### Path 2: Scheduler Cron (every 6h)
```
SchedulerDaemon._seed_memory_tasks() → creates memory-distill task
→ TaskRunner._exec_memory_task() [category="memory", action="distill_range"]
→ CLM.distill_range(since, until)
```

## Retention Policy

- **T0 (episodic)**: Default 365 days, configurable via `config.memory.t0_retention_days`
- **T1 (semantic)**: Indefinite, compressed after 90 days (DEFERRED)
- **Pruning**: `prune_old_entries()` tombstones old T0 entries (never hard delete — P6)
- **Reaper**: Runs every 6h, calls `vacuum_wal()` + `prune_old_entries()`

## HITL Flow

```
1. User calls forget(id) or curate(id, action="forget")
2. MCP server enqueues HITL request (status="pending")
3. HITL pending appears in hitl_list
4. Human approves via hitl_approve(hitl_id)
5. hitl_approve executes the action (tombstone entry or delete chunk)
6. HITL record marked status="approved"
```

## Database Schema

### episodic table
```sql
CREATE TABLE episodic (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,  -- Unix timestamp
    actor TEXT NOT NULL,   -- user_input|tool_output|agent_inference|system_event
    role TEXT NOT NULL,    -- user|assistant|system|tool
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    tags TEXT,             -- JSON array
    meta TEXT              -- JSON dict
);
```

### episodic_tombstones table
```sql
CREATE TABLE episodic_tombstones (
    episodic_id TEXT PRIMARY KEY,
    tombstoned_at INTEGER NOT NULL,
    reason TEXT NOT NULL
);
```

### semantic_chunks table
```sql
CREATE TABLE semantic_chunks (
    id TEXT PRIMARY KEY,
    source_episodic_ids TEXT NOT NULL,  -- JSON array of UUIDs
    actor TEXT NOT NULL,
    kind TEXT NOT NULL,  -- fact|preference|decision|action_item|concept
    text TEXT NOT NULL,
    keywords TEXT,       -- JSON array
    confidence REAL NOT NULL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    occurrences INTEGER NOT NULL DEFAULT 1
);
```

### memory_hitl_pending table
```sql
CREATE TABLE memory_hitl_pending (
    id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- forget_episodic|forget_semantic|approve_task
    reason TEXT NOT NULL,
    trace_id TEXT,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    resolved_at INTEGER
);
```

## Quality Gates

All memory subsystem code passes:
- `ruff check src/aria/memory/` — PASS
- `ruff format --check src/aria/memory/` — PASS
- `mypy src/aria/memory/` — PASS
- `pytest tests/unit/memory/ tests/integration/memory/ -q` — 40 tests PASS

## Files

| File | Purpose |
|------|---------|
| `src/aria/memory/episodic.py` | EpisodicStore (T0) with WAL, FTS5, tombstone, HITL |
| `src/aria/memory/semantic.py` | SemanticStore (T1) with FTS5 |
| `src/aria/memory/clm.py` | Context Lifecycle Manager (distillation) |
| `src/aria/memory/mcp_server.py` | FastMCP server (11 tools) |
| `src/aria/memory/schema.py` | Pydantic models (EpisodicEntry, SemanticChunk, Actor) |
| `src/aria/memory/migrations.py` | Schema migrations |
| `src/aria/memory/actor_tagging.py` | Actor trust scores |
| `src/aria/scheduler/reaper.py` | Background maintenance (WAL checkpoint + retention) |
| `src/aria/scheduler/runner.py` | Task execution (category="memory" handler) |
| `src/aria/scheduler/store.py` | TaskStore with HITL pending table |