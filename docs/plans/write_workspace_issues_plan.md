# Write Workspace Issues - Implementation Plan

## 1. Objective

Stabilizzare in modo robusto la creazione e modifica di Google Docs, Sheets e Slides tramite MCP Google Workspace, eliminando i failure mode osservati nei log e introducendo una pipeline verificabile, testabile e operativamente sicura.

## 2. Scope

Focus su tool di write/create:

- Docs: `create_doc`, `modify_doc_text` (e batch write correlati)
- Sheets: `create_spreadsheet`, `modify_sheet_values`
- Slides: `create_presentation`, `batch_update_presentation`

Fuori scope: implementazione feature business nuove, refactor gateway/scheduler non direttamente necessari alla remediation.

## 3. Evidence Collected

### 3.1 Config and executable mismatch

- `google_workspace` in `.aria/kilocode/mcp.json:53` usa `uvx google_workspace_mcp` ma l'eseguibile non esiste nel package installato; il comando valido e `uvx workspace-mcp`.
- Stato corrente in repo: `.aria/kilocode/mcp.json:56` ha `"disabled": true`, quindi il server non e attivo da questa configurazione.

### 3.2 OAuth/session failures from runtime logs

- Errori ripetuti: `OAuth 2.1 mode requires an authenticated user` in `.aria/kilo-home/.google_workspace_mcp/logs/mcp_server_debug.log:21` e molte occorrenze successive.
- Callback loopback usata nei log OAuth: `redirect_uri=http://localhost:8080/callback` (multiple occorrenze nello stesso file).

### 3.3 Write tools disabled in read-only mode

- Log espliciti di disabilitazione write:
  - `.aria/kilo-home/.google_workspace_mcp/logs/mcp_server_debug.log:3333` `create_doc`
  - `.aria/kilo-home/.google_workspace_mcp/logs/mcp_server_debug.log:3342` `create_spreadsheet`
  - `.aria/kilo-home/.google_workspace_mcp/logs/mcp_server_debug.log:3343` `create_presentation`
- Stesso pattern ricorrente in molte sessioni successive (stesso file).

### 3.4 Missing local integration artifacts

- Handoff e piano fanno riferimento a `scripts/oauth_first_setup.py` e `scripts/wrappers/google-workspace-wrapper.sh` ma nel repository corrente questi file non sono presenti.

### 3.5 Official docs and upstream references

- Upstream MCP tools validated via Context7: `/taylorwilsdon/google_workspace_mcp`.
- Google official guidance validated:
  - OAuth native apps: loopback + PKCE + state
  - Docs/Sheets/Slides usage limits and retry discipline

## 4. Root Causes

1. **Bootstrap command mismatch**
   - Config punta a un executable non valido (`google_workspace_mcp`) invece di `workspace-mcp`.

2. **Server avviato in read-only**
   - I tool write sono sistematicamente disabilitati alla registrazione, quindi la creazione/modifica non puo funzionare per design.

3. **Auth context non propagato in modo deterministico**
   - Errori OAuth 2.1 "no authenticated user" mostrano session mapping incompleto/instabile in diverse sessioni.

4. **OAuth flow fragile su localhost**
   - Uso di `localhost:8080` in ambiente ibrido (host + WSL) aumenta rischio callback non raggiungibile.

5. **Allineamento incompleto tra piano e runtime**
   - File wrapper/setup previsti non presenti; difficile garantire bootstrap ripetibile.

## 5. Target Architecture (Robust)

### 5.1 Deterministic MCP startup profile

- Single startup profile per env (`dev-local`, `prod-local`) con:
  - comando `uvx workspace-mcp`
  - `--tools docs sheets slides drive`
  - niente `--read-only` per profilo write
  - fallback profile separato read-only (solo troubleshooting)

### 5.2 OAuth hardening

- Redirect URI primaria: `http://127.0.0.1:<port>/callback` (non `localhost` quando possibile).
- PKCE `S256` obbligatorio + `state` anti-CSRF.
- Scope minimi e separati per capability:
  - Docs write: `https://www.googleapis.com/auth/documents`
  - Sheets write: `https://www.googleapis.com/auth/spreadsheets`
  - Slides write: `https://www.googleapis.com/auth/presentations`
  - Drive linking/create file: `https://www.googleapis.com/auth/drive.file`
- Verifica post-token delle scope realmente concesse; blocco hard se scope write mancanti.

### 5.3 Capability gating

- Capability matrix runtime (`write_enabled.docs/sheets/slides`) calcolata all'avvio in base a:
  - tool registrati
  - scope effettive
  - stato auth valido
- Se capability non disponibile: errore esplicito e actionable, non fallback silenzioso.

### 5.4 Reliability patterns

