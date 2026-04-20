---
document: ARIA Phase 1 Implementation Plan — Overview
version: 1.1.0
status: in_progress
date_created: 2026-04-20
last_review: 2026-04-20
owner: fulvio
phase: 1
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
previous_phase_plan: docs/plans/phase-0/sprint-00.md
---

# ARIA — Phase 1 (MVP) — Implementation Plan Overview

## Stato avanzamento (aggiornato al 2026-04-20)

- Sprint 1.1: implementato e verificato, con evidence pack in `docs/implementation/phase-1/sprint-01-evidence.md`.
- Sprint 1.2: pronto ad avvio (dipendenze sprint rispettate).
- Stato Phase 1: **in progress** (Go/No-Go Phase 1 non ancora valutabile fino a chiusura Sprint 1.4).

## 0) Come leggere questi documenti

Questo README e i quattro file `sprint-01.md`..`sprint-04.md` costituiscono insieme il **piano canonico di Phase 1**. Il file `aria_foundation_blueprint.md` rimane la **stella polare** (§0.1, §16); in caso di conflitto fra blueprint e piano, vince il blueprint e l'incoerenza DEVE essere risolta con ADR + aggiornamento di entrambi i documenti.

Ogni sprint ha la stessa struttura:
1. Obiettivo, scope, vincoli
2. Pre-requisiti (dipendenze da sprint/phase precedenti)
3. Work Breakdown Structure (WBS) con path file, signature API, schema, esempi
4. Piano giorni (5 giorni lavorativi per sprint)
5. Exit criteria sprint
6. Deliverable checklist (Definition of Done)
7. Quality gates e verifiche (comandi eseguibili)
8. Risk register con mitigazioni
9. ADR collegati
10. Tracciabilita blueprint -> task
11. Note anti-deriva per LLM implementatore (istruzioni prescrittive su nomi, path, librerie da NON reinventare)

## 1) Obiettivo Phase 1 (riepilogo blueprint §15)

Rendere ARIA **operativa end-to-end su Telegram**, con:
- Credential Manager unificato (SOPS+age + keyring + circuit breaker)
- Memoria Tier 0 (raw verbatim) + Tier 1 (FTS5) + CLM base
- ARIA-Memory MCP server esposto a KiloCode
- Scheduler autonomo (cron/oneshot, budget/policy gate, HITL, DLQ) come `systemd --user`
- Gateway Telegram (PTB 22.x, polling) con sessioni persistite e whitelist
- ARIA-Conductor + Search-Agent con 4 provider (Tavily, Brave, Firecrawl, Exa)
- Workspace-Agent con Google Workspace MCP + OAuth PKCE

Criterio di successo Phase 1: **i 5 casi d'uso MVP del blueprint §1.4** funzionano end-to-end, interamente guidati da Telegram o CLI.

## 2) Vincoli inderogabili per l'intera Phase 1

Dal blueprint §16 (Ten Commandments):
- **P1 Isolation First** — tutto sotto `/home/fulvio/coding/aria/`; nessun tool tocca `$HOME/.config/kilocode/` globale.
- **P2 Upstream Invariance** — `kilocode`, `google_workspace_mcp`, `@brave/brave-search-mcp-server` sono **dipendenze pinnate, non modificate**. Forbidden: patch upstream in-place.
- **P3 Polyglot Pragmatism** — tutto il layer ARIA e Python 3.11+; MCP server e wrapper scritti in Python con FastMCP 3.x. Nessun Node code nativo ARIA.
- **P4 Local-First** — DB SQLite locali, credenziali SOPS+age e keyring. Cloud solo per LLM e API esterne whitelisted.
- **P5 Actor-Aware Memory** — ogni `EpisodicEntry.actor` ∈ {`user_input`, `tool_output`, `agent_inference`, `system_event`}. Forbidden: inferenze promosse a fatti senza secondo riscontro.
- **P6 Verbatim Preservation** — T0 (`episodic` table) è **immutabile e autoritativo**. Distillazioni in T1 sono ricostruibili da T0.
- **P7 HITL on Destructive Actions** — ogni scrittura Google Workspace, ogni `forget`, ogni superamento budget deve generare `hitl_pending` o essere bloccato.
- **P8 Tool Priority Ladder** — MCP server maturo > skill markdown > script Python. Documentare in ADR ogni deviazione.
- **P9 Scoped Toolsets ≤ 20** — `allowed-tools` di ogni agente deve avere ≤20 entry (contare i wildcard in modo conservativo).
- **P10 Self-Documenting Evolution** — ogni drift dal blueprint e ADR nuovo.

