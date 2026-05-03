---
document: ARIA Phase 1 — Sprint 1.4 Implementation Plan
version: 1.0.0
status: draft
date_created: 2026-04-20
last_review: 2026-04-20
owner: fulvio
phase: 1
sprint: "1.4"
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
blueprint_sections: ["§12", "§13.3", "§14.3", "§14.4", "§15"]
phase_overview: docs/plans/phase-1/README.md
depends_on: docs/plans/phase-1/sprint-03.md
---

# Sprint 1.4 — Workspace-Agent & E2E MVP

## 1) Obiettivo, scope, vincoli

### 1.1 Obiettivo

Chiudere **Phase 1** con il **Workspace-Agent** operativo (Gmail, Calendar, Drive, Docs, Sheets) via `taylorwilsdon/google_workspace_mcp`, OAuth PKCE, scope minimi, e dimostrare **i 5 casi d'uso MVP del blueprint §1.4 end-to-end** su Telegram. Stabilizzare backup, runbook DR, quality gates quantitativi Phase 1.

### 1.2 In scope

- `scripts/oauth_first_setup.py`: consent flow PKCE, redirect `localhost:8080/callback`, salvataggio `refresh_token` in keyring.
- Attivazione `google_workspace` MCP in `.aria/kilocode/mcp.json` con env da `CredentialManager`.
- `src/aria/agents/workspace/` completo: `oauth_helper.py`, `scope_manager.py` (escalation controllata), `multi_account.py` stub (Fase 2 support ready).
- Workspace-Agent definition `.aria/kilocode/agents/workspace-agent.md` attivato (tolto `disabled`).
- Skills Workspace: `triage-email/`, `calendar-orchestration/`, `doc-draft/`.
- Scheduler task preconfigurati:
  - `daily-email-triage` (cron `0 8 * * *`, category `workspace`, policy `allow`)
  - `weekly-backup` (cron `0 3 * * 0`, category `system`, policy `allow`) — usa `scripts/backup.sh`
- Runbook DR `docs/operations/disaster_recovery.md` + test restore reale.
- ADR-0003 (OAuth Security Posture) Accepted.
- Quality gates quantitativi Phase 1 (§6 README) verificati su dataset reale.
- Implementation Log entry finale Phase 1 mergata nel blueprint §18.G.
- 5 casi d'uso MVP dimostrati live.

### 1.3 Out of scope

- Sub-agente Finance/Health (Fase 2).
- Multi-account reale (scaffolding multi_account.py ma attivazione a un solo account primary in MVP).
- Automazione Zotero / ricerca accademica avanzata (Fase 2).
- WebUI (Fase 2).

### 1.4 Vincoli inderogabili

- **P7 HITL**: ogni `send email`, `create calendar event pubblico`, `update sheet`, `delete drive file` passa per `hitl_manager.ask` con Telegram inline keyboard. Default policy `ask`; `read-only` policy `allow`.
- **P13.3 OAuth keyring**: `refresh_token` SEMPRE in `keyring` service `aria.google_workspace` account `primary`. MAI in file plaintext, MAI in `.env`, MAI in `api-keys.enc.yaml`.
- **P12.2 Scope minimi**: fa Sprint 1.4 inizia con `gmail.readonly + gmail.modify + calendar.events + drive.file + documents + spreadsheets`. Nessuno scope `calendar` broad, `drive` broad. Escalation solo via `scope_manager.escalate(scope)` documentato in ADR.
- **PKCE default**: `GOOGLE_OAUTH_USE_PKCE=true`, `client_secret` opzionale e sconsigliato.
- **P8 Tool Priority Ladder**: usare upstream MCP `taylorwilsdon/google_workspace_mcp`, non reimplementare.

## 2) Pre-requisiti

- Sprint 1.3 chiuso: Conductor + Search-Agent funzionanti, HITL Telegram verde.
- Account Google Cloud Platform con:
  - Progetto OAuth configurato
  - Consent screen pubblicato (test mode ok)
  - `GOOGLE_OAUTH_CLIENT_ID` disponibile (opzionalmente `GOOGLE_OAUTH_CLIENT_SECRET` per edge-case)
- `google_workspace_mcp >= 1.19.0` installabile via `uvx google_workspace_mcp`.
- `pytesseract` + `PyMuPDF` per PDF draft (gia in ML extras).

## 3) Work Breakdown Structure (WBS)

