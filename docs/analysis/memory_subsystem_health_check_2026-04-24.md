---
title: Memory Subsystem Health Check
date: 2026-04-24
author: Claude (claude-sonnet-4-6)
status: final
sources:
  - src/aria/memory/
  - docs/foundation/aria_foundation_blueprint.md §5
  - docs/llm_wiki/wiki/memory-subsystem.md
  - docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md
  - .aria/runtime/memory/episodic.db (live)
  - systemd/aria-memory.service
  - tests/unit/memory/
---

# Memory Subsystem Health Check — 2026-04-24

## Executive Summary

Il sottosistema di memoria è **architetturalmente solido** ma ha **3 gap critici** che rendono il sistema parzialmente non conforme alle specifiche:

| Area | Stato | Severità |
|------|-------|----------|
| Schema Pydantic (§5.5) | ✅ Conforme | — |
| T0 SQLite WAL (§5.2) | ✅ Attivo | — |
| Actor-Aware Tagging (P5, §5.3) | ✅ Conforme | — |
| P6 Verbatim Preservation | ✅ Conforme | — |
| MCP Server tools 10/10 (§5.6) | ✅ Conforme | — |
| Unit Tests 32/32 | ✅ Pass | — |
| CLM mai eseguito — 0 T1 chunk su 1005 T0 | ❌ CRITICO | HIGH |
| HITL approval path inesistente | ❌ CRITICO | HIGH |
| Retention T0/T1 non applicata | ❌ CRITICO | MEDIUM |
| WAL episodic.db mai checkpointato | ⚠️ MANCANTE | MEDIUM |
| Review queue non auto-alimentata | ⚠️ PARZIALE | LOW |
| Integration tests assenti | ⚠️ MANCANTE | LOW |
| T1 compression (90gg) non implementata | ⚠️ MANCANTE | LOW |

---

## 1. Schema e Modelli Pydantic (§5.5)

**Stato: ✅ CONFORME**

Tutti i modelli richiesti dal blueprint sono implementati in `src/aria/memory/schema.py`:

| Modello | Blueprint §5.5 | Implementazione |
|---------|----------------|-----------------|
| `Actor` (StrEnum) | ✅ | 4 valori: USER_INPUT, TOOL_OUTPUT, AGENT_INFERENCE, SYSTEM_EVENT |
| `EpisodicEntry` | ✅ | id, session_id, ts, actor, role, content, content_hash, tags, meta |
| `SemanticChunk` | ✅ | id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id |
| `ProceduralSkill` | ✅ | id, path, name, description, trigger_keywords, allowed_tools, version |
| `Association` | ✅ (stub @fase2) | Definito ma non usato |
| `MemoryStats` | ✅ | t0_count, t1_count, sessions, last_session_ts, avg_entry_size, storage_bytes |

**Differenza minore**: Il blueprint usa `Actor(str, Enum)` ma l'implementazione usa `Actor(StrEnum)`. Comportamento identico, `StrEnum` è il pattern moderno Python 3.11+. Non è un problema.

`content_hash` è auto-generato (SHA-256) nel `__init__` di `EpisodicEntry` — corretto per P6.

---

## 2. Storage Tiers (§5.2)

### T0 — SQLite WAL (✅ Operativo)

```
source: src/aria/memory/episodic.py
```

- SQLite versione runtime: **3.51.3** — esattamente il minimo richiesto da ADR-0002 ✅
- WAL mode: **attivo** (`PRAGMA journal_mode = WAL`) ✅
- PRAGMAs applicati: `synchronous=NORMAL`, `foreign_keys=ON`, `wal_autocheckpoint=1000`, `busy_timeout=5000` ✅
- SQLite version check (`>= 3.51.3`) al `connect()` — lancia `MemoryError` se non soddisfatto ✅
- FTS5 check con warning se non compilato ✅

**Stato runtime live:**
```
Entries T0:        1005
Entries T1:           0   ← CLM MAI ESEGUITO
Tombstones:           0
HITL pending:         0
WAL file:          282KB  ← mai checkpointato (vedi §8)
DB file:           596KB
SQLite version:  3.51.3
```

### T1 — Semantic FTS5 (⚠️ Schema OK, dati vuoti)

```
source: src/aria/memory/semantic.py, migrations.py
```

- Tabella `semantic_chunks` creata correttamente con migration 0001 ✅
- FTS5 virtual table `semantic` con triggers INSERT/UPDATE/DELETE ✅
- Indici su `actor`, `kind`, `first_seen` ✅
- **0 chunk presenti** nonostante 1005 entry T0 — il CLM non è mai stato eseguito ❌

