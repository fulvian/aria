---
title: Memory Subsystem
sources:
  - docs/foundation/aria_foundation_blueprint.md §5
  - docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md
  - src/aria/memory/ (codice sorgente verificato 2026-04-24)
  - docs/analysis/memory_subsystem_health_check_2026-04-24.md
last_updated: 2026-04-24
tier: 1
---

# Memory Subsystem — Memoria 5D

## Tassonomia a 5 Dimensioni

| Tipo | Scope | Storage | Scrittura | Lettura |
|------|-------|---------|-----------|---------|
| **Working** | Sessione corrente, volatile | Context window LLM | Automatica | Implicita |
| **Episodic** | Eventi/interazioni, verbatim | SQLite `episodic.db` | Ogni turn | Per range temporale/tag |
| **Semantic** | Fatti consolidati, concetti | SQLite FTS5 + LanceDB lazy | Distill async (CLM) | Per keyword/similarity |
| **Procedural** | Procedure, workflow, skill | SKILL.md in filesystem | Definite manualmente | Progressive disclosure |
| **Associative** | Relazioni tra entità (@fase2) | SQLite graph tables | Estrazione NER async | Query grafo |

*source: `docs/foundation/aria_foundation_blueprint.md` §5.1*

## Storage Tiers

| Tier | Scopo | Backend | Latenza target | Abilitato | Stato impl |
|------|-------|---------|----------------|-----------|------------|
| **T0** | Raw verbatim episodic | SQLite (WAL mode) | <10ms | MVP | ✅ Operativo |
| **T1** | Summaries + FTS5 | SQLite FTS5 | <50ms | MVP | ⚠️ Schema OK, 0 dati |
| **T2** | Embeddings semantici | LanceDB (lazy-created) | <200ms | MVP (opzionale) | ✅ Stub (ARIA_MEMORY_T2=0) |
| **T3** | Grafo associativo | SQLite graph tables | <500ms | Fase 2 | ✅ Stub @fase2 |

**Regola chiave (P6)**: T0 è **autoritativo e immutabile**. T1/T2/T3 sono **derivati** e ricostruibili da T0 ri-eseguendo il CLM.

*source: `docs/foundation/aria_foundation_blueprint.md` §5.2*

**ADR-0004**: È vietato usare `pickle` come storage canonico per T3. Formati ammessi: SQLite, JSON, Parquet.

*source: `docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md`*

## Actor-Aware Tagging (P5)

Ogni memory unit ha un campo `actor` con 4 valori possibili:

| Actor | Trust Score | Descrizione | Promozione |
|-------|-------------|-------------|------------|
| `user_input` | **1.0** | Messaggio originale dell'utente | — (massimo trust) |
| `tool_output` | **0.9** | Output verificabile di un tool (API response) | — |
| `agent_inference` | **0.6** | Deduzione/ipotesi dell'LLM | Richiede riscontro tool_output o conferma user_input |
| `system_event` | **0.5** | Log di sistema (avvii, errori) | Non promuovibile |

**Regola di promozione**: `agent_inference` non è promuovibile automaticamente a fatto semantico. Serve (a) un secondo riscontro da `tool_output`, oppure (b) conferma esplicita `user_input`.

**Aggregazione**: in presenza di mix di actor, `actor_aggregate()` applica downgrade: AGENT_INFERENCE domina (no promotion), poi TOOL_OUTPUT, poi USER_INPUT.

*source: `src/aria/memory/actor_tagging.py`, `docs/foundation/aria_foundation_blueprint.md` §5.3*

## Context Lifecycle Manager (CLM)

Processo asincrono che:

1. **Scansiona T0** (ultime N conversazioni chiuse)
2. **Distilla** → genera summary tipizzati (persone, fatti, decisioni, action items)
3. **Promuove** in T1 (FTS5) con actor tagging preservato
4. **(Opzionale)** genera embedding T2 per gli item più "caldi"
5. **Non cancella mai T0**

**Trigger spec**: post-session + scheduler ogni 6h via `compaction-agent`.

*source: `docs/foundation/aria_foundation_blueprint.md` §5.4*

### Implementazione CLM (Sprint 1.1)

```
source: src/aria/memory/clm.py
```