### W1.4.A — OAuth PKCE first-time setup

**File**: `scripts/oauth_first_setup.py`.

**Responsabilita**:
1. Legge `GOOGLE_OAUTH_CLIENT_ID` e `GOOGLE_OAUTH_SCOPES` da config.
2. Genera `code_verifier` (43-128 chars random base64url) + `code_challenge` (SHA256).
3. Apre browser (`webbrowser.open`) su URL consent con `client_id`, `redirect_uri=http://localhost:8080/callback`, `code_challenge`, `code_challenge_method=S256`, `scope=space-separated`, `access_type=offline`, `prompt=consent`, `state=<random>`.
4. Avvia `http.server` locale su 8080 che intercetta `/callback?code=...&state=...`.
5. Scambia `code` + `code_verifier` su `https://oauth2.googleapis.com/token` → ottiene `access_token`, `refresh_token`, `expires_in`, `id_token`.
6. Salva `refresh_token` in `keyring` service `aria.google_workspace` account `primary`.
7. Salva scope concessi in `.aria/runtime/credentials/google_workspace_scopes.json` (plaintext, non segreto).
8. Echo "Setup completato" + scope granted.

**CLI**:
```
python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,calendar.events,drive.file,documents,spreadsheets" --account primary [--client-secret-prompt]
```

**Hardening**:
- `redirect_uri` localhost-only, server in-process chiude dopo 1 callback.
- `state` verificato post-callback; mismatch → abort.
- Timeout 5 min per consent; oltre → abort pulito.
- Mai stampare `access_token`/`refresh_token` in stdout; solo "stored in keyring" conferma.
- Se keyring backend insoddisfacente → avviso + fallback age file `.aria/credentials/keyring-fallback/google_workspace-primary.age` cifrato con chiave separata.

**Acceptance**:
- Test manuale con account Google reale → `keyring get aria.google_workspace primary` restituisce token non nullo.
- Test unitario su flow interno (mock HTTP token endpoint con `respx`).

### W1.4.B — Workspace OAuth helper runtime

**File**: `src/aria/agents/workspace/oauth_helper.py`.

Non duplica `scripts/oauth_first_setup.py`: questo modulo **runtime** e chiamato da `google_workspace_mcp` (via env) o da codice ARIA per refresh access_token.

