---
adr: ADR-0010
title: Workspace MCP Wrapper Runtime Credentials Exception
status: draft
date_created: 2026-04-22
owner: fulvio
phase: Phase 0
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0010: Workspace MCP Wrapper Runtime Credentials Exception

## Status

**Draft** — 2026-04-22

## Context

The `google_workspace_mcp` upstream server (v1.19.0) does not natively integrate with OS keyring or ARIA's `KeyringStore`. It reads OAuth credentials from a JSON file in a format it defines at a path specified via `WORKSPACE_MCP_CREDENTIALS_DIR` environment variable.

ARIA's `scripts/wrappers/google-workspace-wrapper.sh` serves as a bridge that:
1. Reads the refresh token from ARIA's keyring (`KeyringStore`)
2. Creates a credentials file in the format expected by `workspace-mcp`
3. Avoids storing the refresh token in plaintext beyond the keyring

This creates a **controlled exception** to ADR-0003 §2.3 which states:
> "refresh_token MUST [...] NEVER be stored in plaintext files"

ADR-0003 anticipated this with:
> "Fallback: If keyring unavailable, use age-encrypted file"

But does not explicitly address the case where an **upstream MCP server requires a specific file format** for compatibility.

## Decision

### 1. Approved Exception: Runtime Credentials File

The runtime credentials file at `WORKSPACE_MCP_CREDENTIALS_DIR/<email>.json` is **approved** as a controlled exception to ADR-0003 §2.3 under the following mandatory conditions:

#### File Location
- **Directory:** `.aria/runtime/credentials/google_workspace_mcp/`
- **File:** `<safe_email>.json` where `safe_email` is the email with special chars replaced
- **Git status:** MUST be in `.gitignore`

#### File Format
```json
{
  "token": "<current_access_token_or_empty>",
  "refresh_token": "<refresh_token_from_keyring>",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
  "expiry": null
}
```

#### Mandatory Hardening
| Requirement | Value | Enforcement |
|-------------|-------|-------------|
| Directory permissions | `0700` | Script enforcement |
| File permissions | `0600` | Script enforcement |
| Keyring as source | refresh_token MUST come from keyring | Code review |
| Cleanup on revoke | File deleted on `revoke` operation | `oauth_helper.revoke()` |

#### What IS stored (exception to ADR-0003):
- `refresh_token` in plaintext file (needed by upstream)
- `client_id`, `client_secret` (needed by upstream)

#### What is NOT stored:
- Access tokens (transient, expire quickly)
- SOPS-encrypted API keys (handled separately)

### 2. Scope Source

Scopes in the runtime credentials file MUST be derived from:
1. **Primary source:** `.aria/runtime/credentials/google_workspace_scopes_primary.json` (canonical)
2. **Override:** Environment variable `WORKSPACE_SCOPES_OVERRIDE` (comma-separated)
3. **Default:** Empty array `[]` (upstream uses its own defaults)

The wrapper MUST NOT hardcode scopes (e.g., `gmail.readonly`).

### 3. Lifecycle

| Event | Action |
|-------|--------|
| OAuth setup | Keyring populated, runtime file created |
| Token refresh | Access token updated in runtime file by upstream |
| Scope change | Re-run `oauth_first_setup.py` with new scopes |
| Revoke | Keyring cleared, runtime file deleted |
| Wrapper invocation | File permissions verified before use |

### 4. Monitoring & Alerting

- File permissions checked at wrapper startup (fail-fast if wrong)
- File existence NOT checked (upstream handles missing gracefully)
- Keyring access failures logged with `***<last4>` token redaction

## Consequences

### Positive
- Enables use of upstream `workspace-mcp` without vendor modification (P2)
- Maintains refresh token security in keyring (primary storage)
- Allows deterministic credential bridging

### Negative
- Refresh token exists in plaintext at runtime (mitigated by file permissions + directory isolation)
- Two sources of truth for refresh token (mitigated by keyring as authoritative)

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| File permissions too open | Low | Critical | Wrapper enforces `chmod 600` on every run |
| File committed to git | Low | Critical | `.gitignore` excludes entire directory |
| Keyring unavailable | Low | High | Fallback handled by wrapper with clear error |
| Upstream credential format change | Medium | Medium | Monitoring upstream releases; ADR review |
| Token exfiltration via filesystem | Low | Critical | Directory isolated in `.aria/runtime/` (not global) |

## References

- ADR-0003: OAuth Security Posture
- Blueprint §12.1: Google Workspace Integration
- Blueprint §13.3: Credential Manager
- `scripts/wrappers/google-workspace-wrapper.sh`
- `src/aria/agents/workspace/oauth_helper.py`
- `docs/roadmaps/workspace_baseline_snapshot_2026-04-22.md`

## Implementation Notes

The following files implement this ADR:

| File | Role |
|------|------|
| `scripts/wrappers/google-workspace-wrapper.sh` | Creates runtime file with correct perms |
| `src/aria/agents/workspace/oauth_helper.py` | Keyring operations + revoke cleanup |
| `src/aria/credentials/keyring_store.py` | KeyringStore class |

---

**End ADR-0010**