## 3) Pre-requisiti Phase 1 (output Phase 0)

Stato confermato chiuso (vedi §18.G blueprint e `docs/plans/phase-0/sprint-00.md`):

- [x] Directory `/home/fulvio/coding/aria/` con layout §4.1
- [x] `bin/aria` launcher con subcommand `repl|run|mode|schedule|gateway|memory|creds|backup`
- [x] `.aria/kilocode/` con `kilo.json`, `mcp.json`, agents/skills placeholder
- [x] `pyproject.toml` + `uv.lock` con dipendenze Phase 1 (fastmcp, PTB 22.x, aiosqlite, keyring, tenacity, croniter, faster-whisper, sd-notify)
- [x] Skeleton `src/aria/{credentials,memory,scheduler,gateway,agents,tools,utils}`
- [x] SOPS+age configurato, `.sops.yaml` in git, chiavi age in `~/.config/sops/age/keys.txt`
- [x] `systemd/aria-{scheduler,gateway,memory}.service` verificati con `systemd-analyze verify`
- [x] `docs/foundation/schemas/sqlite_full.sql` presente
- [x] ADR-0001 (Dependency Baseline) e ADR-0002 (SQLite Reliability) accettati
- [x] SQLite runtime ≥ 3.51.3 installato

**Se uno qualsiasi di questi pre-requisiti non fosse vero**, fermarsi e chiudere Phase 0 prima di iniziare Sprint 1.1.

## 4) Struttura sprint (6-8 settimane, 4 sprint da ~5 giorni)

| Sprint | Tema                                  | File piano               | Focus moduli                                                      |
|--------|---------------------------------------|--------------------------|-------------------------------------------------------------------|
| 1.1    | Credential Manager + Memory T0/T1     | `sprint-01.md`           | `src/aria/credentials/`, `src/aria/memory/`                       |
| 1.2    | Scheduler + Gateway Telegram          | `sprint-02.md`           | `src/aria/scheduler/`, `src/aria/gateway/`                        |
| 1.3    | ARIA-Conductor + Search-Agent         | `sprint-03.md`           | `.aria/kilocode/agents/`, `.aria/kilocode/skills/`, `src/aria/agents/search/` |
| 1.4    | Workspace-Agent + E2E MVP             | `sprint-04.md`           | `src/aria/agents/workspace/`, `scripts/oauth_first_setup.py`      |

Stato operativo sprint:

- [x] Sprint 1.1 chiuso con quality gates e benchmark recall p95 verde.
- [ ] Sprint 1.2 da completare.
- [ ] Sprint 1.3 da completare.
- [ ] Sprint 1.4 da completare.

Ogni sprint finisce con una **demo verificabile** e un **evidence pack** (output comandi gate + log/screenshot).

### 4.1 Dipendenze fra sprint

```
sprint-01 (creds + memory) ─┬─> sprint-02 (scheduler + gateway) ─┬─> sprint-03 (conductor + search)
                            │                                    │
                            └──────────────────────────────────> └─> sprint-04 (workspace + E2E)
```

- Sprint 1.2 dipende da credential manager per `ARIA_TELEGRAM_BOT_TOKEN`.
- Sprint 1.3 dipende da memoria (per `aria-memory/recall`) e da credential manager (per API keys Tavily/Brave/Firecrawl/Exa).
- Sprint 1.4 dipende da scheduler (triage email schedulato) e gateway (HITL Telegram) e conductor (delega al Workspace-Agent).

