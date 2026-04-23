---
title: ARIA LLM Wiki Index
sources:
  - docs/foundation/aria_foundation_blueprint.md
  - docs/foundation/decisions/
  - AGENTS.md
  - README.md
  - pyproject.toml
  - Makefile
  - docs/operations/runbook.md
last_updated: 2026-04-24T00:19
tier: 1
---

# ARIA LLM Wiki — Index

> Bootstrap: 2026-04-23 | Source: `docs/foundation/aria_foundation_blueprint.md` v1.1.0-audit-aligned
> Stella Polare: il blueprint è la fonte autoritativa. Il wiki è un artefatto derivato per consultazione rapida.

## Scope

Questo wiki è la "conoscenza compilata" del progetto ARIA. Sintetizza blueprint, ADR, implementazione e operazioni
in pagine Markdown interconnesse leggibili da umani e LLM. Le fonti grezze (`docs/foundation/`, `docs/foundation/decisions/`,
`docs/operations/`) restano il ground truth (Tier 0). Questo wiki è Tier 1 — derivato, ricostruibile, ottimizzato per query.

## Pagine

| Pagina | Contenuto | Tags |
|--------|-----------|------|
| [[architecture]] | Architettura di sistema, layer diagram, topologia processi, flow sincrono/asincrono | `architecture`, `system` |
| [[ten-commandments]] | I 10 principi architetturali inderogabili (P1–P10) | `principles`, `governance`, `mandatory` |
| [[project-layout]] | Struttura directory, variabili d'ambiente, launcher, isolamento KiloCode | `layout`, `paths`, `isolation` |
| [[memory-subsystem]] | Memoria 5D, storage tiers (T0–T3), actor tagging, CLM, ARIA-Memory MCP | `memory`, `sqlite`, `lancedb` |
| [[scheduler]] | Task store, trigger types, budget gate, policy gate, HITL, DLQ, systemd | `scheduler`, `cron`, `systemd` |
| [[gateway]] | Telegram gateway, sessioni multi-utente, auth, multimodalità, canali | `gateway`, `telegram`, `multimodal` |
| [[agents-hierarchy]] | Gerarchia agenti (Conductor, Search, Workspace, System), child sessions, tool matrix | `agents`, `conductor`, `subagents` |
| [[skills-layer]] | Formato SKILL.md, progressive disclosure, registry, skills MVP, versioning | `skills`, `workflows` |
| [[tools-mcp]] | MCP ecosystem, tool priority ladder, search server architecture, wrapper scripts | `tools`, `mcp`, `providers`, `search-architecture` |
| [[search-agent]] | Provider search, 3-layer arch, key rotation, error handling, SearXNG deployment, MCP tool registry | `search`, `providers`, `routing`, `key-rotation` |
| [[workspace-agent]] | Google Workspace integration, OAuth PKCE, scope, triage email, calendar | `workspace`, `google`, `oauth` |
| [[credentials]] | Credential management: SOPS+age, keyring, circuit breaker, rotation, audit | `security`, `credentials`, `sops` |
| [[adrs]] | Sommario di tutti gli ADR (ADR-0001–ADR-0010) con stato e decisioni chiave | `adr`, `decisions`, `governance` |
| [[governance]] | Logging, metriche Prometheus, sicurezza, backup, ADR workflow | `governance`, `observability`, `security` |
| [[quality-gates]] | Build, lint, format, typecheck, test comandi e policy | `quality`, `ci`, `testing` |
| [[roadmap]] | Phase 0/1/2/3 roadmap, sprint completati, criteri di uscita | `roadmap`, `phases`, `milestones` |

## Raw Sources (Tier 0)

Questi file sono le fonti autoritative da cui il wiki è derivato:

| Fonte | Path | Contenuto |
|-------|------|-----------|
| Foundation Blueprint | `docs/foundation/aria_foundation_blueprint.md` | Specifica tecnica completa (2089 righe) |
| ADR-0001 | `docs/foundation/decisions/ADR-0001-dependency-baseline-2026q2.md` | Dependency baseline, SOPS CLI, ML optional |
| ADR-0002 | `docs/foundation/decisions/ADR-0002-sqlite-reliability-policy.md` | SQLite >= 3.51.3, WAL, FTS5 |
| ADR-0003 | `docs/foundation/decisions/ADR-0003-oauth-security-posture.md` | PKCE-first, scope minimalism, keyring |
| ADR-0004 | `docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md` | No pickle, SQLite per associative |
| ADR-0005 | `docs/foundation/decisions/ADR-0005-scheduler-concurrency.md` | Lease-based concurrency, worker ID |
| ADR-0006 | `docs/foundation/decisions/ADR-0006-prompt-injection-mitigation.md` | `<<TOOL_OUTPUT>>` frame, 3-layer defense |
| ADR-0007 | `docs/foundation/decisions/ADR-0007-stt-stack-dual.md` | faster-whisper primary, openai-whisper fallback |
| ADR-0008 | `docs/foundation/decisions/ADR-0008-systemd-user-capability-limits.md` | No PrivateDevices/ProtectKernelModules in --user |
| ADR-0009 | `docs/foundation/decisions/ADR-0009-kilo-agent-frontmatter-and-mcp-bin-resolution.md` | Kilo AgentConfig, npx bin, tool deny |
| ADR-0010 | `docs/foundation/decisions/ADR-0010-workspace-wrapper-runtime-credentials.md` | Runtime credentials file exception |
| AGENTS.md | `AGENTS.md` | Regole per coding agents |
| README.md | `README.md` | Overview, quick start, architettura |
| Runbook | `docs/operations/runbook.md` | Operazioni day-to-day |
| Workspace OAuth Runbook | `docs/operations/workspace_oauth_runbook.md` | Procedure OAuth operative, troubleshooting, dynamic pruning |
| OAuth Debug Plan 2026-04-23 | `docs/plans/google_workspace_authz_debug_plan_2026-04-23.md` | Piano esteso di diagnosi authz per Workspace MCP (Drive/Slides read) |
| Workspace Tool Governance Matrix | `docs/roadmaps/workspace_tool_governance_matrix.md` | Registry di 114 tool MCP con domain, rw, risk, policy, HITL, min_scope |

## External Knowledge

Documentazione esterna di riferimento in `docs/llm_wiki/ext_knowledge/`:

| Documento | Contenuto |
|-----------|-----------|
| `llm-wiki-paradigm.md` | Analisi approfondita del pattern LLM Wiki (Karpathy, nvk/llm-wiki, nashsu/llm_wiki) |

## Convenzioni

- Ogni pagina wiki inizia con frontmatter YAML: `title`, `sources` (lista path raw), `last_updated`, `tier: 1`.
- I cross-reference usano la sintassi `[[nome-pagina]]` tra pagine wiki.
- I fatti includono sempre la provenienza: `source: <path>`.
- Questo file (`index.md`) è aggiornato ad ogni ingest/lint.
