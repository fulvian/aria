# Workspace Write Reliability - Baseline Inventory
**Created**: 2026-04-24
**Status**: Phase 0 Complete
**Branch**: `feature/workspace-write-reliability`

## Current Configuration State

### MCP Config (`.aria/kilocode/mcp.json`)

| Server | Command | Status | Issues |
|--------|---------|--------|--------|
| `google_workspace` | `uvx google_workspace_mcp` | **DISABLED** | Wrong executable name |
| `google_workspace` | -- | -- | Missing `--tools docs sheets slides drive` |
| `google_workspace` | -- | -- | Uses `localhost:8080` not `127.0.0.1:8080` |
| `google_workspace` | -- | -- | Missing write scope env vars |

### Environment Variables

| Variable | Current Value | Required for Write |
|----------|--------------|-------------------|
| `GOOGLE_OAUTH_CLIENT_ID` | Set (via `${GOOGLE_OAUTH_CLIENT_ID}`) | Yes |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Optional (via `${GOOGLE_OAUTH_CLIENT_SECRET_OPTIONAL}`) | Yes |
| `GOOGLE_OAUTH_REDIRECT_URI` | `http://localhost:8080/callback` | Should be `127.0.0.1` |
| `GOOGLE_OAUTH_USE_PKCE` | `true` | Correct |

### Missing Artifacts (from plan)

| File | Status | Notes |
|------|--------|-------|
| `scripts/oauth_first_setup.py` | **MISSING** | Referenced but not in repo |
| `scripts/wrappers/google-workspace-wrapper.sh` | **MISSING** | Referenced but not in repo |

### Root Causes Identified

1. **Bootstrap command mismatch**: Config uses `google_workspace_mcp` but correct is `workspace-mcp`
2. **Server in read-only mode**: Write tools explicitly disabled
3. **OAuth context not propagated**: `OAuth 2.1 mode requires an authenticated user` errors
4. **Callback uses localhost**: Brittle in hybrid environments (host + WSL)
5. **Missing setup wrappers**: Cannot guarantee repeatable bootstrap

## Required Changes

### Phase 1 - Bootstrap and Auth Fixes

1. [ ] Change `uvx google_workspace_mcp` → `uvx workspace-mcp`
2. [ ] Add `--tools docs sheets slides drive` to args
3. [ ] Change redirect URI from `localhost` to `127.0.0.1`
4. [ ] Create `google-workspace-wrapper.sh` with proper env var setup
5. [ ] Enable the server (remove `"disabled": true`)
6. [ ] Add scope environment variables for write capabilities:
   - `GOOGLE_OAUTH_SCOPE_DOCS=https://www.googleapis.com/auth/documents`
   - `GOOGLE_OAUTH_SCOPE_SHEETS=https://www.googleapis.com/auth/spreadsheets`
   - `GOOGLE_OAUTH_SCOPE_SLIDES=https://www.googleapis.com/auth/presentations`
   - `GOOGLE_OAUTH_SCOPE_DRIVE=https://www.googleapis.com/auth/drive.file`

### Phase 2 - Write Path Robustness

7. [ ] Add retry logic with truncated exponential backoff + jitter
8. [ ] Add idempotency keys for create operations
9. [ ] Add user-facing error mapping for:
   - Missing scopes
   - Read-only mode
   - Auth missing

### Phase 3 - Verification

10. [ ] Create smoke test script `workspace-write-health`
11. [ ] Add CI gate for tool registration check

## Provenance

- Config: `.aria/kilocode/mcp.json`
- Env template: `.env.example`
- Evidence: `docs/llm_wiki/wiki/google-workspace-mcp-write-reliability.md`
- Context7: `/taylorwilsdon/google_workspace_mcp` (verified 2026-04-24)
