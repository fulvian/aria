---
document: Google Workspace OAuth Runbook
version: 1.1.0
status: draft
date_created: 2026-04-22
owner: fulvio
phase: Phase 1
---

# Google Workspace OAuth Runbook

## Purpose

This runbook documents the standard operational procedures for Google Workspace OAuth in ARIA, including setup, refresh, revocation, and recovery.

## Overview

ARIA uses OAuth 2.0 with PKCE to authenticate with Google Workspace APIs. The refresh token is stored in the OS keyring, and a runtime credentials file is created for the `workspace-mcp` server.

From 2026-04-23, the wrapper applies **dynamic tool pruning** before server start: enabled `--tools` are reduced to domains whose read scope is actually granted by the current refresh token. This prevents OAuth loops caused by stale or incomplete scope grants.

**Key components:**
- `oauth_first_setup.py` — Initial OAuth consent flow
- `google-workspace-wrapper.sh` — Bridge that reads keyring and creates runtime credentials
- `oauth_helper.py` — Runtime helper for token operations
- `scope_manager.py` — Scope enforcement and coherence checks

**Credential storage:**
- Refresh token: OS Keyring (primary)
- Runtime credentials: `.aria/runtime/credentials/google_workspace_mcp/<email>.json`
- Scopes metadata: `.aria/runtime/credentials/google_workspace_scopes_primary.json`

---

## Standard Sequences

### 1. Initial Setup (First Consent)

**When:** Fresh installation or after full revocation

**Steps:**
```bash
# 1. Ensure dependencies
./scripts/bootstrap.sh --check

# 2. Run OAuth setup
python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,gmail.send,calendar.readonly,calendar.events,drive.readonly,drive.file,documents.readonly,documents,spreadsheets.readonly,spreadsheets,presentations.readonly"

# 3. Verify
python3 -c "
from aria.agents.workspace.oauth_helper import GoogleOAuthHelper
h = GoogleOAuthHelper()
print('Configured:', h.is_configured())
print('Scopes:', h.get_scopes())
"

# 4. Test wrapper
./scripts/wrappers/google-workspace-wrapper.sh --help
```

**Expected output:**
- Browser opens to Google consent page
- After consent, token stored in keyring
- Scopes file created at `.aria/runtime/credentials/google_workspace_scopes_primary.json`

**Failure signatures:**
| Error | Cause | Resolution |
|-------|-------|------------|
| "No refresh token found" | Setup not run | Run `python scripts/oauth_first_setup.py` |
| Browser blocked | headless environment | Use `--manual` flag and paste redirect URL/code |
| Invalid client_id | Wrong credentials | Check `.env` or session file |

---

### 2. Token Refresh (Automatic)

**When:** Access token expires during operation

**How:** Handled automatically by `workspace-mcp` using the refresh token from keyring.

**No manual action required** — the wrapper passes the refresh token to `workspace-mcp`, which handles refresh internally.

**Monitoring:**
```bash
# Check if token is still valid
python3 -c "
from aria.agents.workspace.oauth_helper import GoogleOAuthHelper
h = GoogleOAuthHelper()
print('Configured:', h.is_configured())
"
```

**Inspect real granted scopes from refresh token (source of truth):**
```bash
/home/fulvio/coding/aria/.venv/bin/python - <<'PY'
import json, urllib.parse, urllib.request
from pathlib import Path
import sys
sys.path.insert(0, '/home/fulvio/coding/aria/src')
from aria.credentials.keyring_store import KeyringStore

session = json.loads(Path('.aria/runtime/credentials/google_oauth_manual_session.json').read_text())
refresh = KeyringStore().get_oauth('google_workspace', 'primary')
payload = urllib.parse.urlencode({
    'client_id': session['client_id'],
    'client_secret': session.get('client_secret', ''),
    'refresh_token': refresh,
    'grant_type': 'refresh_token',
}).encode()
req = urllib.request.Request('https://oauth2.googleapis.com/token', data=payload, headers={'Content-Type':'application/x-www-form-urlencoded'})
with urllib.request.urlopen(req, timeout=20) as r:
    print(json.loads(r.read().decode()).get('scope', ''))
PY
```

---

### 3. Token Revocation

**When:** Security concern, credential rotation, or switching accounts

**Steps:**
```bash
# 1. Revoke via OAuth helper (recommended)
python3 -c "
from aria.agents.workspace.oauth_helper import GoogleOAuthHelper
h = GoogleOAuthHelper()
h.revoke('primary')
print('Revoked successfully')
"

# 2. Verify cleanup
ls -la .aria/runtime/credentials/google_workspace_mcp/  # Should be empty or dir missing
cat .aria/runtime/credentials/google_workspace_scopes_primary.json  # Should fail or be empty

# 3. Keyring verification
python3 -c "
import keyring
token = keyring.get_password('aria.google_workspace', 'primary')
print('Keyring token:', 'None' if token is None else '***' + token[-4:])
"
```

**What gets cleared:**
- Keyring: `aria.google_workspace` / `primary`
- Runtime credentials file: `.aria/runtime/credentials/google_workspace_mcp/<email>.json`
- Scopes file: `.aria/runtime/credentials/google_workspace_scopes_primary.json`

---

### 4. Re-consent After Revocation

**When:** After revocation or when adding new scopes

