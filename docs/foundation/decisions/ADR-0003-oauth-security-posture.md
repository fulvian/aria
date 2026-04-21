---
adr: ADR-0003
title: OAuth Security Posture
status: accepted
date_created: 2026-04-20
date_decided: 2026-04-21
owner: fulvio
phase: 1
sprint: 1.4
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0003: OAuth Security Posture

## Status

**Accepted** — 2026-04-21

## Context

ARIA Phase 1 introduces Google Workspace integration (Gmail, Calendar, Drive, Docs, Sheets) via `google_workspace_mcp`. This requires OAuth 2.0 tokens for user authorization. We needed a security posture that:
- Minimizes token exposure
- Enforces least-privilege scope access
- Provides audit trail for scope grants
- Supports safe revocation

## Decision

### 2.1 PKCE-First (RFC 7636)

- **PKCE is mandatory** for all OAuth flows
- `GOOGLE_OAUTH_USE_PKCE=true` is the default
- `client_secret` is **discouraged** and optional; PKCE provides equivalent protection without shared secret

### 2.2 Scope Minimalism (§12.2)

**Minimal scopes** (usable without escalation):
```python
MINIMAL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]
```

**Broad scopes** (require explicit ADR):
- `gmail` (full)
- `calendar` (full)
- `calendar.readonly` (full)
- `drive` (full)
- `drive.readonly` (full)

### 2.3 Token Storage

**refresh_token MUST**:
- Be stored in OS keyring (Linux Secret Service via `keyring`)
- NEVER be stored in plaintext files, `.env`, or SOPS secrets
- Use service name `aria.google_workspace` account `primary`

**Fallback**: If keyring unavailable, use age-encrypted file in `.aria/credentials/keyring-fallback/` with a separate key from SOPS master key.

### 2.4 Revocation

- Provide explicit revocation via `aria workspace revoke` command
- Always clear both keyring and fallback file on revocation
- Call Google revoke endpoint before clearing local storage

### 2.5 Scope Escalation

- Scope escalation requires a **new ADR** explicitly approving the new scope
- User must re-run `oauth_first_setup.py` with new scopes
- No silent scope creep allowed

### 2.6 Audit

- Scope grants (the list of granted scopes) are **NOT sensitive** and can be logged
- Access tokens and refresh tokens are **NEVER logged**
- Use `***<last4>` redaction pattern for any token logging

## Consequences

### Positive

- Reduced attack surface from token theft
- Clear audit trail for scope changes
- PKCE prevents authorization code interception attacks
- Fallback ensures availability even without Secret Service

### Negative

- First-time setup requires browser interaction (acceptable for MVP)
- Scope escalation requires ADR process (intentional friction)

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Google disables refresh tokens after 6 months inactivity | Health check weekly; alert if 401 |
| Corporate proxy blocks PKCE | Fallback to client_secret documented |
| Keyring backend unavailable | age-encrypted fallback with separate key |

## References

- [RFC 7636 - PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [Google OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
- Blueprint §12.1, §12.2, §12.3, §13.3
- Sprint plan W1.4.K

## Implementation

- `scripts/oauth_first_setup.py` — PKCE OAuth flow
- `src/aria/agents/workspace/oauth_helper.py` — runtime token helper
- `src/aria/agents/workspace/scope_manager.py` — scope enforcement
- `scripts/wrappers/google-workspace-wrapper.sh` — keyring injection

---

**End ADR-0003**
