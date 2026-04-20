---
document: ARIA Phase 0 Implementation Plan
version: 1.0.0
status: completed
date_created: 2026-04-20
last_review: 2026-04-20
owner: fulvio
phase: 0
sprint: 00
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
---

# ARIA — Piano di Implementazione Phase 0 (Foundation)

## 1) Obiettivo, scope, vincoli

Obiettivo della Phase 0: rendere il repository ARIA pronto all'implementazione, con isolamento completo dal KiloCode globale, bootstrap riproducibile e baseline sicurezza/operativita, senza logica agentica di business.

In scope (allineato a blueprint §15):
- struttura directory completa e coerente con blueprint §4.1;
- launcher `bin/aria` funzionante in isolamento;
- configurazione KiloCode dedicata in `.aria/kilocode`;
- setup secret management con SOPS+age;
- bootstrap idempotente ambiente Python/Node e skeleton `src/aria/`;
- unit file systemd pronti (non installati);
- documentazione minima operativa (`README.md`, `CONTRIBUTING.md`).

Out of scope:
- implementazione memoria/scheduler/gateway operativi;
- integrazione provider reali (Tavily, Firecrawl, Google Workspace);
- test E2E dei casi d'uso MVP (Phase 1).

Vincoli inderogabili:
- Ten Commandments blueprint §16, in particolare P1, P2, P4, P7, P8, P10;
- no modifica sorgente KiloCode upstream;
- local-first per dati runtime/credenziali;
- nessun segreto in chiaro committato.

## 2) Path e formato di riferimento

Questo piano usa il formato sprint-level richiesto dal blueprint §0.1:
- `docs/plans/phase-0/sprint-00.md`

Nota di coerenza documentale:
- il blueprint §4.1 mostra anche `docs/implementation/phase-0/` come area documentale;
- in questa fase il piano resta canonico in `docs/plans/phase-0/` e verra referenziato da `docs/implementation/phase-0/README.md`.

## 3) Baseline tecnica 2026 (decisioni operative)

Baseline adottata per ridurre drift iniziale:
- Python `>=3.11` con `uv` e lockfile `uv.lock` obbligatorio;
- package manager Node: `npm`, CLI Kilo installabile come `@kilocode/cli`;
- MCP server custom in Python con `fastmcp 3.x`;
- Telegram stack target `python-telegram-bot 22.x` (solo pinning in Fase 0);
- SQLite runtime floor `>=3.51.3` (mitigazione bug WAL-reset);
- hardening systemd user service allineato a `systemd.exec` con sandbox minima compatibile.

Fonti ufficiali verificate (2026):
- UV docs: `https://docs.astral.sh/uv/guides/projects/`
- FastMCP docs/PyPI: `https://gofastmcp.com/getting-started/installation`, `https://pypi.org/project/fastmcp/`
- PTB v22 docs: `https://docs.python-telegram-bot.org/en/stable/`
- SQLite release notes/WAL: `https://sqlite.org/releaselog/3_51_3.html`, `https://sqlite.org/wal.html`
- SOPS: `https://github.com/getsops/sops`
- age: `https://github.com/FiloSottile/age`
- systemd exec hardening: `https://manpages.debian.org/unstable/systemd/systemd.exec.5.en.html`

## 4) Work Breakdown Structure (WBS)

### W0 — Repository foundation e policy file
- Creare/normalizzare root file: `README.md`, `CONTRIBUTING.md`, `.gitignore`, `.env.example`.
- Inserire regole no-secrets in `.gitignore` e commenti operativi in `.env.example`.
- Acceptance:
  - nessun file runtime sotto `.aria/runtime/` tracciato da git;
  - `.env.example` non contiene valori sensibili reali.

### W1 — Isolamento KiloCode
- Creare `.aria/kilocode/` con:
  - `kilo.json`
  - `mcp.json` (placeholder server core)
  - `agents/`, `skills/`, `modes/`, `sessions/`
