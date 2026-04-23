---
title: Memory Subsystem
sources:
  - docs/foundation/aria_foundation_blueprint.md §5
  - docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md
last_updated: 2026-04-23
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

| Tier | Scopo | Backend | Latenza target | Abilitato |
|------|-------|---------|----------------|-----------|
| **T0** | Raw verbatim episodic | SQLite (WAL mode) | <10ms | MVP |
| **T1** | Summaries + FTS5 | SQLite FTS5 | <50ms | MVP |
| **T2** | Embeddings semantici | LanceDB (lazy-created) | <200ms | MVP (opzionale) |
| **T3** | Grafo associativo | SQLite graph tables | <500ms | Fase 2 |

**Regola chiave (P6)**: T0 è **autoritativo e immutabile**. T1/T2/T3 sono **derivati** e ricostruibili da T0 ri-eseguendo il CLM.

*source: `docs/foundation/aria_foundation_blueprint.md` §5.2*

**ADR-0004**: È vietato usare `pickle` come storage canonico per T3. Formati ammessi: SQLite, JSON, Parquet.

*source: `docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md`*

## Actor-Aware Tagging

Ogni memory unit ha un campo `actor` con 4 valori possibili:

| Actor | Trust | Descrizione |
|-------|-------|-------------|
| `user_input` | Massimo | Messaggio originale dell'utente |
| `tool_output` | Alto | Output verificabile di un tool (API response) |
| `agent_inference` | Condizionato | Deduzione/ipotesi dell'LLM — **non promuovibile automaticamente** a fatto |
| `system_event` | Metadato | Log di sistema (avvii, errori) |

**Regola di promozione**: Per promuovere `agent_inference` a fatto semantico serve (a) un secondo riscontro da `tool_output`, oppure (b) conferma esplicita `user_input`.

*source: `docs/foundation/aria_foundation_blueprint.md` §5.3*

## Context Lifecycle Manager (CLM)

Processo asincrono che:

1. **Scansiona T0** (ultime N conversazioni chiuse)
2. **Distilla** → genera summary tipizzati (persone, fatti, decisioni, action items)
3. **Promuove** in T1 (FTS5) con actor tagging preservato
4. **(Opzionale)** genera embedding T2 per gli item più "caldi"
5. **Non cancella mai T0**

Implementato come sub-agente `compaction-agent`. Trigger: post-session + scheduler ogni 6h.

*source: `docs/foundation/aria_foundation_blueprint.md` §5.4*

## ARIA-Memory MCP Server

**Modulo**: `src/aria/memory/mcp_server.py` (FastMCP)

| Tool | Input | Output | Note |
|------|-------|--------|------|
| `remember` | `content`, `actor`, `role`, `session_id`, `tags[]` | `EpisodicEntry` | Scrive T0 |
| `recall` | `query`, `top_k`, `kinds?`, `since?`, `until?` | `list[SemanticChunk\|EpisodicEntry]` | Prima FTS5, poi vettoriale |
| `recall_episodic` | `session_id` OR `since`, `limit` | `list[EpisodicEntry]` | Cronologico |
| `distill` | `session_id` | `list[SemanticChunk]` | Trigger CLM on-demand |
| `curate` | `id`, `action=promote\|demote\|forget` | `ok` | HITL-gated |
| `forget` | `id` | `ok` | Soft delete + tombstone |
| `stats` | — | `{t0_count, t1_count, ...}` | Telemetria |
| `hitl_ask` | `question`, `options` | HITL pending | Creazione richiesta |
| `hitl_list_pending` | — | `list[HitlPending]` | Lista pending |
| `hitl_cancel` | `id` | `ok` | Cancellazione |

Le chiamate `curate(action=forget)` e `forget` richiedono **HITL** (P7).

*source: `docs/foundation/aria_foundation_blueprint.md` §5.6*

## Implementazione Codice

```
src/aria/memory/
├── __init__.py
├── schema.py          # Pydantic models (EpisodicEntry, SemanticChunk, etc.)
├── episodic.py        # SQLite raw + FTS5
├── semantic.py        # LanceDB wrapper
├── clm.py             # Context Lifecycle Manager
├── actor_tagging.py   # Actor tagging utilities
├── mcp_server.py      # FastMCP ARIA-Memory server
├── migrations.py      # Schema migrations
└── migrations/        # SQL migration files
```

## Governance Memoria

- **Retention default**: T0 conservato 365 giorni, T1 indefinitamente (compresso dopo 90gg)
- **Oblio programmato**: `aria memory forget --session=<id>` con HITL
- **Review queue**: entries con `actor=agent_inference` e `confidence < 0.7` → review queue utente
- **Backup**: `scripts/backup.sh` dump SQLite + tar cifrato age

*source: `docs/foundation/aria_foundation_blueprint.md` §5.7*

## Vedi anche

- [[ten-commandments]] — P5 (Actor-Aware), P6 (Verbatim)
- [[scheduler]] — CLM scheduling
- [[agents-hierarchy]] — Compaction-Agent, Memory-Curator
