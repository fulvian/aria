---
adr: ADR-0003
title: OAuth Security Posture
status: proposed
date_created: 2026-04-20
author: ARIA Core Team
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0003: OAuth Security Posture

## Status

**Proposed** — 2026-04-20

## Context

Blueprint and sprint plan require an explicit OAuth security posture before enabling
Google Workspace write operations.

## Draft Decision

- Keep OAuth credentials outside git and outside runtime logs.
- Persist refresh/access token state only through encrypted local storage.
- Enforce HITL for first-time authentication and scope escalation.
- Block write operations when OAuth token state is missing, invalid, or expired.

## Open Items

- Define exact token rotation policy and revocation workflow.
- Define minimum allowed scopes for Gmail/Calendar/Drive operations.
- Define fallback behavior when keyring is unavailable.

## References

- `docs/foundation/aria_foundation_blueprint.md` §13
- `docs/plans/phase-0/sprint-00.md` §9
