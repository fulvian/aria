# ARIA Memory v3 — Kilo+Wiki Fusion

**Status:** DRAFT v3 — pending user approval
**Date:** 2026-04-27
**Branch:** `fix/memory-recovery`
**Filename note:** kept `auto_persistence_echo.md` for continuity; "Echo" sidecar concept dropped in v3. Suggested rename at merge: `memory_v3_kilo_wiki.md`.
**Supersedes:** v1 Echo-only plan, v2 Echo+Salience+Ollama plan.
**Inputs:** `docs/handoff/auto_memory_handoff.md`, blueprint §5/§16, user Q&A 2026-04-27.

---

## 1. Decisions Locked (User Q&A)

| Q | Decision |
|---|----------|
| Q1 | Karpathy wiki = knowledge organization paradigm. Form: SQLite OK, not forced markdown. Fuse w/ kilo.db. |
| Q2 | End-of-turn self-reflection by conductor. Same LLM Kilo runs. No separate model. |
| Q5 | Personal wiki separate from `docs/llm_wiki/`. Gitignored. |
| Q7 | Best-practice recall, no context bloat. |
| Q8 | SQLite `wiki.db`, pages-as-rows, markdown bodies, FTS5. |
| Q9 | Drop `episodic.db` AND `semantic.db`. `kilo.db` read-only = raw T0. `wiki.db` = distilled. Two stores total. |
| Q10 | Mandatory `wiki_update` tool call end-of-turn + watchdog retry on skip. |
| Q11 | Hybrid recall: profile auto-injected, other pages FTS5-threshold-gated against current user message. |
| Q12 | 5 kinds: `profile`, `topic`, `lesson`, `entity`, `decision`. |

---

## 2. Architecture (Two Stores, One LLM)

```
┌─────────────────────────────────────────────────────────────┐
│  kilo.db   (Kilo-owned, read-only for ARIA, P2-compliant)   │
│   message + part tables = T0 raw conversation               │
│   ARIA never writes here                                    │
└────────────────────┬────────────────────────────────────────┘
                     │ read on watchdog catch-up only
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  wiki.db   (.aria/runtime/memory/wiki.db, gitignored)       │
│   page table, kinds={profile,topic,lesson,entity,decision}  │
│   FTS5 index on (title, body_md)                            │
│   page_revision for audit trail                             │
│   wiki_watermark for skip-recovery                          │
└─────────────────────────────────────────────────────────────┘
                     ▲                            ▲
                     │                            │
   end-of-turn       │            watchdog        │
   wiki_update       │            catch-up        │
   (conductor LLM)   │            (scheduler)     │
                     │                            │
        ┌────────────┴───┐               ┌────────┴────────┐
        │  aria-conductor│               │ aria-scheduler  │
        │  (Kilo agent)  │               │ memory-watchdog │
        └────────────────┘               └─────────────────┘
```

### 2.1 Why this is simpler than v1/v2

- Drops `episodic.db` (kilo.db has it).
- Drops `semantic.db` (wiki.db has it w/ richer kinds + provenance).
- Drops Echo sidecar (no separate capture daemon — kilo.db is already capture).
- Drops Ollama / separate model (conductor LLM does reflection).
- Drops regex CLM entirely.
- Net: from **3 stores + sidecar daemon + extraction pipeline** → **1 new store + 2 MCP tools + 1 scheduler task**.

---

## 3. Storage — `wiki.db`

### 3.1 Schema