## 5) Quality gates trasversali (applicati alla fine di ogni sprint)

Comandi gate obbligatori (devono tornare verdi prima di chiudere sprint):

```bash
# Static analysis
uv run ruff check .
uv run ruff format --check .
uv run mypy src

# Tests (coverage mirata per sprint)
uv run pytest -q --cov=aria --cov-report=term-missing

# Bootstrap/isolation smoke
./scripts/bootstrap.sh --check
./bin/aria --help
sqlite3 --version    # deve essere >= 3.51.3

# Systemd templates (solo in sprint 1.2+)
systemd-analyze verify systemd/aria-*.service
```

Target coverage Phase 1:
- `src/aria/credentials/`: ≥ 85%
- `src/aria/memory/`: ≥ 80%
- `src/aria/scheduler/`: ≥ 75%
- `src/aria/gateway/`: ≥ 70%
- `src/aria/agents/`: ≥ 60% (dominio I/O-heavy)

## 6) Quality gates quantitativi Phase 1 (blueprint §15)

Devono essere **tutti verdi** prima di dichiarare Phase 1 completata:

| Metrica                              | Target                | Come misurare                             |
|--------------------------------------|-----------------------|-------------------------------------------|
| p95 recall memoria (T0+T1)           | < 250ms               | Test benchmark su dataset baseline (1k messaggi, 200 query) |
| DLQ rate scheduler                   | < 2% rolling 7gg      | `SELECT count(*) FROM dlq / count(*) FROM task_runs` |
| HITL timeout rate                    | < 5% richieste `ask`  | `SELECT count(*) WHERE resolved_at IS NULL AND expires_at < now() / count(*)` |
| Provider degradation rate            | < 15% query search    | Contatori provider `circuit_state != closed` |
| Scheduler success rate               | > 98% task `allow`    | `outcome='success' / total` su task con `policy='allow'` |

Gli SLO sopra sono **condizione di uscita** per il Go/No-Go Phase 1 (§12).

## 7) ADR da finalizzare in Phase 1

Gli ADR-0001 e ADR-0002 sono gia accettati in Phase 0. Phase 1 DEVE chiudere:

- **ADR-0003 — OAuth Security Posture**: PKCE-first, `client_secret` opzionale, scope minimi, keyring per refresh token, revoca esplicita. Chiudere in Sprint 1.4 prima del merge Workspace-Agent.
- **ADR-0004 — Associative Memory Persistence Format**: no-pickle per storage canonico; scelta formato (SQLite graph tables vs Parquet vs engine dedicato). Chiudere prima della Fase 2, ma redatto come `Proposed` in Sprint 1.1 per bloccare drift.
- **ADR-0005 (nuovo) — Scheduler Concurrency Model**: strategia di locking/leasing per impedire doppia esecuzione task (es. `advisory lock` SQLite, lease token in `tasks` row). Chiudere in Sprint 1.2.
- **ADR-0006 (nuovo) — Prompt Injection Mitigation**: frame `<<TOOL_OUTPUT>>...<</TOOL_OUTPUT>>` obbligatorio, system prompt template per Conductor, sanitization skill. Chiudere in Sprint 1.3.
- **ADR-0007 (nuovo) — STT Stack Dual (faster-whisper + openai-whisper fallback)**: solo se in Sprint 1.2 si abilita voice transcription.

Regola operativa: **nessun merge main senza ADR accepted** se il PR introduce una delle decisioni sopra.

## 8) Osservabilita e logging (requisito trasversale)

Tutti i moduli Phase 1 DEVONO usare `src/aria/utils/logging.py` (da creare in Sprint 1.1). Requisiti:

- JSON line su file giornaliero `.aria/runtime/logs/<component>-YYYY-MM-DD.log`, stdout se interactive (TTY).
- Campi obbligatori: `ts` (ISO8601 UTC), `level`, `logger`, `event`, `context` (dict), `trace_id`.
- `trace_id` propagato Gateway -> Conductor -> Sub-Agent -> Tool via `contextvars.ContextVar`.
- Log rotation: `.log.gz` dopo 1 giorno; retention 90 giorni.
- Rediaction: chiavi API, token, refresh_token mascherati come `***<last4>`.

