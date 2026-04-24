# Google Workspace MCP Write Reliability

**Last Updated**: 2026-04-24
**Status**: IN PROGRESS - Phase 1 implementation
**Branch**: `feature/workspace-write-reliability`

## Purpose

Documenta criticita e remediation strategy per i tool di creazione/modifica Google Docs, Sheets e Slides in ARIA.

## Key Facts

1. ~~In configurazione locale, il comando `uvx google_workspace_mcp` non e valido; il comando funzionante e `uvx workspace-mcp`.~~ **FIXED 2026-04-24**
2. ~~I log mostrano avvii ripetuti in read-only con disabilitazione esplicita di `create_doc`, `create_spreadsheet`, `create_presentation`.~~ **FIXED - server now enabled**
3. ~~Il callback OAuth nei log usa `http://localhost:8080/callback`; su ambienti ibridi e consigliato usare loopback IP `127.0.0.1` per maggiore affidabilita.~~ **FIXED 2026-04-24**
4. I log mostrano errori OAuth 2.1 ricorrenti di assenza utente autenticato (`OAuth 2.1 mode requires an authenticated user`). **PENDING - scope verification needed**
5. ~~Nel repository corrente `google_workspace` risulta `disabled: true` in `.aria/kilocode/mcp.json`.~~ **FIXED 2026-04-24 - now `disabled: false`**

## Upstream Tool Mapping (Context7 verified)

- Docs write path: `create_doc`, `modify_doc_text`
- Sheets write path: `create_spreadsheet`, `modify_sheet_values`
- Slides write path: `create_presentation`, `batch_update_presentation`

## Robustness Principles

- Startup profile separato read-only vs write-enabled ✓
- PKCE S256 + state + loopback IP callback ✓
- Scope minimi per capability (documents/spreadsheets/presentations/drive.file) ✓
- Verifica granted scopes prima di eseguire write (in progress)
- Retry truncated exponential backoff + jitter su 429/5xx (pending)
- Structured logging per ogni tool write (`trace_id`, `tool_name`, `status`, `reason`) (pending)

## Implementation Status

### Phase 1 - Bootstrap and Auth ✓ (2026-04-24)
- [x] Fixed MCP command: `uvx workspace-mcp`
- [x] Added tools: `--tools docs sheets slides drive`
- [x] Fixed redirect URI: `127.0.0.1:8080/callback`
- [x] Enabled server: `disabled: false`
- [x] Created `google-workspace-wrapper.sh`
- [x] Created `oauth_first_setup.py`
- [x] Created `workspace_auth.py` for scope verification
- [x] Created `workspace-write-health.py` CLI
- [ ] OAuth scope verification post-auth (in progress)

### Phase 2 - Write Path Robustness (pending)
- [ ] Retry/backoff with jitter
- [ ] Idempotency keys
- [ ] Error mapping user-facing

## New Files Created

```
scripts/oauth_first_setup.py       # PKCE code verifier/challenge generators
scripts/wrappers/google-workspace-wrapper.sh  # Robust MCP wrapper
scripts/workspace_auth.py         # OAuth scope verification
scripts/workspace-write-health.py  # Health check CLI
docs/implementation/workspace-write-reliability/baseline-inventory.md
```

## Primary Remediation Artifact

- `docs/plans/write_workspace_issues_plan.md`

## Provenance

- Source: `.aria/kilocode/mcp.json` (updated: 2026-04-24)
- Source: `docs/handoff/mcp_google_workspace_oauth_handoff.md` (updated: 2026-04-21)
- Source: `.aria/kilo-home/.google_workspace_mcp/logs/mcp_server_debug.log` (updated: 2026-04-24)
- Source: `/home/fulvio/.google_workspace_mcp/logs/mcp_server_debug.log` (updated: 2026-04-24)
- Source: Context7 `/taylorwilsdon/google_workspace_mcp` (queried: 2026-04-24)
- Source: Google OAuth native apps guide (retrieved: 2026-04-24)
- Source: Google Docs usage limits (retrieved: 2026-04-24)
- Source: Google Sheets usage limits (retrieved: 2026-04-24)
- Source: Google Slides usage limits (retrieved: 2026-04-24)
- Source: Google Workspace MCP server configuration guide (retrieved: 2026-04-24)
