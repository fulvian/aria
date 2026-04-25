# Google Workspace MCP Write Reliability

**Last Updated**: 2026-04-25
**Status**: PHASE 3 VERIFICATION - In Progress
**Branch**: `feature/workspace-write-reliability`

## Purpose

Documenta criticita e remediation strategy per i tool di creazione/modifica Google Docs, Sheets e Slides in ARIA.

## OAuth Re-Authentication Instructions (Write Scope Recovery)

**Date**: 2026-04-25
**Status**: PENDING - Awaiting browser access
**When**: User will perform re-authentication when browser is available

### Problem

Current credentials have **read-only** scopes only:
```
✗ https://www.googleapis.com/auth/documents      (for create_doc, modify_doc_text)
✗ https://www.googleapis.com/auth/spreadsheets    (for create_spreadsheet, modify_sheet_values)
✗ https://www.googleapis.com/auth/presentations   (for create_presentation, batch_update_presentation)
✗ https://www.googleapis.com/auth/drive.file      (for drive file operations)
```

The existing token expired on 2026-04-24 and only has `readonly` versions of these scopes.

### Required Steps for Re-Authentication

When browser access is available, execute the following steps:

#### Step 1: Verify Credentials File Location
```bash
cat .aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json
```
Note: Contains `refresh_token` which will be used for new auth flow.

#### Step 2: Set Environment Variables
```bash
export GOOGLE_OAUTH_CLIENT_ID="YOUR_CLIENT_ID.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="YOUR_CLIENT_SECRET"
export GOOGLE_OAUTH_REDIRECT_URI="http://127.0.0.1:8080/callback"
export OAUTHLIB_INSECURE_TRANSPORT=1
```

**Note**: Actual credentials are in `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json`

#### Step 3: Run OAuth Setup Script
```bash
cd /home/fulvio/coding/aria
python3 scripts/oauth_first_setup.py
```

Or use the wrapper script:
```bash
./scripts/wrappers/google-workspace-wrapper.sh --setup
```

#### Step 4: Complete Consent Screen (Browser Required)

1. The script will open a browser window for Google's OAuth consent screen
2. **IMPORTANT**: When presented with scopes, ensure these write scopes are checked:
   - `https://www.googleapis.com/auth/documents` (NOT readonly)
   - `https://www.googleapis.com/auth/spreadsheets` (NOT readonly)
   - `https://www.googleapis.com/auth/presentations` (NOT readonly)
   - `https://www.googleapis.com/auth/drive.file`
   - Also include: `https://www.googleapis.com/auth/gmail.send` (if needed)

3. Authorize the application
4. The redirect will be captured and `refresh_token` will be stored

#### Step 5: Verify Write Scopes

After re-authentication, verify scopes:
```bash
python3 scripts/workspace_auth.py
# Or with verbose output:
python3 scripts/workspace-write-health.py --verbose
```

Expected output when write scopes are granted:
```
Write Ready: True
Granted Scopes should include:
  + https://www.googleapis.com/auth/documents
  + https://www.googleapis.com/auth/spreadsheets
  + https://www.googleapis.com/auth/presentations
  + https://www.googleapis.com/auth/drive.file
```

#### Step 6: Test Write Operations

```bash
# Run unit tests (will no longer be skipped)
pytest tests/unit/tools/test_workspace_write.py -v

# Run health check
python3 scripts/workspace-write-health.py --verbose
```

### Script References

| Script | Purpose |
|--------|---------|
| `scripts/oauth_first_setup.py` | PKCE code verifier/challenge generators |
| `scripts/workspace_auth.py` | OAuth scope verification (used after re-auth) |
| `scripts/workspace-write-health.py` | Health check CLI |
| `scripts/wrappers/google-workspace-wrapper.sh` | Robust MCP startup wrapper |

### Credentials File

Location: `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json`

After successful re-authentication, this file will be updated with:
- New `token` (refreshed access token)
- New `expiry` timestamp
- Full write scopes

### Security Notes

- **Never commit** credentials files to git
- **Never log** tokens or refresh tokens
- The `refresh_token` is stored locally in the credentials file (NOT in keyring per current implementation)
- If keyring becomes available, migrate to keyring storage per original design

---

## Key Facts

1. ~~In configurazione locale, il comando `uvx google_workspace_mcp` non e valido; il comando funzionante e `uvx workspace-mcp`.~~ **FIXED 2026-04-24**
2. ~~I log mostrano avvii ripetuti in read-only con disabilitazione esplicita di `create_doc`, `create_spreadsheet`, `create_presentation`.~~ **FIXED - server now enabled**
3. ~~Il callback OAuth nei log usa `http://localhost:8080/callback`; su ambienti ibridi e consigliato usare loopback IP `127.0.0.1` per maggiore affidabilita.~~ **FIXED 2026-04-24**
4. I log mostrano errori OAuth 2.1 ricorrenti di assenza utente autenticato (`OAuth 2.1 mode requires an authenticated user`). **PENDING - Re-authentication required for write scopes**
5. ~~Nel repository corrente `google_workspace` risulta `disabled: true` in `.aria/kilocode/mcp.json`.~~ **FIXED 2026-04-24 - now `disabled: false`**
6. **Current credentials have READ-ONLY scopes only. Missing all write scopes.** **PENDING - Re-authentication with browser required**

## Upstream Tool Mapping (Context7 verified)

- Docs write path: `create_doc`, `modify_doc_text`
- Sheets write path: `create_spreadsheet`, `modify_sheet_values`
- Slides write path: `create_presentation`, `batch_update_presentation`

## Robustness Principles

- Startup profile separato read-only vs write-enabled ✓
- PKCE S256 + state + loopback IP callback ✓
- Scope minimi per capability (documents/spreadsheets/presentations/drive.file) ✓
- Verifica granted scopes prima di eseguire write (in progress)
- Retry truncated exponential backoff + jitter su 429/5xx ✓
- Structured logging per ogni tool write (`trace_id`, `tool_name`, `status`, `reason`) ✓
- Idempotency key generation + dedup store ✓

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

### Phase 2 - Write Path Robustness ✓ (2026-04-24)
- [x] Retry/backoff with jitter (`workspace_retry.py`)
- [x] Idempotency keys (`workspace_idempotency.py`)
- [x] Error mapping user-facing (`workspace_errors.py`)
- [x] Bug fix: forward reference in `IdempotencyRecord.from_dict()`

### Phase 3 - Verification Suite ⚠️ (In Progress)
- [x] Unit tests for retry logic, idempotency, error mapping (`tests/unit/tools/test_workspace_write.py`)
- [x] Health check CLI (`scripts/workspace-write-health.py`)
- [ ] Integration tests with live OAuth (requires `TEST_GOOGLE_WORKSPACE=1`)
- [ ] CI gate for write tools registration/scopes (PENDING)
- [ ] 50-run smoke test for >= 99% success rate (requires live OAuth)

**Note**: Unit tests are skipped by default due to `TEST_GOOGLE_WORKSPACE` guard.
Pure logic tests (retry, idempotency, error classes) verified via direct import.

### Phase 4 - Operational Hardening ✓ (2026-04-24)
- [x] Runbook: `docs/implementation/workspace-write-reliability/runbook.md`
- [x] Health check CLI
- [x] Error budget metrics
- [x] RTO targets documented

### Key Verified Behaviors (2026-04-25)
- Retry backoff: monotonic increase, capped at 60s ✓
- Idempotency key: deterministic, unique per operation+params ✓
- IdempotencyStore: tracks, deduplicates, marks completed ✓
- Error classes: AuthError, ScopeError, QuotaError, ModeError, NetworkError ✓

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
