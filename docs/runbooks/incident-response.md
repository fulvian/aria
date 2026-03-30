# Incident Response Guide - ARIA

## Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|--------------|---------|
| P1 | Critical - Complete outage | 15 minutes | ARIA not responding at all |
| P2 | High - Major feature broken | 1 hour | Fast path returning errors |
| P3 | Medium - Degraded performance | 4 hours | Slow responses (>30s) |
| P4 | Low - Minor issue | 24 hours | UI glitch, non-critical error |

## Incident Response Process

### 1. Detection
Incidents can be detected via:
- Automated alerting (check CI/CD dashboards)
- User reports in #incidents channel
- On-call engineer observation

### 2. Initial Assessment
```bash
# Check service status
curl -s http://localhost:8080/health || echo "Service down"

# Check recent logs
tail -100 ~/.aria/logs/aria.log | grep -i error

# Check resource usage
top -bn1 | grep opencode
```

### 3. Declare Incident
```bash
# Create incident in tracking system
# Notify in #incidents channel:
# "@oncall P2 incident: Fast path returning 500 errors - investigating"
```

### 4. Assemble Response Team
For P1/P2:
- Incident Commander
- On-Call Engineer
- Relevant developer(s)

For P3/P4:
- On-Call Engineer

### 5. Investigate

**Common Issues:**

| Issue | Check | Fix |
|-------|-------|-----|
| Memory leak | `top` + `journalctl` | Restart service, file bug |
| Database lock | Check SQLite | Restart, check queries |
| LLM provider down | Provider status page | Use fallback |
| Permission denied | Check file permissions | Fix ownership |
| Network timeout | `curl` to endpoints | Check firewall |

**Investigation Commands:**
```bash
# View all recent errors
grep ERROR ~/.aria/logs/aria.log | tail -50

# View specific session
ls ~/.aria/sessions/
cat ~/.aria/sessions/<session-id>.json

# Check system resources
df -h
free -h
uptime

# Check database integrity
sqlite3 ~/.aria/aria.db "PRAGMA integrity_check"
```

### 6. Implement Fix

Possible fixes:
- Restart service: `systemctl restart aria`
- Clear cache: `rm -rf ~/.aria/cache/`
- Rollback config: See rollback-plan.md
- Disable feature: `export ARIA_FEATURE_X=false`

### 7. Verify Resolution

```bash
# Test basic functionality
./opencode -p "test"

# Check error rate
grep -c ERROR ~/.aria/logs/aria.log | tail -10

# Monitor for 10 minutes
watch -n 5 'curl -s localhost:8080/health'
```

### 8. Close Incident

1. Document root cause in incident tracker
2. Update #incidents with resolution
3. Schedule post-mortem if P1/P2
4. Create follow-up tickets for permanent fix

## Post-Mortem Template

```markdown
# Incident: [Title]
Date: [YYYY-MM-DD]
Severity: P[1-4]
Duration: [X hours Y minutes]

## Summary
[2-3 sentence description of what happened]

## Impact
- Users affected: [number or estimate]
- Duration: [how long issue lasted]

## Root Cause
[Technical explanation of why it happened]

## Timeline
- HH:MM - Issue detected
- HH:MM - Investigation started
- HH:MM - Fix deployed
- HH:MM - Issue resolved

## Lessons Learned
1. [What went well]
2. [What went poorly]
3. [Action items for prevention]

## Follow-up
- [ ] Ticket to fix root cause
- [ ] Improve monitoring
- [ ] Update runbook
```

## Monitoring & Alerting

Key metrics to monitor:
- Response latency (p95 < 5s)
- Error rate (< 1%)
- CPU usage (< 80%)
- Memory usage (< 90%)
- Disk usage (< 85%)

## Useful Commands Reference

```bash
# Service management
systemctl status aria
journalctl -u aria -f

# Logs
tail -f ~/.aria/logs/aria.log
grep ERROR ~/.aria/logs/aria.log | tail -100

# Configuration
cat ~/.aria/config.yaml
# Edit: nano ~/.aria/config.yaml

# Sessions
ls ~/.aria/sessions/
cat ~/.aria/sessions/<id>.json | jq

# Database
sqlite3 ~/.aria/aria.db ".tables"
sqlite3 ~/.aria/aria.db "SELECT COUNT(*) FROM episodes"
```

## Contacts

| Role | Primary | Backup |
|------|---------|--------|
| On-Call | [TBD] | [TBD] |
| DevOps | [TBD] | [TBD] |
| Security | [TBD] | [TBD] |
