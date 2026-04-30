# Piano di Stabilizzazione ARIA — Pre-Fase 2

> **Data**: 2026-04-30
> **Owner proposto**: Fulvio (HITL su decisioni distruttive)
> **Branch corrente**: `fix/wiki-update-title-field`
> **Branch base post-merge**: `main` (dopo merge `feature/productivity-agent-mvp`)
> **Stella Polare**: `docs/foundation/aria_foundation_blueprint.md`
> **Vincoli autoritativi**: `AGENTS.md` (CLAUDE.md), Ten Commandments §16, Wiki-First, Context7-First
> **Priorità decisionale**: Refoundation v2 rollback-first (gateway NON giustificato ora)
> **Scope coordinamento**: Massimo (capability matrix enforced + handoff JSON + shared context envelope + observability end-to-end)
> **Phase 2 scaffold**: LLM routing dichiarativo + observability scaffold (tutto il resto deferred a piani dedicati)

---

## Indice

0. [Executive Summary](#0-executive-summary)
1. [Stato Attuale & Gap Analysis](#1-stato-attuale--gap-analysis)
2. [Principi Guida (rollback-first, baseline-protected)](#2-principi-guida)
3. [Architettura Target a 4 Livelli](#3-architettura-target-a-4-livelli)
4. [Piano Esecutivo (6 Fasi)](#4-piano-esecutivo-6-fasi)
   - [F0 — Branch Reconciliation & Baseline Tag](#f0--branch-reconciliation--baseline-tag)
   - [F1 — Audit, Freeze e Drift Inventory](#f1--audit-freeze-e-drift-inventory)
   - [F2 — Coordinamento Agenti (capability + handoff + envelope)](#f2--coordinamento-agenti-capability--handoff--envelope)
   - [F3 — MCP Refoundation Rollback-First (catalog + drift + lazy + PoC gateway)](#f3--mcp-refoundation-rollback-first)
   - [F4 — Observability + LLM Routing Scaffold](#f4--observability--llm-routing-scaffold)
   - [F5 — Hardening Test, Rollback Drill, Release Gates](#f5--hardening-test-rollback-drill-release-gates)
5. [Rollback Matrix Completa](#5-rollback-matrix-completa)
6. [Gate di Attivazione Obbligatori](#6-gate-di-attivazione-obbligatori)
7. [KPI di Successo](#7-kpi-di-successo)
8. [Rischi & Mitigazioni](#8-rischi--mitigazioni)
9. [ADR Backlog](#9-adr-backlog)
10. [Provenance & Context7 Verification Plan](#10-provenance--context7-verification-plan)
11. [Appendice A — Capability Matrix v1.0 Enforced](#appendice-a--capability-matrix-v10-enforced)
12. [Appendice B — Handoff JSON Schema](#appendice-b--handoff-json-schema)
13. [Appendice C — Trace Context Envelope](#appendice-c--trace-context-envelope)
14. [Appendice D — LLM Routing YAML (esempio)](#appendice-d--llm-routing-yaml-esempio)
15. [Appendice E — File da Creare/Aggiornare](#appendice-e--file-da-creareaggiornare)

---

## 0. Executive Summary

ARIA Phase 1 MVP è in verifica con **3 sub-agenti implementati** (search, workspace, productivity) ma il lavoro su `productivity-agent` e tutta l'analisi MCP (gateway evaluation, refoundation v2, capability matrix, mcp_productivity_coordination plan) vive su `feature/productivity-agent-mvp` (18 commit ahead di `main`). Il branch corrente `fix/wiki-update-title-field` non li include.

Prima della Fase 2 ARIA deve consolidare 5 fronti, in quest'ordine:

1. **Branch reconciliation**: merge `feature/productivity-agent-mvp` → `main` con quality gate completo, tag `baseline-LKG-v1`.
2. **Coordinamento agenti** veramente integrato: capability matrix v1.0 enforced ovunque, handoff JSON standardizzato con `trace_id` propagato, **shared context envelope** ricostruito via `wiki_recall` pre-spawn, prompt riscritti uniformi.
3. **MCP refoundation rollback-first**: catalogo canonico (`mcp_catalog.yaml`), drift checks shadow-mode, capability probe + schema snapshots, lazy-loading-per-intent dietro flag, gateway PoC SOLO su dominio search con bypass hard.
4. **LLM routing dichiarativo**: matrice task→modello (`.aria/config/llm_routing.yaml`) — Opus 4.7 conductor, Sonnet 4.6 sub-agents, Haiku 4.5 classifier — base scalabile per Fase 2.
5. **Observability scaffold**: structured JSON logging end-to-end con `trace_id` propagato, metriche Prometheus-ready in `.aria/runtime/metrics/`, schema eventi per scheduler/gateway.

Nessuna delle 6 fasi tocca lo stato persistente (DB memoria, OAuth tokens, credenziali SOPS). Tutto il refactor avviene nel **config-plane** e nei prompt. Ogni fase è reversibile in ≤5 minuti tramite drill provato.

**Decisione MCP confermata** (allineata con `mcp_gateway_evaluation.md`): **NIENTE gateway monolitico** in questa fase. Si va con lazy-loading-per-intent + scoped toolset enforced. Gateway eventualmente solo dominio search e solo dietro PoC con bypass.

**Output atteso a fine piano**:
- 1 branch `main` consolidato con 3 agenti operativi e capability matrix enforced
- 1 catalogo MCP canonico con drift checks verdi
- 1 sistema osservabile con `trace_id` per turno e metriche per agente
- 1 LLM routing config dichiarativo
- 4 ADR ratificati (catalog, lazy loading, cutover/rollback, LLM routing)
- 1 baseline LKG taggata e drillata
- Fondamenta robuste per partire con Memory Tier 3, multi-canale, nuovi agenti Phase 2

---

## 1. Stato Attuale & Gap Analysis

### 1.1 Branch divergence & merge gap

| Asset | `main` | `feature/productivity-agent-mvp` | `fix/wiki-update-title-field` |
|-------|:------:|:-------------------------------:|:----------------------------:|
| `productivity-agent.md` | ❌ | ✅ | ❌ |
| 4 skill produttività | ❌ | ✅ | ❌ |
| `mcp_catalog.yaml` (proposto) | ❌ | ❌ | ❌ |
| Capability probe framework | ❌ | ✅ | ❌ |
| Query preprocessor centralizzato | ❌ | ✅ | ❌ |
| ADR-0008 productivity-agent | ❌ | ✅ | ❌ |
| `agent-capability-matrix.md` | ❌ | ✅ | ❌ |
| `mcp_gateway_evaluation.md` | ❌ | ✅ | ❌ |
| `gestione_mcp_refoundation_plan_v2.md` | ❌ | ✅ | ❌ |
| `mcp_productivity_coordination_optimization_plan.md` | ❌ | ✅ | ❌ |
| `mcp-architecture.md` wiki page | ❌ | ✅ | ❌ |
| Conductor lista productivity-agent | ❌ | ✅ | ❌ |
| Search-agent espone scientific-papers tool | ❌ | ✅ | ❌ |
| Wiki bug fix (P0+P1+P2) | ❌ | ❌ | ✅ |

### 1.2 Drift critici osservati

#### 1.2.1 Drift `aria-conductor.md`
Su `main` lista solo 2 sub-agenti. Productivity-agent non appare.

#### 1.2.2 Drift `workspace-agent.md`
File è uno stub di 25 righe ("Vedi §12"). Discrepanza con search-agent (128 righe) e productivity-agent (109 righe).

#### 1.2.3 Drift `search-agent.md`
Riferimento a tool `pubmed-mcp/*` rimossi (commit `af4df79`) ma policy academic ancora menziona pubmed.

#### 1.2.4 Drift MCP inventory
- `analisi_sostenibilita_mcp_report.md` cita 12 server
- `.aria/kilocode/mcp.json` su `feature/productivity-agent-mvp` ne dichiara 16, abilitati 15
- Su `main` differente ancora
- Nessun catalogo canonico → drift permanente atteso

#### 1.2.5 Drift documentale
Wiki page `mcp-architecture.md`, `agent-capability-matrix.md`, `productivity-agent.md` referenziate in `index.md` ma fisicamente assenti su `main`. Solo su `feature/productivity-agent-mvp`.

### 1.3 Lacune di coordinamento agenti
- Handoff non enforced, shared context assente, nessuna metrica per agente, nessun structured tracing, spawn depth non enforced

### 1.4 Lacune di scalabilità MCP
- 49+ tool esposti, cold start 6.5s, proiezione 25 server → ~16s
- Nessuna lazy loading, nessun catalogo canonico, nessuno schema snapshot
- Capability probe copre solo 2 server

### 1.5 Lacune SOTA (Aprile 2026)
- MCP spec rev 2025-06-18: tool search/lazy loading, outputSchema, notifications/tools/list_changed
- Anthropic prompt caching: 5-min TTL
- Multi-agent orchestration (mcp-agent, MetaMCP)

### 1.6 Riepilogo gap critici

| # | Gap | Severità | Fase |
|---|-----|:--------:|:----:|
| 1 | Branch `feature/productivity-agent-mvp` non in `main` | P0 | F0 |
| 2 | Conductor non lista productivity-agent | P0 | F0/F2 |
| 3 | workspace-agent prompt è stub | P0 | F2 |
| 4 | Capability matrix non enforced | P0 | F2 |
| 5 | Handoff JSON / trace_id non enforced | P0 | F2 |
| 6 | Shared context envelope assente | P1 | F2 |
| 7 | MCP catalog canonico assente | P0 | F3 |
| 8 | Drift checks assenti | P0 | F3 |
| 9 | Lazy loading non attivo | P1 | F3 |
| 10 | Schema snapshots non integrati al boot | P1 | F3 |
| 11 | LLM routing dichiarativo assente | P1 | F4 |
| 12 | Trace_id end-to-end assente | P1 | F4 |
| 13 | Metriche per agente assenti | P1 | F4 |
| 14 | Wiki drift fisico/index | P1 | F1 |
| 15 | Test consistency non in CI | P1 | F5 |
| 16 | Prompt caching non strutturato | P2 | F4 |

---

## 2. Principi Guida

### P-Stab-1 — Baseline Protetta (LKG)
L'architettura attuale post-merge è il last-known-good. Ogni cambiamento è un overlay reversibile.

### P-Stab-2 — Config-Plane Only
Niente migrazioni di stato persistente. Solo mcp.json, agent prompt MD, .aria/config/*.yaml, generatori, validator.

### P-Stab-3 — Cutover per Dominio
Blast radius ∈ {server, domain, session, global}. Cutover global vietato.

### P-Stab-4 — Direct-Path Preservation
Ogni nuovo layer ha bypass hard documentato.

### P-Stab-5 — Gate-Driven Activation
Drift checks green, schema snapshot compatibility, smoke test, rollback drill, HITL.

### P-Stab-6 — Self-Documenting Cutover
Ogni attivazione/rollback genera entry in docs/llm_wiki/wiki/log.md.

### P-Stab-7 — Ten Commandments Reaffirmed
P1 Isolation, P7 HITL Destructive, P8 Tool Priority Ladder, P9 ≤20 tool, P10 Self-Documenting.

---

## 3. Architettura Target a 4 Livelli

```
+-----------------------------------------------------------+
| L4 — Observability Plane                                  |
|   structured JSON logs (trace_id end-to-end)              |
|   metrics Prometheus-ready (.aria/runtime/metrics/)       |
|   events: spawn, handoff, hitl, rollback, drift, cutover  |
+-----------------------------------------------------------+
| L3 — LLM Routing Plane                                    |
|   .aria/config/llm_routing.yaml                           |
|   matrice task→modello (deterministica + fallback)        |
|   prompt caching strategy per agente                      |
+-----------------------------------------------------------+
| L2 — MCP Plane (Refoundation v2)                          |
|   .aria/config/mcp_catalog.yaml (SoT)                     |
|   drift checks shadow-mode (script CI)                    |
|   capability probe + schema snapshots                     |
|   lazy bootstrap per intent (flag)                        |
|   search-domain gateway PoC (flag, bypass hard)           |
+-----------------------------------------------------------+
| L1 — Coordinamento Agenti                                 |
|   capability matrix v1.0 enforced (validator + CI)        |
|   handoff JSON schema (Pydantic, runtime check)           |
|   shared context envelope (wiki_recall conductor-level)   |
|   spawn-subagent depth guard (≤2 hop)                     |
+-----------------------------------------------------------+
              ▲
              | invoca
              |
[Gateway Telegram] → [Conductor] → [search/workspace/productivity]
```

### 3.1 L1 — Coordinamento Agenti
- `src/aria/agents/coordination/handoff.py` — Pydantic model HandoffRequest
- `src/aria/agents/coordination/envelope.py` — ContextEnvelope
- `src/aria/agents/coordination/registry.py` — AgentRegistry
- `src/aria/agents/coordination/spawn.py` — spawn wrapper validato

Invarianti: ogni spawn-subagent DEVE includere HandoffRequest valido, spawn_depth ≤ 2,
ContextEnvelope costruito una volta dal conductor.

### 3.2 L2 — MCP Plane
Catalogo canonicale mcp_catalog.yaml. Componenti: check_mcp_drift.py, probe_mcp_capabilities.py,
lazy_loader.py, bin/aria esteso con --profile e --intent.

Cutover policy: cambi mcp.json solo via catalog→generatore, drift validator in CI, schema mismatch → quarantena.

### 3.3 L3 — LLM Routing Plane
File `.aria/config/llm_routing.yaml` con modelli (opus, sonnet, haiku), routing per agente, intent_overrides, policy (budget gate $5/day, fallback chain max 2).

### 3.4 L4 — Observability Plane
Logger structlog JSON, metriche Prometheus (6 counter/histogram), eventi tipati, trace_id UUIDv7.

---

## 4. Piano Esecutivo (6 Fasi)

### F0 — Branch Reconciliation & Baseline Tag

**Durata**: 0.5 giorni | **Owner**: Fulvio (HITL su merge)

Attività:
1. git fetch --all --prune
2. Quality gate su feature/productivity-agent-mvp
3. PR feature/productivity-agent-mvp → main
4. HITL approval (Fulvio)
5. Squash & merge
6. Rebase fix/wiki-update-title-field su nuovo main
7. PR fix/wiki-update-title-field → main
8. Tag baseline-LKG-v1

Deliverable: main aggiornato, tag baseline-LKG-v1, working tree clean.

### F1 — Audit, Freeze e Drift Inventory

**Durata**: 1 giorno | **Owner**: agent + Fulvio (review)

Attività:
1. Snapshot inventory MCP attuale (mcp_baseline.md)
2. Snapshot prompt agenti
3. Drift inventory script (scripts/audit_drift.py)
4. Pubblica wiki page mancanti fisicamente
5. Rollback matrix iniziale (docs/operations/rollback_matrix.md)

### F2 — Coordinamento Agenti

**Durata**: 3-4 giorni | **Owner**: agent + Fulvio (review prompt)

F2.1: .aria/config/agent_capability_matrix.yaml
F2.2: Handoff JSON schema enforced (src/aria/agents/coordination/handoff.py)
F2.3: Shared context envelope (src/aria/agents/coordination/envelope.py)
F2.4: Riscrittura prompt agenti (template comune)
F2.5: Conductor dispatch rules formalizzate
F2.6: Test integrazione coordinamento (≥35 test)

### F3 — MCP Refoundation Rollback-First

**Durata**: 4-6 giorni | **Owner**: agent + Fulvio (review catalog + ADR)

F3.1: MCP catalog YAML (.aria/config/mcp_catalog.yaml)
F3.2: Drift validator (scripts/check_mcp_drift.py)
F3.3: Capability probe generalizzato + snapshot al boot
F3.4: Lazy bootstrap per intent (src/aria/launcher/lazy_loader.py)
F3.5: Search-domain gateway PoC (decisione condizionata)
F3.6: ADR ratification (0009-0012)

### F4 — Observability + LLM Routing Scaffold

**Durata**: 3-4 giorni | **Owner**: agent + Fulvio (review schema)

F4.1: Logger structured JSON (src/aria/observability/logger.py)
F4.2: Metriche Prometheus textfile (src/aria/observability/metrics.py)
F4.3: Trace propagation (UUIDv7)
F4.4: LLM routing scaffold (src/aria/routing/llm_router.py)
F4.5: Prompt caching strategy
F4.6: ADR observability (0013-0014)

### F5 — Hardening Test, Rollback Drill, Release Gates

**Durata**: 2-3 giorni | **Owner**: agent + Fulvio (HITL drill)

F5.1: Cross-agent integration tests
F5.2: Rollback drill scripts (4 script)
F5.3: CI gates (make check-drift, check-capability, check-coverage)
F5.4: Smoke E2E orchestrazione 3 agenti
F5.5: Update wiki + documentation

---

## 5. Rollback Matrix Completa

| Fase | Scope | Artefatto attivato | Trigger rollback | Rollback minimo | Blast radius | MTTR |
|------|-------|--------------------|------------------|-----------------|--------------|:----:|
| F0 | global | Branch merge + tag | Regressione | git revert PR | global | <30min |
| F1 | none | Documentazione | n/a | rm file output | none | n/a |
| F2 | session | Handoff validator | Sub-agent bloccato | ARIA_HANDOFF_VALIDATION=0 | session | <2min |
| F2 | session | Envelope | Sub-agent non legge | Fallback wiki_recall | session | <2min |
| F2 | domain | Capability matrix | Validator blocca handoff | ARIA_CAPABILITY_ENFORCEMENT=0 | domain | <5min |
| F3 | server | Drift validator | Drift legittimo bloccato | --shadow mode | server | <5min |
| F3 | server | Quarantena | Falso positivo | lifecycle=enabled forzato | server | <2min |
| F3 | domain | Lazy bootstrap | Server non caricato | --profile baseline | session | <2min |
| F3 | domain | Gateway PoC | Errore/ Latenza | ARIA_GATEWAY_SEARCH=0 | domain | <2min |
| F4 | session | Logger | Logger crash | logging stdlib | session | <2min |
| F4 | session | Metrics | Disk fail | ARIA_METRICS_ENABLED=0 | session | <2min |
| F4 | session | Trace_id | Sub-agent rifiuta | trace_id locale | session | <2min |
| F4 | session | LLM router | Modello non disponibile | Fallback chain | session | <2min |
| F5 | none | Test + drill | n/a | Test skippabili | none | n/a |

---

## 6. Gate di Attivazione Obbligatori

Per ogni fase post-F0:
1. ✅ Baseline metrics captured (F1 deliverable presente)
2. ✅ Drift checks green (shadow OK per F2, enforce per F3+)
3. ✅ Schema snapshot compatibility green (post F3.3)
4. ✅ Smoke tests dominio green
5. ✅ Rollback action documentata
6. ✅ Rollback drill eseguito ≥1 volta in sandbox
7. ✅ HITL approval su F0 merge, F2 prompt rewrite, F3 ADR, F4 ADR
8. ✅ `make quality` verde prima del merge ogni fase

---

## 7. KPI di Successo

### KPI Tecnici
| KPI | Baseline | Target |
|-----|:--------:|:------:|
| Cold start MCP all-enabled | ~6.5s | ≤6.5s (15 server) |
| Cold start MCP profile=productivity | n/a | ≤1.0s |
| Context tool definitions iniziali | ~30K | ≤12K |
| Drift incidents/mese | non misurato | ≤1 |
| Capability matrix violations | non misurato | 0 |
| Rollback MTTR per fase | non misurato | <5 min |
| Test coverage core coordination | n/a | ≥75% |

### KPI Coordinamento
| KPI | Baseline | Target |
|-----|:--------:|:------:|
| Handoff validation pass rate | n/a | 100% |
| Trace_id presence in logs | ~0% | ≥95% |
| Envelope reuse rate (2-hop+) | 0% | ≥70% |
| Conductor dispatch correctness | qualitative | ≥95% |

### KPI Operativi
| KPI | Baseline | Target |
|-----|:--------:|:------:|
| ADR Accepted post-F5 | 8 | ≥12 |
| Wiki pages fisicamente vs index | parziale | 100% |
| Cutover documented in log.md | parziale | 100% |

---

## 8. Rischi & Mitigazioni

| ID | Rischio | Prob | Impatto | Mitigazione |
|----|---------|:----:|:-------:|-------------|
| R1 | Merge introduce regressioni | Media | Alto | Quality gate + smoke test + tag rollback |
| R2 | Capability matrix blocca handoff legittimi | Media | Medio | Shadow mode 1 settimana + env-flag |
| R3 | Catalog MCP drift inverso | Bassa | Medio | Drift validator bidirezionale + CI |
| R4 | Lazy loading rompe intent classification | Media | Medio | Profile=baseline default |
| R5 | LLM routing non integrabile in KiloCode | Alta | Basso | Fallback env-var |
| R6 | Prompt rewrite cambia comportamento | Alta | Medio | HITL diff + smoke E2E |
| R7 | Logger rallenta runtime | Bassa | Basso | Async writer + sampling |
| R8 | Merge conflitti complessi | Media | Medio | Rebase incrementale |
| R9 | Wiki page divergence | Media | Basso | F1 audit + auto-sync |

---

## 9. ADR Backlog

| ADR | Titolo | Status | Fase |
|-----|--------|:------:|:----:|
| ADR-0008 | productivity-agent introduction | Accepted | pre-F0 |
| ADR-0009 | MCP catalog as single source of truth | Proposed→Accepted | F3.1 |
| ADR-0010 | Lazy loading per intent enablement | Proposed→Accepted | F3.4 |
| ADR-0011 | Search gateway introduction (PoC) | Deferred | F3.5 |
| ADR-0012 | MCP cutover and rollback policy | Proposed→Accepted | F3.6 |
| ADR-0013 | LLM routing as declarative matrix | Proposed→Accepted | F4.4 |
| ADR-0014 | Observability schema and trace propagation | Proposed→Accepted | F4.6 |
| ADR-0015 | Capability matrix as runtime contract | Proposed→Accepted | F2 |
| ADR-0016 | Handoff JSON schema enforcement | Proposed→Accepted | F2 |

---

## 10. Provenance & Context7 Verification Plan

### 10.1 Wiki sources letti
- docs/llm_wiki/wiki/index.md, log.md, mcp-architecture.md, agent-capability-matrix.md, research-routing.md

### 10.2 Plans/analyses letti
- analisi_sostenibilita_mcp_report.md, mcp_gateway_evaluation.md, gestione_mcp_refoundation_plan_v2.md, mcp_productivity_coordination_optimization_plan.md, agent-capability-matrix.md, blueprint §15-16

### 10.3 Codice/config ispezionato
- .aria/kilocode/agents/{aria-conductor,search-agent,workspace-agent,productivity-agent}.md

### 10.4 Context7 verification eseguita
- /modelcontextprotocol/modelcontextprotocol, /lastmile-ai/mcp-agent, /metatool-ai/metamcp, /cyanheads/pubmed-mcp-server (rimosso), /benedict2310/scientific-papers-mcp, /microsoft/markitdown

### 10.5 Context7 verification DEFERRED a implementazione
- **F2**: pydantic (v2 latest) per Handoff/Envelope schema
- **F3**: KiloCode mcp.json schema spec
- **F4**: structlog per logger structured, prometheus_client (textfile collector)

---

## Appendice A — Capability Matrix v1.0 Enforced

Schema YAML per `.aria/config/agent_capability_matrix.yaml`:
```yaml
agents:
  - name: aria-conductor
    type: primary
    allowed_tools: [...]
    mcp_dependencies: [aria-memory]
    delegation_targets: [search-agent, workspace-agent, productivity-agent]
    hitl_triggers: [destructive, costly, oauth_consent]
    max_tools: 20
    max_spawn_depth: 2
  - name: search-agent
    type: worker
    ...
  - name: workspace-agent
    type: worker
    ...
  - name: productivity-agent
    type: worker
    ...
```

## Appendice B — Handoff JSON Schema

```python
class HandoffRequest(BaseModel):
    goal: str = Field(..., max_length=500)
    constraints: str | None = None
    required_output: str | None = None
    timeout_seconds: int = Field(default=120, ge=10, le=300)
    trace_id: str
    parent_agent: str
    spawn_depth: int = Field(default=1, ge=1, le=2)
    envelope_ref: str | None = None
```

## Appendice C — Trace Context Envelope

```python
class ContextEnvelope(BaseModel):
    envelope_id: str
    trace_id: str
    session_id: str
    wiki_pages: list[WikiPageSnapshot]
    profile_snapshot: str | None
    created_at: datetime
    expires_at: datetime
```

## Appendice D — LLM Routing YAML

```yaml
models:
  opus_4_7: { id: claude-opus-4-7, cost_tier: high, capabilities: [orchestration] }
  sonnet_4_6: { id: claude-sonnet-4-6, cost_tier: medium, capabilities: [research] }
  haiku_4_5: { id: claude-haiku-4-5-20251001, cost_tier: low, capabilities: [triage] }

routing:
  - agent: aria-conductor, primary: opus_4_7, fallback: sonnet_4_6
  - agent: search-agent, primary: sonnet_4_6, fallback: haiku_4_5
  - agent: workspace-agent, primary: sonnet_4_6, fallback: haiku_4_5
  - agent: productivity-agent, primary: sonnet_4_6, fallback: haiku_4_5

policy: { daily_token_cap_usd: 5.0, overflow_action: degrade, fallback_chain_max: 2 }
```

## Appendice E — File da Creare/Aggiornare

### Nuovi file
- `.aria/config/agent_capability_matrix.yaml`
- `.aria/config/mcp_catalog.yaml`
- `.aria/config/llm_routing.yaml`
- `src/aria/agents/coordination/handoff.py`
- `src/aria/agents/coordination/envelope.py`
- `src/aria/agents/coordination/registry.py`
- `src/aria/agents/coordination/spawn.py`
- `src/aria/mcp/capability_probe.py`
- `src/aria/launcher/lazy_loader.py`
- `src/aria/observability/logger.py`
- `src/aria/observability/metrics.py`
- `src/aria/observability/events.py`
- `src/aria/routing/llm_router.py`
- `scripts/audit_drift.py`
- `docs/operations/rollback_matrix.md`
- `docs/operations/baseline_lkg_v1/mcp_baseline.md`

### File da aggiornare
- `.aria/kilocode/agents/aria-conductor.md`
- `.aria/kilocode/agents/search-agent.md`
- `.aria/kilocode/agents/workspace-agent.md`
- `.aria/kilocode/agents/productivity-agent.md`
- `docs/llm_wiki/wiki/index.md`
- `docs/llm_wiki/wiki/log.md`
- `Makefile`
