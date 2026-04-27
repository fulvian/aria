# Memory v3 — Kilo+Wiki Fusion

**Status**: Phase A ✅ | Phase B ✅ | Phase C ✅ | Phase D ✅ COMPLETE | Phase E — Pending (2026-05-27)
**Date**: 2026-04-27
**Source**: `docs/plans/auto_persistence_echo.md`
**Branch**: `fix/memory-recovery`

## Architecture

Two-store model:
1. **kilo.db** (Kilo-owned, read-only for ARIA) — raw T0 conversations
2. **wiki.db** (`.aria/runtime/memory/wiki.db`, gitignored) — distilled knowledge pages

No Echo sidecar, no separate model, no regex CLM. Conductor LLM does end-of-turn reflection.

## Page Kinds

| Kind | Cardinality | Mutability |
|------|-------------|------------|
| `profile` | exactly 1 (slug="profile") | Full rewrite each tick |
| `topic` | many | Append + edit |
| `lesson` | many | Append-only after create |
| `entity` | many | Append |
| `decision` | many | IMMUTABLE after create |

## Key Components (Phase A + B)

| Module | Purpose |
|--------|---------|
| `src/aria/memory/wiki/schema.py` | Pydantic: PagePatch, WikiUpdatePayload, Page |
| `src/aria/memory/wiki/migrations.py` | wiki.db DDL with FTS5, page_revision, watermark, tombstone |
| `src/aria/memory/wiki/db.py` | WikiStore CRUD + schema fingerprint check |
| `src/aria/memory/wiki/recall.py` | FTS5 query + score thresholding |
| `src/aria/memory/wiki/tools.py` | 4 MCP tools: wiki_update, wiki_recall, wiki_show, wiki_list |
| `src/aria/memory/wiki/kilo_reader.py` | kilo.db read-only reader + schema fingerprint (Phase B) |
| `src/aria/memory/wiki/watchdog.py` | Gap detection + catch-up trigger (Phase B) |
| `src/aria/memory/wiki/prompt_inject.py` | Memory contract + profile + recall block (Phase B) |

## MCP Tools (Phase A + B)

| Tool | Purpose |
|------|---------|
| `wiki_update` | End-of-turn structured patch |
| `wiki_recall(query, max_pages, min_score)` | FTS5 search returning scored pages |
| `wiki_show(kind, slug)` | Get full page by kind+slug |
| `wiki_list(kind, limit)` | List pages by kind |

## Watchdog + Catch-up (Phase B)

- **Scheduler task** `memory-watchdog` runs every 15 min (`*/15 * * * *`)
- Queries kilo.db for sessions with conductor messages
- Compares against wiki_watermark (last curated timestamp)
- Gap > 5 min + ≥ 3 unprocessed messages → catch-up trigger
- KiloReader opens kilo.db in `immutable=1` read-only mode (P2)
- Schema fingerprint (SHA256 of PRAGMA table_info) detects Kilo upgrade drift

## Conductor Prompt (Phase B)

Added wiki memory contract per plan §5.2:
- **Start of turn**: mandatory `wiki_recall_tool` call with user message
- **End of turn**: mandatory `wiki_update_tool` call with patches or no_salience_reason
- Salience triggers: stable facts → profile, corrections → lesson, architectural choices → decision
- Skip rules: casual chat → empty patches with reason

## Profile Auto-Inject (Phase C)

- **Template source**: `_aria-conductor.template.md` contains `{{ARIA_MEMORY_BLOCK}}` placeholder
- **Active template**: `aria-conductor.md` is regenerated from source with profile substituted
- **Boot hook**: MCP server `main()` runs regeneration before `mcp.run()`
- **Update hook**: `wiki_update` with profile patch triggers immediate regeneration
- **Budget**: Profile body truncated to ~300 tokens (1200 chars)
- **Non-blocking**: Regeneration failure logs warning, does not block tool calls

## Constraints

- FTS5 on (title, body_md) with kind/slug UNINDEXED
- UNIQUE(kind, slug) constraint
- page_revision for audit trail
- Cross-linking: `[[slug]]` in body_md
- Decision pages immutable (no edit/delete)
- Profile exactly 1 page

## Context7 Verification (2026-04-27)

- aiosqlite `/omnilib/aiosqlite`: async SQLite API confirmed
- FastMCP `/prefecthq/fastmcp`: @mcp.tool, dict returns confirmed
- Pydantic `/pydantic/pydantic`: Literal, field_validator confirmed

## Blueprint Alignment

- P1 Isolation: wiki.db in `.aria/runtime/memory/`
- P2 Upstream Invariance: kilo.db read-only, schema fingerprint check
- P5 Actor-aware: source_kilo_msg_ids provenance
- P6 Verbatim T0: kilo.db is T0, wiki.db is derived with revision audit
- P7 HITL: forget() → tombstone via HITL approval
- P8 Tool ladder: MCP-first (4 wiki tools)
- P9 ≤ 20 tools: after Phase D = 10 memory tools (4 wiki + 2 bridge + 4 HITL)
