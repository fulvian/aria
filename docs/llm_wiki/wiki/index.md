# ARIA LLM Wiki — Index

**Last Updated**: 2026-05-03T09:34 (v7.0 — naming convention migration double-underscore → single-underscore)
**Status**: ✅ **v7.0** — completata la migrazione da `server__tool` (doppio underscore) a `server_tool` (singolo underscore) in tutto il codebase. Semplificati i compatibility shim in `_matches()`, `is_tool_allowed()`, `resolve_server_from_tool()` e `_tool_server_name()`. Il formato singolo underscore è ora l'unico standard. 1004 test passanti.

## Purpose

This wiki is the single source of project knowledge for LLMs working in this repository. Per AGENTS.md, all meaningful changes must update the wiki. Ogni fatto qui riportato ha provenienza tracciata (source path + data).

## Wiki Structure

```
docs/llm_wiki/
├── ext_knowledge/          # Raw extracted sources (external docs)
│   └── README.md
├── wiki/                  # Synthesized knowledge
│   ├── index.md          # This file — wiki overview
│   ├── log.md            # Implementation log
│   ├── memory-subsystem.md
│   ├── memory-v3.md
│   ├── research-routing.md
│   ├── google-workspace-mcp-write-reliability.md
│   ├── mcp-api-key-operations.md
│   ├── aria-launcher-cli-compatibility.md
│   ├── productivity-agent.md
│   ├── mcp-architecture.md
│   ├── agent-capability-matrix.md
│   ├── agent-coordination.md       # NEW v5.0 — L1 Coordinamento Agenti
│   ├── mcp-refoundation.md          # NEW v5.0 — L2 MCP Catalog + Lazy Load
│   ├── observability.md            # NEW v5.0 — L4 Logging + Metrics
│   ├── llm-routing.md              # NEW v5.0 — L3 LLM Declarative Routing
│   └── <future pages>
└── SKILL.md              # Reserved for future skill system
```

## Architecture 4 Livelli

```
+-----------------------------------------------------------+
| L4 — Observability Plane (v1.0)                           |
|   src/aria/observability/{logger,metrics,events}.py       |
|   structured JSON logs (trace_id end-to-end)              |
|   metrics Prometheus-ready (.aria/runtime/metrics/)       |
|   events: spawn, handoff, hitl, rollback, drift, cutover  |
+-----------------------------------------------------------+
| L3 — LLM Routing Plane (v1.0)                             |
|   .aria/config/llm_routing.yaml                           |
|   src/aria/routing/llm_router.py                          |
|   matrice task→modello (deterministica + fallback)        |
|   prompt caching strategy per agente                      |
+-----------------------------------------------------------+
| L2 — MCP Plane / Refoundation v2 (v1.0)                  |
|   .aria/config/mcp_catalog.yaml (19 server SoT)           |
|   src/aria/mcp/proxy/ (NEW v6.0) FastMCP-native proxy     |
|   src/aria/mcp/capability_probe.py (generalizzato)        |
|   src/aria/launcher/lazy_loader.py (da deprecare in F4)   |
|   scripts/check_mcp_drift.py (drift validator CI)         |
+-----------------------------------------------------------+
| L1 — Coordinamento Agenti (v1.0)                          |
|   .aria/config/agent_capability_matrix.yaml               |
|   src/aria/agents/coordination/{handoff,envelope,registry,spawn}.py |
|   Handoff JSON schema (Pydantic v2, runtime check)        |
|   shared context envelope (wiki_recall conductor-level)   |
|   spawn-subagent depth guard (≤2 hop)                     |
+-----------------------------------------------------------+
              ▲
              | invoca
              |
[Gateway Telegram] → [Conductor] → [search/workspace/productivity]
```

## Raw Sources Table

### Architecture & Plans
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `docs/foundation/aria_foundation_blueprint.md` | Primary technical reference (blueprint §1-16) | 2026-04-20 |
| `docs/plans/stabilizzazione_aria.md` | **Piano stabilizzazione pre-Fase 2** — 6 fasi, rollback-first | 2026-04-30 |
| `docs/foundation/agent-capability-matrix.md` | Capability Matrix canonica + handoff protocol | 2026-04-30 |
| `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md` | ADR productivity-agent austere MVP | 2026-04-29 |
| `docs/protocols/protocollo_creazione_agenti.md` | **NEW**: protocollo unico per intake → ricerca → decision ladder → piano agenti | 2026-05-01 |