Metriche Prometheus-ready (endpoint opzionale `127.0.0.1:9090/metrics`) attivato in Sprint 1.2:
- `aria_tasks_total{category,status}` counter
- `aria_task_duration_seconds{category}` histogram
- `aria_tokens_used_total{model,provider}` counter
- `aria_memory_entries_total{tier}` gauge
- `aria_credential_circuit_state{provider,key_id}` gauge
- `aria_hitl_pending_total` gauge

## 9) Testing policy Phase 1

Tre livelli di test con ruoli distinti:

1. **Unit test** (`tests/unit/<module>/`): mock I/O (filesystem, DB, HTTP). Target: ≥80% branch coverage su logic modules (schema, circuit breaker, routers).
2. **Integration test** (`tests/integration/`): DB reale (SQLite tmp), MCP server in-process, provider stub via `respx` (httpx mock). No rete esterna. Marker: `@pytest.mark.integration`.
3. **E2E test** (`tests/e2e/`, da aggiungere in Sprint 1.4): gateway Telegram con `pytest-asyncio` e `PTBTestApp`; invocazione conductor child-session via `aria run`. Marker: `@pytest.mark.e2e`.

Regole:
- **Nessun test pua chiamare rete esterna reale** (Tavily, Google, Telegram). Fixtures VCR o stub hardcoded.
- **Nessun test pua scrivere fuori `tmp_path`**.
- **Nessun test pua richiedere SOPS key fisica**: usare age key di test generata in `tests/fixtures/age/test_key.txt`.

## 10) Sequenza di esecuzione consigliata Phase 1

1. Chiudere Sprint 1.1 (credentials + memory) prima di avviare qualsiasi scheduler/gateway
2. Chiudere Sprint 1.2 (scheduler + gateway + HITL) prima di avviare sub-agenti
3. In Sprint 1.3, avviare con **Search-Agent** prima di collegarlo al Conductor, per isolare bug
4. In Sprint 1.4, Workspace-Agent su un account Google di test (non primario) fino a fine sprint, poi migrazione a primary
5. Chiudere Phase 1 con **demo dei 5 casi d'uso §1.4 blueprint** dal vivo (anche solo registrata) prima di dichiarare GO

## 11) Documentazione richiesta (parallela al codice)

Durante Phase 1 mantenere aggiornati:

- `docs/implementation/phase-1/README.md` — index degli artefatti di ogni sprint (link a commit/PR principali)
- `docs/operations/runbook.md` — procedure di avvio/stop/restart daemon, troubleshooting tipico
- `docs/operations/provider_exhaustion.md` — runbook degradation search (Sprint 1.3)
- `docs/operations/disaster_recovery.md` — restore da backup (chiudere in Sprint 1.4)
- Implementation Log append-only in `aria_foundation_blueprint.md` §18.G (una entry per sprint chiuso)

## 12) Criterio di uscita Phase 1 (Go/No-Go)

**GO** solo se TUTTE sono vere:

- [ ] Tutti i deliverable dei 4 sprint sono chiusi al 100%
- [ ] Quality gates trasversali (§5) verdi
- [ ] SLO quantitativi (§6) raggiunti su dataset reale
- [ ] ADR-0003 (OAuth Security), ADR-0005 (Scheduler Concurrency), ADR-0006 (Prompt Injection) accettati
- [ ] 5 casi d'uso MVP §1.4 blueprint dimostrati end-to-end su Telegram
- [ ] Nessun incident di sicurezza aperto (leak chiavi, scope OAuth sovradimensionati, `ReadWritePaths` systemd troppo larghi)
- [ ] Backup `scripts/backup.sh` schedulato e verificato con restore reale
- [ ] `blueprint-keeper` ha runnato almeno una volta senza trovare drift

**NO-GO** se anche uno solo degli item sopra fallisce. In caso NO-GO: **non iniziare Phase 2**, aprire ADR con piano di rimedio e aggiungere uno `sprint-05.md` di remediation.