```sql
CREATE TABLE page (
    id              TEXT PRIMARY KEY,           -- UUID
    slug            TEXT NOT NULL,              -- kebab-case, unique per kind
    kind            TEXT NOT NULL,              -- profile|topic|lesson|entity|decision
    title           TEXT NOT NULL,
    body_md         TEXT NOT NULL,              -- markdown, may contain [[slug]] links
    confidence      REAL NOT NULL DEFAULT 1.0,  -- 0.0-1.0
    importance      TEXT NOT NULL DEFAULT 'med',-- low|med|high
    source_kilo_msg_ids TEXT NOT NULL,          -- JSON array of kilo message ids (provenance)
    first_seen      INTEGER NOT NULL,           -- unix epoch
    last_seen       INTEGER NOT NULL,
    occurrences     INTEGER NOT NULL DEFAULT 1,
    UNIQUE(kind, slug)
);

CREATE INDEX idx_page_kind ON page(kind);
CREATE INDEX idx_page_last_seen ON page(last_seen DESC);

-- Audit trail: every body_md change recorded (P6-style derived-but-traceable)
CREATE TABLE page_revision (
    id              TEXT PRIMARY KEY,
    page_id         TEXT NOT NULL REFERENCES page(id),
    body_md_before  TEXT,                       -- NULL on creation
    body_md_after   TEXT NOT NULL,
    diff_summary    TEXT,                       -- LLM-emitted change rationale
    source_kilo_msg_ids TEXT NOT NULL,
    ts              INTEGER NOT NULL
);

CREATE INDEX idx_revision_page ON page_revision(page_id, ts DESC);

-- FTS5 index over title + body for recall
CREATE VIRTUAL TABLE page_fts USING fts5(
    title, body_md, kind UNINDEXED, slug UNINDEXED,
    content='page', content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER page_ai AFTER INSERT ON page BEGIN
  INSERT INTO page_fts(rowid, title, body_md, kind, slug)
  VALUES (new.rowid, new.title, new.body_md, new.kind, new.slug);
END;
CREATE TRIGGER page_au AFTER UPDATE ON page BEGIN
  UPDATE page_fts SET title=new.title, body_md=new.body_md
  WHERE rowid=old.rowid;
END;
CREATE TRIGGER page_ad AFTER DELETE ON page BEGIN
  DELETE FROM page_fts WHERE rowid=old.rowid;
END;

-- Watchdog watermark per session (skip-recovery)
CREATE TABLE wiki_watermark (
    kilo_session_id TEXT PRIMARY KEY,
    last_seen_msg_id TEXT NOT NULL,
    last_seen_ts INTEGER NOT NULL,
    last_curated_ts INTEGER NOT NULL
);

-- Tombstone (P7 HITL on hard delete)
CREATE TABLE page_tombstone (
    page_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    tombstoned_at INTEGER NOT NULL
);
```

### 3.2 Kinds + body conventions

| Kind | Cardinality | Body shape | Update mode |
|------|-------------|-----------|-------------|
| `profile` | exactly 1 (slug=`profile`) | Markdown w/ sections: Identity, Preferences, Working Style, Active Projects | mutable, full rewrite each tick |
| `topic` | many (slug=`memory-system`, `oauth-fix`, ...) | Markdown, free-form, may include `## Decision YYYY-MM-DD` sections, `[[entity]]` links | mutable, append + edit |
| `lesson` | many (slug=`dont-mock-db`, `prefer-bundled-pr`) | Markdown — Rule / Why / When-to-apply / Source | append-only after creation; edits via revision |
| `entity` | many (slug=`fulvio`, `kilo-code`, `aria-scheduler`) | Markdown w/ aliases, type, related `[[topics]]`, attributes | mutable, append |
| `decision` | many (slug=`adr-memory-v3`, `drop-episodic-db`) | Markdown — Context / Decision / Rationale / Date — IMMUTABLE after first write | append-only; superseded via new decision page |

Cross-linking convention: `[[slug]]` anywhere in body. Resolved at recall time via FTS5 match on slug.

### 3.3 Why SQLite + markdown body (not pure md files)

- Index/dedup/prune via SQL — sustainable at 10k+ pages
- FTS5 ranking out of box
- Audit trail via `page_revision`
- Single backup file
- Still human-friendly: `aria memory show <slug>` renders body as markdown
- `aria memory export` dumps to .md tree on demand for human edit

---

## 4. Capture (kilo.db as T0)

### 4.1 No Echo sidecar

`kilo.db` already contains every turn. ARIA reads it on demand. No mirroring daemon.

