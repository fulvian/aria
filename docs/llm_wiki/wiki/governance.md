---
title: Governance & Observability
sources:
  - docs/foundation/aria_foundation_blueprint.md §14
  - docs/foundation/aria_foundation_blueprint.md §17
last_updated: 2026-04-23
tier: 1
---

# Governance & Observability

## Logging (Structured JSON)

- **Formato**: JSON line, UTC ISO8601, `level`, `logger`, `event`, `context{}`
- **Destinazioni**: File giornaliero in `.aria/runtime/logs/`; stdout se interactive
- **Livelli**: DEBUG|INFO|WARN|ERROR|CRITICAL (default: INFO)
- **Correlation**: `trace_id` propagato Gateway → Conductor → Sub-Agent → Tool
- **Mai loggare**: secrets, tokens, raw credential payloads
- **Retention**: log rotation giornaliera

*source: `docs/foundation/aria_foundation_blueprint.md` §14.1*

## Metriche Prometheus

Endpoint `http://127.0.0.1:9090/metrics` (bind `127.0.0.1`, no `0.0.0.0`):

| Metrica | Tipo | Descrizione |
|---------|------|-------------|
| `aria_tasks_total{category,status}` | Counter | Task per categoria e stato |
| `aria_task_duration_seconds{category}` | Histogram | Durata esecuzione task |
| `aria_tokens_used_total{model,provider}` | Counter | Token consumati |
| `aria_memory_entries_total{tier}` | Gauge | Entry memoria per tier |
| `aria_credential_circuit_state{provider,key_id}` | Gauge | Stato circuit breaker (0/1/2) |
| `aria_hitl_pending_total` | Gauge | HITL requests in attesa |

*source: `docs/foundation/aria_foundation_blueprint.md` §14.2*

## Security Policy

- **Nessun accesso root**: tutto in user space
- **No-destroy without HITL** (P7): delete, overwrite, send → default `ask`
- **Nessuna esfiltrazione silenziosa**: tool esterni verso domini non in whitelist → warn loggato
- **Prompt injection mitigation** (ADR-0006): tool output in `<<TOOL_OUTPUT>>` frame
- **Sandbox** (Fase 2): esecuzione script in container Docker

*source: `docs/foundation/aria_foundation_blueprint.md` §14.3*

## Backup

Script: `scripts/backup.sh`
- tar di `.aria/runtime/` + `.aria/credentials/`
- Cifrato con age (chiave backup pubblica)
- Depositato in `~/.aria-backups/`
- Retention: 30 giorni
- Schedulato daily: `aria schedule add --cron '0 3 * * *' --name daily-backup`

Restore: `scripts/restore.sh` — stop services → copy → verify.

*source: `docs/foundation/aria_foundation_blueprint.md` §14.4*

## ADR Workflow

**Directory**: `docs/foundation/decisions/`
**Naming**: `ADR-NNNN-<slug>.md`
**Stati**: `Proposed` → `Accepted` | `Rejected` | `Superseded by ADR-MMMM`
**Template**: Blueprint §18.D

Ogni ADR che impatta una sezione del blueprint → PR che modifica sia il blueprint sia crea l'ADR.

*source: `docs/foundation/aria_foundation_blueprint.md` §17.2*

## Blueprint-Keeper Skill

Skill di sistema schedulata (`cron: '0 10 * * 0'` — domenica 10:00):

1. Legge blueprint, verifica file referenziati esistano
2. Scansiona `src/aria/**/*.py` per divergenze
3. Confronta agents/skills nel filesystem con §8–§9
4. Se divergenza → genera ADR draft + PR (batch max 1/settimana, max 3 sezioni)
5. Notifica utente via Telegram

*source: `docs/foundation/aria_foundation_blueprint.md` §17.3*

## Section Frontmatter Policy

Ogni sezione blueprint ha: `status` (draft|ratified|implemented|deprecated), `last_review`, `owner`.
Sezioni `implemented` DEVONO linkare i file/moduli che le implementano.

*source: `docs/foundation/aria_foundation_blueprint.md` §17.1*

## Vedi anche

- [[adrs]] — Sommario di tutti gli ADR
- [[ten-commandments]] — P7 (HITL), P10 (Self-Documenting)
- [[credentials]] — Audit logging credenziali
- [[quality-gates]] — Quality gates CI