- Retry con truncated exponential backoff + jitter su 429/5xx.
- Uso atomic batch endpoints:
  - Docs: `documents.batchUpdate`
  - Sheets: `spreadsheets.values.batchUpdate`
  - Slides: `presentations.batchUpdate`
- Idempotency key applicativa su operazioni di create (dedup su retry).

### 5.5 Observability and diagnostics

- Structured log obbligatorio per ogni write call:
  - `trace_id`, `tool_name`, `doc_type`, `attempt`, `http_status`, `error_reason`, `latency_ms`
- Health checks:
  - `mcp_list_tools_write_ready`
  - `oauth_scopes_write_ready`
  - `auth_subject_bound`

## 6. Implementation Plan

## Phase 0 - Safety and baseline (0.5 day)

1. Redigere inventory stato corrente (config attiva, env vars, cred path)
2. Sanitizzare processi/log per evitare secret leakage in output
3. Congelare baseline testabile (no feature changes)

**Acceptance**
- Baseline documentata
- Nessun secret stampato nei report

## Phase 1 - Bootstrap and auth fixes (1 day)

1. Correggere command line startup a `workspace-mcp`
2. Separare profili read-only vs write-enabled
3. Implementare callback loopback robusto con fallback su `127.0.0.1`
4. Verifica scope effettive subito dopo auth

**Acceptance**
- `list_tools` mostra tool write docs/sheets/slides disponibili nel profilo write
- Nessun errore "OAuth 2.1 mode requires an authenticated user" durante smoke flow

## Phase 2 - Write-path robustness (1.5 days)

1. Uniformare chiamate ai tool upstream reali (`create_doc`, `modify_sheet_values`, ecc.)
2. Introdurre retry/backoff standardizzato per 429/5xx
3. Introdurre idempotency key e dedup create
4. Aggiungere error mapping user-facing (scope missing, read-only mode, auth missing)

**Acceptance**
- Create+modify riusciti su Docs/Sheets/Slides in test end-to-end
- Retry verificato con fault injection su 429

## Phase 3 - Verification suite and regression guardrails (1 day)

1. Test matrix automatizzata per write tools
2. Smoke CLI `workspace-write-health` (o equivalente)
3. CI gate: fail se tool write non registrati/scopes mancanti

**Acceptance**
- Test suite green
- Gate CI blocca regressioni read-only/auth/scopes

## Phase 4 - Operational hardening (0.5 day)

1. Runbook incident response (auth expired, callback fail, 403 scope mismatch)
2. Dashboard minimale con error budget write ops
3. Rollback profile read-only documentato

**Acceptance**
- Runbook operativo disponibile
- Recovery time target <= 15 minuti per incident auth

## 7. Verification Matrix (Mandatory)

Per ogni test, registrare `trace_id`, input, output, HTTP status e link oggetto creato.

1. **Docs create**: `create_doc` -> documento creato, ID e URL validi
2. **Docs modify**: `modify_doc_text`/batch -> testo aggiornato, verifica contenuto
3. **Sheets create**: `create_spreadsheet` -> file creato
4. **Sheets modify**: `modify_sheet_values` -> range aggiornato con valori attesi
5. **Slides create**: `create_presentation` -> presentazione creata
6. **Slides batch update**: `batch_update_presentation` -> elemento slide inserito/aggiornato
7. **Negative test - read-only**: profilo RO deve fallire con errore esplicito e non ambiguo
8. **Negative test - missing scope**: errore esplicito + hint di remediation

## 8. Risks and Mitigations

- **R1 Callback non raggiungibile in ambienti ibridi**
  - Mitigazione: preferire `127.0.0.1`, porta random libera, fallback guidato.

- **R2 Scope creep o consent eccessivo**
  - Mitigazione: scope minimi per capability, verifica granted scopes, blocco hard.

- **R3 Retry storm su errori quota**
  - Mitigazione: backoff jitter + max retry + circuit breaker breve.

- **R4 Regressione su tool naming upstream**
  - Mitigazione: tool contract tests su nomi reali esposti da `list_tools`.

## 9. Deliverables

- Config startup MCP corretta e versionata
- Pipeline OAuth/callback robusta con verifica scope
- Test e2e per Docs/Sheets/Slides write paths
- Runbook operativo e dashboard metriche minime
- Aggiornamento wiki/provenance

## 10. Exit Criteria

Il piano si considera completato quando:

1. Tutti i test della Verification Matrix passano in ambiente locale ripetibile.
2. I log non mostrano piu disable dei tool write nel profilo write-enabled.
3. Nessun errore ricorrente "OAuth 2.1 mode requires an authenticated user" durante i flussi di write.
4. Docs/Sheets/Slides create+modify funzionano con success rate >= 99% su 50 run consecutivi di smoke test controllati.
