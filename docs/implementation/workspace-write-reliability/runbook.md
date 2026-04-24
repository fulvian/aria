# Google Workspace MCP Runbook

**Document**: Incident Response and Operational Runbook
**Last Updated**: 2026-04-24
**Status**: Phase 4 - Operational Hardening
**Branch**: `feature/workspace-write-reliability`

## Overview

This runbook covers operational procedures for the Google Workspace MCP server,
including incident response, rollback procedures, and error budget monitoring.

## Health Check Commands

### Pre-Flight Check

```bash
# Verify wrapper script and configuration
./scripts/wrappers/google-workspace-wrapper.sh --check

# Verify OAuth scopes (requires valid token)
python scripts/workspace_auth.py $GOOGLE_ACCESS_TOKEN

# Run full health check
python scripts/workspace-write-health.py --verbose
```

### Runtime Monitoring

Check MCP server logs:
```bash
tail -f ~/.google_workspace_mcp/logs/mcp_server_debug.log
```

## Common Issues and Remediation

### Issue: "OAuth 2.1 mode requires an authenticated user"

**Severity**: High
**Impact**: Write operations fail, auth not propagating

**Diagnosis**:
1. Check if token exists: `echo $GOOGLE_OAUTH_CLIENT_ID`
2. Check token freshness: OAuth tokens may expire
3. Check callback reached: Look for `/callback` in logs

**Remediation**:
1. Re-run OAuth flow:
   ```bash
   python scripts/oauth_debug.py
   ```
2. Verify credentials in `.env`
3. Check `OAUTHLIB_INSECURE_TRANSPORT=1` is set (for local dev)
4. If token expired, revoke and re-authenticate at:
   https://myaccount.google.com/permissions

---

### Issue: "Read-only mode: Disabling tool 'create_doc'"

**Severity**: High
**Impact**: Create operations explicitly disabled

**Diagnosis**:
1. Check `disabled` flag in `.aria/kilocode/mcp.json`
2. Check if using correct startup profile

**Remediation**:
1. Ensure `google_workspace.disabled` is `false` or use `google_workspace_readonly` profile
2. Restart MCP server with write-enabled profile
3. Verify tools registered: `list_tools` should show `create_doc`

---

### Issue: "Rate limit exceeded" (HTTP 429)

**Severity**: Medium
**Impact**: Temporary failure, retries will succeed

**Remediation**:
1. Wait for Retry-After header value
2. Implementation has built-in backoff with jitter
3. If persistent, reduce request frequency

---

### Issue: "Missing required OAuth scopes"

**Severity**: High
**Impact**: Operation fails, needs re-consent

**Diagnosis**:
```python
from scripts.workspace_auth import verify_write_scopes
result = verify_write_scopes(access_token)
print(result.missing_scopes)
```

**Remediation**:
1. Revoke existing tokens: https://myaccount.google.com/permissions
2. Re-run OAuth setup with all scopes:
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/presentations`
   - `https://www.googleapis.com/auth/drive.file`

---

### Issue: Callback URL not reachable (hybrid environments)

**Severity**: Medium
**Impact**: OAuth flow cannot complete

**Symptoms**: Browser shows "Unable to connect" after auth

**Remediation**:
1. Use `127.0.0.1` instead of `localhost`:
   ```bash
   export GOOGLE_OAUTH_REDIRECT_URI="http://127.0.0.1:8080/callback"
   ```
2. Check firewall/proxy settings
3. Try different port if 8080 is blocked

---

## Rollback Procedure

### To Rollback to Read-Only Profile

1. **Disable write-enabled server**:
   ```bash
   # Edit .aria/kilocode/mcp.json
   # Set google_workspace.disabled: true
   # Set google_workspace_readonly.disabled: false
   ```

2. **Restart MCP server**

3. **Verify**:
   ```bash
   python scripts/workspace-write-health.py
   # Should show read-only mode
   ```

### To Disable Google Workspace MCP Entirely

```bash
# Edit .aria/kilocode/mcp.json
# Set google_workspace.disabled: true
# Set google_workspace_readonly.disabled: true

# Restart MCP client
```

---

## Error Budget

### Write Operations Success Rate Target

- **Target**: >= 99% success rate
- **Measurement Window**: 50 consecutive smoke tests
- **Alert Threshold**: < 95% success rate

### Monitoring Commands

```bash
# Run 50 smoke tests
for i in {1..50}; do
    python scripts/workspace-write-health.py || echo "FAIL: $i"
done

# Check success rate
echo "Success rate: X/50"
```

---

## Recovery Time Objectives

| Incident Type | Target Recovery Time |
|--------------|---------------------|
| Auth expired | <= 15 minutes |
| Callback fail | <= 15 minutes |
| 403 scope mismatch | <= 30 minutes |
| Quota exceeded | <= 60 minutes (natural recovery) |

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | (required) | OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | (required) | OAuth client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | `http://127.0.0.1:8080/callback` | OAuth callback |
| `GOOGLE_OAUTH_USE_PKCE` | `true` | Use PKCE validation |
| `OAUTHLIB_INSECURE_TRANSPORT` | `1` | Allow HTTP for local dev |
| `GOOGLE_WORKSPACE_TOOLS` | `docs sheets slides drive` | Tools to register |

### MCP Configuration

**Write-enabled profile** (`.aria/kilocode/mcp.json`):
```json
{
  "command": "uvx",
  "args": ["workspace-mcp", "--tools", "docs", "sheets", "slides", "drive"],
  "disabled": false,
  "env": {
    "GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:8080/callback"
  }
}
```

**Read-only fallback profile**:
```json
{
  "command": "uvx",
  "args": ["workspace-mcp", "--tools", "docs", "sheets", "slides", "drive"],
  "disabled": true,
  "env": {
    "GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:8081/callback"
  }
}
```

---

## Contacts

- **Primary**: Owner of `GOOGLE_OAUTH_CLIENT_ID` credentials
- **Documentation**: `docs/plans/write_workspace_issues_plan.md`
- **LLM Wiki**: `docs/llm_wiki/wiki/google-workspace-mcp-write-reliability.md`