### T2 — LanceDB (✅ Stub corretto)

```
source: src/aria/memory/semantic.py (T2Store)
```

- Implementato come stub che lancia `NotImplementedError` a meno che `ARIA_MEMORY_T2=1` ✅
- `semantic/` directory presente (vuota, lazy-created) ✅
- Feature flag `config.memory.t2_enabled` funzionante ✅

### T3 — Grafo Associativo (✅ Stub corretto)

- `Association` model definito come stub `@fase2` ✅
- Nessuna tabella creata — corretto per MVP ✅
- ADR-0004 rispettato (no pickle) ✅

---

## 3. Actor-Aware Tagging (P5, §5.3)

**Stato: ✅ CONFORME**

```
source: src/aria/memory/actor_tagging.py
```

| Actor | Trust score | Blueprint | Implementazione |
|-------|-------------|-----------|-----------------|
| USER_INPUT | 1.0 | Massimo | ✅ 1.0 |
| TOOL_OUTPUT | 0.9 | Alto | ✅ 0.9 |
| AGENT_INFERENCE | 0.6 | Condizionato | ✅ 0.6 |
| SYSTEM_EVENT | 0.5 | Metadato | ✅ 0.5 |

`derive_actor_from_role()` mappa correttamente `user→USER_INPUT`, `assistant→AGENT_INFERENCE`, `tool→TOOL_OUTPUT`, `system→SYSTEM_EVENT`.

`actor_aggregate()` applica la regola di downgrade: in presenza di AGENT_INFERENCE, il risultato è AGENT_INFERENCE (non promozione automatica). ✅

**Regola di promozione non automatica** (P5): Il CLM estrattivo processa SOLO `USER_INPUT` entries per generare semantic chunks, non promuove mai `agent_inference` automaticamente. ✅

**Distribuzione attuale nel DB live:**
```
user_input:       1004  (99.9%)
agent_inference:     1  (0.1%)
tool_output:         0
system_event:        0
```

---

## 4. P6 Verbatim Preservation

**Stato: ✅ CONFORME**

```
source: src/aria/memory/episodic.py
```

- Nessun `UPDATE` su colonne di contenuto (content, content_hash, actor, role, session_id, ts) ✅
- Soft delete via tabella `episodic_tombstones` — mai hard delete ✅
- `tombstone()` inserisce record in `episodic_tombstones`, il contenuto originale resta intatto ✅
- Tutte le query filtrano `LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id WHERE t.episodic_id IS NULL` ✅
- `insert_many()` usa `executemany` senza UPDATE ✅

---

## 5. MCP Server e Tool Inventory (§5.6)

**Stato: ✅ CONFORME (espansione consentita)**

```
source: src/aria/memory/mcp_server.py
```

Il blueprint specifica 7 tool. L'implementazione ne espone 10, aggiungendo 3 tool HITL espliciti (previsti ma non elencati nel blueprint §5.6).

| Tool | Blueprint | Implementazione | Note |
|------|-----------|-----------------|------|
| `remember` | ✅ | ✅ | Scrive T0 con actor/role/session_id/tags |
| `recall` | ✅ | ✅ | T1 FTS5 first, T0 fallback |
| `recall_episodic` | ✅ | ✅ | Cronologico per session o time range |
| `distill` | ✅ | ✅ | Trigger CLM on-demand |
| `curate` | ✅ | ✅ | promote/demote immediati, forget→HITL |
| `forget` | ✅ | ✅ | Soft delete HITL-gated |
| `stats` | ✅ | ✅ | Telemetria t0/t1/sessions/storage |
| `hitl_ask` | non nel §5.6 | ✅ | Crea HITL request |
| `hitl_list_pending` | non nel §5.6 | ✅ | Lista pending |
| `hitl_cancel` | non nel §5.6 | ✅ | Cancella pending |

Totale: 10 tool ≤ 20 (soglia P9). ✅

**Inizializzazione lazy**: `_ensure_store()` inizializza `EpisodicStore`, `SemanticStore`, `CLM` al primo tool call — corretto. Richiede che `ARIA_SESSION_ID` sia impostato per session tracking.

**Transport**: `stdio` (corretto per MCP via KiloCode). Fallisce esplicitamente (return 1) per altri transport. ✅

**Logging**: su file `mcp-aria-memory-YYYY-MM-DD.log` in `.aria/runtime/logs/` — non su stdout per non corrompere il protocollo MCP. ✅

---

## 6. Context Lifecycle Manager (CLM) ❌ CRITICO

**Stato: ❌ NON OPERATIVO — CLM MAI ESEGUITO**

