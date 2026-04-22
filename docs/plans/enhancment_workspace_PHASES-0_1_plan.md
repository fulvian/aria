---
document: Google Workspace MCP Enhancement Plan (Phases 0-1)
version: 1.0.0
status: draft
date_created: 2026-04-22
last_review: 2026-04-22
owner: fulvio
phase_scope: "roadmap phase 0 + phase 1"
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
source_roadmap: docs/roadmaps/google-workspace_MCP_enhanchement_roadmap.md
---

# ARIA - Piano implementativo robusto (Fasi 0 e 1)

## 0) Executive intent

Obiettivo del documento: trasformare la roadmap Workspace in un piano operativo, verificabile e handoff-ready per le sole Fasi 0 e 1, rispettando blueprint e ADR attive, con evidenze ufficiali aggiornate (Context7 + fonti authoritative 2025/2026).

Output atteso a fine Fase 1:
- baseline governance completa e anti-drift (Fase 0);
- baseline auth/scope/security professionale multi-servizio (Fase 1);
- test evidence eseguibile e runbook operativo pronto per team handoff.

---

## 1) Fonti ufficiali e evidenze utilizzate (aggiornate)

### 1.1 Context7 (mandatory verification)

1. `/taylorwilsdon/google_workspace_mcp`
   - quick start, launch options e advanced flags (`--tool-tier`, `--tools`, `--read-only`, `--permissions`, `--single-user`, `--transport`)
   - tool coverage per dominio Workspace
   - pattern di deployment (stdio/http, selective loading, tiering)
2. `/openai/codex`
   - pattern prompt deterministici orientati a output verificabile
3. `/anthropics/claude-code`
   - pattern multi-step con checkpoint, completion criteria e safety workflow

### 1.2 Fonti ufficiali web 2025/2026

1. Google Identity OAuth Best Practices (last updated 2026-04-15)
   - https://developers.google.com/identity/protocols/oauth2/resources/best-practices
2. Google Workspace Auth Overview (last updated 2026-04-03)
   - https://developers.google.com/workspace/guides/auth-overview
3. Google Workspace OAuth Consent & scope categories (last updated 2026-04-01)
   - https://developers.google.com/workspace/guides/configure-oauth-consent
4. IETF OAuth Security BCP - RFC 9700 (Jan 2025)
   - https://www.rfc-editor.org/rfc/rfc9700
5. OAuth for Native Apps - RFC 8252 (BCP)
   - https://www.rfc-editor.org/rfc/rfc8252

### 1.3 Repo evidence (stato reale)

- Wrapper attuale con hardcode scope Gmail read-only: `scripts/wrappers/google-workspace-wrapper.sh`
- Helper OAuth e scope enforcement: `src/aria/agents/workspace/oauth_helper.py`, `src/aria/agents/workspace/scope_manager.py`
- Validator attuali orientati a `mcp.json`: `scripts/validate_agents.py`, `scripts/validate_skills.py`
- Analisi gap gia consolidata: `docs/analysis/workspace_enhancement_analysis.md`

---

## 2) Vincoli inderogabili (Blueprint -> piano)

1. P1 Isolation First: solo percorsi ARIA (`/home/fulvio/coding/aria`, `.aria/`)
2. P2 Upstream Invariance: zero fork/patch di `workspace-mcp`
3. P4 Local-first: token/credential in locale con hardening e no secret leakage
4. P7 HITL: ogni write/distruttivo/costoso con gate esplicito
5. P8 Tool priority ladder: MCP upstream > skill > script locale
6. P9 Scoped toolsets: limite <=20 tool simultanei per sub-agent
7. P10 Self-documenting evolution: deviazioni solo via ADR

Regola operativa di piano:
- nessun task Fase 1 viene chiuso senza evidenza test + evidence log + aggiornamento docs/ADR pertinenti.

---

## 3) Pattern tecnici confermati dalle evidenze

### 3.1 workspace-mcp: modalita raccomandate

Snippet ufficiale (Context7 + README upstream):

```bash
# tiering progressivo
uvx workspace-mcp --tool-tier core
uvx workspace-mcp --tool-tier extended
uvx workspace-mcp --tool-tier complete

# modalita read-only
uvx workspace-mcp --read-only

# granular permissions (mutualmente esclusivo con --read-only)
uvx workspace-mcp --permissions gmail:organize drive:readonly

# transport mode
uvx workspace-mcp --transport streamable-http
```

Implicazione per ARIA:
- il wrapper deve passare opzioni in modo deterministico e policy-driven (non hardcoded).

### 3.2 OAuth security baseline 2026

Convergenza Google + RFC9700 + RFC8252:
- PKCE mandatory per public clients.
- no implicit flow; usare authorization code flow.
- least privilege scopes + incremental authorization in-context.
- state anti-CSRF obbligatorio.
- refresh token protetti, revocabili, con lifecycle esplicito.

