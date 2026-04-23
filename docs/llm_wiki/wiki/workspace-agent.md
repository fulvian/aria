---
title: Workspace Agent
sources:
  - docs/foundation/aria_foundation_blueprint.md §12
  - docs/foundation/decisions/ADR-0003-oauth-security-posture.md
  - docs/foundation/decisions/ADR-0010-workspace-wrapper-runtime-credentials.md
last_updated: 2026-04-23
tier: 1
---

# Workspace Agent — Google Workspace Integration

## Dipendenza

**Upstream**: `taylorwilsdon/google_workspace_mcp` v1.19.0+ (MIT, Python 3.10+), installato via `uvx workspace-mcp`.

*source: `docs/foundation/aria_foundation_blueprint.md` §12.1*

## OAuth PKCE Flow (ADR-0003)

### Setup (first-time)

`scripts/oauth_first_setup.py`:
1. Apre browser sul Google consent screen con **PKCE secret-less**
2. Redirect su `localhost:8080/callback`
3. Intercetta callback, memorizza `refresh_token` in **OS keyring** (service `aria.google_workspace`, account `primary`)
4. `client_secret` **opzionale e sconsigliato** — PKCE fornisce protezione equivalente

### Runtime

- Il server MCP recupera `refresh_token` dal keyring via `keyring.get_password()`
- Refresh `access_token` quando scaduto, transparente per l'agente
- Utente non deve riautenticarsi se non scade il refresh (Google: fino a 6 mesi inattività)

### Revoca

`aria workspace revoke` → chiama Google revoke endpoint + rimuove keyring entry + elimina runtime credentials file.

*source: `docs/foundation/decisions/ADR-0003-oauth-security-posture.md`*

## Scope Minimi

| Servizio | Scope | Giustificazione |
|----------|-------|-----------------|
| Gmail | `gmail.readonly` | Lettura e classificazione |
| Gmail | `gmail.modify` | Label, archive, no delete |
| Gmail | `gmail.send` | Invio esplicito email |
| Calendar | `calendar.readonly` | Lettura eventi |
| Calendar | `calendar.events` | Creazione/modifica eventi |
| Drive | `drive.readonly` | Ricerca/lettura file |
| Drive | `drive.file` | Scrittura file gestiti da ARIA |
| Docs | `documents.readonly` | Lettura documenti |
| Docs | `documents` | Scrittura documenti |
| Sheets | `spreadsheets.readonly` | Lettura fogli |
| Sheets | `spreadsheets` | Scrittura fogli |
| Slides | `presentations.readonly` | Lettura presentazioni (Google API scope name) |

**Nota**: Il Google API scope per Slides è `presentations.readonly` (non `slides.readonly`). Il governance matrix (`docs/roadmaps/workspace_tool_governance_matrix.md`) è stato aggiornato per usare il naming corretto. La funzione `normalize_scope()` nel wrapper prepende `https://www.googleapis.com/auth/` allo scope name, quindi il nome base deve essere `presentations.readonly`.

**Scope escalation**: Richiede nuovo ADR esplicito + re-run `oauth_first_setup.py`. No silent scope creep.

*source: `docs/foundation/aria_foundation_blueprint.md` §12.2*

## Runtime Credentials File (ADR-0010)

Il server `google_workspace_mcp` upstream richiede un file JSON con le credenziali OAuth in un formato specifico. ARIA crea questo file runtime dal keyring:

**Path**: `.aria/runtime/credentials/google_workspace_mcp/<safe_email>.json`

**Eccezione controllata** ad ADR-0003 (che vieta plaintext):
- Directory permissions: `0700`
- File permissions: `0600`
- Keyring resta la fonte autoritativa (source of truth)
- File eliminato su revoke
- `.gitignore` esclude l'intera directory

*source: `docs/foundation/decisions/ADR-0010-workspace-wrapper-runtime-credentials.md`*

## Wrapper Script

`scripts/wrappers/google-workspace-wrapper.sh`:
1. Legge refresh_token dal keyring
2. **Pre-refresh dell'access_token**: ottiene un access_token fresco prima di scrivere il credentials file, così workspace-mcp vede credenziali valide e non attiva il suo flusso OAuth interno (loop "ACTION REQUIRED")
3. Crea il runtime credentials file con permessi corretti (access_token fresco + expiry futura)
4. Imposta `GOOGLE_MCP_CREDENTIALS_DIR`
5. Normalizza args di startup MCP: se mancano selettori (`--tool-tier`, `--tools`, `--permissions`), forza default sicuro `--tools gmail calendar drive docs sheets slides --read-only` per evitare scope inflation e loop di re-auth su richieste read
6. Prune dinamico dei tool in base agli scope **realmente grantiti** dal refresh token (es. se manca `presentations.readonly`, il dominio `slides` viene rimosso automaticamente dagli args MCP)
7. Esegue `uvx workspace-mcp` con args effettivi

*source: `scripts/wrappers/google-workspace-wrapper.sh` (update 2026-04-23)*

## Policy per Operazioni

| Tipo operazione | Policy default | HITL? |
|----------------|---------------|-------|
| Read (email, calendar, drive) | `allow` | No |
| Write non-distruttivo (create event, label email) | `allow` | No |
| Write distruttivo (delete, send email) | `ask` | Sì |

## Implementazione Codice

```
src/aria/agents/workspace/
├── __init__.py
├── oauth_helper.py       # Runtime token management
└── scope_manager.py      # Minimal scopes enforcement
```

## Vedi anche

- [[credentials]] — OAuth token storage, keyring
- [[agents-hierarchy]] — Workspace-Agent nella gerarchia
- [[skills-layer]] — triage-email, calendar-orchestration, doc-draft