- Definire default agent `aria-conductor` e path locali relativi.
- Acceptance:
  - `bin/aria repl` usa config isolata;
  - la home config globale di KiloCode resta intatta.

### W2 — Launcher `bin/aria`
- Implementare launcher bash idempotente con:
  - export variabili `ARIA_*`, `KILOCODE_*`;
  - pre-flight checks (config dir, kilo.json);
  - subcommands `repl`, `run`, `mode`, `schedule`, `gateway`, `memory`, `creds`, `backup`.
- Hardening script:
  - `set -euo pipefail`
  - errore esplicito su prerequisiti mancanti.
- Acceptance:
  - `bin/aria repl` avvia CLI in workspace ARIA;
  - `bin/aria --help` mostra guida locale.

### W3 — Python project bootstrap
- Creare `pyproject.toml` con dipendenze Phase 0 (core + dev tools).
- Inizializzare ambiente con `uv sync --dev`.
- Creare skeleton package:
  - `src/aria/__init__.py`
  - namespace placeholder per `credentials`, `memory`, `scheduler`, `gateway`, `agents`, `tools`, `utils`.
- Acceptance:
  - `uv sync --dev` completa senza errori;
  - `python -c "import aria"` funziona nella venv.

### W4 — Secrets e credential baseline
- Creare `.aria/credentials/.sops.yaml` (in git) e struttura:
  - `.aria/credentials/secrets/api-keys.enc.yaml` (cifrato)
  - `.aria/runtime/credentials/providers_state.enc.yaml` (fuori git)
- Generare chiavi age e posizionarle fuori repo (`~/.config/sops/age/keys.txt`).
- Implementare script bootstrap che valida `sops`/`age` presenti.
- Acceptance:
  - `sops -d .aria/credentials/secrets/api-keys.enc.yaml` funziona localmente;
  - nessuna chiave privata in repository.

### W5 — Scripts operativi e systemd templates
- Creare script:
  - `scripts/bootstrap.sh` (idempotente)
  - `scripts/install_systemd.sh`
  - `scripts/backup.sh`, `scripts/restore.sh`
- Creare template unit files:
  - `systemd/aria-scheduler.service`
  - `systemd/aria-gateway.service`
  - `systemd/aria-memory.service` (opzionale)
- Acceptance:
  - `systemd-analyze verify systemd/*.service` senza errori bloccanti;
  - directives hardening compatibili con user services.

### W6 — Schema SQL foundation + test di smoke
- Generare `docs/foundation/schemas/sqlite_full.sql` da sezioni blueprint (§5, §6, §7).
- Preparare smoke checks:
  - creazione DB vuoti con PRAGMA WAL;
  - check disponibilita `fts5`.
- Acceptance:
  - script smoke eseguibile e ripetibile;
  - file schema presente e versionato.

## 5) Piano sprint (2 sprint, 10 giorni lavorativi)

### Sprint 00A (giorni 1-5)
- D1: W0 + W1 (struttura, config isolata)
- D2: W2 (launcher completo + smoke)
- D3: W3 (pyproject, uv, skeleton)
- D4: W4 (SOPS+age baseline)
- D5: review tecnica + fix + evidenze

Exit criteria Sprint 00A:
- launcher funzionante in isolamento;
- bootstrap Python riproducibile;
- cifratura secrets operativa.

### Sprint 00B (giorni 6-10)
- D6: W5 (scripts + systemd templates)
- D7: W6 (schema SQL + smoke DB)
- D8: hardening pass (service files, .gitignore, docs)
- D9: quality gate completo (lint/type/tests smoke)
- D10: chiusura fase + implementation log seed

Exit criteria Sprint 00B:
- deliverable checklist Phase 0 chiusa al 100%;
- quality gates verdi;
- documentazione onboarding sufficiente.

## 6) Deliverable checklist (Definition of Done Phase 0)