Implicazione per ARIA:
- ADR-0003 gia coerente, ma Fase 1 deve renderla enforced end-to-end (wrapper + check + test + runbook).

---

## 4) Piano Fase 0 - Program setup e governance baseline

## Objective
Stabilire un singolo piano di controllo anti-drift tra upstream workspace-mcp, configurazioni ARIA, policy HITL/scope e quality gates.

## Context
- roadmap: sezione "Fase 0" in `docs/roadmaps/google-workspace_MCP_enhanchement_roadmap.md`
- blueprint: P1..P10 + sezioni governance/documentazione
- stato attuale validator e config agent/skills

## Constraints
- no modifiche sorgente upstream
- nessuna policy write senza owner + HITL policy
- tutte le matrici e i validator devono essere machine-checkable

## Inputs
- `.aria/kilocode/kilo.json`, `.aria/kilocode/mcp.json`
- `.aria/kilocode/agents/*.md`, `.aria/kilocode/skills/**/SKILL.md`
- `scripts/validate_agents.py`, `scripts/validate_skills.py`

## Execution Plan (atomic backlog)

### W0.1 - Baseline snapshot freeze
1. Generare snapshot versioni/tool surface upstream Workspace.
2. Generare snapshot config locale ARIA (agent, skills, scheduler hooks, wrapper runtime env).
3. Salvare evidence in documento dedicato.

Deliverable:
- `docs/roadmaps/workspace_baseline_snapshot_YYYY-MM-DD.md`

Snippet esempio (estrazione baseline):

```bash
uvx workspace-mcp --help
uvx workspace-mcp --tool-tier core --read-only --transport streamable-http --help
python scripts/validate_agents.py
python scripts/validate_skills.py
```

### W0.2 - Tool Governance Matrix centralizzata
1. Creare matrice canonica: tool -> dominio -> read/write -> rischio -> HITL -> scope minimo -> owner -> test-id.
2. Separare row policy tra `allow`, `ask`, `deny`.
3. Inserire mapping verso skill/workflow previsti.

Deliverable:
- `docs/roadmaps/workspace_tool_governance_matrix.md`

Schema minimo consigliato:

```markdown
| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|----|------|--------|---------------|-----------|-------|-------------|
| google_workspace_search_gmail_messages | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-R-001 |
| google_workspace_send_gmail_message | gmail | write | high | ask | yes | gmail.send | workspace-owner | GW-W-004 |
```

### W0.3 - ADR posture credenziali wrapper/runtime
1. Formalizzare deroga controllata: file runtime compatibilita upstream + keyring first.
2. Documentare hardening, retention, cleanup, ownership, permessi file.

Deliverable:
- `docs/foundation/decisions/ADR-00XX-workspace-wrapper-runtime-credentials.md`

### W0.4 - Validator modernization (legacy -> canonical)
1. Aggiornare validator da `mcp.json`-only a `kilo.json` + fallback controlled.
2. Aggiungere check automatico P9 su agent e skill contexts.
3. Aggiungere check policy completeness sulla governance matrix.

Deliverable:
- update `scripts/validate_agents.py`
- update `scripts/validate_skills.py`
- new `scripts/validate_workspace_governance.py`

Pseudo-check snippet:

```python
def assert_policy_row(row: dict[str, str]) -> None:
    required = ["tool_name", "rw", "risk", "policy", "hitl_required", "min_scope", "owner", "testcase_id"]
    missing = [k for k in required if not row.get(k)]
    if missing:
        raise ValueError(f"governance row incomplete: {missing}")
    if row["rw"] == "write" and row["hitl_required"] != "yes":
        raise ValueError(f"write tool without HITL: {row['tool_name']}")
```

## Definition of Done - Fase 0

Tutti i seguenti veri:
1. governance matrix completa per tutti i domini upstream;
2. validator verdi su config reale;
3. nessuna write policy senza owner/HITL/test-id;
4. ADR credenziali wrapper approvata;
5. evidence pack pubblicato.

## Verification

```bash
python scripts/validate_agents.py
python scripts/validate_skills.py
python scripts/validate_workspace_governance.py
pytest -q tests/unit/agents/workspace tests/unit/scripts
```

## Expected Output

- `docs/roadmaps/workspace_baseline_snapshot_YYYY-MM-DD.md`
- `docs/roadmaps/workspace_tool_governance_matrix.md`
- `docs/foundation/decisions/ADR-00XX-workspace-wrapper-runtime-credentials.md`
- validator aggiornati e test associati

## Non-goals

- nessuna estensione funzionale runtime Workspace
- nessun refactor scheduler execution path

---

## 5) Piano Fase 1 - Auth, scope e security hardening

