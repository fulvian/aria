# Rollback Plan - ARIA

## Overview

This document describes the rollback procedures for ARIA in case of production issues.

## Rollback Triggers

Initiate rollback when:
- Error rate exceeds 5% of requests
- p95 latency exceeds 10 seconds for 5 consecutive minutes
- Critical functionality broken (e.g., no responses returned)
- Security incident detected

## Rollback Levels

### Level 1: Feature Flag Disable

If issues are isolated to specific features (agencies, deep path, policy router):

```bash
# Disable specific feature flags via environment variables
export ARIA_FEATURE_DEEP_PATH=false
export ARIA_FEATURE_AGENCIES=false
export ARIA_FEATURE_POLICY_ROUTER=false
```

### Level 2: Configuration Rollback

If issues are related to recent configuration changes:

1. Identify last known good configuration
2. Restore from backup:
   ```bash
   cp ~/.aria/config.yaml.backup ~/.aria/config.yaml
   ```
3. Restart ARIA

### Level 3: Binary Rollback

If issues require binary rollback:

1. Identify last known good release:
   ```bash
   # List recent tags
   git tag -l --sort=-version:refname | head -10
   ```

2. For Homebrew:
   ```bash
   brew downgrade opencode-ai
   ```

3. For AUR:
   ```bash
   # Install previous version
   wget https://github.com/opencode-ai/opencode/releases/download/vX.Y.Z/opencode-linux-x86_64.tar.gz
   tar -xzf opencode-linux-x86_64.tar.gz
   sudo mv opencode /usr/bin/
   ```

4. For manual installation:
   ```bash
   wget https://github.com/opencode-ai/opencode/releases/download/vX.Y.Z/opencode-linux-x86_64.tar.gz
   tar -xzf opencode-linux-x86_64.tar.gz
   ./opencode --version
   ```

## Rollback Verification

After rollback, verify:

1. **Build & Test**:
   ```bash
   go test ./...
   go build ./...
   ```

2. **Basic Functionality**:
   ```bash
   ./opencode -p "Hello"
   # Should return a response within 30 seconds
   ```

3. **Check Logs**:
   ```bash
   # Look for ERROR level logs
   journalctl -u aria --since "10 minutes ago" | grep ERROR
   tail -100 ~/.aria/logs/aria.log | grep ERROR
   ```

## Emergency Contacts

| Role | Contact |
|------|---------|
| On-Call Engineer | [TBD] |
| DevOps Lead | [TBD] |
| Security | [TBD] |

## Post-Rollback Actions

1. **Document** the incident in the incident tracker
2. **Notify** stakeholders via #incidents channel
3. **Schedule** post-mortem within 48 hours
4. **Create** fix branch for the root cause