Strategia: il server MCP upstream gestisce internamente la logica OAuth **se** forniamo le env var corrette (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_USE_PKCE=true`, `GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8080/callback`). Il `refresh_token` deve essere accessibile via keyring o env var.

**Opzione preferita**: se `google_workspace_mcp` supporta lettura keyring nativa → configurare. Se non supporta, iniettare `GOOGLE_OAUTH_REFRESH_TOKEN` via wrapper che legge dal keyring just-in-time.

**File wrapper**: `scripts/wrappers/google-workspace-wrapper.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
export ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
export GOOGLE_OAUTH_REFRESH_TOKEN="$(python -c "import keyring; print(keyring.get_password('aria.google_workspace','primary') or '')")"
if [[ -z "${GOOGLE_OAUTH_REFRESH_TOKEN:-}" ]]; then
  echo "ERR: no refresh token in keyring (run scripts/oauth_first_setup.py)" >&2
  exit 1
fi
exec uvx google_workspace_mcp
```

Aggiornare `.aria/kilocode/mcp.json`: `google_workspace.command` = path wrapper, rimuovere `GOOGLE_OAUTH_CLIENT_SECRET_OPTIONAL` da env a meno che non sia veramente necessaria (ADR-0003).

**API Python `oauth_helper.py`**:

```python
class GoogleOAuthHelper:
    def _init_(self, cm: CredentialManager): ...
    def ensure_refresh_token(self, account: str = "primary") -> str: ...   # raise if missing, with actionable msg
    def get_scopes(self, account: str = "primary") -> list[str]: ...
    def revoke(self, account: str = "primary") -> None: ...                 # calls Google revoke endpoint + clears keyring
```

**Acceptance**:
- `ensure_refresh_token` su keyring vuoto → `OAuthSetupRequired` con istruzioni (`run scripts/oauth_first_setup.py`).
- `revoke` aggiorna keyring + status.json.

### W1.4.C — Scope manager

**File**: `src/aria/agents/workspace/scope_manager.py`.

```python
class ScopeManager:
    MINIMAL = ["gmail.readonly","gmail.modify","calendar.events","drive.file","documents","spreadsheets"]

    def _init_(self, helper: GoogleOAuthHelper): ...
    def current(self, account: str = "primary") -> list[str]: ...
    def request_escalation(self, new_scopes: list[str], reason: str) -> EscalationTicket: ...
    # produce un hitl_pending + ADR reference; user deve rilanciare oauth_first_setup con nuovi scope
```

**Regola**: nessun scope broad (`gmail`, `calendar`, `drive` full) senza ADR esplicito referenziato in `EscalationTicket.adr_ref`.

### W1.4.D — Workspace-Agent definition attivata

**File**: `.aria/kilocode/agents/workspace-agent.md`.

Rimuovere eventuale `disabled: true`. Frontmatter blueprint §8.3.2 letterale. `allowed-tools`:

```yaml
allowed-tools:
  - google_workspace/gmail.*
  - google_workspace/calendar.*
  - google_workspace/drive.*
  - google_workspace/docs.*
  - google_workspace/sheets.*
  - aria-memory/remember
  - aria-memory/recall
  - aria-ops/hitl_ask        # o hitl-queue skill
```

Verificare count dei tool wildcard reali: ogni `google_workspace/<ns>.*` si espande in circa 4-6 tool; stimare ~25 wildcards unpacked → rischio > 20. **Mitigazione**: restringere a subset esplicito:

```yaml
allowed-tools:
  - google_workspace/gmail.search
  - google_workspace/gmail.read
  - google_workspace/gmail.modify_labels
  - google_workspace/gmail.send             # HITL-gated
  - google_workspace/calendar.list
  - google_workspace/calendar.read
  - google_workspace/calendar.create        # HITL
  - google_workspace/drive.search
  - google_workspace/drive.read
  - google_workspace/drive.create_file      # HITL
  - google_workspace/docs.read
  - google_workspace/docs.write             # HITL
  - google_workspace/sheets.read
  - google_workspace/sheets.update          # HITL
  - aria-memory/remember
  - aria-memory/recall
  - aria-ops/hitl_ask
```

Totale: 17 tool, sotto budget 20 (P9 ok).

### W1.4.E — Skill `triage-email`

**Directory**: `.aria/kilocode/skills/triage-email/`.

**SKILL.md** (frontmatter):
```yaml
name: triage-email
version: 1.0.0
description: Triage giornaliero Inbox Gmail — classifica, sintetizza, evidenzia urgenti
trigger-keywords: [email, triage, inbox, riassumi mail]
user-invocable: true
allowed-tools:
  - google_workspace/gmail.search
  - google_workspace/gmail.read
  - google_workspace/gmail.modify_labels
  - aria-memory/remember
max-tokens: 30000
estimated-cost-eur: 0.05
```

Procedura:
1. Query `gmail.search` con `q="is:unread newer_than:24h"`.
2. Per ogni messaggio: `gmail.read` → estrai `from`, `subject`, `snippet`, `timestamp`.
3. Classifica heuristically: newsletter / personal / work / urgent (keyword).
4. Sintesi: digest markdown con sezioni per classe.
5. Per urgenti: proponi label `ARIA/urgent` → `gmail.modify_labels` (HITL `ask`).
6. Salva digest in memoria: `aria-memory/remember` actor=AGENT_INFERENCE, tag=`email_digest`.
7. Reply Telegram con digest.

Invarianti:
- NON eliminare email (skill hardcoded: no `gmail.delete`).
- NON inviare risposte automatiche.

### W1.4.F — Skill `calendar-orchestration`

**Directory**: `.aria/kilocode/skills/calendar-orchestration/`.

Frontmatter:
```yaml
name: calendar-orchestration
version: 1.0.0
description: Proposta slot + creazione eventi Calendar con HITL obbligatorio
trigger-keywords: [calendario, meeting, evento, pianifica]
user-invocable: true
allowed-tools:
  - google_workspace/calendar.list
  - google_workspace/calendar.read
  - google_workspace/calendar.create
  - aria-memory/remember
  - aria-memory/recall
  - aria-ops/hitl_ask
max-tokens: 20000
```

Procedura:
1. Parse request utente (data range, durata, attendees).
2. `calendar.list` per free/busy nei prossimi 7-14gg.
3. Proponi 3 slot candidati.
4. `aria-ops/hitl_ask` con inline keyboard "Scegli slot: [A] [B] [C] [annulla]".
5. Risposta A/B/C → `calendar.create` (policy `ask` ma gia approvato implicitamente da HITL scelta).
6. Salva evento id in memoria tag `calendar_event`.

### W1.4.G — Skill `doc-draft`

**Directory**: `.aria/kilocode/skills/doc-draft/`.

Frontmatter:
```yaml
name: doc-draft
version: 1.0.0
description: Redige bozza Google Docs a partire da input utente + contesto memoria
trigger-keywords: [bozza, doc, scrivi documento]
user-invocable: true
allowed-tools:
  - google_workspace/drive.create_file
  - google_workspace/docs.write
  - google_workspace/docs.read
  - aria-memory/recall
  - aria-ops/hitl_ask
```

Procedura:
1. Recupera contesto da memoria via `aria-memory/recall`.
2. Genera bozza markdown + propone titolo.
3. HITL "Crea doc '<titolo>' in Drive? [Sì] [Modifica titolo] [Annulla]".
4. `drive.create_file(mimeType='application/vnd.google-apps.document')` → `docs.write` con contenuto.
5. Reply con link Drive.

### W1.4.H — Scheduler task preconfigurati

Via CLI `aria schedule add` oppure migrazione `src/aria/scheduler/migrations/0001_seed_tasks.sql`:

Task 1 — Daily email triage:
```
aria schedule add \
  --name daily-email-triage \
  --cron '0 8 * * *' \
  --category workspace \
  --policy allow \
  --payload '{"sub_agent":"workspace-agent","skill":"triage-email","trace_prefix":"daily-triage"}'
```

Task 2 — Weekly backup:
```
aria schedule add \
  --name weekly-backup \
  --cron '0 3 * * 0' \
  --category system \
  --policy allow \
  --payload '{"command":"scripts/backup.sh"}'
```

Task 3 — Blueprint-keeper stub (policy `deny` fino Fase 2):
```
aria schedule add \
  --name blueprint-review \
  --cron '0 10 * * 0' \
  --category system \
  --policy deny \
  --payload '{"sub_agent":"blueprint-keeper"}'
```

**Acceptance**:
- `aria schedule list` mostra 3 task.
- Systemd scheduler esegue `daily-email-triage` al prossimo 08:00 (test manuale il giorno dopo deploy).

### W1.4.I — Backup + DR runbook

**File**: `scripts/backup.sh` (esistente Phase 0) — verificare contenuto blueprint §14.4:
- tar `.aria/runtime`, `.aria/credentials` (sops files gia cifrati)
- cifra con age (chiave `.age-backup.pub` in repo; **chiave privata fuori repo**: `$HOME/.aria-backup-keys/backup_key.txt`)
- deposita in `$HOME/.aria-backups/aria-backup-<ts>.tar.age`
- pulisce piu di 30gg

**File**: `scripts/restore.sh`:
- decrypt tar con chiave privata
- estrai in temporaneo
- confirm prompt utente prima di sovrascrivere `.aria/runtime`
- restore atomico (rename)

**File**: `docs/operations/disaster_recovery.md`:
- RPO: 7gg (backup weekly); suggerire daily per utenti attivi
- RTO: <30 min
- Procedura restore step-by-step
- Test obbligatorio: `scripts/test_backup_restore.sh` che su tmp crea DB sintetico, backup, restore, valida.

**Acceptance**:
- `scripts/test_backup_restore.sh` esce 0.
- Restore reale da backup di staging → sistema ripartito.

### W1.4.J — Quality gates quantitativi Phase 1

Creare `tests/benchmarks/phase1_slo.py` che misura:

1. **p95 recall memoria**: dataset fixture 1k entry, 200 query miste FTS5 + episodic time-range; calcola p95 ms < 250.
2. **DLQ rate**: su 7gg simulati (o staging reale) calcola `count(dlq) / count(task_runs)` < 2%.
3. **HITL timeout rate**: simulazione 100 HITL con 5 timeout → 5% boundary, deve essere < 5% reale.
4. **Provider degradation rate**: `circuit_state != closed / total_probe` < 15%.
5. **Scheduler success rate**: `outcome='success' / total` per `policy='allow'` > 98%.

Output: `tests/benchmarks/phase1_slo_report.md` (commit evidence).

### W1.4.K — ADR-0003 OAuth Security Posture

**File**: `docs/foundation/decisions/ADR-0003-oauth-security-posture.md`.

Contenuto (decisioni):
- PKCE-first, `client_secret` opzionale e sconsigliato.
- Scope minimi (§12.2 blueprint).
- `refresh_token` in keyring (Linux Secret Service); fallback age file con chiave separata da SOPS.
- Revoca via `aria workspace revoke`.
- Escalation scope → richiede ADR linkato + run script `oauth_first_setup.py`.
- Loggare scope grantati non e sensibile; token sempre redacted.

Status: Accepted in Sprint 1.4.

### W1.4.L — Dimostrazione 5 casi d'uso MVP

Il team (Fulvio + eventuale co-pilot) esegue dal vivo i 5 casi d'uso blueprint §1.4:

1. **Ricerca tematica**: "ARIA, fai una ricerca approfondita su `vector DBs 2026`" → report in Drive + Telegram. [Search-Agent + Workspace-Agent]
2. **Triage email**: scheduler esegue 08:00 → digest Telegram; urgenti labelled. [Workspace-Agent]
3. **Gestione calendario**: "ARIA, pianifica call 30min con Mario la prossima settimana" → HITL scelta slot → evento creato. [Workspace-Agent]
4. **Analisi documento**: "ARIA, leggi <PDF attached> e dimmi punti chiave" → PDF extract + sintesi in memoria + Telegram reply. [skill `pdf-extract`]
5. **Conversazione persistente**: nuova sessione Telegram, "ricorda cosa abbiamo deciso su `aria-ops` server?" → recall memoria semantica. [Conductor + aria-memory]

Registrare output (transcript + screenshot) in `docs/implementation/phase-1/mvp_demo_2026-XX-XX.md`.

### W1.4.M — Implementation Log Phase 1 entry

Aggiungere in `docs/foundation/aria_foundation_blueprint.md` §18.G entry `### <DATE> — Phase 1 Completed` con bullet list di deliverable chiusi + link PR/commit. NON sovrascrivere entry Phase 0.

## 4) Piano sprint (5 giorni)

### D1 — OAuth setup + scope management
- W1.4.A `oauth_first_setup.py`
- W1.4.B `oauth_helper.py` + wrapper bash
- W1.4.C scope manager
- End-of-day: script eseguito con account di test → refresh_token in keyring

### D2 — Workspace-Agent + skill triage-email
- W1.4.D agent definition attiva
- W1.4.E skill triage-email
- Smoke test: "Leggi le mie email non lette" → triage via `aria repl`

### D3 — Skills calendar-orchestration + doc-draft
- W1.4.F calendar-orchestration
- W1.4.G doc-draft
- Smoke con account test

### D4 — Scheduler seed + backup DR
- W1.4.H seed task
- W1.4.I backup + DR runbook + test_backup_restore
- End-of-day: backup/restore verificato in ambiente pulito

### D5 — Benchmarks SLO + ADR + demo + chiusura
- W1.4.J SLO benchmarks
- W1.4.K ADR-0003 accepted
- W1.4.L 5 casi d'uso MVP demo
- W1.4.M Implementation Log entry
- Quality gates finali + Phase 1 Go/No-Go

## 5) Exit criteria Sprint 1.4

- [ ] `scripts/oauth_first_setup.py` funziona end-to-end su account reale
- [ ] Workspace-Agent operativo; 3 skill (triage-email, calendar-orchestration, doc-draft) testate
- [ ] 3 task scheduler seedati e visibili in `aria schedule list`
- [ ] `scripts/backup.sh` + `restore.sh` testati con `test_backup_restore.sh` verde
- [ ] Tutti e 5 i casi d'uso MVP §1.4 dimostrati con transcript registrato
- [ ] SLO quantitativi Phase 1 (README §6) verdi
- [ ] ADR-0003 Accepted
- [ ] Implementation Log §18.G aggiornato
- [ ] Phase 1 Go/No-Go: GO

## 6) Deliverable checklist (Definition of Done Phase 1)

### Sprint 1.4 specifici
- [ ] `scripts/oauth_first_setup.py`
- [ ] `scripts/wrappers/google-workspace-wrapper.sh`
- [ ] `src/aria/agents/workspace/{oauth_helper,scope_manager,multi_account}.py`
- [ ] `.aria/kilocode/agents/workspace-agent.md` attivato
- [ ] `.aria/kilocode/skills/{triage-email,calendar-orchestration,doc-draft}/SKILL.md`
- [ ] `.aria/kilocode/skills/_registry.json` aggiornato
- [ ] `.aria/kilocode/mcp.json` con `google_workspace` attivo (disabled=false) e wrapper path
- [ ] `scripts/test_backup_restore.sh`
- [ ] `docs/operations/disaster_recovery.md`
- [ ] `tests/benchmarks/phase1_slo.py` + report committato
- [ ] `docs/implementation/phase-1/mvp_demo_<DATE>.md`
- [ ] ADR-0003 Accepted

### Checklist Phase 1 complessiva (blueprint §15)
- [ ] Credential Manager operativo (Sprint 1.1)
- [ ] Memoria T0+T1 operativa con ARIA-Memory MCP (Sprint 1.1)
- [ ] Scheduler systemd user service operativo (Sprint 1.2)
- [ ] Gateway Telegram operativo (Sprint 1.2)
- [ ] Conductor + Search-Agent operativi (Sprint 1.3)
- [ ] Workspace-Agent operativo (Sprint 1.4)
- [ ] 5 casi d'uso MVP end-to-end (Sprint 1.4)

## 7) Quality gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/aria/agents/workspace src/aria/utils

uv run pytest tests/unit tests/integration tests/e2e -q --cov=aria --cov-report=term-missing

# OAuth smoke (manuale)
python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,calendar.events,drive.file,documents,spreadsheets"
# verifica: keyring get_password('aria.google_workspace','primary') non nullo

# Workspace MCP smoke
./bin/aria repl
# /tools list -> google_workspace/gmail.* etc presenti
# test: "quante email non lette?"

# SLO benchmarks
uv run python tests/benchmarks/phase1_slo.py --fail-on-breach

# Backup/restore
./scripts/test_backup_restore.sh

# Systemd full stack
systemctl --user is-active aria-scheduler.service aria-gateway.service
```

## 8) Risk register

| ID  | Rischio                                                           | Impatto | Mitigazione                                                                    |
|-----|-------------------------------------------------------------------|---------|--------------------------------------------------------------------------------|
| R41 | `google_workspace_mcp` upstream non legge keyring nativamente     | Medio   | Wrapper bash inietta `GOOGLE_OAUTH_REFRESH_TOKEN` env just-in-time             |
| R42 | Consent screen in "test mode" limita a 100 utenti                | Basso   | MVP single-user; notificare se pubblicazione necessaria                         |
| R43 | Scope escalation non coordinata → break skill                    | Medio   | `scope_manager.current()` check pre-skill esecuzione; fail fast                 |
| R44 | PKCE non supportato da proxy corporate                            | Basso   | Fallback a client_secret opzionale documentato in ADR-0003                      |
| R45 | Revoca Google dopo 6 mesi inattivita                             | Medio   | Health check weekly su `google_workspace_mcp`; alert se 401                     |
| R46 | SLO benchmarks falliscono su hw dev inadeguato                   | Alto    | Documentare ambiente benchmark; se fallisce, aprire remediation sprint          |
| R47 | Demo 5 casi d'uso rivela bug latente                             | Alto    | Rehearsal in D4; fix in D5; se show-stopper, estendere sprint di 2gg            |
| R48 | Backup cifrato corrotto non restorabile                          | Alto    | `test_backup_restore.sh` obbligatorio in CI; retention 30gg + offsite manual    |

## 9) ADR collegati

- **ADR-0003 — OAuth Security Posture** (Accepted): PKCE default, scope minimi, keyring storage, revoke explicit.
- Eventuale **ADR-0009 — Phase 1 Completion Report** (opzionale): snapshot SLO, debito tecnico, backlog Fase 2.

## 10) Tracciabilita blueprint -> task

| Sezione blueprint                 | Task Sprint 1.4                    |
|-----------------------------------|-------------------------------------|
| §12.1 Dipendenza upstream MCP     | W1.4.B wrapper                     |
| §12.2 Scope minimi                | W1.4.C + ADR-0003                  |
| §12.3 OAuth flow PKCE             | W1.4.A                             |
| §12.4 Multi-account (stub)        | `multi_account.py` scaffolding     |
| §12.5 Handbook comandi            | W1.4.E + W1.4.F + W1.4.G           |
| §13.3 Keyring per OAuth           | W1.4.A + W1.4.B                    |
| §14.4 Backup                      | W1.4.I                             |
| §15 Exit Phase 1                  | W1.4.J + W1.4.L + W1.4.M           |
| §1.4 Casi d'uso fondativi         | W1.4.L                             |

## 11) Note prescrittive per l'LLM implementatore (anti-allucinazione)

### 11.1 Non inventare API Google

| Cosa                            | Fonte autoritativa                                                             |
|---------------------------------|--------------------------------------------------------------------------------|
| OAuth 2.0 best practices        | https://developers.google.com/identity/protocols/oauth2/resources/best-practices |
| OAuth 2.0 overview              | https://developers.google.com/identity/protocols/oauth2                        |
| PKCE RFC                        | RFC 7636                                                                       |
| Google Workspace MCP            | https://github.com/taylorwilsdon/google_workspace_mcp                          |

Tool name Google MCP: NON inventare; verificare lista reale tool con `aria repl` + `/tools list` dopo attivazione MCP. Se un tool manca (es. `gmail.modify_labels` non esiste e si chiama `gmail.add_label`), aggiornare `allowed-tools` nel workspace-agent.md.

### 11.2 Errori comuni

1. **NON** salvare `refresh_token` in `.env`, in SOPS secrets, in `api-keys.enc.yaml`, o in qualsiasi altro file commitato — SOLO keyring (blueprint §13.3).
2. **NON** usare scope broad (`gmail`, `calendar`, `drive` senza sub-scope) — violazione §12.2.
3. **NON** impostare `disabled: true` su `google_workspace` dopo Sprint 1.4 (ma lasciare setup opzionale documentato).
4. **NON** cachare `access_token` su disco: e gestito runtime dal MCP server upstream.
5. **NON** sostituire `keyring` con file plaintext "perche e comodo" — bypass di P13.3.
6. **NON** chiamare `gmail.send`, `calendar.create`, `docs.write`, `sheets.update`, `drive.create_file`, `drive.delete` senza passare HITL `ask` (P7).
7. **NON** usare `client_secret` senza ADR (ADR-0003 esplicita PKCE-first).
8. **NON** rimuovere `state` check in OAuth callback — CSRF mitigation.
9. **NON** esporre `localhost:8080/callback` in dev server persistente — solo per 5 min durante setup.
10. **NON** committare nel repo copie del consent screen o token screenshot.

### 11.3 Testing

- Test OAuth: mock token endpoint con `respx`; verificare PKCE `code_verifier` coerente con `code_challenge`.
- Nessun test fa chiamate reali a Google.
- Fixture `tests/fixtures/google/` con JSON rappresentativi (gmail search response, calendar freebusy).

### 11.4 HITL nelle skill

Ogni operazione write DEVE chiamare `aria-ops/hitl_ask` (o `hitl-queue` skill) PRIMA dell'API call. Pattern skill:

```
1. Prepara payload write
2. aria-ops/hitl_ask(question="Invio questa email? <preview>", options=["send","edit","cancel"])
3. Se response="send" → google_workspace/gmail.send
4. Altrimenti abort gracefully, log attempt
```

### 11.5 Budget e quiet hours

- `triage-email` scheduled alle 08:00: fuori quiet hours (07:00 termine), policy `allow` OK.
- `weekly-backup` alle 03:00 domenica: in quiet hours → policy `allow` esplicita, category `system` (background), non genera notifica HITL.
- Mai schedulare task `policy=ask` in quiet hours senza `deferred` logic (blueprint §6.4).

### 11.6 Demo 5 casi d'uso

Preparare checklist Go/No-Go per la demo prima di dichiarare Phase 1 completata. Se anche uno solo dei 5 casi fallisce: **NO-GO Phase 1**, documentare gap in ADR-0009 (Phase 1 Completion Report) e aprire sprint di remediation.

### 11.7 Non-requisiti

- NON implementare multi-account reale: stub pronto, attivazione Fase 2.
- NON implementare Finance-Agent / Health-Agent (Fase 2 backlog).
- NON creare WebUI per consent screen: Telegram + CLI sufficienti.
- NON attivare `blueprint-keeper` cron reale (policy=deny in seed task).
- NON abilitare Playwright (Fase 2).

---

**Fine Sprint 1.4.** Se Exit criteria § 5 + checklist §6 + Go/No-Go Phase 1 (README §12) tutti verdi → **Phase 1 COMPLETATA**, procedere con piano Phase 2 (da redigere).

In caso contrario: aprire `docs/plans/phase-1/sprint-05-remediation.md` con piano mirato ai gap emersi.