## 13) Tracciabilita blueprint -> sprint

| Sezione blueprint | Sprint principale | Sprint secondari |
|-------------------|-------------------|------------------|
| §5 Memoria 5D     | Sprint 1.1        | Sprint 1.3 (recall in conductor) |
| §6 Scheduler      | Sprint 1.2        | Sprint 1.4 (triage schedulato)   |
| §7 Gateway        | Sprint 1.2        | Sprint 1.4 (HITL Workspace)      |
| §8 Gerarchia agenti | Sprint 1.3      | Sprint 1.4 (workspace-agent)     |
| §9 Skills         | Sprint 1.3 (deep-research, planning-with-files, pdf-extract) | Sprint 1.4 (triage-email, calendar-orchestration, doc-draft) |
| §10 MCP ecosystem | Sprint 1.1 (aria-memory) | Sprint 1.3 (tavily, brave, firecrawl, exa), Sprint 1.4 (google_workspace) |
| §11 Search agent  | Sprint 1.3        | —                                |
| §12 Workspace agent | Sprint 1.4      | —                                |
| §13 Credentials   | Sprint 1.1        | Sprint 1.4 (OAuth keyring)       |
| §14 Osservabilita | Sprint 1.1 (logging base) | Sprint 1.2 (metrics), tutti gli sprint |
| §16 Ten Commandments | tutti          | tutti                             |
| §17 Auto-update blueprint | —          | chiusura Phase 1                 |

## 14) Note prescrittive per l'LLM implementatore (anti-allucinazione)

**Queste regole valgono per TUTTI gli sprint Phase 1.** L'agente LLM che implementa DEVE rispettarle alla lettera; ogni deviazione richiede ADR.

### 14.1 Stack e librerie — usare ESATTAMENTE queste

| Ambito             | Libreria/tool       | Versione pin (semver range)  | Fonte autoritativa                      |
|--------------------|---------------------|------------------------------|-----------------------------------------|
| MCP server custom  | `fastmcp`           | `>=3.2,<4.0`                 | https://gofastmcp.com/                  |
| Telegram bot       | `python-telegram-bot` | `>=22.0,<23.0` (async `Application`) | https://docs.python-telegram-bot.org/  |
| SQLite async       | `aiosqlite`         | `>=0.19`                     | https://pypi.org/project/aiosqlite/     |
| Vector store (lazy) | `lancedb`          | `>=0.30,<0.31`               | https://docs.lancedb.com                |
| Crypto primitives  | `cryptography`      | `>=42.0`                     |                                          |
| Keyring (Linux)    | `keyring` + `secretstorage` | `>=25.0`             | https://pypi.org/project/keyring/       |
| HTTP client        | `httpx`             | `>=0.27` (async)             |                                          |
| Retry/circuit      | `tenacity`          | `>=8.2`                      |                                          |
| Cron               | `croniter`          | `>=2.0`                      |                                          |
| STT locale         | `faster-whisper`    | `>=1.2,<2.0`                 |                                          |
| OCR                | `pytesseract`       | `>=0.3`                      |                                          |
| Systemd watchdog   | `sd-notify`         | `>=0.1`                      |                                          |
| CLI                | `typer`, `rich`     | come in `pyproject.toml`     |                                          |
| SOPS               | CLI binary `sops`   | `>=3.8`                      | https://github.com/getsops/sops          |
| age                | CLI binary `age`    | latest stable                | https://github.com/FiloSottile/age       |

**Forbidden alternatives:**
- NON usare `python-telegram-bot` v13.x (sync) — breaking change in v20; MVP e solo async.
- NON usare `sqlalchemy` — si usa `aiosqlite` + SQL puro per controllo.
- NON usare `pydantic v1` — solo v2 (`>=2.6`).
- NON usare `requests` — solo `httpx` async.
- NON usare `mem0`, `zep`, `chroma`: memoria e locale-first (P4, blueprint §5).
- NON usare `pickle` per persistenza — vietato da ADR-0004 (blueprint §5.2).
- NON usare `click` — si usa `typer`.
- NON usare `loguru` o `logging.config.dictConfig` senza wrapping di `aria.utils.logging`.