```
source: src/aria/memory/clm.py
```

### Cosa è implementato

Il CLM estrattivo (`clm.py`) è corretto come implementazione Sprint 1.1:

- `distill_session()` recupera T0 entries, applica pattern extractive, inserisce in T1 ✅
- `distill_range()` per range temporali ✅
- Processa SOLO `USER_INPUT` (corretto per P5) ✅
- Deduplicazione per `(source_id, text[:50])` ✅
- Pattern per: action_items, preference/decision, facts ✅
- `promote()` / `demote()` delegano a `SemanticStore` ✅

**Limitazione nota** (Sprint 1.1): distillazione puramente estrattiva (regex), non LLM-based. Il blueprint §5.4 implica distillazione semantica. Questa è una limitazione di fase, documentata in codice. Non è un bug.

### Il problema critico

**Il CLM non è mai stato invocato in produzione.** Evidenza:

```
T0 entries in episodic.db:  1005
T1 semantic_chunks:            0  ← ZERO
```

Il blueprint §5.4 specifica: *"trigger: post-session + scheduler ogni 6h"*.

**Causa**: Non esiste nessun Python scheduler task che invoca il CLM. Il compaction-agent è definito come agente KiloCode (`_system/compaction-agent.md`) ma:

1. Nessuna task schedulata nel database del scheduler (`aria-scheduler`) punta a `compaction-agent`
2. Nessun hook `post-session` nel gateway che triggeri la distillazione
3. Il tool MCP `distill` esiste ma deve essere chiamato esplicitamente (non automaticamente)

### Impatto operativo

- La funzione di `recall` non restituisce semantic chunks (T1 vuoto) — solo fallback su T0 FTS5
- Le keyword search sulla memoria semantica sono degradate a ricerca verbatim T0
- L'accumulo di T0 senza distillazione degrada la qualità del recall nel tempo

---

## 7. Sistema HITL ❌ CRITICO

**Stato: ❌ ENQUEUE-ONLY — NESSUN APPROVAL PATH**

```
source: src/aria/memory/mcp_server.py, src/aria/memory/episodic.py
```

### Cosa è implementato (enqueue)

- `forget(id)` → crea record in `memory_hitl_pending` con `action=forget_episodic` ✅
- `curate(id, forget)` → crea record con `action=forget_semantic` ✅
- `hitl_ask(action, target_id)` → crea record generico ✅
- `hitl_list_pending()` → lista pending records ✅
- `hitl_cancel(hitl_id)` → marca `status=cancelled` ✅

### Cosa manca (approval → execution)

**Non esiste nessun meccanismo per approvare una HITL request e eseguire l'azione consequente:**

1. **Nessun `hitl_approve` tool**: Il ciclo `list_pending → approve → execute` non è implementato
2. **`forget` non tombstona**: Chiama `enqueue_hitl()` ma non chiama mai `store.tombstone()`. Il record viene marcato pending e non succede nulla
3. **`curate(forget)` non cancella**: Analoga situazione per i chunk T1
4. **Nessun HITL responder per memory**: Il gateway ha `hitl_responder.py` per il gateway stesso, ma non gestisce HITL di memoria
5. **La code commenta**: *"Full HITL wiring in Sprint 1.2"* — la implementazione è riconosciuta incompleta

### Impatto operativo

- `aria memory forget` crea un record che non viene mai processato
- L'utente non può cancellare memoria tramite MCP tools — il sistema è di fatto append-only anche quando non dovrebbe esserlo
- Nessuna notification HITL raggiunge l'utente (Telegram, CLI)

---

## 8. Scheduler Integration e WAL Checkpoint

### CLM scheduling (❌ MANCANTE)

Come descritto in §6, il CLM non è schedulato. Non esiste nessun task in `aria-scheduler` che chiami `distill`.

### WAL checkpoint per episodic.db (⚠️ MANCANTE)

Il `TaskReaper` dello scheduler esegue `PRAGMA wal_checkpoint(TRUNCATE)` ogni 6h, ma solo sul database del **scheduler** (`scheduler.db`). Il WAL di `episodic.db` non viene mai checkpointato programmaticamente.

**Evidenza runtime:**
```
episodic.db-wal:  282KB  (ultimo write: 2026-04-24 00:29)
```

Il WAL cresce senza essere mai svuotato. Con `wal_autocheckpoint=1000` (default), SQLite dovrebbe fare auto-checkpoint a 1000 pagine (~1MB), quindi non è un problema immediato. Tuttavia:
- Il processo `aria-memory` viene avviato dal gateway MCP on-demand, non come daemon persistente
- Se il processo è short-lived, l'auto-checkpoint potrebbe non scattare
- La funzione `vacuum_wal()` su `EpisodicStore` esiste ma nessuno la chiama

