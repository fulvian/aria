# Google Workspace MCP Write Reliability

**Last Updated**: 2026-05-02T13:45+02:00
**Status**: ✅ WRITE-ENABLED — OAuth re-auth completata, catalog/prompt/skill contract riallineato ai tool upstream
**Branch**: `fix/memory-recovery`

## Purpose

Documenta criticita, remediation e stato attuale per i tool Google Workspace in ARIA: Gmail, Drive, Calendar, Docs, Sheets, Slides — tutti con scopes write.

## Stato Attuale (2026-04-27)

### OAuth Re-authentication — COMPLETATA ✅

Il 2026-04-27 è stato eseguito il flusso OAuth PKCE completo con:
- PKCE S256 (code_verifier + code_challenge)
- Callback server su `http://localhost:8080/callback`
- `prompt=consent` per refresh_token sempre nuovo
- Scambio autorizzazione → token con verifier matching
- Salvataggio token JSON in `fulviold@gmail.com.json`

### Token Attuale

**File**: `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json`
**Backup pre-scrittura**: `fulviold@gmail.com.json.pre-write` (readonly scopes)

| Campo | Valore |
|-------|--------|
| Client ID | `PLACEHOLDER_CLIENT_ID` |
| Client Secret | `PLACEHOLDER_CLIENT_SECRET` |
| Refresh Token | ✅ Presente (persistente, non scade) |
| Access Token | ✅ Fresco (scade in 1h, auto-refresh con refresh_token) |
| Expiry | 2026-04-27T12:32 (rinnovabile automaticamente) |

### Scopes Concessi (10 — FULL WRITE)

```
✅ https://www.googleapis.com/auth/gmail.readonly
✅ https://www.googleapis.com/auth/gmail.modify
✅ https://www.googleapis.com/auth/gmail.send
✅ https://www.googleapis.com/auth/calendar
✅ https://www.googleapis.com/auth/calendar.events
✅ https://www.googleapis.com/auth/drive
✅ https://www.googleapis.com/auth/drive.file
✅ https://www.googleapis.com/auth/documents
✅ https://www.googleapis.com/auth/spreadsheets
✅ https://www.googleapis.com/auth/presentations
```

**Tutti gli scopes write sono concessi**: documents, spreadsheets, presentations, drive.file, drive.

## Architettura

### Wrapper Script

**File**: `scripts/wrappers/google-workspace-wrapper.sh` (v2)

Il wrapper gestisce:
- **Placeholder stripping**: `${VAR}` letterali → unset
- **Fallback OAuth creds**: se `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` mancanti, legge dal token JSON
- **Fallback email**: se `USER_GOOGLE_EMAIL` manca, legge da `google_workspace_user_email.txt`
- **Flag `--single-user`**: bypassa session mapping, usa refresh_token dal JSON
- **Tool set esteso**: `gmail drive calendar docs sheets slides`

### MCP Config

**File**: `.aria/kilocode/mcp.json`

```jsonc
"google_workspace": {
  "command": "scripts/wrappers/google-workspace-wrapper.sh",
  "env": {
    "GOOGLE_OAUTH_CLIENT_ID": "${GOOGLE_OAUTH_CLIENT_ID}",
    "GOOGLE_OAUTH_CLIENT_SECRET": "${GOOGLE_OAUTH_CLIENT_SECRET}",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:8080/callback",
    "USER_GOOGLE_EMAIL": "${USER_GOOGLE_EMAIL}",
    "GOOGLE_WORKSPACE_TOOLS": "gmail drive calendar docs sheets slides"
  }
}
```

### Env Vars (`.env`)

```
GOOGLE_OAUTH_CLIENT_ID=PLACEHOLDER_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET=PLACEHOLDER_CLIENT_SECRET
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8080/callback
USER_GOOGLE_EMAIL=fulviold@gmail.com
```

## OAuth Re-Authentication Details

### Script Usato

**File**: `scripts/oauth_exchange.py` (self-contained, creato 2026-04-27)

Flusso:
1. Genera PKCE code_verifier (64 byte) + code_challenge (S256)
2. Costruisce URL autorizzazione con tutti i 10 scopes
3. Avvia callback server HTTP su `localhost:8080/callback`
4. Apre browser automaticamente (webbrowser.open)
5. Attende redirect da Google (timeout 300s)
6. Scambia authorization code per token CON code_verifier
7. Salva token JSON in `fulviold@gmail.com.json` (chmod 600)
8. Verifica scopes concessi