### 4.2 Schema-fingerprint check on startup

`wiki_update` MCP server boot: runs `PRAGMA table_info(message)` + `PRAGMA table_info(part)` on `kilo.db`, compares hash to known-good fingerprint. Mismatch → log warning, refuse curator writes (read-only mode), require user attention. Mitigates Kilo upgrade schema drift.

### 4.3 Provenance pointer

Every `page` and `page_revision` row carries `source_kilo_msg_ids` (JSON array of Kilo `message.id`). Reconstruction always possible by re-running curator.

---

## 5. Curation — End-of-Turn `wiki_update`

### 5.1 Single MCP tool

```python
@mcp.tool
async def wiki_update(payload: WikiUpdatePayload) -> dict:
    """Persist salience extracted from current turn.
    
    Called ONCE at end of every conductor turn.
    """
```

`WikiUpdatePayload` = Pydantic structured input:

```python
class PagePatch(BaseModel):
    kind: Literal["profile","topic","lesson","entity","decision"]
    slug: str                          # kebab-case
    op: Literal["create", "update", "append"]
    title: str | None = None           # required on create
    body_md: str                       # full body OR appended section
    importance: Literal["low","med","high"] = "med"
    confidence: float = 0.8            # 0..1
    source_kilo_msg_ids: list[str]     # provenance for this patch
    diff_summary: str                  # one-line change rationale

class WikiUpdatePayload(BaseModel):
    patches: list[PagePatch]           # may be empty
    no_salience_reason: str | None = None  # set when patches=[] (e.g. "casual ack")
    kilo_session_id: str               # for watermark advance
    last_msg_id: str                   # for watermark advance
```

### 5.2 Conductor prompt addition

```markdown
## Memory contract (v3)

ARIA stores knowledge in wiki.db (kinds: profile/topic/lesson/entity/decision).
At turn START you receive an injected <memory> block with:
  - <profile>: your current snapshot of the user
  - <relevant>: pages auto-matched against the user's message (FTS5)

At turn END you MUST call wiki_update exactly once with:
  - patches: list of PagePatch (may be empty)
  - no_salience_reason: required if patches=[] (e.g. "user said thanks, nothing to learn")
  - kilo_session_id, last_msg_id: from your session env

Patch rules:
  - profile: op="update", slug="profile", body_md=full new body
  - topic: op="append" w/ ## section, or "update" full rewrite
  - lesson: op="create" only (immutable after); slug=kebab summary
  - entity: op="create" or "append" — alias updates, related pages
  - decision: op="create" only — IMMUTABLE; supersede via new decision page

Salience triggers (when to emit a patch):
  - User states stable fact about themselves → profile patch
  - User expresses preference/dislike → profile patch + lesson if rule-shaped
  - User corrects you → lesson(kind=correction)
  - User validates an unusual approach → lesson(kind=validation)
  - Architectural choice made → decision page
  - Recurrent topic w/ new info → topic page
  - New person/project/tool named → entity page

Skip rules:
  - Casual chat / acknowledgement → patches=[], no_salience_reason="casual"
  - Tool output only → patches=[], no_salience_reason="tool_only"
  - Question already answered from existing pages → patches=[], no_salience_reason="recall_only"
```

### 5.3 Skip risk — watchdog catch-up

LLM may skip `wiki_update`. Mitigation:

- **Scheduler task `memory-watchdog`** runs every 15 min
- Query: `SELECT session_id, max(time_created) AS last_ts FROM kilo.message WHERE agent='aria-conductor' GROUP BY session_id`
- For each session, compare `last_ts` vs `wiki_watermark.last_seen_ts`
- Gap > 5 min and ≥ 3 messages unprocessed → invoke catch-up
- **Catch-up mechanism**: spawn `aria-conductor` w/ special env `ARIA_MODE=curator-only`, narrow toolset (only `wiki_update`), pass kilo session id + msg range. Conductor reads kilo.db turns and emits backfill `wiki_update` call.
- Catch-up uses **same Kilo + same model** (P3 honored, no extra model).
- Watermark advanced on each successful `wiki_update`.

