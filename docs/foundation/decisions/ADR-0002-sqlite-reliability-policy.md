---
adr: ADR-0002
title: SQLite Reliability Policy
status: accepted
date_created: 2026-04-20
date_accepted: 2026-04-20
author: ARIA Chief Architect
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0002: SQLite Reliability Policy

## Status

**Accepted** — 2026-04-20

## Context

ARIA uses SQLite as the primary database for:
- Episodic memory (`memory/episodic.db`)
- Scheduler task tracking (`scheduler/scheduler.db`)
- Gateway session mapping (`gateway/sessions.db`)

SQLite's WAL (Write-Ahead Logging) mode provides concurrency but has a known bug in versions < 3.51.3 that can cause WAL reset on specific crash scenarios.

## Decision

### Required SQLite Version
- **Minimum**: SQLite >= 3.51.3
- **Rationale**: Mitigates WAL-reset bug (https://sqlite.org/releaselog/3_51_3.html)

### Required PRAGMA Settings
All ARIA SQLite databases MUST be initialized with:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
```

### FTS5 Requirement
- Full-Text Search (FTS5) MUST be compiled into SQLite
- Used by episodic memory for efficient search
- Bootstrap validates: `sqlite3 --version` reports >= 3.51.3 AND FTS5 available

### Backup Policy
- SQLite databases are backed up via `scripts/backup.sh`
- Backups include WAL checkpoint before copy: `PRAGMA wal_checkpoint(TRUNCATE)`
- Backup retention: 7 daily, 4 weekly

## Implementation Notes

- SQLite built from source with: `CFLAGS="-DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_JSON1"`
- Schema: `docs/foundation/schemas/sqlite_full.sql`
- Smoke test: `scripts/smoke_db.sh` validates all PRAGMA settings

## Consequences

1. **Bootstrap must verify SQLite version** before starting any service
2. **Target systems without SQLite 3.51.3** require custom build
3. **WAL mode** provides concurrent read access but requires careful checkpointing

---

## References

- Blueprint §5 (Memory 5D) — episodic store requirements
- Blueprint §6 (Scheduler) — task/run tracking
- Blueprint §7 (Gateway) — session mapping
- SQLite WAL docs: https://sqlite.org/wal.html
- SQLite release 3.51.3: https://sqlite.org/releaselog/3_51_3.html