- **Tipo**: estrattivo (regex, no LLM calls) — limitazione Sprint 1.1 documentata in codice
- Processa SOLO `USER_INPUT` entries (P5 compliance)
- Pattern riconosciuti:
  - Action items: `devo`, `bisogna`, `ricordami di`, `need to`, `must`, ...
  - Preference/decision: `ricorda`, `preferisco`, `voglio`, `deciso`, `decided`, ...
  - Facts: `è ... di`, `il ... è`, `si chiama`, `ha N ...`
- Confidence = `actor_trust_score * (0.5 + 0.5 * keyword_match_ratio)`
- `distill_session()` idempotente: se già distillata, ritorna `[]` (a meno di `force=True`)

**⚠️ CRITICO**: Il CLM non è mai stato invocato. Nessun scheduler task o hook post-sessione esiste.
`compaction-agent` è definito in `.aria/kilocode/agents/_system/` ma non schedulato.

*source: `src/aria/memory/clm.py`, `docs/analysis/memory_subsystem_health_check_2026-04-24.md`*

## ARIA-Memory MCP Server

**Modulo**: `src/aria/memory/mcp_server.py` (FastMCP `"aria-memory"`)

| Tool | Input | Output | Stato |
|------|-------|--------|-------|
| `remember` | `content`, `actor`, `role`, `session_id`, `tags[]` | `{status, entry_id, session_id, content_hash}` | ✅ |
| `recall` | `query`, `top_k`, `kinds?`, `since?`, `until?` | `list[SemanticChunk\|EpisodicEntry]` | ✅ (T1 vuoto → solo T0 FTS5) |
| `recall_episodic` | `session_id` OR `since`, `limit` | `list[EpisodicEntry]` | ✅ |
| `distill` | `session_id` | `list[SemanticChunk]` | ✅ (manuale; auto non schedulato) |
| `curate` | `id`, `action=promote\|demote\|forget` | `ok` o `pending_hitl` | ✅ (forget→HITL; promote/demote immediati) |
| `forget` | `id` | `pending_hitl` | ⚠️ (enqueue only, no execute) |
| `stats` | — | `{t0_count, t1_count, sessions, ...}` | ✅ |
| `hitl_ask` | `action`, `target_id`, `reason?` | `{status, hitl_id}` | ✅ |
| `hitl_list_pending` | `limit?` | `list[HitlPending]` | ✅ |
| `hitl_cancel` | `hitl_id` | `{status}` | ✅ |

Totale: **10 tool** (spec §5.6 elenca 7; i 3 HITL sono estensione. 10 ≤ 20 per P9.)

**Init**: lazy — `_ensure_store()` inizializza EpisodicStore + SemanticStore + CLM al primo tool call.
**Transport**: `stdio` (configurable via `ARIA_MEMORY_MCP_TRANSPORT`).
**Logging**: file `mcp-aria-memory-YYYY-MM-DD.log` in `.aria/runtime/logs/` (no stdout).

*source: `src/aria/memory/mcp_server.py`, `docs/foundation/aria_foundation_blueprint.md` §5.6*

## HITL Implementation State

**⚠️ CRITICO**: Solo enqueue implementato. Approval path mancante (Sprint 1.2).

| Funzione | Stato |
|----------|-------|
| Enqueue HITL request (`forget`, `curate/forget`, `hitl_ask`) | ✅ |
| Lista pending (`hitl_list_pending`) | ✅ |
| Cancel pending (`hitl_cancel`) | ✅ |
| **Approve + execute** (`hitl_approve`) | ❌ Non implementato |
| Tombstone execution post-approve | ❌ Non implementato |
| Notify utente via Telegram/CLI | ❌ Non implementato |

`forget()` crea record in `memory_hitl_pending` ma NON chiama `store.tombstone()`. La memoria rimane accessibile dopo `forget`.

*source: `src/aria/memory/mcp_server.py`, `docs/analysis/memory_subsystem_health_check_2026-04-24.md`*

## Schema SQLite (Migrations)

3 migrations applicate via `MigrationRunner` (checksum-verified, idempotenti):

| Migration | Tabelle create |
|-----------|----------------|
| 0001 init | `episodic`, `episodic_fts` (FTS5), `semantic_chunks`, `semantic` (FTS5), `schema_migrations` + triggers insert/update/delete |
| 0002 tombstones | `episodic_tombstones` (soft delete P6) |
| 0003 hitl_pending | `memory_hitl_pending` + indici |