This makes the system **eventually consistent**: live writes via end-of-turn tool, lossy turns recovered within 15 min.

---

## 6. Recall — Hybrid Auto-Inject

### 6.1 Profile always-on

Conductor agent system prompt (Kilo agent template) includes substitution `{{ARIA_MEMORY_BLOCK}}`. ARIA's MCP server boot writes the agent template w/ the current profile body inlined. On profile update, template is regenerated. ~300 tokens budget.

### 6.2 Per-message FTS5 threshold injection

No tool call needed for inject. Mechanism:

- Conductor calls `wiki_recall(query=<user_msg>, max_pages=5, min_score=0.3)` as **mandatory first action** of each turn (prompt rule)
- Returns: list of `{kind, slug, title, body_excerpt, score}`
- LLM treats them as ambient context for the turn
- Cap: 2k tokens total. Pages over budget truncated to first paragraph.
- Skip handling: if conductor forgets `wiki_recall`, watchdog logs as a soft warning (not catastrophic — recall is read-only convenience). No retry needed.

### 6.3 Why not auto-inject everything

- Profile auto-inject (always) is small + always relevant
- Topic/entity/lesson/decision pages are situational — FTS5 against user message is the cheapest relevance signal
- Mandatory tool call for recall is acceptable risk: missing recall = degraded response, missing `wiki_update` = data loss. Asymmetric.

---

## 7. MCP Tool Surface (after v3)

| Tool | Purpose | New / Changed |
|------|---------|---------------|
| `wiki_update` | End-of-turn structured patch | NEW |
| `wiki_recall(query, max_pages, min_score)` | FTS5 search returning pages | NEW |
| `wiki_show(kind, slug)` | Get full page by id | NEW |
| `wiki_list(kind, limit)` | List pages by kind for inspection | NEW |
| `forget(slug)` | HITL-gated tombstone | KEPT (re-pointed at wiki) |
| `hitl_list_pending` | Pending HITL queue | KEPT |
| `hitl_cancel`, `hitl_approve` | HITL flow | KEPT |
| `stats` | Telemetry — page counts per kind, last_curated, watchdog gap | KEPT (new metrics) |
| `health` | Boot-time check incl. kilo.db schema fingerprint | KEPT (extended) |
| `remember` | DROPPED — covered by `wiki_update` w/ explicit user intent path | DROPPED |
| `complete_turn` | DROPPED — replaced by `wiki_update` | DROPPED |
| `recall`, `recall_episodic` | DROPPED — replaced by `wiki_recall` + kilo.db reads | DROPPED |
| `distill`, `curate` | DROPPED — curation is end-of-turn now | DROPPED |

Net: 11 → 9 tools. P9 (≤ 20) honored.

---

## 8. File Layout

```
src/aria/memory/
├── wiki/                            # NEW v3 module
│   ├── __init__.py
│   ├── db.py                        # wiki.db schema + queries (aiosqlite)
│   ├── tools.py                     # MCP tool implementations
│   ├── recall.py                    # FTS5 query + score thresholding
│   ├── watchdog.py                  # scheduler task: kilo.db gap detection + curator-only spawn
│   ├── prompt_inject.py             # profile substitution into agent template
│   ├── schema.py                    # Pydantic: PagePatch, WikiUpdatePayload, Page
│   └── migrations.py                # wiki.db schema migrations
├── mcp_server.py                    # CHANGED: drop old tools, register wiki tools
├── episodic.py                      # FROZEN — read-only legacy until cleanup ADR
├── semantic.py                      # FROZEN — read-only legacy until cleanup ADR
├── clm.py                           # FROZEN — legacy regex extractor
└── schema.py                        # add Page, PagePatch alongside legacy models

.aria/runtime/memory/
├── wiki.db                          # NEW canonical store
├── episodic.db                      # FROZEN — kept for rollback during Phase A
└── (semantic content embedded in episodic.db)

src/aria/scheduler/
└── tasks/
    └── memory_watchdog.py           # NEW catch-up task
```

