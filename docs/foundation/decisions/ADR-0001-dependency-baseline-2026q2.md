---
adr: ADR-0001
title: Dependency Baseline 2026Q2
status: accepted
date_created: 2026-04-20
date_accepted: 2026-04-20
author: ARIA Chief Architect
project: ARIA — Autonomous Reasoning & Intelligent Assistant
---

# ADR-0001: Dependency Baseline 2026Q2

## Status

**Accepted** — 2026-04-20

## Context

Phase 0 implementation revealed several dependency-related deviations from initial assumptions that require explicit documentation per P10 (Self-Documenting Evolution). This ADR establishes the ratified dependency baseline for ARIA.

## Deviation 1: SOPS Python Binding Unavailable

### Initial Assumption
- `sops>=3.8` Python binding from `pyproject.toml` would provide SOPS integration

### Reality
- SOPS Python binding was deprecated and removed
- SOPS is now Go-only and distributed as a standalone CLI binary

### Resolution
- Install SOPS CLI v3.12.2 as standalone binary to `~/.local/bin/sops`
- Continue using SOPS+age for encrypted credential management
- Age encryption unchanged and functional

### Risk Assessment
- **Impact**: Low — SOPS CLI provides equivalent functionality
- **Mitigation**: Bootstrap script validates SOPS binary presence

---

## Deviation 2: Heavy ML Dependencies Moved to Optional

### Initial Assumption
- Core dependencies would include: `lancedb`, `faster-whisper`, `openai-whisper`, `pytesseract`, `pillow`

### Reality
- These dependencies cause installation timeouts due to CUDA/numpy compilation
- Not required for Phase 0 (foundation) functionality

### Resolution
- Moved to `[project.optional-dependencies] ml = [...]`
- Users must explicitly install: `pip install aria[ml]` or `uv sync --extra ml`
- Core installation remains fast and lightweight

### Risk Assessment
- **Impact**: Low — ML features are Phase 1+ scope
- **Mitigation**: Clear documentation in pyproject.toml extras

---

## Deviation 3: SQLite Version Requirement

### Initial Assumption
- Ubuntu's system SQLite (3.45.1) would be sufficient

### Reality
- Blueprint requires SQLite >=3.51.3 (WAL-reset bug mitigation)
- Ubuntu 24.04 ships with SQLite 3.45.1

### Resolution
- Build SQLite 3.51.3 from source with FTS5 support
- Install to `/usr/local/` prefix
- Bootstrap script validates SQLite version: `sqlite3 --version`

### Risk Assessment
- **Impact**: Medium — requires custom build on target system
- **Mitigation**: Bootstrap script handles installation; documented in README

---

## Deviation 4: KiloCode CLI Package Reference

### Initial Assumption
- `@kilocode/cli` npm package would be directly installable and pin-able

### Reality
- `bin/aria` launcher uses `KILOCODE_CONFIG_DIR` for isolation
- Actual KiloCode binary may be installed separately from npm

### Resolution
- `package.json` references `kilocode: 0.9.19` as placeholder
- Main launcher `bin/aria` is shell-based and version-agnostic
- **Open**: Validate actual KiloCode CLI version on target system

### Risk Assessment
- **Impact**: Medium — launcher may need adjustment when KiloCode version is validated
- **Mitigation**: Document validation step in README

---

## Decision

The following dependency baseline is **ratified** for ARIA Phase 0:

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | >=3.11 | uv-managed |
| SQLite | >=3.51.3 | Built from source |
| SOPS | 3.12.2 | Go CLI binary |
| age | any | Debian apt package |
| ruff | latest | Linting |
| mypy | latest | Type checking |
| pytest | latest | Testing |

### Explicitly NOT in Core Dependencies
- lancedb, faster-whisper, openai-whisper, pytesseract, pillow (moved to `ml` extras)

---

## Consequences

- Bootstrap script must validate all runtime dependencies before service start
- `pyproject.toml` accurately reflects optional ML dependencies
- `bin/aria` launcher remains agnostic to KiloCode version (isolated config)

---

## References

- Blueprint §4.4 (Dependency Versions)
- Blueprint §16 (Ten Commandments) — P10 Self-Documenting Evolution
- Sprint-00.md Risk Register (R1, R2, R3, R4, R5)