### Troubleshooting

**Problema**: `redirect_uri_mismatch` con `http://127.0.0.1:8080/callback`
**Soluzione**: Usare `http://localhost:8080/callback` (localhost è registrato in GCP Console per questo client_id)

### Scrittura e Refresh

Il server `workspace-mcp` in `--single-user` mode:
1. Legge il token JSON da `.aria/runtime/credentials/google_workspace_mcp/`
2. Se `expiry` passato, usa `refresh_token` + `client_id` + `client_secret` per ottenere nuovo access token
3. Il `refresh_token` non scade mai (access_type=offline + prompt=consent)

## Key Facts

1. ✅ `uvx workspace-mcp` comando funzionante (non `google_workspace_mcp`)
2. ✅ Server abilitato: `disabled: false`
3. ✅ Redirect URI: `http://localhost:8080/callback` (funzionante)
4. ✅ OAuth re-auth completata con write scopes
5. ✅ Single-user mode attivo
6. ✅ Token JSON con refresh_token + write scopes salvato

## Script References

| Script | Purpose |
|--------|---------|
| `scripts/oauth_first_setup.py` | PKCE code verifier/challenge generators |
| `scripts/oauth_exchange.py` | Self-contained OAuth PKCE flow + token exchange (CREATO 2026-04-27) |
| `scripts/workspace_auth.py` | OAuth scope verification |
| `scripts/workspace-write-health.py` | Health check CLI |
| `scripts/wrappers/google-workspace-wrapper.sh` | MCP wrapper v2 (single-user, Gmail/Calendar) |

## Upstream Tool Mapping (Context7 verified)

- Gmail: `search_gmail_messages`, `send_gmail`, `modify_gmail`
- Calendar: `list_calendar_events`, `create_calendar_event`, `update_calendar_event`
- Docs write: `create_doc`, `modify_doc_text`
- Sheets write: `create_spreadsheet`, `modify_sheet_values`
- Slides write: `create_presentation`, `batch_update_presentation`
- Drive: `search_drive_files`, `get_drive_file`, `create_drive_file`

## Repo Contract Alignment (2026-05-02)

È stato corretto un drift interno tra wiki/docs e runtime ARIA:

- **Prompt synthetic tools**: il pattern corretto è
  1. `aria-mcp-proxy__search_tools({...})`
  2. `aria-mcp-proxy__call_tool({...})`
- **Catalog/skill naming**: i nomi legacy interni come
  `gmail_search`, `drive_list`, `docs_create`, `sheets_create`, `slides_create`
  non sono più la source of truth.
- La source of truth applicativa è ora allineata al naming upstream `workspace-mcp`
  riportato sopra.
- Il proxy mantiene una compatibilità retroattiva limitata per alcuni alias legacy
  `google_workspace`, ma i prompt e le skill devono usare i nomi canonici upstream.

## Robustness Principles (implementati)

- PKCE S256 + state + loopback IP callback ✅
- Scope completi per capability ✅ (dopo re-auth)
- Verifica granted scopes disponibile (`workspace_auth.py`) ✅
- Retry truncated exponential backoff + jitter su 429/5xx ✅
- Structured logging per ogni tool write ✅
- Idempotency key generation + dedup store ✅

## Security Notes

- **Never commit** credentials files to git (`.gitignore` ha `.env`)
- **Never log** tokens or refresh tokens
- Token JSON ha permessi `600` (solo owner)
- `.env` è gitignorato

## Provenance

- `.env` (aggiornato 2026-04-27)
- `.aria/kilocode/mcp.json` (aggiornato 2026-04-27)
- `scripts/wrappers/google-workspace-wrapper.sh` (v2, 2026-04-27)
- `scripts/oauth_exchange.py` (creato 2026-04-27)
- `scripts/oauth_first_setup.py` (creato 2026-04-24)
- `scripts/workspace_auth.py` (creato 2026-04-24)
- Context7 `/taylorwilsdon/google_workspace_mcp` (queried 2026-04-27)
- `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` (token con write scopes)