- [x] `bin/aria` isolato e funzionante
- [x] `.aria/kilocode/kilo.json` e `.aria/kilocode/mcp.json` validi
- [x] `.aria/credentials/.sops.yaml` + secrets cifrati presenti
- [x] `pyproject.toml` + `uv.lock` presenti
- [x] skeleton `src/aria/` creato
- [x] `systemd/*.service` templates presenti
- [x] `scripts/bootstrap.sh` idempotente
- [x] `docs/foundation/schemas/sqlite_full.sql` presente
- [x] `README.md` + `CONTRIBUTING.md` aggiornati
- [x] entry iniziale in `§18.G Implementation Log` pronta per append

Post-audit 2026-04-20:
- corretto wiring launcher/entrypoint Python (`memory`, `scheduler`, `gateway`, `creds`);
- ripristinati quality gates (`ruff`, `mypy`, `pytest`) con fix tipizzati minimi;
- hardening policy segreti in `.gitignore` (solo `.sops.yaml` e `*.enc.yaml` tracciati sotto `.aria/credentials`);
- aggiunti ADR backlog richiesti: `ADR-0003`, `ADR-0004`.

## 7) Quality gates e verifiche

Comandi gate minimi:
```bash
ruff check .
ruff format --check .
mypy src
pytest -q
```

Comandi bootstrap/smoke Phase 0:
```bash
uv sync --dev
./scripts/bootstrap.sh --check
./bin/aria repl --help
python -m aria.memory.mcp_server --help
sqlite3 --version
systemd-analyze verify systemd/aria-scheduler.service
```

Evidenze richieste in PR:
- output comandi gate;
- screenshot/log di `bin/aria repl` in isolamento;
- prova cifratura/decrittazione SOPS su file example.

## 8) Risk register (Phase 0)

R1 — Drift tra blueprint e CLI Kilo reale
- Impatto: alto
- Mitigazione: validare naming package/bin (`@kilocode/cli`, comando reale) prima freeze launcher.

R2 — Hardening systemd troppo aggressivo su user services
- Impatto: medio
- Mitigazione: usare baseline minima sicura e iterare con `systemd-analyze verify` + smoke start.

R3 — setup SOPS/age incompleto su macchina target
- Impatto: alto
- Mitigazione: bootstrap con pre-flight e messaggi diagnostici azionabili.

R4 — assenza lock riproducibile (uv)
- Impatto: medio
- Mitigazione: lockfile obbligatorio e aggiornamento solo via PR.

R5 — mismatch SQLite runtime floor
- Impatto: alto
- Mitigazione: check versione in bootstrap; fail fast se `<3.51.3`.

## 9) ADR obbligatori collegati (post-audit)

Da aprire o finalizzare durante/chiusura Phase 0:
- ADR-0001: Dependency Baseline 2026Q2
- ADR-0002: SQLite Reliability Policy
- ADR-0003: OAuth Security Posture
- ADR-0004: Associative Memory Persistence Format

Regola: nessuna deviazione dalle sezioni §4, §10, §13, §14 senza ADR Accepted.

## 10) Sequenza di esecuzione consigliata

1. Bootstrap repo/files policy (W0)
2. Isolamento Kilo + launcher (W1/W2)
3. Python scaffold + lock (W3)
4. Secrets baseline e bootstrap idempotente (W4/W5)
5. SQL schema + smoke + quality gates (W6)
6. Chiusura con evidence pack e aggiornamento Implementation Log

## 11) Criterio di uscita fase (Go/No-Go)

Go solo se tutte vere:
- checklist deliverable completata;
- quality gates verdi;
- isolamento confermato (`aria repl` non usa config globale);
- segreti cifrati e runtime separato;
- nessun blocker aperto su sicurezza/bootstrap.

No-Go se una qualsiasi condizione fallisce.

## 12) Tracciabilita blueprint -> task

- Blueprint §4 (isolamento) -> W1, W2
- Blueprint §10 (MCP ecosystem) -> W1, W3
- Blueprint §13 (credential management) -> W4
- Blueprint §14 (governance/backup/systemd hardening) -> W5
- Blueprint §15 (roadmap phase 0 deliverable) -> W0..W6
- Blueprint §16 (ten commandments) -> vincoli globali del piano