`.aria/runtime/memory/` already in `.gitignore`. Confirmed private.

---

## 9. Migration Plan (No Big-Bang)

| Phase | Goal | Reversibility |
|-------|------|---------------|
| **A** | Land `wiki.db` schema + `wiki_update`/`wiki_recall`/`wiki_show`/`wiki_list` MCP tools. Old MCP tools (`remember` etc.) still active. Conductor prompt unchanged. Manual smoke test: call `wiki_update` from REPL and verify rows. | Drop wiki.db, no impact. |
| **B** | Ship watchdog task + kilo.db reader. Conductor prompt updated to call `wiki_update` end-of-turn + `wiki_recall` start-of-turn. Watchdog runs every 15 min. Old persistence still active in parallel (belt+suspenders). | Disable watchdog task, revert conductor prompt. |
| **C** | Profile auto-inject in conductor agent template. Stats tool reports both old + new. Run 7 days, validate parity. | Remove substitution, regen template. |
| **D** | Deprecate old tools (`remember`, `complete_turn`, `recall`, `recall_episodic`, `distill`, `curate`). Drop from MCP. ADR-NNNN documents removal. `episodic.py`/`semantic.py`/`clm.py` marked frozen but kept for forensic read. | ADR-driven. |
| **E** | After 30 days stable: hard-delete old code + old DBs. Final ADR. | Final. |

Each phase ships independently. Phase A is non-breaking — pure addition.

---

## 10. Inderogable Rules Audit (Blueprint §16)

| Rule | v3 stance |
|------|-----------|
| P1 Isolation | wiki.db lives in `$ARIA_HOME/.aria/runtime/memory/`. Watchdog spawns Kilo w/ isolated config. ✅ |
| P2 Upstream Invariance | kilo.db read-only. Schema fingerprint check + graceful refuse on drift. No Kilo source touched. ✅ |
| P3 Local-first | No external services. Same LLM Kilo already uses. ✅ |
| P4 Polyglot Pragmatism | Python only for ARIA layer. ✅ |
| P5 Actor-aware | Pages carry `source_kilo_msg_ids`. Provenance traceable. Page kind taxonomy captures actor implicitly (profile=user, lesson=user-correction, decision=mutual). ✅ |
| P6 Verbatim T0 | kilo.db is verbatim T0 (Kilo-owned). wiki.db is derived; `page_revision` audit + provenance allow full reconstruction. ✅ |
| P7 HITL on destructive | `forget(slug)` enqueues HITL pending → tombstone on approve. Decision pages immutable (no edit at all). ✅ |
| P8 Tool ladder | MCP-first (4 wiki tools). Skill `memory-curator` orchestrates if multi-step. Python only inside MCP server. ✅ |
| P9 ≤ 20 tools | After v3: 9 memory tools. ✅ |
| P10 ADR | Phase D requires ADR-NNNN-memory-v3-cutover documenting deprecation. Schema drift policy = separate ADR. ✅ |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Conductor LLM skips `wiki_update` | High (confirmed prior with `complete_turn`) | Lossy salience | Watchdog catch-up every 15 min replays from kilo.db |
| Conductor LLM skips `wiki_recall` | High | Degraded response only (no data loss) | Accepted; profile still auto-injected |
| Kilo upgrades change message/part schema | Medium | Watchdog breaks | Schema fingerprint check on boot; refuse-mode + alert until ADR re-aligns |
| Profile body grows unbounded | Medium | Token bloat | Hard cap 2k tokens; conductor prompt rule "compress redundant lines"; quarterly compaction sub-skill |
| LLM emits invalid `slug` (collisions, weird chars) | Medium | DB constraint errors | Pydantic validator + slugify in tool layer; reject + return error to LLM for retry within turn |
| LLM hallucinates wrong profile fact | Medium | Wrong identity stored | Confidence ≥ 0.7 to apply; user sees `<profile>` block every turn → notices & corrects → lesson logged |
| Catch-up loop creates duplicate pages | Low | Wiki noise | UNIQUE(kind, slug) constraint + watermark gating |
| `wiki.db` corruption | Low | Total memory loss | Existing `aria-backup.timer` covers `.aria/runtime/`; watchdog can rebuild from kilo.db |
| Recall too slow at scale | Low | UX latency | FTS5 + indexes; cap pages at 5 + token budget; benchmark Phase B exit |

