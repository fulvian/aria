---
title: Scheduler
sources:
  - docs/foundation/aria_foundation_blueprint.md §6
  - docs/foundation/decisions/ADR-0005-scheduler-concurrency.md
  - docs/foundation/decisions/ADR-0008-systemd-user-capability-limits.md
last_updated: 2026-04-23
tier: 1
---

# Scheduler & Autonomia

## Task Store SQLite

**File**: `.aria/runtime/scheduler/scheduler.db`

### Tabelle principali

| Tabella | Scopo |
|---------|-------|
| `tasks` | Definizione task (cron/oneshot/manual), status, policy, budget |
| `task_runs` | Storico esecuzioni con outcome, tokens, cost |
| `dlq` | Dead Letter Queue per task falliti definitivamente |
| `hitl_pending` | Richieste HITL in attesa di risposta umana |

*source: `docs/foundation/aria_foundation_blueprint.md` §6.1*

### Stati task

`active` → `paused` → `completed` / `failed` / `dlq`

### Policy gate values

| Policy | Comportamento |
|--------|--------------|
| `allow` | Esegue senza chiedere (task safe, read-only) |
| `ask` | Apre HITL pending, notifica Telegram/CLI, aspetta risposta (timeout 15min) |
| `deny` | Non esegue, logga |

Default per categoria: `search=allow`, `workspace.read=allow`, `workspace.write=allow`, `workspace.destructive=ask`, `memory.forget=ask`

*source: `docs/foundation/aria_foundation_blueprint.md` §6.4*

## Tipi di Trigger

| Tipo | Descrizione | Esempio |
|------|-------------|---------|
| `cron` | Espressione cron 5-field | `0 8 * * *` = ogni giorno 08:00 |
| `event` | Internal event bus | Memoria semantica soglia, DLQ |
| `webhook` | HTTP endpoint con HMAC auth | Trigger esterni |
| `oneshot` | Eseguito una volta a `next_run_at` | Task singoli |
| `manual` | Solo via CLI o Telegram `/run` | Ad-hoc |

*source: `docs/foundation/aria_foundation_blueprint.md` §6.2*

## Lease-Based Concurrency (ADR-0005)

Il scheduler supporta istanze multiple per HA con lease-based locking:

```
tasks.lease_owner TEXT           -- NULL = unleased
tasks.lease_expires_at INTEGER  -- epoch ms
```

- **TTL default**: 300 secondi (5 minuti)
- **Heartbeat**: refresh ogni 60s per task lunghi
- **Reaper**: background process ogni 30s rilascia lease scaduti
- **Worker ID format**: `scheduler-{pid}-{8-char-random-hex}`
- **Acquisizione atomica**: singola UPDATE statement con subquery

*source: `docs/foundation/decisions/ADR-0005-scheduler-concurrency.md`*

## Budget Gate

Ogni task ha budget opzionali:
- `budget_tokens` per run (es. 50.000)
- `budget_cost_eur` per run
- Aggregato `category_daily_budget_tokens` in config

Violazione → `outcome=blocked_budget`, task in pausa 24h, notifica utente.

*source: `docs/foundation/aria_foundation_blueprint.md` §6.3*

## DLQ e Retry

- Dopo `max_retries` (default 3) fallimenti consecutivi → `status=dlq`
- DLQ check ogni 60s; task in DLQ non ri-provati automaticamente
- Recovery manuale: `aria schedule replay <id>`

*source: `docs/foundation/aria_foundation_blueprint.md` §6.5*

## Systemd Integration

Servizio `aria-scheduler.service` con:
- `Type=notify` + `WatchdogSec=60s`
- `sd_notify('WATCHDOG=1')` ogni ~30s
- Hardening: `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, ecc.
- **ADR-0008**: `PrivateDevices` e `ProtectKernelModules` rimossi per compatibilità desktop `--user`

*source: `docs/foundation/decisions/ADR-0008-systemd-user-capability-limits.md`*

## Implementazione Codice

```
src/aria/scheduler/
├── __init__.py
├── daemon.py          # systemd entrypoint
├── store.py           # SQLite tasks/runs/dlq
├── schema.py          # Pydantic models
├── triggers.py        # cron/event/webhook/oneshot/manual + EventBus
├── budget_gate.py     # Budget enforcement
├── policy_gate.py     # Policy allow/ask/deny
├── hitl.py            # HITL manager
├── runner.py          # Task execution
├── reaper.py          # Stale lease reaper
├── notify.py          # sd_notify watchdog
└── cli.py             # CLI interface
```

## CLI Scheduler

```bash
aria schedule list                    # Lista task attivi
aria schedule add --name X --cron ... # Aggiungi task
aria schedule remove <id>             # Rimuovi task
aria schedule run <id>                # Esegui manualmente
aria schedule replay <id>             # Replay da DLQ
aria schedule status --verbose        # Status dettagliato
```

## Vedi anche

- [[gateway]] — HITL via Telegram
- [[memory-subsystem]] — CLM scheduling
- [[credentials]] — Budget per provider