### Coordination (L1)
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/config/agent_capability_matrix.yaml` | Capability matrix YAML canonica (4 agenti), now includes direct `google_workspace_*` reach for `productivity-agent` | 2026-05-01 |
| `src/aria/agents/coordination/handoff.py` | **NEW**: Handoff Pydantic model + validator | 2026-04-30 |
| `src/aria/agents/coordination/envelope.py` | **NEW**: ContextEnvelope + persistenza + cleanup | 2026-04-30 |
| `src/aria/agents/coordination/registry.py` | **NEW**: AgentRegistry (loader + validator) | 2026-04-30 |
| `src/aria/agents/coordination/spawn.py` | **NEW**: Spawn wrapper validato (depth guard) | 2026-04-30 |
| `tests/unit/agents/coordination/` | **NEW**: 68 test unitari coordinamento | 2026-04-30 |
| `tests/integration/coordination/` | **NEW**: 18 test integrazione coordinamento | 2026-04-30 |

### MCP Plane (L2)
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/config/mcp_catalog.yaml` | **NEW**: Catalogo MCP canonico (19 server, metadata completi) | 2026-05-02 |
| `src/aria/mcp/capability_probe.py` | **NEW**: Probe generalizzato per tutti i server MCP | 2026-04-30 |
| `src/aria/launcher/lazy_loader.py` | **NEW**: Lazy bootstrap per intent (baseline/candidate/shadow) | 2026-04-30 |
| `scripts/check_mcp_drift.py` | **NEW**: Drift validator CI (shadow/enforce/baseline) | 2026-04-30 |
| `docs/operations/rollback_matrix.md` | **NEW**: Matrice rollback completa per tutte le fasi | 2026-04-30 |
| `docs/operations/baseline_lkg_v1/mcp_baseline.md` | **NEW**: Snapshot MCP baseline LKG | 2026-04-30 |

### LLM Routing (L3)
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/config/llm_routing.yaml` | **NEW**: Matrice routing dichiarativa (3 modelli × 4 agenti) | 2026-04-30 |
| `src/aria/routing/llm_router.py` | **NEW**: Router LLM (select, fallback, budget gate) | 2026-04-30 |

### Observability (L4)
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `src/aria/observability/logger.py` | **NEW**: Logger JSON strutturato (structlog + stdlib fallback) | 2026-04-30 |
| `src/aria/observability/metrics.py` | **NEW**: Metriche Prometheus (6 metric types) | 2026-04-30 |
| `src/aria/observability/events.py` | **NEW**: Eventi tipati (cutover, rollback, drift, quarantine) | 2026-04-30 |

### Agent Prompts
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/kilocode/agents/aria-conductor.md` | conductor dispatch rules + productivity/workspace/trader boundary | 2026-05-02 |
| `.aria/kilocode/agents/search-agent.md` | **v5.0**: canonical proxy model, no backend wildcards in frontmatter | 2026-05-01 |
| `.aria/kilocode/agents/productivity-agent.md` | **v5.0**: unified work-domain agent, proxy canonical, direct GW access | 2026-05-01 |
| `.aria/kilocode/agents/trader-agent.md` | **NEW v6.5**: finance domain agent, proxy canonical, 7 skills, 8 intent categories | 2026-05-02 |
| `.aria/kilocode/agents/workspace-agent.md` | **TRANSITIONAL**: compatibility stub, to be deprecated | 2026-05-01 |
| `.aria/kilocode/skills/trading-analysis/SKILL.md` | **NEW v6.6**: trading brief orchestrator skill | 2026-05-02 |
| `.aria/kilocode/skills/{fundamental,technical,macro,sentiment,options,crypto}-analysis/SKILL.md` | **NEW v6.6**: 6 domain-specific trader skills | 2026-05-02 |