---

## 9. Retention e Compressione

### T0 retention 365gg (❌ NON APPLICATA)

```
source: src/aria/config.py (config.memory.t0_retention_days = 365)
```

- La configurazione `t0_retention_days=365` è presente ✅
- Non esiste nessun codice in `EpisodicStore` o nel scheduler che applichi la retention ❌
- Le entry più vecchie di 365 giorni non vengono mai eliminate (nemmeno tombstonate)

### T1 compression 90gg (❌ NON IMPLEMENTATA)

```
source: src/aria/config.py (config.memory.t1_compression_after_days = 90)
```

- La configurazione `t1_compression_after_days=90` è presente ✅
- Non esiste codice di compressione per semantic chunks ❌

---

## 10. Review Queue (⚠️ PARZIALE)

**Stato: ⚠️ Architettura corretta, non auto-alimentata**

Il blueprint §5.7 specifica: *"entries con `actor=agent_inference` e `confidence < 0.7` vanno in review queue"*.

- `memory-curator` agent definito in `_system/memory-curator.md` ✅
- Può usare `recall`, `curate`, `hitl_ask`, `hitl_list_pending`, `hitl_cancel` ✅
- **Nessun meccanismo automatico** identifica i chunk `agent_inference + confidence < 0.7` e li invia alla review queue ❌
- Il CLM non genera chunk `agent_inference` (solo `USER_INPUT`) — la review queue non si riempirebbe comunque ❌
- Dipendenza circolare: serve prima che il CLM giri per avere dati da curare

---

## 11. Testing

### Unit Tests (✅ 32/32 passing)

```
tests/unit/memory/
├── test_schema.py          # EpisodicEntry, SemanticChunk, Actor, content_hash
├── test_episodic_store.py  # Insert, search, tombstone, WAL, stats
├── test_migrations.py      # MigrationRunner, checksum, idempotency
├── test_actor_tagging.py   # derive_actor, trust_score, aggregate
├── test_semantic_store.py  # Insert, search FTS5, promote, demote
├── test_clm.py             # distill_session, P5 compliance
└── test_mcp_server.py      # Tool paths (happy + error)
```

`uv run pytest -q tests/unit/memory/` → **32 passed in 1.45s** ✅

### Integration Tests (❌ ASSENTI)

Non esiste `tests/integration/memory/`. Nessun test verifica:

- Flusso E2E `remember → distill → recall` su DB reale
- HITL: `forget → approve → tombstone`
- CLM scheduling integration
- Retention pruning
- WAL checkpoint behavior

### Benchmark

`tests/benchmarks/memory_recall_p95.py` esiste — verifica latenza P95 recall. Non eseguito nel normale `pytest -q`.

---

## 12. Systemd e Deployment

**Stato: ✅ CONFORME**

```
source: systemd/aria-memory.service
```

- `Type=notify` + `WatchdogSec=60s` ✅
- `Restart=on-failure` + `RestartSec=5s` ✅
- Security hardening (NoNewPrivileges, ProtectSystem=strict, PrivateTmp, ecc.) ✅
- `ReadWritePaths=%h/coding/aria/.aria` per accesso al database ✅
- **Nota**: il servizio viene avviato dal gateway come processo MCP child (non standalone normalmente). Il .service file è per deployment standalone opzionale.

---

## 13. Backup

**Stato: ✅ SCRIPT ESISTE**

- `scripts/backup.sh` esiste e funziona ✅
- Crea tar cifrato con age in `~/.aria-backups/` ✅
- Nessuna automazione (nessun cron/systemd timer per il backup) ⚠️

---

## Tavola Riepilogativa Gap vs Spec