---

## 12. Implementation Effort

| Phase | Work | Effort |
|-------|------|--------|
| A | wiki.db schema, migrations, 4 MCP tools, unit tests | ~8 h |
| B | Watchdog task + curator-only mode for conductor + kilo.db reader + integration test | ~8 h |
| C | Profile auto-inject substitution + agent template regen on update + recall threshold tuning | ~4 h |
| D | Deprecate old tools, ADRs, observability metrics | ~4 h |
| E | Hard-delete legacy after 30 days stable | ~2 h |
| **Total** | | **~26 h** |

Roughly half the v2 estimate. Simpler architecture, fewer moving parts.

---

## 13. Success Criteria

Phase A:
- [ ] `wiki.db` initializable, all 5 kinds inserted via `wiki_update`, FTS5 returns hits
- [ ] `wiki_recall(query="memory")` returns scored pages
- [ ] Schema fingerprint check correctly detects kilo.db drift (synthetic test)

Phase B:
- [ ] Conductor end-of-turn `wiki_update` lands rows in 100% of test sessions
- [ ] Watchdog detects synthetic gap (skipped `wiki_update`) within 15 min and recovers
- [ ] Catch-up curator-only spawn uses same Kilo model (verify env in logs)

Phase C:
- [ ] Profile auto-inject visible in agent prompt at session start (kilo.db `step-start` snapshot)
- [ ] FTS5 recall surfaces relevant pages on test queries; precision@5 ≥ 0.7 on 20-message fixture

Quality:
- [ ] `make quality` passes
- [ ] No new runtime dep beyond `aiosqlite` (already present)
- [ ] `.aria/runtime/memory/` confirmed gitignored

---

## 14. Open Items (User Confirm Before Phase A)

1. **Filename rename** at merge: `auto_persistence_echo.md` → `memory_v3_kilo_wiki.md`. OK?
2. **Phase A scope split**: should Phase A include the conductor prompt change, or strictly tools-only first? (Recommend tools-only, prompt at B.)
3. **Watchdog frequency**: 15 min sane, or tighter (5 min) for live correctness vs. cheaper (60 min)?
4. **HITL on `decision` create**: decisions are immutable architectural choices. Require HITL on creation too, or only on supersede? (Recommend: no HITL on create, HITL on supersede.)
5. **Profile token budget**: 2k hard cap? Lower (1k) more conservative for free models?
6. **Cross-link resolution**: `[[slug]]` links auto-rendered to in-context on inject, or LLM follows manually via `wiki_show`? (Recommend: LLM follows on demand — keeps inject light.)

---

## 15. What Got Dropped vs Earlier Plans

- ❌ Echo sidecar daemon (kilo.db read on demand replaces it)
- ❌ Separate `episodic.db` (redundant with kilo.db)
- ❌ Separate `semantic.db` (folded into wiki.db)
- ❌ Regex CLM (LLM does extraction in same turn)
- ❌ Ollama / separate model (conductor LLM does it)
- ❌ `complete_turn`, `remember`, `recall`, `recall_episodic`, `distill`, `curate` MCP tools
- ❌ `profile.md` + `lessons.md` flat files (replaced by SQLite-backed pages)
- ❌ `mem0`/`letta`/`langmem` framework deps

What's left: **one new module (`memory/wiki/`), one new SQLite file, four MCP tools, one scheduler task, one prompt update.** That's the whole v3.

---

*End of plan v3. Awaiting answers to §14 before Phase A.*
