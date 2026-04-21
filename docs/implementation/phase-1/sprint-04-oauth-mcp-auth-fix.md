# Sprint 1.4 - Google Workspace MCP OAuth stabilization

Date: 2026-04-21

## Problem

Google Workspace MCP started correctly but Gmail tool calls failed with:

- `OAuth 2.1 mode requires an authenticated user for search_gmail_messages, but none was found`

Observed behavior:

- MCP process was alive and tools were listed.
- Tool calls still failed because stdio calls had no OAuth 2.1 authenticated user context.
- In some runs, forcing `--single-user` caused startup incompatibility with OAuth 2.1 mode.

## Root cause

Integration mismatch between ARIA wrapper flow and upstream `workspace-mcp` auth mode:

- ARIA used local refresh-token/keyring flow for a single local user.
- Upstream server was running with OAuth 2.1 expectations (context-bound authenticated user).
- Wrapper did not sync credentials into the upstream credential-store file format used by `workspace-mcp`.

## Implemented fix

### 1) OAuth setup resilience

`scripts/oauth_first_setup.py`

- Added manual fallback for callback failures:
  - parse full redirect URL, raw query string, or raw `code`.
  - keep CSRF `state` validation in manual path.
- Added `--manual` mode to skip local callback listener entirely and complete via paste.

### 2) Workspace wrapper alignment with upstream credential store

`scripts/wrappers/google-workspace-wrapper.sh`

- Resolve OAuth config from env, with fallback to ARIA runtime session metadata.
- Export deterministic credentials directory:
  - `WORKSPACE_MCP_CREDENTIALS_DIR=.aria/runtime/credentials/google_workspace_mcp`
- Auto-sync credential file for the active user in upstream JSON format:
  - `<email>.json` with `refresh_token`, `client_id`, `client_secret`, `token_uri`, `scopes`, `expiry`.
- Force compatible mode for local stdio/keyring integration:
  - `MCP_ENABLE_OAUTH21=false`

### 3) MCP config consistency

`.aria/kilocode/kilo.json`

- Added `MCP_ENABLE_OAUTH21=false` under `google_workspace.environment`.

## Verification evidence

- Wrapper startup exits cleanly (`EXIT=0`).
- Workspace MCP reports tool listing successfully in Kilo logs.
- Credentials directory validation points to ARIA runtime credential path.
- OAuth setup script unit tests pass:
  - `tests/unit/credentials/test_oauth_first_setup_script.py`

## Operational note

After config changes, a full ARIA session restart is required to reload MCP environment.