SQLite PRAGMAs: `WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `wal_autocheckpoint=1000`, `busy_timeout=5000`.
Version check al connect: `>= 3.51.3` (lancia `MemoryError` se non soddisfatto).

*source: `src/aria/memory/migrations.py`, `src/aria/memory/episodic.py`*

## Implementazione Codice

```
src/aria/memory/
├── schema.py          # Pydantic models: Actor, EpisodicEntry, SemanticChunk, etc.
├── episodic.py        # EpisodicStore: SQLite WAL + FTS5 + tombstone + HITL queue
├── semantic.py        # SemanticStore: FTS5 T1 + T2Store stub
├── clm.py             # CLM estrattivo (Sprint 1.1 - no LLM)
├── actor_tagging.py   # derive_actor, trust_score, actor_aggregate
├── mcp_server.py      # FastMCP server "aria-memory" (10 tool)
├── migrations.py      # MigrationRunner + 3 embedded SQL migrations
├── migrations/        # SQL files su disco (sincronizzati da migrations.py)
└── __init__.py
```

**Test**: `tests/unit/memory/` — 7 file, 32 test, tutti passing.
**Integration tests**: nessuno (gap identificato).

*source: `src/aria/memory/`, verificato 2026-04-24*

## Governance Memoria

| Policy | Spec | Implementazione |
|--------|------|-----------------|
| T0 retention 365gg | §5.7 | ⚠️ Config ok, enforcement assente |
| T1 compression 90gg | §5.7 | ❌ Non implementato |
| Review queue agent_inference < 0.7 | §5.7 | ⚠️ `memory-curator` esiste, non auto-alimentato |
| Oblio programmato HITL | §5.7 | ⚠️ Enqueue ok, no execution |
| Backup | §5.7 | ✅ `scripts/backup.sh` (no automazione) |

*source: `docs/foundation/aria_foundation_blueprint.md` §5.7, `src/aria/config.py`*

## Stato Runtime Live (2026-04-24)

Verificato via query diretta su `.aria/runtime/memory/episodic.db`:

| Metrica | Valore | Note |
|---------|--------|------|
| T0 entries | **1005** | 1004 user_input, 1 agent_inference |
| T1 semantic chunks | **0** | CLM mai eseguito |
| Tombstones | 0 | — |
| HITL pending | 0 | — |
| SQLite versione | 3.51.3 | Minimo richiesto ADR-0002 ✅ |
| WAL mode | attivo | ✅ |
| WAL file size | 282KB | Non checkpointato (reaper checkpoint solo scheduler.db) |
| DB file size | 596KB | — |
| Migrations applicate | 3/3 | ✅ |
| semantic/ dir | vuota | T2 disabilitato (ARIA_MEMORY_T2=0) |

*source: `docs/analysis/memory_subsystem_health_check_2026-04-24.md`, last_updated: 2026-04-24*

## Gap Critici Identificati (2026-04-24)

Per analisi completa: `docs/analysis/memory_subsystem_health_check_2026-04-24.md`

| Gap | Severità | Dettaglio |
|-----|----------|-----------|
| CLM mai eseguito — 0 T1 da 1005 T0 | HIGH | Nessun scheduler task, nessun hook post-sessione |
| HITL approval path inesistente | HIGH | `forget` enqueue-only, no tombstone, no notify |
| Retention T0/T1 non applicata | MEDIUM | Config presente, codice assente |
| WAL episodic.db non checkpointato | MEDIUM | `vacuum_wal()` esiste ma non chiamata |
| Review queue non auto-alimentata | LOW | `memory-curator` esiste, non schedulato |
| Integration tests assenti | LOW | Solo unit tests (32/32) |
| T1 compression 90gg non implementata | LOW | Config presente, codice assente |

*source: `docs/analysis/memory_subsystem_health_check_2026-04-24.md`*

## Vedi anche

- [[ten-commandments]] — P5 (Actor-Aware), P6 (Verbatim)
- [[scheduler]] — CLM scheduling (gap)
- [[agents-hierarchy]] — Compaction-Agent, Memory-Curator
