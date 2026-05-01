# ARIA LLM Wiki — Index

**Last Updated**: 2026-04-30T20:26 (v5.0 — Stabilizzazione completa: architettura a 4 livelli)
**Status**: ✅ **v5.0** — Stabilizzazione ARIA pre-Fase 2 completa. Architettura ibrida a 4 livelli implementata: L1 (coordinamento agenti Pydantic v2), L2 (MCP catalog + lazy loader), L3 (LLM routing dichiarativo), L4 (observability JSON/metriche). Tutti i quality gate verdi: ruff 0, mypy 0 (81 files), pytest 634/634 pass. Tag `baseline-LKG-v1` su `main`.

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
|   .aria/config/mcp_catalog.yaml (14 server SoT)           |
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

### Coordination (L1)
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/config/agent_capability_matrix.yaml` | **NEW**: Capability matrix YAML canonica (4 agenti) | 2026-04-30 |
| `src/aria/agents/coordination/handoff.py` | **NEW**: Handoff Pydantic model + validator | 2026-04-30 |
| `src/aria/agents/coordination/envelope.py` | **NEW**: ContextEnvelope + persistenza + cleanup | 2026-04-30 |
| `src/aria/agents/coordination/registry.py` | **NEW**: AgentRegistry (loader + validator) | 2026-04-30 |
| `src/aria/agents/coordination/spawn.py` | **NEW**: Spawn wrapper validato (depth guard) | 2026-04-30 |
| `tests/unit/agents/coordination/` | **NEW**: 68 test unitari coordinamento | 2026-04-30 |
| `tests/integration/coordination/` | **NEW**: 18 test integrazione coordinamento | 2026-04-30 |

### MCP Plane (L2)
| Source | Description | Last Updated |
|--------|-------------|--------------|
| `.aria/config/mcp_catalog.yaml` | **NEW**: Catalogo MCP canonico (14 server, metadata completi) | 2026-04-30 |
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
| `.aria/kilocode/agents/aria-conductor.md` | **v4.6**: colonna `title`, auto-estrazione, productivity-agent dispatch | 2026-04-30 |
| `.aria/kilocode/agents/search-agent.md` | **v4.0**: dual-tier-1, pubmed→scientific-papers, reddit keyless | 2026-04-29 |
| `.aria/kilocode/agents/productivity-agent.md` | **v4.0**: 11 tool, 4 skill, boundary delega workspace-agent | 2026-04-29 |
| `.aria/kilocode/agents/workspace-agent.md` | **STUB**: 25 righe, da riscrivere in Phase 2 | 2026-04-30 |

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
| [[mcp-api-key-operations]] | Runbook: 5 provider, 17 keys, multi-account rotation, circuit breaker | Active ✅ |
| [[aria-launcher-cli-compatibility]] | bin/aria launcher: CLI invocation, hard isolation, MCP migration | Active ✅ |
| [[mcp-architecture]] | Inventario MCP reale, drift strutturali, direzione refoundation | Active ✅ v2 |
| [[agent-capability-matrix]] | Capability matrix, handoff protocol e routing policy (3 agenti) | Active ✅ v1.0 |
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
- 2026-05-01: **v6.0 (F1)** — `src/aria/mcp/proxy/` core implementation complete. HybridSearchTransform, CapabilityMatrixMiddleware, catalog loader, credential injector, LM Studio embedder. 35 unit + 3 integration tests. Fase F2-F5 pianificate.

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
- `docs/llm_wiki/wiki/mcp-proxy.md` — **NEW v6.0 (F1)**: FastMCP-native MCP proxy replacing lazy loader
- `docs/llm_wiki/wiki/agent-capability-matrix.md` — capability matrix
- `docs/operations/rollback_matrix.md` — rollback matrix completa