| Requisito Blueprint | Sezione | Stato | Gap |
|--------------------|---------|-------|-----|
| 5D memory taxonomy | §5.1 | ✅ | — |
| T0 SQLite WAL | §5.2 | ✅ | — |
| T1 FTS5 schema | §5.2 | ✅ | Schema OK, 0 dati |
| T2 LanceDB lazy | §5.2 | ✅ stub | — |
| T3 graph @fase2 | §5.2 | ✅ stub | — |
| Actor-aware tagging | §5.3 | ✅ | — |
| CLM distillazione | §5.4 | ❌ | Mai eseguito |
| CLM trigger 6h | §5.4 | ❌ | Non schedulato |
| CLM post-session | §5.4 | ❌ | Nessun hook |
| Schema Pydantic | §5.5 | ✅ | — |
| MCP tools 7 spec + 3 HITL | §5.6 | ✅ | — |
| Retention T0 365gg | §5.7 | ❌ | Config solo, no enforcement |
| T1 compression 90gg | §5.7 | ❌ | Non implementato |
| Review queue auto | §5.7 | ❌ | Curator esiste ma non schedulato |
| Backup | §5.7 | ⚠️ | Script ok, no automazione |
| P5 actor-aware | P5 | ✅ | — |
| P6 verbatim | P6 | ✅ | — |
| P7 HITL gating enqueue | P7 | ✅ | Enqueue ok |
| P7 HITL gating execute | P7 | ❌ | No approval path |
| WAL checkpoint episodic.db | §6.1.1 | ⚠️ | Reaper checkpoint scheduler.db only |
| SQLite >= 3.51.3 | ADR-0002 | ✅ | 3.51.3 esatto |
| No pickle T3 | ADR-0004 | ✅ | — |

---

## Raccomandazioni Prioritizzate

### P0 — Blocca funzionalità core

**1. Schedulare il CLM ogni 6h**

```python
# In aria-scheduler seeds o post-init del daemon:
# Aggiungere task tipo:
{
    "name": "memory-distill",
    "category": "memory",
    "trigger_type": "cron",
    "schedule_cron": "0 */6 * * *",
    "payload": {"sub_agent": "compaction-agent", "prompt": "distill recent sessions"}
}
```

Alternativa rapida: aggiungere hook nel gateway che chiami `distill(session_id)` al termine di ogni sessione.

**2. Implementare HITL approval path**

```python
# Aggiungere a mcp_server.py:
@mcp.tool
async def hitl_approve(hitl_id: str) -> dict:
    # 1. Legge record da memory_hitl_pending
    # 2. Se action=forget_episodic → store.tombstone(target_id)
    # 3. Se action=forget_semantic → semantic.delete(target_id)
    # 4. Marca resolved in memory_hitl_pending
```

### P1 — Affidabilità

**3. WAL checkpoint per episodic.db**

Aggiungere al `TaskReaper` o a un task scheduler separato:

```python
# Alternativa: aggiungere un scheduled task in aria-scheduler
# oppure modificare reaper per fare checkpoint anche di episodic.db
episodic_store = await create_episodic_store(config)
await episodic_store.vacuum_wal()
```

**4. Retention enforcement T0**

```python
# In EpisodicStore, aggiungere:
async def prune_old_entries(self, retention_days: int) -> int:
    cutoff = int((datetime.now(UTC).timestamp()) - retention_days * 86400)
    cursor = await conn.execute(
        "INSERT INTO episodic_tombstones (episodic_id, tombstoned_at, reason) "
        "SELECT id, ?, 'retention_expired' FROM episodic WHERE ts < ? "
        "AND id NOT IN (SELECT episodic_id FROM episodic_tombstones)",
        (int(time.time()), cutoff)
    )
    return cursor.rowcount
```

### P2 — Completezza

**5. Integration tests per memory**

Creare `tests/integration/memory/` con test E2E:
- `test_remember_distill_recall.py`
- `test_hitl_forget_approve.py`
- `test_retention_pruning.py`

**6. Backup scheduling**

Aggiungere systemd timer o task scheduler per `scripts/backup.sh` settimanale.

**7. T1 compression 90gg**

Quando il CLM sarà operativo, implementare soft-compression dei semantic chunks dopo 90gg (merge chunks simili, riduzione occurrences).

---

## Stato Conforme alle Ten Commandments

| Commandment | Stato |
|-------------|-------|
| P1 Isolation First | ✅ memoria in `.aria/runtime/memory/` |
| P2 Upstream Invariance | ✅ solo FastMCP + aiosqlite standard |
| P3 Polyglot Pragmatism | ✅ Python layer |
| P4 Local-First | ✅ tutto on-disk |
| P5 Actor-Aware | ✅ piena conformità |
| P6 Verbatim Preservation | ✅ no UPDATE, tombstone only |
| P7 HITL on Destructive | ⚠️ enqueue OK, approve mancante |
| P8 Tool Priority Ladder | ✅ MCP tools esposti |
| P9 Scoped Toolsets | ✅ 10 tool ≤ 20 |
| P10 Self-Documenting | ✅ ADR-0004 presente |

---

*Report generato da: Claude (claude-sonnet-4-6) su analisi di `src/aria/memory/`, blueprint §5, e database runtime live.*
*Wiki da aggiornare: `docs/llm_wiki/wiki/memory-subsystem.md`*
