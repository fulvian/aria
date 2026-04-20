---
adr: ADR-0004
title: Associative Memory Persistence Format
status: proposed
date_created: 2026-04-20
author: ARIA Core Team
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0004: Associative Memory Persistence Format

## Status

**Proposed** — 2026-04-20

## Context

Blueprint forbids `pickle` as canonical persistence format for associative memory
and requires a secure, versionable storage model for Phase 2.

## Draft Decision

- Use SQLite tables as canonical storage for associative edges and metadata.
- Store export/import snapshots in JSON for auditability and migrations.
- Keep graph persistence local-first under `.aria/runtime/memory/graph/`.

## Open Items

- Decide normalization strategy for entities and relationship types.
- Define migration/versioning scheme for graph schema updates.
- Define compaction and retention policy tied to CLM lifecycle.

## References

- `docs/foundation/aria_foundation_blueprint.md` §5.2, §18.H
- `docs/plans/phase-0/sprint-00.md` §9