### 14.2 Path canonici — non deviare

| Cosa                       | Path (assoluto)                                                         |
|----------------------------|-------------------------------------------------------------------------|
| Root progetto              | `/home/fulvio/coding/aria/`                                             |
| KiloCode config isolata    | `/home/fulvio/coding/aria/.aria/kilocode/`                              |
| KiloCode sessions          | `/home/fulvio/coding/aria/.aria/kilocode/sessions/`                     |
| Runtime state              | `/home/fulvio/coding/aria/.aria/runtime/`                               |
| Memory DB                  | `/home/fulvio/coding/aria/.aria/runtime/memory/episodic.db`             |
| Scheduler DB               | `/home/fulvio/coding/aria/.aria/runtime/scheduler/scheduler.db`         |
| Gateway sessions DB        | `/home/fulvio/coding/aria/.aria/runtime/gateway/sessions.db`            |
| LanceDB dir (lazy)         | `/home/fulvio/coding/aria/.aria/runtime/memory/semantic/`               |
| Credentials runtime state  | `/home/fulvio/coding/aria/.aria/runtime/credentials/providers_state.enc.yaml` |
| Secrets at-rest (IN GIT)   | `/home/fulvio/coding/aria/.aria/credentials/secrets/api-keys.enc.yaml`  |
| SOPS config                | `/home/fulvio/coding/aria/.aria/credentials/.sops.yaml`                 |
| age key file (OUT OF REPO) | `$HOME/.config/sops/age/keys.txt`                                       |
| Logs                       | `/home/fulvio/coding/aria/.aria/runtime/logs/`                          |
| Backups                    | `$HOME/.aria-backups/`                                                  |
| Systemd user units         | `$HOME/.config/systemd/user/aria-*.service`                             |

### 14.3 Naming convention modulo

- Moduli Python: `snake_case.py`.
- Classi: `PascalCase`. Evitare suffissi ridondanti (`MemoryMemoryManager` vietato).
- Costanti: `UPPER_SNAKE_CASE`.
- Tabelle SQL: `snake_case` plurale.
- Nomi file KiloCode agent/skill: `kebab-case`.
- Nomi variabili env utente-facing: `ARIA_<AREA>_<DETAIL>` (es. `ARIA_TELEGRAM_WHITELIST`).

### 14.4 Regole di scrittura codice

- **Type hints obbligatori** su ogni funzione pubblica; `mypy --strict` su `src/aria/{credentials,memory,scheduler}`.
- **Async by default** per I/O (DB, HTTP, filesystem via `aiofiles`). Sync solo per CLI entrypoint.
- **Nessun `print()`** in codice applicativo; usare il logger.
- **Nessuna `time.sleep()` bloccante** in path asincroni; usare `asyncio.sleep`.
- **Timeout espliciti** su ogni `httpx` call (default 30s, tunabile via config).
- **Try/except con log + re-raise** per errori inattesi; MAI `except:` nudo o `except Exception: pass`.
- **Contesto `with`/`async with`** per connessioni DB, file handle, HTTP client, SOPS processes.
- **Segreti MAI in log**: redigere con helper `redact_secret(value)` in `aria.utils.logging`.
- **Nessun dato PII in issue/ADR** — usare fixtures sintetiche.

### 14.5 Quando in dubbio

Ordine di consultazione:
1. Blueprint `docs/foundation/aria_foundation_blueprint.md` — sezione specifica + §16 Ten Commandments
2. Sprint plan corrente (`sprint-0N.md`)
3. ADR accepted in `docs/foundation/decisions/`
4. Fonte ufficiale upstream (link in §18.F blueprint)

**Se la risposta non c'e in nessuno dei 4**, NON improvvisare: aprire ADR `Proposed` con domanda esplicita e fermare il lavoro finche non viene accettato dal proprietario.

---

**Fine README Phase 1.** Procedere con `sprint-01.md`.