### Config & Runtime
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/kilocode/mcp.json` | MCP server runtime config (15 server enabled) | 2026-04-29 |
| `.aria/credentials/secrets/api-keys.enc.yaml` | SOPS+age YAML credential store | 2026-04-27 |
| `scripts/rollback_baseline.sh` | **Rollback drill**: restore baseline da git in <5 min | 2026-04-29 |
| `scripts/benchmarks/mcp_startup_latency.py` | Benchmark cold/warm start MCP | 2026-04-29 |

## Pages

| Page | Description | Status |
|------|-------------|--------|
| [[memory-subsystem]] | Memory subsystem: 5D model, 11 MCP tools, HITL flow, CLM, retention | Active |
| [[memory-v3]] | Memory v3 Kilo+Wiki Fusion: wiki.db, 4 wiki MCP tools, profile auto-inject | Active |
| [[research-routing]] | Ricerca multi-tier: dual-tier-1, academic 6 tier, keyless Reddit | Active ✅ v4.0 |
| [[google-workspace-mcp-write-reliability]] | GWS MCP: write scopes concessi, single-user, Gmail/Calendar, 10 scopes | Active ✅ |
| [[mcp-api-key-operations]] | Runbook: 7 provider (incl. fred, alpaca), 19+ keys, multi-account rotation, circuit breaker | Active ✅ |
| [[aria-launcher-cli-compatibility]] | bin/aria launcher: CLI invocation, hard isolation, MCP migration | Active ✅ |
| [[mcp-architecture]] | Active MCP runtime baseline after proxy cutover/remediation | Active ✅ v6.3 |
| [[agent-capability-matrix]] | Post-remediation capability model: proxy synthetic surface + matrix-governed backend reachability | Active ✅ v6.3 |
| [[productivity-agent]] | Unified work-domain agent after ADR-0008 amendment | Active ✅ v6.3 |
| `docs/protocols/protocollo_creazione_agenti.md` | Protocollo unico per la creazione futura di sub-agenti, skill e tool | Active ✅ v1.0 |
| **[[agent-coordination]]** | **NEW v5.0**: L1 — Handoff Pydantic, ContextEnvelope, Registry, Spawn validator. 86 test | **✅ v1.0** |
| **[[mcp-refoundation]]** | **NEW v5.0**: L2 — MCP Catalog (14 server), Drift validator, Capability probe, Lazy loader | **✅ v1.0** |
| **[[observability]]** | **NEW v5.0**: L4 — Logger structured JSON, Prometheus metrics, Events tipati, Trace_id UUIDv7 | **✅ v1.0** |
| **[[llm-routing]]** | **NEW v5.0**: L3 — Matrice dichiarativa YAML, Router Python, Budget gate, Cache strategy | **✅ v1.0** |
| [[log]] | Implementation log with timestamps | Active |

## Implementation Branch

- **Branch**: `main` (consolidato via F0)
- **Baseline tag**: `baseline-LKG-v1` (2026-04-30T19:52)
- **Commits finali**:
  - `5a4e242` — quality fixes (21 ruff, 12 mypy, 6 test failures)
  - `a117904` — F1+F2 (audit + coordination modules + 86 test)
  - `4ecc42c` — F3+F4 (MCP catalog, observability, LLM routing)
- **ADR ratificati**: ADR-0008 (productivity-agent), ADR-0009 (MCP catalog), ADR-0010 (lazy loading), ADR-0012 (cutover/rollback), ADR-0013 (LLM routing), ADR-0014 (observability)
- **Quality gate finale**: ruff 0, mypy 0 (81 files), pytest 634/634 pass

## Bootstrap Log

- 2026-04-24: Wiki bootstrapped during memory gap remediation Sprint 1.2
- 2026-04-27: Comprehensive update after ripristino ricerca + Google Workspace
- 2026-04-29: v3.x — MCP refoundation, capability matrix, productivity-agent
- 2026-04-30: **v4.4** — pubmed-mcp fix bunx→npx
- 2026-04-30: **v4.5** — pubmed-mcp RIMOSSO, sostituito da scientific-papers-mcp/europepmc
- 2026-04-30: **v4.6** — FIX wiki_update_tool title field P0+P1+P2
- 2026-04-30: **v4.8** — F0 quality fix (21 ruff, 12 mypy, 6 test failures)
- 2026-04-30: **v4.9** — PR #3+#4 merged, baseline-LKG-v1 tag
- 2026-04-30: **v5.0** — **ARCHITETTURA 4 LIVELLI** completa. L1: agent coordination (86 test). L2: MCP catalog + lazy loader. L3: LLM routing dichiarativo. L4: Observability JSON/metriche. 634 test totali. 81 file Python verificati mypy.
- 2026-05-01: **v6.0 (F1)** — `src/aria/mcp/proxy/` core implementation complete. HybridSearchTransform, CapabilityMatrixMiddleware, catalog loader, credential injector, LM Studio embedder. 35 unit + 3 integration tests.
- 2026-05-01: **v6.0 (F2)** — Shadow mode: proxy entry added to mcp.json alongside 15 existing servers.
- 2026-05-01: **v6.0 (F3)** — **CUTOVER**: mcp.json reduced to 2 entries (aria-memory + aria-mcp-proxy). Agent prompts namespaced with `_` tool names + `_caller_id` rule. Tagged `proxy-cutover-v1`.
- 2026-05-01: **v6.0 (F4)** — Lazy loader removed (`src/aria/launcher/lazy_loader.py`). `lazy_load`/`intent_tags` stripped from catalog. ADR-0015 written.
- 2026-05-01: **v6.0 (F5)** — `proxy.*` events + `aria_proxy_*` metrics in observability. All skill files updated to namespaced tool names. Wiki finalized.
- 2026-05-01: **v6.0 (F6)** — **Debug & stabilizzazione runtime**. Scoperti 3 problemi critici: (1) server rumorosi — creato `mcp-stdio-filter.py` per 4 wrapper; (2) naming mismatch — middleware ora gestisce single/double underscore; (3) capability matrix ora usa wildcard `server_*` invece di nomi esatti.
- 2026-05-01: **v6.1** — Fix search-flow cinema session: riuso stabile della child session Kilo nel gateway (`--session` propagato), proxy con caller-aware backend boot filtering per escludere `google_workspace` da search-agent, validator di delega parent→target corretto, prompt di grounding irrigiditi per follow-up `continua`.
- 2026-05-01: **v6.2** — Baseline cleanup dei quality gate repository-wide: `ruff check .`, `mypy src` e `pytest -q` tutti verdi. Fix minimi su packaging test MCP, import pytest di `scripts.*`, re-export obsoleto del launcher e configurazione lint/type-check per rumore storico dei test/script.
- 2026-05-01: **v6.2** — Baseline gate cleanup post-cutover: fixed pytest package/import collisions (`proxy.conftest`, `scripts` visibility), removed stale launcher lazy-loader re-export, added narrow `croniter` mypy override, aligned stale prompt-config tests with proxy wildcard exposure, and scoped Ruff noise down to green gates.
- 2026-05-01: **v6.3** — Proxy remediation complete: fail-closed middleware, canonical proxy synthetic prompt surface, `productivity-agent` gains direct `google_workspace_*`, `workspace-agent` transitional, ADR-0008 amended.
- 2026-05-01: **v6.3a** — Detailed wiki consolidation: refreshed `mcp-proxy`, `mcp-architecture`, `mcp-refoundation`, `productivity-agent`, and `agent-capability-matrix` to match the live post-remediation baseline.
- 2026-05-01: **v6.3b** — Conductor behavioral remediation: hardened prompt with no-direct-ops section, GW→productivity-agent routing fix, mixed-domain dispatch rules, wiki validity guard, workspace-agent dispatch prohibition. 16 new tests (689 total).
- 2026-05-01: **v6.3c** — Fixed runtime/source-of-truth drift: aligned the actual Kilo-loaded conductor file under `.aria/kilocode/agents/aria-conductor.md`, restored the Kilo-home template placeholder, and fixed `prompt_inject.py` test isolation so test fixtures no longer corrupt the live conductor prompt.
- 2026-05-01: **v6.3d** — Hardened `productivity-agent` and core work-domain skills against host-native helper drift and pseudo-HITL. Added prompt/skill contract tests. Full suite now at 700 passed.
- 2026-05-01: **v6.3e** — Added definitive proxy/runtime hardening: middleware now extracts nested `_caller_id` for synthetic `call_tool`, stale Kilo-home conductor artifacts were restored, and conductor/productivity prompts now explicitly forbid code edits, config edits, process killing, and runtime self-remediation during ordinary user workflows.
- 2026-05-01: **v6.4** — Creato `docs/protocols/protocollo_creazione_agenti.md`: workflow unico per nuovi agenti/sub-agenti, con intake, wiki-first reconstruction, ricerca repo + `github-discovery`, branch di ricerca manuale via ARIA, decision ladder P8, guardrail P9/HITL/wiki.db/proxy, e output obbligatorio dei piani in `docs/plans/agents/`.
- 2026-05-02: **v6.5** — **trader-agent runtime integration**. Il trader-agent (esistente in `.aria/kilo-home/.kilo/agents/` con 7 skill) era invisibile al conductor perché mancava da tutti i touchpoint runtime. Fix: capability matrix entry, conductor dispatch rules con keyword routing per 40+ termini finanziari, prompt canonico in `.aria/kilocode/agents/trader-agent.md`, delegation chain aggiornata. Aggiornato `protocollo_creazione_agenti.md` con **Fase L (Runtime Integration Checklist)** — 8 touchpoint obbligatori per prevenire integrazioni parziali future. 28 nuovi test trader-agent.
- 2026-05-02: **v6.7** — **targeted restoration**: conductor prompt regressed → restaurato con trader-agent, no-direct-ops, wiki validity guard, finance dispatch. Kilo-home template coerente con `{{ARIA_MEMORY_BLOCK}}`. 7 trader skill fixate con esempi proxy canonici `server_tool`. Capability matrix con backend finance wildcard per boot-time filtering. 913 test passanti.
- 2026-05-02: **v6.6** — **trader-agent backend MCP registration + credential pipeline**. Scoperto che il commit `41e0ef3` su `feature/trader-agent-mvp` (mai mergiato) conteneva il lavoro completo (20 file, +1957 linee). Recuperato selettivamente: 7 skill, ADR, wiki, 157 test. Registrati 5 backend MCP finanziari nel `mcp_catalog.yaml` (3 stdio enabled, 2 HTTP disabled Phase 2). Setup repos esterni: mcp-fredapi + alpaca-mcp clonati con venv. Credential pipeline: SOPS + .env + CredentialInjector `${VAR}` placeholders. Catalog parser esteso per leggere campo `env`. 877 test passanti.
- 2026-05-03: **v7.0** — **MCP naming convention migration**: completata la migrazione da `server__tool` (doppio underscore) a `server_tool` (singolo underscore) in 76 file. Semplificati i compatibility shim in 4 funzioni Python. Il formato singolo underscore è ora l'unico standard. 1004 test passanti.

## Git & GitHub Rules

Definite in `AGENTS.md` § "Git & GitHub Workflow Rules". Regole chiave:
- **MAI** forzare push su `main` senza HITL
- **MAI** usare `git filter-branch` / `filter-repo` senza backup e approvazione
- **MAI** committare segreti in chiaro
- **SEMPRE** working tree pulito (< 10 untracked)
- **SEMPRE** backup prima di operazioni distruttive

## Relevant Files

- `AGENTS.md` — coding standards and agent rules
- `docs/llm_wiki/wiki/agent-coordination.md` — L1 coordination system
- `docs/llm_wiki/wiki/mcp-refoundation.md` — L2 MCP catalog + lazy loader
- `docs/llm_wiki/wiki/llm-routing.md` — L3 LLM routing matrix
- `docs/llm_wiki/wiki/observability.md` — L4 logging, metrics, events
- `docs/llm_wiki/wiki/research-routing.md` — tier policy
- `docs/llm_wiki/wiki/mcp-architecture.md` — MCP architecture
- `docs/llm_wiki/wiki/mcp-proxy.md` — **v6.3**: canonical proxy contract + fail-closed enforcement + work-domain convergence.
- `pyproject.toml` — **v6.2**: per-file ignores Ruff mirati, pytest bootstrap path, override mypy per `croniter`.
- `docs/llm_wiki/wiki/agent-capability-matrix.md` — capability matrix
- `docs/protocols/protocollo_creazione_agenti.md` — protocollo prescrittivo per nuovi agenti/sub-agenti
- `docs/operations/rollback_matrix.md` — rollback matrix completa