## Objective
Passare da baseline Gmail-read operativa a baseline multi-servizio governata, sicura e verificata (Gmail/Calendar/Drive/Docs/Sheets).

## Context
- roadmap: sezione "Fase 1"
- blueprint + ADR-0003
- gap reale nel wrapper: scope hardcoded Gmail

## Constraints
- no secret leakage nei log
- scope escalation solo via policy/ADR
- write path sempre HITL

## Inputs
- `scripts/wrappers/google-workspace-wrapper.sh`
- `src/aria/agents/workspace/oauth_helper.py`
- `src/aria/agents/workspace/scope_manager.py`
- `.aria/runtime/credentials/google_workspace_scopes_primary.json`

## Execution Plan (atomic backlog)

### W1.1 - Scope source canonicale e de-hardcode wrapper
1. Rimuovere hardcode `gmail.readonly` dal payload credenziali wrapper.
2. Caricare scopes da sorgente canonica runtime + env policy override.
3. Ordinare/deduplicare scopes deterministicamente.

Esempio payload target (wrapper sync):

```python
payload = {
    "token": existing_token,
    "refresh_token": refresh_token,
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": client_id,
    "client_secret": client_secret,
    "scopes": resolved_scopes,  # no hardcode statico
    "expiry": None,
}
```

### W1.2 - Scope coherence check runtime vs toolset
1. Derivare `required_scopes` dai tool abilitati (via governance matrix).
2. Confrontare con granted scopes runtime.
3. Bloccare esecuzione write/read non consentiti con errore actionabile.

Esempio check:

```python
missing = sorted(set(required_scopes) - set(granted_scopes))
if missing:
    raise OAuthError(
        "Missing OAuth scopes for active toolset: " + ", ".join(missing)
    )
```

### W1.3 - Hardening credenziali runtime
1. Enforce permessi: dir `0700`, file `0600`.
2. Redaction obbligatoria per token/logging.
3. Cleanup policy su revoke/rotation.
4. Testare rotazione/revoca con prova di cleanup.

Snippet shell hardening:

```bash
chmod 700 "$ARIA_HOME/.aria/runtime/credentials/google_workspace_mcp"
find "$ARIA_HOME/.aria/runtime/credentials/google_workspace_mcp" -type f -name "*.json" -exec chmod 600 {} \;
```

### W1.4 - Auth E2E test matrix
1. Setup manual fallback (keyring unavailable path).
2. Token refresh flow.
3. Revoca + re-consent.
4. Smoke auth su 5 domini target.

Test matrix minima:

```markdown
| test_id | scenario | expected |
|---------|----------|----------|
| GW-AUTH-001 | first consent primary scopes | token + scopes file written |
| GW-AUTH-004 | missing scope for calendar | actionable error + re-consent path |
| GW-AUTH-007 | revoke token | keyring + runtime file cleanup |
| GW-SMOKE-010 | Gmail search | pass |
| GW-SMOKE-011 | Calendar list/get | pass |
| GW-SMOKE-012 | Drive search/read | pass |
| GW-SMOKE-013 | Docs read/create | pass |
| GW-SMOKE-014 | Sheets read/modify | pass |
```

### W1.5 - Runbook operativo
1. Scrivere runbook con path, comandi, failure signatures, recovery.
2. Includere sequenza standard: setup -> refresh -> revoke -> re-consent.

Deliverable:
- `docs/operations/workspace_oauth_runbook.md`

## Definition of Done - Fase 1

Tutti i seguenti veri:
1. scope baseline multi-servizio attivabile da source canonica;
2. auth smoke pass su Gmail/Calendar/Drive/Docs/Sheets;
3. zero token leakage in log (unit + integration evidence);
4. wrapper e helper coperti da test regressione;
5. runbook operativo completo.

## Verification

```bash
pytest -q tests/unit/agents/workspace/test_oauth_helper.py
pytest -q tests/unit/agents/workspace/test_scope_manager.py
pytest -q tests/unit/credentials/test_oauth_first_setup_script.py
pytest -q tests/integration -k "workspace and oauth"
ruff check src scripts
mypy src
```

## Expected Output

- patch `scripts/wrappers/google-workspace-wrapper.sh`
- test suite auth/scope estesa
- `docs/operations/workspace_oauth_runbook.md`

## Non-goals

- segmentazione toolset P9 (fase 2)
- implementazione full scheduler workspace path (fase 4)

---

## 6) Handoff operativo dettagliato (Fase 0 -> Fase 1)

### 6.1 Handoff package obbligatorio

Per ogni fase consegnare bundle con:
1. change summary (what/why/risk)
2. evidenze comandi (lint/type/test/smoke)
3. diff policy/security-sensitive
4. issue list aperta con severita e owner
5. rollback plan validato

Template handoff:

```markdown
# Handoff - Phase X

## Scope completed
- ...

## Files changed
- ...

## Verification evidence
- command: ...
- result: PASS/FAIL

## Security checks
- token redaction: PASS
- file perms: PASS
- HITL policy: PASS

## Known gaps
- ...

## Rollback
- git revert strategy: ...
- runtime cleanup: ...
```

### 6.2 Gate formali prima del passaggio fase

Gate G0 (fine Fase 0):
- governance matrix accepted
- validator CI green
- ADR credenziali runtime accepted

Gate G1 (fine Fase 1):
- auth e2e matrix green
- runbook validato con dry-run
- leak scan log green

### 6.3 Ruoli consigliati per team handoff

- Owner tecnico: workspace maintainer
- Security reviewer: credential/logging reviewer
- QA owner: auth e2e owner
- Docs owner: operations/runbook owner

---

## 7) Prompt pack operativo (Codex/Claude/OpenCode/KiloCode)

Formato comune (roadmap contract):

```text
Objective: <specifico e misurabile>
Context: <path file + roadmap/blueprint refs>
Constraints: <P1..P10 + ADR refs>
Inputs: <matrix, config, tests>
Execution Plan:
1) ...
2) ...
Definition of Done:
- ...
Verification:
- <command>
Expected Output:
- <file>
Non-goals:
- ...
```

Esempio pronto Fase 1 (wrapper de-hardcode):

```text
Objective: Replace hardcoded gmail.readonly scopes in wrapper with canonical scope resolution.
Context: scripts/wrappers/google-workspace-wrapper.sh, docs/roadmaps/google-workspace_MCP_enhanchement_roadmap.md (Phase 1), docs/foundation/aria_foundation_blueprint.md (P1,P2,P4,P7).
Constraints: No upstream fork; no secret logging; deterministic scope ordering.
Inputs: .aria/runtime/credentials/google_workspace_scopes_primary.json, docs/roadmaps/workspace_tool_governance_matrix.md.
Execution Plan:
1) Add canonical scope loading function.
2) Replace static payload scopes with resolved scopes.
3) Add regression tests for fallback and invalid scope file.
Definition of Done:
- No static gmail.readonly in wrapper credential payload.
- Tests pass.
Verification:
- pytest -q tests/unit/agents/workspace/test_oauth_helper.py
- pytest -q tests/unit/agents/workspace/test_scope_manager.py
Expected Output:
- updated scripts/wrappers/google-workspace-wrapper.sh
- updated tests
Non-goals:
- Toolset segmentation and scheduler runtime changes.
```

---

## 8) Risk register mirato (Fasi 0-1)

1. Scope creep non controllato
   - Mitigazione: incremental auth + ADR escalation + governance matrix gates
2. Regressione OAuth in wrapper refactor
   - Mitigazione: canary account + auth e2e + rollback script
3. Drift upstream/local
   - Mitigazione: baseline snapshot periodico + validator drift check
4. Token leakage log/runtime
   - Mitigazione: redaction tests + file permission enforcement + CI grep guard

Leak guard snippet (CI safety check):

```bash
rg -n "refresh_token|access_token|GOOGLE_OAUTH_CLIENT_SECRET" .aria/runtime/logs src tests docs && exit 1 || true
```

---

## 9) Rollout e rollback sintetico

### Rollout (safe order)
1. Merge Fase 0 governance + validator.
2. Deploy wrapper hardening su canary account.
3. Eseguire auth e2e matrix.
4. Promuovere su primary account dopo 2 run verdi consecutivi.

### Rollback
1. Revert commit wrapper.
2. Ripristino file credenziali runtime da backup cifrato.
3. Re-run oauth setup minimal scopes.
4. Validazione smoke Gmail read path.

---

## 10) Checklist finale pronta all'esecuzione

- [ ] Baseline snapshot completato e firmato
- [ ] Governance matrix creata e validata
- [ ] ADR credenziali runtime approvata
- [ ] Validator aggiornati e verdi
- [ ] Wrapper de-hardcoded su scopes
- [ ] Scope coherence check attivo
- [ ] Hardening permessi/redaction attivo
- [ ] Auth e2e matrix completa e verde
- [ ] Runbook OAuth pubblicato
- [ ] Handoff package fase 0 e fase 1 consegnati

---

## 11) Tracciabilita rapida (Roadmap -> Piano)

- Roadmap Fase 0 attivita 1-4 -> Sezioni 4.1-4.4 di questo piano
- Roadmap Fase 1 attivita 1-5 -> Sezioni 5.1-5.5 di questo piano
- Roadmap deliverable/exit criteria -> DoD/Verification/Checklist sezioni 4-5-10

Questo documento e pronto per esecuzione incrementale con milestone M1 (fine Fase 0) e M2 (fine Fase 1) come gate formali.