**Steps:**
```bash
# 1. Run setup again (will prompt for fresh consent)
python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,gmail.send,calendar.readonly,calendar.events,drive.readonly,drive.file,documents.readonly,documents,spreadsheets.readonly,spreadsheets,presentations.readonly"

# 2. If adding new scopes, specify them
python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,gmail.send,calendar.readonly,calendar.events,drive.readonly,drive.file,documents.readonly,documents,spreadsheets.readonly,spreadsheets,presentations.readonly"

# 3. Verify new scopes
python3 -c "
from aria.agents.workspace.oauth_helper import GoogleOAuthHelper
h = GoogleOAuthHelper()
print('Scopes:', h.get_scopes())
"
```

---

## Scope Management

### Current Minimal Scopes (per ADR-0003)

| Scope | Purpose |
|-------|---------|
| `gmail.readonly` | Read emails, labels, filters |
| `gmail.modify` | Modify labels, manage filters |
| `gmail.send` | Send emails |
| `calendar.readonly` | Read events without write intent |
| `calendar.events` | Manage calendar events |
| `drive.readonly` | Read/search all accessible Drive files |
| `drive.file` | Access Drive files created by app |
| `documents.readonly` | Read Google Docs |
| `documents` | Read/write Google Docs |
| `spreadsheets.readonly` | Read Google Sheets |
| `spreadsheets` | Read/write Google Sheets |
| `presentations.readonly` | Read Google Slides |

### Adding New Scopes

**Steps:**
1. Define the exact target scopes for the new toolset/policy
2. Run re-consent with explicit scopes: `python scripts/oauth_first_setup.py --scopes "..."`
3. Verify scopes file updated
4. Test with: `google-workspace-wrapper.sh`

**Note:** Broad scopes (`gmail`, `calendar`, `drive`, `presentations`) require explicit ADR approval.

---

## Credential Hardening (per ADR-0010)

### File Permissions

| Path | Permissions | Enforcement |
|------|-------------|-------------|
| `.aria/runtime/credentials/google_workspace_mcp/` | `0700` (drwx------) | Wrapper creates with `chmod 700` |
| `.aria/runtime/credentials/google_workspace_mcp/<email>.json` | `0600` (-rw-------) | Wrapper creates with `chmod 600` |

### Verification
```bash
# Check directory permissions
ls -la .aria/runtime/credentials/google_workspace_mcp/

# Should show: drwx------ (0700) for directory
# Should show: -rw------- (0600) for files
```

### If Permissions Are Wrong
```bash
# Fix directory
chmod 700 .aria/runtime/credentials/google_workspace_mcp

# Fix files
find .aria/runtime/credentials/google_workspace_mcp -name "*.json" -exec chmod 600 {} \;
```

---

## Troubleshooting

### "No refresh token found"

**Cause:** OAuth not configured or was revoked

**Resolution:**
```bash
python scripts/oauth_first_setup.py --scopes "gmail.readonly,gmail.modify,gmail.send,calendar.readonly,calendar.events,drive.readonly,drive.file,documents.readonly,documents,spreadsheets.readonly,spreadsheets,presentations.readonly"
```

### "Missing OAuth scopes for enabled toolset"

**Cause:** Runtime scopes don't match required scopes

**Resolution:**
1. Check current scopes: `cat .aria/runtime/credentials/google_workspace_scopes_primary.json`
2. Re-consent with correct scopes: `python scripts/oauth_first_setup.py --scopes "..."`

### Repeated `ACTION REQUIRED` on Drive/Slides read

**Cause:** enabled tool domain requires a scope not present in the currently granted refresh token scopes.

**Resolution path (deterministic):**
1. Check granted scopes via token refresh endpoint (command in section 2).
2. Ensure ARIA is restarted so wrapper dynamic pruning is applied.
3. If missing scope is required (e.g. `presentations.readonly`), run explicit re-consent:

```bash
python scripts/oauth_first_setup.py --scope-pack core-read --account primary
```

4. Re-run wrapper smoke test:

```bash
./scripts/wrappers/google-workspace-wrapper.sh --help
```

If output contains `INFO: workspace wrapper pruned tools missing granted scope: ...`, pruning is active and OAuth loop protection is in place.

### Wrapper fails with "credential file permissions too open"

**Cause:** File permissions on credentials file are too permissive

**Resolution:**
```bash
chmod 600 .aria/runtime/credentials/google_workspace_mcp/*.json
chmod 700 .aria/runtime/credentials/google_workspace_mcp/
```

### Keyring access fails

**Cause:** Keyring backend not available (e.g., no GNOME Keyring on headless)

**Resolution:** Check if `keyring` Python package can access backend:
```python
import keyring
keyring.get_password('test', 'test')  # Should not raise
```

If keyring unavailable, fallback to encrypted file per ADR-0003.

---

## Security Notes

### What IS Logged
- Scope grants (list of granted scopes) — NOT sensitive
- Operation outcomes (success/failure) — NOT sensitive
- Error messages (with token redaction) — NOT sensitive

### What IS NOT Logged
- Refresh tokens
- Access tokens
- Client secrets
- Any token-derived values

### Token Redaction Pattern
Logs use `***<last4>` pattern for any token values that might appear:
```
Refresh token: ***abcd
```

---

## References

- ADR-0003: OAuth Security Posture
- ADR-0010: Workspace MCP Wrapper Runtime Credentials Exception
- `docs/roadmaps/workspace_tool_governance_matrix.md`
- `scripts/oauth_first_setup.py`
- `scripts/wrappers/google-workspace-wrapper.sh`
- `src/aria/agents/workspace/oauth_helper.py`
- `src/aria/agents/workspace/scope_manager.py`

---

*This runbook is part of Phase 1 auth/scope hardening per `docs/plans/enhancment_workspace_PHASES-0_1_plan.md`.*
