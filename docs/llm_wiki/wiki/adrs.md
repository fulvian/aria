---
title: Architecture Decision Records (ADRs)
sources:
  - docs/foundation/decisions/ADR-0001 through ADR-0010
last_updated: 2026-04-23
tier: 1
---

# Architecture Decision Records — Sommario

> Gli ADR sono la memoria delle decisioni architetturali. Ogni deviazione dal blueprint DEVE essere registrata qui (P10).
> Path: `docs/foundation/decisions/ADR-NNNN-<slug>.md`

## Indice ADR

### ADR-0001: Dependency Baseline 2026Q2
- **Status**: Accepted (2026-04-20)
- **Decisioni chiave**:
  - SOPS Python binding deprecato → SOPS CLI Go binary v3.12.2
  - ML dependencies (lancedb, faster-whisper, ecc.) moved to `[project.optional-dependencies] ml`
  - SQLite >= 3.51.3 built from source (WAL-reset bug fix)
  - KiloCode CLI versione agnostica nel launcher

### ADR-0002: SQLite Reliability Policy
- **Status**: Accepted (2026-04-20)
- **Decisioni chiave**:
  - SQLite >= 3.51.3 mandatory
  - PRAGMA: WAL mode, synchronous=NORMAL, busy_timeout=5000, foreign_keys=ON
  - FTS5 must be compiled in
  - Backup: WAL checkpoint before copy, retention 7 daily / 4 weekly

### ADR-0003: OAuth Security Posture
- **Status**: Accepted (2026-04-21)
- **Decisioni chiave**:
  - PKCE mandatory for all OAuth flows
  - Scope minimalism: solo gli scope minimi necessari
  - refresh_token in OS keyring (mai plaintext)
  - Scope escalation richiede nuovo ADR
  - Fallback: age-encrypted file se keyring non disponibile

### ADR-0004: Associative Memory Persistence Format
- **Status**: Proposed (2026-04-20)
- **Decisioni chiave**:
  - `pickle` vietato come storage canonico
  - SQLite tables per associative edges
  - JSON per export/import snapshots
  - Open: normalizzazione entità, migration scheme, compaction policy

### ADR-0005: Scheduler Concurrency
- **Status**: Accepted (Sprint 1.2)
- **Decisioni chiave**:
  - Lease-based concurrency con `lease_owner` + `lease_expires_at`
  - TTL default: 300s, heartbeat ogni 60s
  - Worker ID: `scheduler-{pid}-{8-char-hex}`
  - Reaper ogni 30s per lease scaduti
  - Single-writer invariante garantito da atomic UPDATE

### ADR-0006: Prompt Injection Mitigation
- **Status**: Accepted (Sprint 1.3)
- **Decisioni chiave**:
  - 3-layer defense: syntax frame + nested sanitization + system prompt
  - Tool outputs wrapped in `<<TOOL_OUTPUT>>...<</TOOL_OUTPUT>>`
  - Pre-processing strip nested frames (TOCTOU prevention)
  - `src/aria/utils/prompt_safety.py`: `wrap_tool_output()`, `sanitize_nested_frames()`

### ADR-0007: STT Stack Dual
- **Status**: Accepted (2026-04-20)
- **Decisioni chiave**:
  - Primary: `faster-whisper` (local, model `small`, CPU/GPU auto)
  - Fallback: `openai-whisper` (se faster-whisper import fails)
  - Cloud Whisper API: solo con flag `WHISPER_USE_CLOUD=1`
  - Lazy loading, graceful degradation

### ADR-0008: systemd --user Capability Limits
- **Status**: Accepted (2026-04-21)
- **Decisioni chiave**:
  - `PrivateDevices=true` e `ProtectKernelModules=true` rimossi
  - Causa: `218/CAPABILITIES` failure in systemd --user su Ubuntu 24.04 desktop
  - Tutte le altre hardening directives rimangono attive
  - Futuro: profili desktop vs server richiedono ADR dedicato

### ADR-0009: Kilo Agent Frontmatter + MCP npx Bin Resolution
- **Status**: Accepted (2026-04-21)
- **Decisioni chiave**:
  - Agent frontmatter riscritto con solo chiavi Kilo `AgentConfig` valide
  - Conductor: `websearch: false`, `codesearch: false`, `webfetch: false`
  - MCP config inline in `kilo.json` (non file `mcp.json` separato)
  - npx bin resolution: forma esplicita `--package=<@scope/pkg> <bin>`
  - Wrapper scripts per secret injection (brave, github, tavily, firecrawl, ecc.)

### ADR-0010: Workspace MCP Wrapper Runtime Credentials
- **Status**: Draft (2026-04-22)
- **Decisioni chiave**:
  - Eccezione controllata ad ADR-0003 per runtime credentials file
  - File JSON plaintext con refresh_token per google_workspace_mcp upstream
  - Permessi `0700`/`0600`, keyring come fonte autoritativa
  - File eliminato su revoke, escluso da git

### ADR-0011: Searcher Optimizer — Free-First Economic Router
- **Status**: Approved (2026-04-23)
- **Decisioni chiave**:
  - Tiered cost classification: A(free-unlimited) → B(free-limited) → C(costly) → D(paid)
  - Quality gates per intent: unique_results, distinct_domains, recency_ratio, top3_score_mean
  - RRF fusion (k=60) for multi-provider result merging
  - Budget enforcement via QuotaState with daily/monthly reset windows
  - Telemetry for cost/quality KPIs
  - 5 new modules: cost_policy, quality_gate, quota_state, fusion, telemetry

## Vedi anche

- [[ten-commandments]] — P10 (Self-Documenting Evolution)
- [[governance]] — ADR workflow e processo
