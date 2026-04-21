---
document: ARIA Phase 1 Sprint 1.5 Launch Readiness Evidence
version: 1.1.0
status: pass_cli_path_isolated
date_created: 2026-04-21
last_review: 2026-04-21
owner: fulvio
phase: 1
sprint: "1.5"
---

# Sprint 1.5 Launch Readiness Evidence

## Scope

- Root-cause isolation for `systemd --user` startup failure `218/CAPABILITIES`.
- Desktop-compatible hardening baseline applied to ARIA user units.
- Verification of first-start operational path and quality gates.
- Full Kilo runtime isolation from global user configuration.

## Root Cause Reproduction (Deterministic)

```bash
systemd-run --user --wait --collect -p PrivateDevices=true /usr/bin/true
# exit=218

journalctl --user -u run-u1864.service -n 10 --no-pager
# ... Failed to drop capabilities: Operation not permitted
# ... status=218/CAPABILITIES

systemd-run --user --wait --collect -p ProtectKernelModules=true /usr/bin/true
# exit=218

journalctl --user -u run-u1865.service -n 10 --no-pager
# ... Failed to drop capabilities: Operation not permitted
# ... status=218/CAPABILITIES

systemd-run --user --wait --collect \
  -p NoNewPrivileges=true \
  -p ProtectSystem=strict \
  -p ProtectHome=tmpfs \
  -p PrivateTmp=true \
  -p ProtectControlGroups=true \
  -p RestrictSUIDSGID=true \
  -p LockPersonality=true \
  -p MemoryDenyWriteExecute=true \
  -p RestrictAddressFamilies='AF_UNIX AF_INET AF_INET6' \
  -p SystemCallArchitectures=native \
  /usr/bin/true
# exit=0
```

Conclusion: `PrivateDevices=true` and `ProtectKernelModules=true` are not
compatible with this desktop user-session environment.

## Required Verification Commands and Outcomes

### 1) Unit validation

```bash
systemd-analyze verify systemd/aria-gateway.service systemd/aria-scheduler.service systemd/aria-memory.service
```

- Outcome: PASS (no diagnostics)

### 2) Install/update units

```bash
./scripts/install_systemd.sh install
```

- Outcome: PASS (`aria-scheduler`, `aria-gateway`, `aria-memory` installed/up-to-date)

### 3) Daemon reload

```bash
systemctl --user daemon-reload
```

- Outcome: PASS

### 4) Restart core services

```bash
systemctl --user restart aria-gateway.service aria-scheduler.service
```

- Outcome: PASS

### 5) Active state check

```bash
systemctl --user is-active aria-gateway.service aria-scheduler.service
```

- Outcome: `active`, `active`

### 6) Gateway status

```bash
systemctl --user status aria-gateway.service --no-pager -n 20
```

- Outcome: active (running), Telegram `getMe` and `deleteWebhook` 200 OK

### 7) Scheduler status

```bash
systemctl --user status aria-scheduler.service --no-pager -n 20
```

- Outcome: active (running)

### 8) Gateway journal

```bash
journalctl --user -u aria-gateway.service -n 30 --no-pager
```

- Outcome: startup completed, metrics on `127.0.0.1:9090`, polling active

### 9) Scheduler journal

```bash
journalctl --user -u aria-scheduler.service -n 30 --no-pager
```

- Outcome: scheduler loop active, periodic task execution logged

### 10) Bootstrap check

```bash
./scripts/bootstrap.sh --check
```

- Outcome: PASS (SOPS config and encrypted files verified)

### 11) CLI run smoke

```bash
./bin/aria run "Test isolamento ARIA: rispondi solo OK"
```

- Outcome: PASS (process exits `0`; no `npm error could not determine executable to run`)
- Note: in this non-interactive execution, `aria run` does not emit assistant text to
  stdout, but invocation path is healthy and executable resolution is fixed.

### 12) REPL smoke

```bash
./bin/aria repl
```

- Outcome: not automatable in this non-interactive session
- Manual smoke step: open REPL, submit `Test isolamento ARIA: rispondi solo OK`,
  verify response is exactly `OK`, then exit with `Ctrl-D`.

## Quality Gates

```bash
ruff check src/
ruff format --check src/
uv run mypy src
uv run pytest -q
```

- `ruff check src/`: PASS
- `ruff format --check src/`: PASS (70 files)
- `uv run mypy src`: PASS (0 issues)
- `uv run pytest -q`: PASS (280 passed)

## CLI Runtime Fix (W1.5.D Follow-up)

- Launcher runtime invocation updated to official package:
  - `bin/aria`: `npx --yes --package @kilocode/cli kilo ...`
- Gateway bridge invocation aligned to official package/executable:
  - `src/aria/gateway/conductor_bridge.py`
    - strategy A uses `npx --yes --package @kilocode/cli kilo run ...`
    - strategy B prefers `kilo chat ...` and falls back to `kilocode chat ...`
- NPM dependency aligned and pinned from live metadata:
  - `package.json`: `"@kilocode/cli": "7.2.14"`
- Full runtime isolation for Kilo v7+:
  - `bin/aria` now runs Kilo with dedicated ARIA homes:
    - `HOME=$ARIA_HOME/.aria/kilo-home`
    - `XDG_CONFIG_HOME=$ARIA_HOME/.aria/kilo-home/.config`
    - `XDG_DATA_HOME=$ARIA_HOME/.aria/kilo-home/.local/share`
    - `XDG_STATE_HOME=$ARIA_HOME/.aria/kilo-home/.local/state`
  - `KILO_CONFIG_DIR=$ARIA_HOME/.aria/kilocode`
  - `KILO_DISABLE_EXTERNAL_SKILLS=true`
  - Result: no config merge from `~/.config/kilo`, `~/.kilocode`, `~/.kilo`, `~/.opencode`.

### Isolation verification snapshot

```bash
./bin/aria run "ping" --print-logs --log-level DEBUG
```

- Observed config roots only under `.aria/kilo-home/.config/kilo` and
  `.aria/kilocode`.
- No log lines loading global config directories.
- Effective custom agents exposed by ARIA config:
  - `aria-conductor (primary)`
  - `search-agent (subagent)`
  - `workspace-agent (subagent)`
- Built-in Kilo agents (e.g., `ask`, `code`, `orchestrator`) remain visible by
  product design and are not evidence of global config leakage.
- Installer lifecycle behavior corrected for first-start reliability:
  - `scripts/install_systemd.sh` keeps install/status/uninstall coverage for
    `aria-memory.service`, but `start`/`enable` now target only core services
    (`aria-scheduler.service`, `aria-gateway.service`).
  - `disable` handles `aria-memory.service` opportunistically when present and
    does not hard-fail if memory is not enabled/available.

## W1.5.F Automated Cleanup

- Removed stale backup artifact:
  - `.aria/credentials/secrets/api-keys.enc.yaml.age-bak`
- Updated workflow and handoff tracking:
  - `.workflow/state.md`
  - `docs/handoff/first-start-handoff.md`

## Artifacts Updated

- `systemd/aria-gateway.service`
- `systemd/aria-scheduler.service`
- `systemd/aria-memory.service`
- `scripts/install_systemd.sh`
- `bin/aria`
- `src/aria/gateway/conductor_bridge.py`
- `package.json`
- `docs/operations/runbook.md`
- `docs/handoff/first-start-handoff.md`
- `docs/foundation/decisions/ADR-0008-systemd-user-capability-limits.md`
- `.workflow/state.md`
- `docs/implementation/phase-1/README.md`
