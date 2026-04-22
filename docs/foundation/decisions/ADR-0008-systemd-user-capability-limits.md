---
adr: ADR-0008
title: systemd --user capability limits on desktop baseline
status: accepted
date_created: 2026-04-21
date_accepted: 2026-04-21
author: ARIA Chief Architect
project: ARIA - Autonomous Reasoning & Intelligent Assistant
context: Sprint 1.5 W1.5.E first-start blocker
---

# ADR-0008: systemd --user Capability Limits

## Status

**Accepted** - 2026-04-21

## Context

Blueprint section 6.6 defines a strong hardening profile for ARIA systemd
services. During Sprint 1.5 first-start verification on Ubuntu 24.04 desktop
(`systemd 255`, user manager), `aria-gateway.service` and
`aria-scheduler.service` failed with:

- `Failed to drop capabilities: Operation not permitted`
- `status=218/CAPABILITIES`

Failure occurred before Python process startup, indicating systemd exec phase
capability handling rather than application runtime logic.

Deterministic transient tests showed that, in this environment:

- `PrivateDevices=true` -> reproducible `218/CAPABILITIES`
- `ProtectKernelModules=true` -> reproducible `218/CAPABILITIES`

Equivalent tests with the remaining hardening directives succeeded.

## Decision

For desktop-first `systemd --user` baseline, ARIA service units MUST NOT set:

- `PrivateDevices=true`
- `ProtectKernelModules=true`

All other currently compatible hardening directives remain enabled, including:

- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=tmpfs`
- `PrivateTmp=true`
- `ProtectControlGroups=true`
- `ProtectKernelTunables=true` (where already present)
- `RestrictSUIDSGID=true`
- `LockPersonality=true` (where already present)
- `MemoryDenyWriteExecute=true` (where already present)
- `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`
- `SystemCallArchitectures=native`

## Rationale

- Preserves desktop operability for user services without requiring elevated
  capabilities (`CAP_SYS_ADMIN`) or root-managed system units.
- Keeps the strongest subset of hardening proven to work in this environment.
- Aligns with blueprint governance by documenting this divergence explicitly in
  an ADR (Ten Commandment #10).

## Consequences

### Positive

- `aria-gateway.service` and `aria-scheduler.service` start successfully under
  `systemd --user`.
- First-start experience becomes deterministic and automatable.

### Negative

- Reduced hardening compared to full section 6.6 profile for desktop user mode.
- Device namespace and kernel module protection are not enforced in user-mode
  baseline.

### Neutral / Future

- Server/container targets may re-enable stricter directives when run in
  environments that support required capability operations.
- Any future profile split (desktop vs server) requires follow-up ADR/update.

## Implementation

- Updated:
  - `systemd/aria-gateway.service`
  - `systemd/aria-scheduler.service`
  - `systemd/aria-memory.service`
- Added installer resilience:
  - `scripts/install_systemd.sh` now verifies units via `systemd-analyze verify`
  - installs `aria-memory.service` consistently

## References

- Blueprint: `docs/foundation/aria_foundation_blueprint.md` section 6.6
- Evidence pack: `docs/implementation/phase-1/sprint-15-launch-readiness-evidence.md`
- Handoff: `docs/handoff/first-start-handoff.md`
