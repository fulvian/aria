# Sprint 1.5 — First Start Handoff

**Date:** 2026-04-21
**Author:** Kilo (execution agent)
**Status:** RESOLVED — W1.5.D/E first-start path fixed and Kilo runtime isolated
**Blueprint:** `docs/foundation/aria_foundation_blueprint.md` §6.6, §7

---

## Executive Summary

The first-start blocker (`status=218/CAPABILITIES`) was reproduced and resolved.

Root cause is now confirmed with deterministic transient tests: in this desktop
`systemd --user` environment, the directives below trigger capability-drop
operations that fail before process exec:

- `PrivateDevices=true`
- `ProtectKernelModules=true`

Both directives were removed from ARIA desktop baseline units
(`aria-gateway`, `aria-scheduler`, `aria-memory`). Other hardening directives
remain active.

---

## Deterministic Root Cause Evidence

### Failing probes (218/CAPABILITIES)

```bash
systemd-run --user --wait --collect -p PrivateDevices=true /usr/bin/true
# exit=218
journalctl --user -u run-u1864.service -n 10 --no-pager
# Failed to drop capabilities: Operation not permitted

systemd-run --user --wait --collect -p ProtectKernelModules=true /usr/bin/true
# exit=218
journalctl --user -u run-u1865.service -n 10 --no-pager
# Failed to drop capabilities: Operation not permitted
```

### Passing probe (desktop-safe profile)

```bash
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

---

## Fix Applied

### Updated units

- `systemd/aria-gateway.service`
- `systemd/aria-scheduler.service`
- `systemd/aria-memory.service`

Changes:

- Removed `PrivateDevices=true`
- Removed `ProtectKernelModules=true`
- Added explicit comments documenting desktop user-mode incompatibility and ADR
  reference.

### Installer improvements

`scripts/install_systemd.sh` now:

- validates all three unit files with `systemd-analyze verify` during install
- installs/updates `aria-memory.service` consistently with the baseline
- starts/enables/disables `aria-memory.service` when unit is installed

### Kilo runtime isolation (global config exclusion)

`bin/aria` now executes Kilo with a dedicated ARIA runtime home to prevent
loading user-global config trees:

- `HOME=$ARIA_HOME/.aria/kilo-home`
- `XDG_CONFIG_HOME=$ARIA_HOME/.aria/kilo-home/.config`
- `XDG_DATA_HOME=$ARIA_HOME/.aria/kilo-home/.local/share`
- `XDG_STATE_HOME=$ARIA_HOME/.aria/kilo-home/.local/state`
- `KILO_CONFIG_DIR=$ARIA_HOME/.aria/kilocode`
- `KILO_DISABLE_EXTERNAL_SKILLS=true`

Debug evidence confirms `./bin/aria` does not load config from:

- `~/.config/kilo`
- `~/.kilocode`
- `~/.kilo`
- `~/.opencode`

Note: built-in Kilo agents are still visible in picker by product behavior;
this is separate from user-global agent files.

---

## Verification Snapshot

Executed checks after applying fix:

- `systemd-analyze verify ...` -> PASS
- `./scripts/install_systemd.sh install` -> PASS
- `systemctl --user daemon-reload` -> PASS
- `systemctl --user restart aria-gateway.service aria-scheduler.service` -> PASS
- `systemctl --user is-active aria-gateway.service aria-scheduler.service` -> `active`, `active`
- `./scripts/bootstrap.sh --check` -> PASS
- `./bin/aria run "Test isolamento ARIA: rispondi solo OK"` -> PASS (exit `0`,
  no npm executable-resolution error)

Service state now:

- `aria-gateway.service`: active (running)
- `aria-scheduler.service`: active (running)

---

## Sprint 1.5 W1.5.D/E/F Status

- W1.5.D (CLI first launch):
  - launcher/runtime invocation now uses official package `@kilocode/cli`
    and official executable path (`kilo`, fallback `kilocode`) in bridge
  - `./bin/aria run "Test isolamento ARIA: rispondi solo OK"` -> PASS
    (non-interactive run exits `0`; assistant text remains REPL/manual for
    deterministic content assertion)
  - `./bin/aria repl` -> manual-only (interactive), expected reply `OK`
- W1.5.E (Telegram first launch via systemd): RESOLVED (gateway active under `systemd --user`)
- W1.5.F (cleanup/evidence/workflow updates): COMPLETED for automatable scope
  (evidence docs + workflow update + `.age-bak` cleanup).

---

## Governance

Divergence from blueprint hardening profile is documented in:

- `docs/foundation/decisions/ADR-0008-systemd-user-capability-limits.md`
