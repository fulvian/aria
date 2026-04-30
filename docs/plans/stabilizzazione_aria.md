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
> **Nota di ricostruzione**: questo documento NON è il piano originale; è una ricostruzione basata su wiki, log, blueprint e stato repository. Va interpretato come direzione tecnica da riallineare continuamente con il codice reale.

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

ARIA Phase 1 MVP risulta oggi gia' consolidato nel repository con **3 sub-agenti implementati** (search, workspace, productivity) e con artefatti v5.0 gia' presenti su `main`. Le assunzioni di branch divergence riportate piu sotto hanno valore storico: vanno lette come provenienza del lavoro, non come stato corrente garantito.

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

> **Reality check 2026-04-30 sera**: questa sezione descrive il gap storico usato per ricostruire la direzione del piano. Lo stato attuale del repository deve essere verificato contro `docs/llm_wiki/wiki/index.md`, `docs/llm_wiki/wiki/log.md`, `git log`, e i file reali sotto `src/aria/` e `.aria/config/`.

| Asset | `main` | `feature/productivity-agent-mvp` | `fix/wiki-update-title-field` |
|-------|:------:|:-------------------------------:|:----------------------------:|
| `productivity-agent.md` | ❌ | ✅ | ❌ |
| 4 skill produttività (office-ingest, consultancy-brief, meeting-prep, email-draft) | ❌ | ✅ | ❌ |
| `mcp_catalog.yaml` (proposto) | ❌ | ❌ | ❌ |
| Capability probe framework | ❌ | ✅ | ❌ |
| Query preprocessor centralizzato | ❌ | ✅ | ❌ |
| ADR-0008 productivity-agent | ❌ | ✅ | ❌ |
| `agent-capability-matrix.md` (foundation + wiki) | ❌ | ✅ | ❌ |
| `mcp_gateway_evaluation.md` | ❌ | ✅ | ❌ |
| `gestione_mcp_refoundation_plan_v2.md` | ❌ | ✅ | ❌ |
| `mcp_productivity_coordination_optimization_plan_2026-04-29.md` | ❌ | ✅ | ❌ |
| `mcp-architecture.md` wiki page | ❌ | ✅ | ❌ |
| Conductor lista productivity-agent | ❌ | ✅ | ❌ |
| Search-agent espone scientific-papers tool | ❌ | ✅ | ❌ |
| Wiki bug fix (P0+P1+P2) | ❌ | ❌ | ✅ |

Ramo corrente `fix/wiki-update-title-field` è una hotfix lineare su un ramo più indietro. Va integrato dopo il merge produttività.

### 1.2 Drift critici osservati (cumulativi tra branch)

#### 1.2.1 Drift `aria-conductor.md`

- File `.aria/kilocode/agents/aria-conductor.md` su `main` lista solo 2 sub-agenti (`search-agent`, `workspace-agent`).
- Il `productivity-agent` non appare nei sub-agenti disponibili → conductor non può delegare task office/briefing.
- Mancano **regole di dispatch** esplicite per workflow misti (ricerca→sintesi, file→email).

#### 1.2.2 Drift `workspace-agent.md`

- File è uno **stub di 25 righe** ("Vedi §12"). Nessuna procedura, nessun handbook, nessuna regola HITL esplicita, nessun esempio di handoff JSON.
- Discrepanza grave con il livello di dettaglio di `search-agent.md` (128 righe) e `productivity-agent.md` (109 righe).

#### 1.2.3 Drift `search-agent.md`

- Su `feature/productivity-agent-mvp`: contiene riferimento a tool `pubmed-mcp/*` rimossi (commit `af4df79`) ma policy academic ancora menziona pubmed in tabella. Da pulire.
- Allineamento con router Python: parziale, c'è un test di consistency (test_config_consistency.py) ma NON gira in CI come gate bloccante.

#### 1.2.4 Drift MCP inventory

- `analisi_sostenibilita_mcp_report.md` cita 12 server.
- `.aria/kilocode/mcp.json` su `feature/productivity-agent-mvp` ne dichiara 16, abilitati 15.
- Su `main` differente ancora.
- Nessun catalogo canonico → drift permanente atteso.

#### 1.2.5 Drift documentale

- Wiki page `mcp-architecture.md` referenziata in `index.md` ma fisicamente assente nella directory `wiki/` su `main`. È solo su `feature/productivity-agent-mvp`.
- Wiki page `agent-capability-matrix.md`, `productivity-agent.md`: stesso problema.
- File index del wiki **mente** sullo stato della directory.

### 1.3 Lacune di coordinamento agenti

- **Handoff non enforced**: `agent-capability-matrix.md` documenta protocollo JSON (`goal/constraints/required_output/timeout/trace_id`) ma nessun validator né runtime check. Sub-agent può ricevere payload free-form e nessun trace_id propaga.
- **Shared context assente**: ogni sub-agent rifa `wiki_recall` da capo, senza envelope condiviso del conductor. Cost duplicato + possibili divergenze di interpretazione.
- **No metriche per agente**: nessun contatore di chiamate, durata, esito per agente. Niente metric su HITL (richieste, approvazioni, rifiuti).
- **No structured tracing**: `trace_id` in `aria-memory/forget` e logs sparsi, ma non sistemicamente propagato gateway → conductor → sub-agent → tool.
- **Spawn depth non enforced**: capability matrix dice max 2-hop ma niente runtime guard.

### 1.4 Lacune di scalabilità MCP

- 49+ tool esposti totali (post-pubmed-removal, da benchmark `mcp_startup_latency.py`).
- Cold start cumulativo 6.5s (9 server testati). Proiezione 25 server → ~16s. Già percepibile.
- **Nessuna lazy loading attiva**: tutti i server stdio si avviano al boot della sessione KiloCode.
- **Nessun catalogo canonico**: `mcp.json` è la sola fonte di verità, senza metadata (domain, owner, tier, lifecycle, rollback_class).
- **Nessuno schema snapshot**: drift `tools/list` non rilevabile senza confronto manuale.
- **Capability probe esiste** (`src/aria/agents/search/capability_probe.py`) ma copre solo 2 server (pubmed/scientific) e non è integrato nel boot.

### 1.5 Lacune SOTA (Aprile 2026)

Riferimenti SOTA per sistemi multi-agente con MCP:
- **Anthropic Engineering "Code execution with MCP"** (Nov 2025): pattern code-execution per ridurre context.
- **Claude Code 2.1.7+ tool search**: lazy loading nativo (95% riduzione context).
- **MCP spec rev 2025-06-18**: `serverInstructions`, `outputSchema`, `notifications/tools/list_changed`.
- **Anthropic prompt caching**: 5-min TTL, deve essere prima del payload variabile.
- **Multi-agent orchestration patterns** (mcp-agent, MetaMCP): orchestrator/worker, parallel, evaluator-optimizer.

ARIA non sfrutta:
1. **Tool search / lazy loading** (MCP spec 2025-06-18 supportato, KiloCode da verificare).
2. **Prompt caching strutturato** sui system prompt grandi (conductor ha profile inject + memory contract = ~2K token; con caching diventa cache-hit per turno).
3. **`outputSchema` MCP** per validazione output tool (riduce errori parsing).
4. **`notifications/tools/list_changed`**: detection runtime di cambi schema senza re-probe completo.
5. **`requireApproval` HITL nativo MCP** dove disponibile.

### 1.6 Riepilogo gap critici

| # | Gap | Severità | Fase target |
|---|-----|:--------:|:----------:|
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

L'architettura attuale post-merge è il **last-known-good**. Ogni cambiamento è un **overlay reversibile**, mai una sostituzione distruttiva. Il direct-path MCP, il prompt corrente del conductor, e il dispatch attuale devono restare richiamabili in ogni momento.

### P-Stab-2 — Config-Plane Only

Niente migrazioni di stato persistente:
- ❌ Nessuna modifica a `wiki.db`, `kilo.db`, scheduler SQLite, OAuth tokens.
- ❌ Nessuna modifica a `.aria/credentials/secrets/*`, `.aria/runtime/credentials/*`.
- ✅ Modifiche solo a: `mcp.json`, agent prompt MD, `.aria/config/*.yaml`, generatori, validator.

### P-Stab-3 — Cutover per Dominio

Ogni cutover deve dichiarare **blast radius** ∈ `{server, domain, session, global}`. Cutover `global` vietato finché tutti i `domain` non sono drillati.

### P-Stab-4 — Direct-Path Preservation

Ogni nuovo layer (lazy loader, gateway, envelope, routing) ha **bypass hard** documentato. La rimozione di un path legacy richiede ADR e finestra di stabilità ≥14 giorni.

### P-Stab-5 — Gate-Driven Activation

Nessuna fase si chiude senza gate verde:
1. Drift checks green
2. Schema snapshot compatibility green
3. Smoke test dominio green
4. Rollback drill eseguito ≥1 volta nel sandbox
5. HITL approval se la fase tocca superfici auth/write

### P-Stab-6 — Self-Documenting Cutover

Ogni attivazione/rollback genera entry in `docs/llm_wiki/wiki/log.md` come evento di prima classe (timestamp, scope, trigger, outcome). Niente cutover silenzioso.

### P-Stab-7 — Ten Commandments Reaffirmed

Tutti i 10 comandamenti restano vincolanti. In particolare:
- **P1 Isolation First**: nessuna fuga in `~/.kilo` globale.
- **P7 HITL Destructive**: capability matrix enforced include trigger HITL.
- **P8 Tool Priority Ladder**: MCP > Skill > Python script.
- **P9 ≤20 tool per sub-agente**: enforced via validator.
- **P10 Self-Documenting Evolution**: ogni divergenza → ADR.

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

**Componenti**:
- `src/aria/agents/coordination/handoff.py` — Pydantic model `HandoffRequest` con campi `goal/constraints/required_output/timeout/trace_id/parent_agent/spawn_depth`.
- `src/aria/agents/coordination/envelope.py` — `ContextEnvelope` con `wiki_pages: list[WikiSnapshot]`, `profile_snapshot`, `trace_id`, `session_id`.
- `src/aria/agents/coordination/registry.py` — `AgentRegistry` con capability matrix loader (da `.aria/config/agent_capability_matrix.yaml`), validation tool-set ≤20, validation delegation graph.
- `src/aria/agents/coordination/spawn.py` — wrapper di `spawn-subagent` che inietta envelope + valida payload + incrementa `spawn_depth`.

**Invarianti**:
- Ogni `spawn-subagent` call **DEVE** includere `HandoffRequest` valido. Validator runtime rifiuta payload free-form.
- `spawn_depth ≤ 2` enforced. Tentativo di livello 3 → errore + log evento.
- `ContextEnvelope` viene **costruito una volta** dal conductor (single `wiki_recall`) e propagato a tutti i sub-agent della catena. Sub-agent non rifa `wiki_recall` se envelope presente.
- `trace_id` ereditato dal gateway o generato dal conductor, propagato in tutti i log/metrics dei figli.

### 3.2 L2 — MCP Plane (Refoundation v2)

**Catalogo `mcp_catalog.yaml`** — single source of truth. Schema:
```yaml
servers:
  - name: scientific-papers-mcp
    domain: search
    owner_agent: search-agent
    tier: 2
    transport: stdio
    lifecycle: enabled  # enabled | disabled | quarantined
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [search_papers, fetch_content, fetch_latest, list_categories, fetch_top_cited]
    risk_level: low
    cost_class: free
    source_of_truth: scripts/wrappers/scientific-papers-wrapper.sh
    rollback_class: server  # server | domain | session
    baseline_status: lkg    # lkg | candidate | shadow | disabled
    intent_tags: [academic]
    lazy_load: true
    intent_required: [academic]
    notes: "patched npm v0.1.40, version pin via wrapper checksum"
```

**Componenti**:
- `scripts/check_mcp_drift.py` — confronta catalog ↔ `mcp.json` ↔ agent prompt allowed-tools ↔ router code. Output diff machine-readable.
- `scripts/probe_mcp_capabilities.py` — esegue `initialize` + `tools/list` per ogni server enabled, salva snapshot in `.aria/runtime/mcp-schema-snapshots/`, confronta con `expected_tools`.
- `src/aria/launcher/lazy_loader.py` — generatore di `mcp.json` runtime basato su intent classificato (al momento solo nei profili `bin/aria` start, non runtime hot-swap).
- `bin/aria` — extend con flag `--profile {baseline|candidate|shadow}` e `--intent {general|academic|social|productivity|all}`.
- `docs/operations/mcp_cutover_rollback.md` — runbook cutover/rollback.

**Cutover policy**:
- Tutti i cambi a `mcp.json` passano via catalog → generatore. No editing manuale.
- Drift validator gira in CI come gate bloccante.
- Schema snapshot mismatch → quarantena server, non rollback dominio.
- Gateway PoC search: dietro flag `ARIA_GATEWAY_SEARCH=1`, bypass = unset.

### 3.3 L3 — LLM Routing Plane

**File `.aria/config/llm_routing.yaml`**:
```yaml
models:
  opus_4_7:
    id: claude-opus-4-7
    cost_tier: high
    capabilities: [orchestration, deep_reasoning, planning]
  sonnet_4_6:
    id: claude-sonnet-4-6
    cost_tier: medium
    capabilities: [research, synthesis, drafting, tool_use]
  haiku_4_5:
    id: claude-haiku-4-5-20251001
    cost_tier: low
    capabilities: [classification, triage, formatting, cheap_calls]

routing:
  - agent: aria-conductor
    primary: opus_4_7
    fallback: sonnet_4_6
    cache_strategy: long  # cache prefix oltre 1024 token
    max_tokens: 8192
  - agent: search-agent
    primary: sonnet_4_6
    fallback: haiku_4_5
    cache_strategy: medium
    max_tokens: 4096
  - agent: workspace-agent
    primary: sonnet_4_6
    fallback: haiku_4_5
    cache_strategy: medium
    max_tokens: 4096
  - agent: productivity-agent
    primary: sonnet_4_6
    fallback: haiku_4_5
    cache_strategy: long  # ingest prompt è grande
    max_tokens: 6144

intent_overrides:
  - intent: triage
    model: haiku_4_5
  - intent: deep_reasoning
    model: opus_4_7

policy:
  budget_gate:
    daily_token_cap_usd: 5.0
    overflow_action: degrade  # degrade | block | hitl
  fallback_chain_max: 2
```

**Componenti**:
- `src/aria/routing/llm_router.py` — loader + selector + budget gate.
- Hook di integrazione: KiloCode usa l'API Claude esposta. Se KiloCode non supporta routing dichiarativo per agente, ARIA **propone** il modello via `aria-memory` config slot e KiloCode legge prima dello spawn.
- ADR-0013 documenta il punto di integrazione esatto (richiede investigazione tecnica KiloCode in F4).

### 3.4 L4 — Observability Plane

**Componenti**:
- `src/aria/observability/logger.py` — wrapper `structlog`-compatible che produce JSON con campi: `ts`, `level`, `event`, `trace_id`, `session_id`, `agent`, `tool`, `duration_ms`, `outcome`.
- `src/aria/observability/metrics.py` — registry Prometheus-style con counters/histograms:
  - `aria_agent_spawn_total{agent, parent}`
  - `aria_agent_spawn_duration_seconds{agent}`
  - `aria_tool_call_total{agent, tool, outcome}`
  - `aria_hitl_request_total{agent, action_type, outcome}`
  - `aria_mcp_startup_seconds{server}`
  - `aria_llm_tokens_total{agent, model, kind}` con kind=`input|output|cache_read|cache_write`
- `src/aria/observability/events.py` — emitter eventi tipati: `cutover_event`, `rollback_event`, `drift_detected`, `quarantine_triggered`.
- Output: `.aria/runtime/logs/aria.jsonl` (append, rotato), `.aria/runtime/metrics/aria.prom` (Prometheus textfile collector compatibile).

**Trace propagation**:
- `trace_id` generato al gateway entrypoint (UUIDv7 per ordinabilità temporale).
- Conductor riceve in input e lo include in tutti i `HandoffRequest`.
- Sub-agent loga e propaga ai tool MCP via `tool_metadata.trace_id` se MCP server lo supporta.
- Memory wiki tools accettano `trace_id` opzionale e lo persistono in pagina event/log.

---

## 4. Piano Esecutivo (6 Fasi)

### F0 — Branch Reconciliation & Baseline Tag

**Durata stimata**: 0.5 giorni  
**Owner**: Fulvio (HITL su merge)  
**Dipendenze**: nessuna

**Obiettivi**:
- Allineare `main` con `feature/productivity-agent-mvp`.
- Integrare il fix wiki title (corrente branch) sopra il merge.
- Creare baseline LKG.

**Attività**:

1. Verifica stato remote, sync.
   ```bash
   git fetch --all --prune
   git status
   ```
2. Quality gate completo su `feature/productivity-agent-mvp`:
   ```bash
   git checkout feature/productivity-agent-mvp
   make quality   # ruff + format check + mypy + pytest
   ```
3. Aprire PR `feature/productivity-agent-mvp` → `main`. Conventional Commits title: `feat(agents): integrate productivity-agent + MCP coordination v1`.
4. PR description include: lista 3 agenti operativi, 4 skill produttività, ADR-0008, capability matrix v1.0, gateway evaluation conclusion (NIENTE gateway monolitico ora).
5. HITL approval (Fulvio).
6. Squash & merge (per CLAUDE.md merging strategy).
7. Rebase `fix/wiki-update-title-field` su nuovo `main`. Risolvi conflitti su `aria-conductor.md` se presenti.
8. Aprire PR `fix/wiki-update-title-field` → `main`. Quality gate. Squash & merge.
9. Tag `git tag -a baseline-LKG-v1 -m "Baseline LKG dopo integrazione productivity-agent + wiki title fix"`.
10. Push tag.

**Deliverable**:
- `main` aggiornato con 3 agenti operativi
- Tag `baseline-LKG-v1`
- 0 untracked / clean working tree

**Gate uscita**:
- `make quality` verde
- Tag pushato e visibile su origin
- `pytest -q` ≥ 200 test pass (post-merge baseline)

**Rollback strategia**:
- Reset hard a tag pre-existing (ma TAG `baseline-LKG-v1` deve essere preservato come anchor).
- HITL prima di qualsiasi reset.

**Blast radius**: `global` (è l'unica fase global ammessa, perché baseline-restoring).

---

### F1 — Audit, Freeze e Drift Inventory

**Durata stimata**: 1 giorno  
**Owner**: agent + Fulvio (review)  
**Dipendenze**: F0

**Obiettivi**:
- Fotografare lo stato `baseline-LKG-v1` esplicitamente.
- Mappare ogni drift residuo.
- Pubblicare rollback matrix iniziale.

**Attività**:

1. **Snapshot inventory MCP attuale**:
   - Esegui `python scripts/benchmarks/mcp_startup_latency.py` su `baseline-LKG-v1`. Salva output in `docs/operations/baseline_lkg_v1/mcp_baseline.md`.
   - Snapshot `mcp.json` integrale + checksum.

2. **Snapshot prompt agenti**:
   - Salva copia di tutti gli `.aria/kilocode/agents/*.md` in `docs/operations/baseline_lkg_v1/agents/`.

3. **Drift inventory script**:
   - Crea `scripts/audit_drift.py` che produce report:
     - mismatch index `wiki/index.md` ↔ filesystem `wiki/*.md`
     - mismatch agent `allowed-tools` ↔ `mcp_dependencies` ↔ `mcp.json` enabled servers
     - mismatch router code ↔ search-agent `allowed-tools`
     - file orfani / referenze rotte
   - Output: `docs/operations/baseline_lkg_v1/drift_report.md`

4. **Pubblica wiki page mancanti fisicamente**:
   - Verificare `wiki/mcp-architecture.md`, `wiki/agent-capability-matrix.md`, `wiki/productivity-agent.md` esistano post-merge.
   - Se mancano, recovery da `git log` + ricreazione.

5. **Rollback matrix iniziale**:
   - File `docs/operations/rollback_matrix.md` con tabella server×domain → rollback scope, trigger, blast radius, runbook ref.

**Deliverable**:
- `docs/operations/baseline_lkg_v1/` directory completa (inventory, prompt snapshots, drift report)
- `scripts/audit_drift.py` eseguibile e idempotente
- `docs/operations/rollback_matrix.md` v0.1
- Wiki pages fisicamente presenti (non solo nell'index)

**Gate uscita**:
- Drift report < 5 issue P0 (issue P1+P2 ammesse, da risolvere in F2/F3)
- Wiki pages tutte fisicamente presenti
- `audit_drift.py` ritorna exit code 0 se eseguito sul baseline (modalità `--baseline-mode`)

**Rollback strategia**:
- Niente runtime cutover. Fase puramente documentale.
- Eventuali file di output rimuovibili senza impatto.

**Blast radius**: `none` (solo doc).

---

### F2 — Coordinamento Agenti (capability + handoff + envelope)

**Durata stimata**: 3-4 giorni  
**Owner**: agent + Fulvio (review prompt)  
**Dipendenze**: F1

**Obiettivi**:
- Capability matrix v1.0 enforced ovunque (config / prompt / runtime / test).
- Handoff JSON enforced runtime (validator Pydantic).
- Shared context envelope implementato.
- Workspace-agent prompt completo.
- Conductor con dispatch rules formali.

**Attività**:

#### F2.1 Capability matrix come file YAML canonico

1. Creare `.aria/config/agent_capability_matrix.yaml` derivato da `docs/foundation/agent-capability-matrix.md`.
2. Schema:
   ```yaml
   agents:
     - name: aria-conductor
       type: primary
       allowed_tools: [...]
       mcp_dependencies: [aria-memory]
       delegation_targets: [search-agent, workspace-agent, productivity-agent]
       hitl_triggers: [destructive, costly, oauth_consent]
       intent_categories: []
       max_tools: 20
       max_spawn_depth: 2
   ```
3. Validator `src/aria/agents/coordination/registry.py` legge YAML al boot, espone API `get_allowed_tools(agent)`, `validate_delegation(parent, target)`, `validate_tool_count(agent)`.

#### F2.2 Handoff JSON schema enforced

1. Creare `src/aria/agents/coordination/handoff.py`:
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
2. Wrapper `spawn_subagent_validated()` in `src/aria/agents/coordination/spawn.py` che valida payload, incrementa depth, emette evento `aria_agent_spawn_total`.
3. Test unitari: `tests/unit/agents/coordination/test_handoff.py` (≥10 test), `tests/unit/agents/coordination/test_spawn.py` (≥8 test).

#### F2.3 Shared context envelope

1. `src/aria/agents/coordination/envelope.py`:
   ```python
   class ContextEnvelope(BaseModel):
       envelope_id: str  # UUID
       trace_id: str
       session_id: str
       wiki_pages: list[WikiPageSnapshot]
       profile_snapshot: str | None
       created_at: datetime
       expires_at: datetime
   ```
2. Conductor compone envelope una volta per turno. Sub-agent legge da memory MCP o riceve via handoff.
3. Storage envelope: `.aria/runtime/envelopes/{envelope_id}.json` (TTL 10 min, cleanup task scheduler).

#### F2.4 Riscrittura prompt agenti — uniformità

Template comune per ogni agent prompt MD:
```
# <Agent Name>

## Ruolo
...

## Boundary
...

## HITL
...

## Memoria contestuale
- Inizio turno: ContextEnvelope, altrimenti wiki_recall
- Fine turno: wiki_update_tool

## Handoff in ingresso
...

## Handoff in uscita
...

## Tool catalog
...
```

#### F2.5 Conductor dispatch rules formalizzate

```
## Dispatch Decision Tree
| Input pattern | Action |
|---------------|--------|
| Domanda factual | wiki_recall → answer |
| Richiesta ricerca web | spawn search-agent |
| Gmail/Calendar/Drive | spawn workspace-agent |
| File office locale | spawn productivity-agent |
| Ricerca + sintesi | search-agent → productivity-agent |
| File + email | productivity-agent → workspace-agent |
| Operazione distruttiva | hitl_ask → wait → execute |
```

#### F2.6 Test integrazione coordinamento

- `tests/integration/coordination/test_handoff_validation.py`
- `tests/integration/coordination/test_envelope_propagation.py`
- `tests/integration/coordination/test_spawn_depth_guard.py`
- `tests/integration/coordination/test_capability_matrix.py`

**Deliverable**:
- `.aria/config/agent_capability_matrix.yaml`
- `src/aria/agents/coordination/{handoff,envelope,registry,spawn}.py`
- 4 prompt agenti riscritti uniformi
- Conductor con dispatch decision tree
- ≥35 test (unit + integration) verdi
- Wiki page `agents-coordination.md` (nuova)

**Gate uscita**:
- `pytest -q` → 100% pass
- `make quality` verde
- Validator detect 0 tool count violation, 0 delegation violation
- Conductor dispatch tree review approvata HITL

**Rollback strategia**:
- Capability matrix YAML disabilitabile via env `ARIA_CAPABILITY_ENFORCEMENT=0`.
- Handoff validator disabilitabile via env `ARIA_HANDOFF_VALIDATION=0`.
- Envelope opzionale (sub-agent fa fallback a `wiki_recall` diretto se envelope_ref assente).

**Blast radius**: `session` + `domain`.

---

### F3 — MCP Refoundation Rollback-First

**Durata stimata**: 4-6 giorni  
**Owner**: agent + Fulvio (review catalog + ADR)  
**Dipendenze**: F2 (capability matrix YAML come riferimento)

**Obiettivi**:
- Catalog canonico SoT per MCP.
- Drift checks shadow-mode poi enforced.
- Capability probe + schema snapshots integrati al boot.
- Lazy bootstrap per intent dietro flag.
- Search-domain gateway PoC (solo se misurazione lo giustifica).

**Attività**:

#### F3.1 MCP catalog YAML
1. `.aria/config/mcp_catalog.yaml` con schema definito in §3.2.
2. Tutti i 15-16 server enabled mappati con metadata completi.
3. ADR-0009 "MCP catalog as single source of truth" — Proposed.

#### F3.2 Drift validator
1. `scripts/check_mcp_drift.py`:
   - Carica catalog + mcp.json + agent prompt + router code.
   - Confronta tutto, produce diff strutturato.
2. Modalità `--shadow` e `--enforce`.
3. Integrato in `make quality` come step opzionale `make check-drift`.

#### F3.3 Capability probe + snapshot al boot
1. Generalizzare `src/aria/agents/search/capability_probe.py` a tutti i server.
2. Trasformare in `src/aria/mcp/capability_probe.py` (modulo dedicato).
3. Salva snapshot in `.aria/runtime/mcp-schema-snapshots/`.
4. Integrato come comando `bin/aria probe-mcp`.
5. Drift schema → quarantena server.

#### F3.4 Lazy bootstrap per intent
1. `src/aria/launcher/lazy_loader.py`:
   - Input: lista intent richiesti.
   - Output: `mcp.json` ridotto (solo server core + matching intent_tags).
2. `bin/aria start --profile baseline|candidate|shadow --intent <list>`.
3. Test: `tests/integration/launcher/test_lazy_loader.py` (≥6 test).

#### F3.5 Search-domain gateway PoC (decisione condizionata)
**DECISION GATE**: Prima di scrivere codice gateway, ri-eseguire benchmark. Se cold-start sessione search-only > 8s o server search > 10, procedi.

Se procede: gateway dietro flag `ARIA_GATEWAY_SEARCH=1`, bypass unset → direct path.
Se NON procede: ADR-0011 stato `Deferred`.

#### F3.6 ADR ratification
- ADR-0009 (catalog SoT) — Accepted
- ADR-0010 (lazy loading) — Accepted
- ADR-0011 (search gateway) — Accepted o Deferred
- ADR-0012 (MCP cutover and rollback policy) — Accepted

**Deliverable**:
- `.aria/config/mcp_catalog.yaml`
- `scripts/check_mcp_drift.py`
- `src/aria/mcp/capability_probe.py`
- `src/aria/launcher/lazy_loader.py`
- `bin/aria` extended con `--profile`, `--intent`, `probe-mcp`
- 4 ADR (0009-0012)
- `docs/operations/mcp_cutover_rollback.md` runbook

**Rollback strategia**:
- `--profile baseline` riporta a `mcp.json` originale.
- Quarantena per-server: lifecycle nel catalog runtime, NON tocca catalog SoT.

**Blast radius**: `domain`, mai `global`.

---

### F4 — Observability + LLM Routing Scaffold

**Durata stimata**: 3-4 giorni  
**Owner**: agent + Fulvio (review schema)  
**Dipendenze**: F2, F3

**Obiettivi**:
- Trace_id end-to-end propagato.
- Structured logging JSON in posizione canonica.
- Metriche Prometheus-textfile per agente/tool/HITL/MCP/LLM.
- LLM routing dichiarativo `llm_routing.yaml`.
- Prompt caching strategy esplicita per agente.

**Attività**:

#### F4.1 Logger structured JSON
1. `src/aria/observability/logger.py` con wrapper `structlog`-compatible (verifica con Context7).
2. Schema evento JSON canonico.
3. Output rotato in `.aria/runtime/logs/aria.jsonl` (10 file × 50MB).
4. Categorie eventi: `agent.*`, `tool.*`, `hitl.*`, `mcp.*`, `cutover.*`, `rollback.*`, `drift.*`, `llm.*`.

#### F4.2 Metriche Prometheus textfile
1. `src/aria/observability/metrics.py` — Counter/Histogram via prometheus_client.
2. Output `.aria/runtime/metrics/aria.prom`.
3. 6 metriche minime (vedi §3.4).

#### F4.3 Trace propagation
1. Gateway: genera trace_id UUIDv7, include in messaggio Telegram.
2. Conductor: passa trace_id a HandoffRequest.
3. Sub-agent: passa trace_id come tool_metadata in MCP call.
4. ARIA-Memory MCP: registra trace_id su pagine event/log.

#### F4.4 LLM routing scaffold
1. `.aria/config/llm_routing.yaml`.
2. `src/aria/routing/llm_router.py`: select_model, apply_fallback, enforce_budget.
3. ADR-0013 "LLM routing as declarative matrix".

#### F4.5 Prompt caching strategy
1. Conductor: cache-control prefix >1024 token.
2. Per agente in `llm_routing.yaml`: cache_strategy long|medium|short|none.

#### F4.6 ADR observability
- ADR-0014 "Observability schema and trace propagation".

**Deliverable**:
- `src/aria/observability/{logger,metrics,events}.py`
- `src/aria/routing/llm_router.py`
- `.aria/config/llm_routing.yaml`
- ADR-0013, ADR-0014
- Wiki page `observability.md`, `llm-routing.md`

**Rollback strategia**:
- Logger fallback a stdlib logging se structlog non disponibile.
- Metriche: `ARIA_METRICS_ENABLED=0`.
- LLM router: `ARIA_LLM_ROUTING=0`.
- Trace_id opzionale (se mancante, tools generano locale).

---

### F5 — Hardening Test, Rollback Drill, Release Gates

**Durata stimata**: 2-3 giorni  
**Owner**: agent + Fulvio (HITL su drill esecuzione)  
**Dipendenze**: F2, F3, F4

**Obiettivi**:
- Cross-agent integration tests sistematici.
- Rollback drill provato per ogni fase.
- CI policy consistency gates.
- Smoke E2E orchestrazione 3 agenti.

**Attività**:

#### F5.1 Cross-agent integration tests
- `tests/integration/orchestration/test_chain_search_to_productivity.py`
- `tests/integration/orchestration/test_chain_productivity_to_workspace.py`
- `tests/integration/orchestration/test_chain_full_3_hop.py`
- `tests/integration/orchestration/test_envelope_reused_across_chain.py`

#### F5.2 Rollback drill scripts
- `scripts/drill_rollback_baseline.sh`
- `scripts/drill_rollback_capability_matrix.sh`
- `scripts/drill_rollback_lazy_loading.sh`
- `scripts/drill_rollback_observability.sh`

#### F5.3 CI gates
Aggiornare `Makefile` target `make quality`:
```makefile
make lint
make format-check
make typecheck
make test
make check-drift   # nuovo
make check-capability  # nuovo
```

#### F5.4 Smoke E2E
`tests/e2e/test_full_orchestration.py`:
1. Bootstrap session
2. User input "Cerca le ultime news AI e fai brief"
3. Assert: search-agent spawn, productivity-agent spawn, output composto
4. Assert: trace_id presente in tutti i log eventi
5. Assert: envelope condiviso

#### F5.5 Update wiki + documentation
- `docs/llm_wiki/wiki/log.md`, `index.md`
- Wiki nuove pagine: `agents-coordination.md`, `observability.md`, `llm-routing.md`
- `docs/operations/mcp_cutover_rollback.md`

---

## 5. Rollback Matrix Completa

| Fase | Scope | Artefatto attivato | Trigger rollback | Rollback minimo | Blast radius | MTTR target |
|------|-------|--------------------|------------------|-----------------|--------------|:----------:|
| F0 | global | Branch merge + tag | Test fail post-merge, regressione utente | `git revert` PR + ripristino branch | global | <30 min |
| F1 | none | Documentazione baseline | n/a | rimuovere file output | none | n/a |
| F2 | session/domain | Capability matrix YAML enforced | Validator blocca handoff legittimi | `ARIA_CAPABILITY_ENFORCEMENT=0` + revert prompt | domain | <5 min |
| F2 | session | Handoff JSON validator | Sub-agent bloccato | `ARIA_HANDOFF_VALIDATION=0` | session | <2 min |
| F2 | session | Context envelope | Sub-agent non legge envelope | Sub-agent fallback a `wiki_recall` diretto | session | <2 min |
| F3 | server/domain | MCP catalog drift validator | Drift legittimo bloccato | Modalità `--shadow` | server | <5 min |
| F3 | server | Capability probe quarantine | Falso positivo quarantena | Catalog runtime: lifecycle=enabled forzato | server | <2 min |
| F3 | domain | Lazy bootstrap | Server necessario non caricato | `--profile baseline` | session | <2 min |
| F3 | domain | Search gateway PoC | Latenza/errori | Unset `ARIA_GATEWAY_SEARCH` | domain | <2 min |
| F4 | session | Structured logger | Logger crash | Fallback a `logging` standard | session | <2 min |
| F4 | session | Metrics emitter | Disk write fail | `ARIA_METRICS_ENABLED=0` | session | <2 min |
| F4 | session | Trace propagation | Sub-agent rifiuta `trace_id` | Tool genera trace_id locale | session | <2 min |
| F4 | session | LLM router | Modello non disponibile | Fallback chain o KiloCode default | session | <2 min |
| F5 | none | Test + drill | n/a | Test skippabili via marker | none | n/a |

---

## 6. Gate di Attivazione Obbligatori

Per **ogni** fase post-F0:

1. ✅ **Baseline metrics captured** (F1 deliverable presente)
2. ✅ **Drift checks green** (modalità shadow OK come minimo per F2, enforce per F3+)
3. ✅ **Schema snapshot compatibility green** (post F3.3)
4. ✅ **Smoke tests dominio green**
5. ✅ **Rollback action documentata** in fase
6. ✅ **Rollback drill eseguito ≥1 volta** in sandbox
7. ✅ **HITL approval** su F0 merge, F2 prompt rewrite review, F3 ADR, F4 ADR
8. ✅ **`make quality` verde** prima del merge ogni fase

---

## 7. KPI di Successo

### KPI Tecnici (post-F5 vs baseline-LKG-v1)

| KPI | Baseline | Target | Misurato in |
|-----|:-------:|:------:|:------------|
| Cold start MCP all-enabled | ~6.5s (9 server) | ≤ 6.5s (15 server con catalog) | F3 |
| Cold start MCP profile=productivity | n/a | ≤ 1.0s | F3.4 |
| Context iniziale token tool definitions | ~30K | ≤ 12K (con scoped + lazy) | F3 |
| Drift incidents/mese | non misurato | ≤ 1 | F5 |
| Capability matrix violations | non misurato | 0 | F2 |
| Rollback MTTR per fase | non misurato | < 5 min | F5 |
| Test coverage core coordination modules | n/a | ≥ 75% | F2/F5 |

### KPI Coordinamento

| KPI | Baseline | Target | Misurato in |
|-----|:-------:|:------:|:------------|
| Handoff JSON validation pass rate | n/a | 100% | F2 |
| Trace_id presence in logs (sampled) | ~0% | ≥ 95% | F4 |
| Envelope reuse rate (chains 2-hop+) | 0% | ≥ 70% | F4 |
| Conductor sub-agent dispatch correctness | qualitative | ≥ 95% test E2E | F5 |

### KPI Observability

| KPI | Baseline | Target | Misurato in |
|-----|:-------:|:------:|:------------|
| Metriche emesse/min sotto carico | 0 | ≥ 20 | F4 |
| Eventi loggati senza trace_id | 100% | ≤ 5% | F4 |
| Log size dopo 1 settimana | n/a | < 500MB con rotation | F5 |

### KPI Operativi

| KPI | Baseline | Target |
|-----|:-------:|:------:|
| ADR Accepted post-F5 | 8 | ≥ 12 |
| Wiki pages fisicamente presenti vs index | parziale | 100% |
| `make quality` time (full suite) | ~ minuti | ≤ 5 min |
| Cutover documented in log.md | parziale | 100% |

---

## 8. Rischi & Mitigazioni

| ID | Rischio | Probabilità | Impatto | Mitigazione |
|----|---------|:----------:|:-------:|-------------|
| R1 | Merge `feature/productivity-agent-mvp` introduce regressioni nascoste | Media | Alto | Quality gate completo + smoke test mirato pre-merge + tag rollback anchor |
| R2 | Capability matrix enforced blocca handoff legittimi | Media | Medio | Modalità shadow per 1 settimana prima di enforce + env-flag rollback |
| R3 | Catalog MCP introduce drift inverso (catalog vs realtà runtime) | Bassa | Medio | Drift validator bidirezionale + CI gate |
| R4 | Lazy loading rompe intent classification edge case | Media | Medio | Profile=baseline come default, candidate dietro flag manuale |
| R5 | LLM routing non integrabile in KiloCode | Alta | Basso | Investigation prima di scrivere router; fallback documentato a env-var per spawn |
| R6 | Prompt rewrite cambia comportamento agente | Alta | Medio | Diff comparativo HITL prima del merge + smoke E2E pre/post |
| R7 | Logger structured rallenta runtime sotto carico | Bassa | Basso | Async writer + sampling configurabile |
| R8 | Branch merge conflitti complessi | Media | Medio | Rebase incrementale + risoluzione manuale guidata |
| R9 | Wiki page divergence legacy vs nuovo | Media | Basso | F1 audit + auto-sync index.md |
| R10 | ADR backlog troppo lungo causa fatigue review | Media | Basso | Batch review settimanale + template ADR snello |
| R11 | Productivity agent non integrato realmente in Kilo runtime | Bassa | Alto | Smoke E2E manuale post-merge prima di F2 |
| R12 | Drift fra `mcp.json` (`feature/productivity-agent-mvp`) e config reale post-merge | Media | Medio | F1 snapshot + audit script |

---

## 9. ADR Backlog

| ADR | Titolo | Status proposto | Fase | Dipende da |
|-----|--------|:----------------:|:----:|:----------:|
| ADR-0009 | MCP catalog as single source of truth | Proposed → Accepted | F3.1 | — |
| ADR-0010 | Lazy loading per intent enablement | Proposed → Accepted | F3.4 | ADR-0009 |
| ADR-0011 | Search gateway introduction (PoC) | Proposed → Accepted/Deferred | F3.5 | ADR-0009, ADR-0010 |
| ADR-0012 | MCP cutover and rollback policy | Proposed → Accepted | F3.6 | ADR-0009 |
| ADR-0013 | LLM routing as declarative matrix | Proposed → Accepted | F4.4 | — |
| ADR-0014 | Observability schema and trace propagation | Proposed → Accepted | F4.6 | — |
| ADR-0015 | Capability matrix as runtime contract | Proposed → Accepted | F2 | — |
| ADR-0016 | Handoff JSON schema enforcement | Proposed → Accepted | F2 | ADR-0015 |

Ogni ADR usa il template §18.D del blueprint.

---

## 10. Provenance & Context7 Verification Plan

### 10.1 Wiki sources letti per costruire questo piano

- `docs/llm_wiki/wiki/index.md` (read 2026-04-30, v4.6)
- `docs/llm_wiki/wiki/log.md` (read 2026-04-30, head 200 lines)
- `docs/llm_wiki/wiki/mcp-architecture.md` (read da `feature/productivity-agent-mvp`, 2026-04-29)
- `docs/llm_wiki/wiki/agent-capability-matrix.md` (read da `feature/productivity-agent-mvp`, 2026-04-29)
- `docs/llm_wiki/wiki/research-routing.md` (referenced)
- `docs/llm_wiki/wiki/memory-subsystem.md`, `memory-v3.md` (referenced)

### 10.2 Plans/analyses letti

- `docs/analysis/analisi_sostenibilita_mcp_report.md` (read 2026-04-30, full report ~22 sections)
- `docs/analysis/mcp_gateway_evaluation.md` (read 2026-04-30, complete)
- `docs/plans/gestione_mcp_refoundation_plan_v2.md` (read 2026-04-30, complete)
- `docs/plans/mcp_productivity_coordination_optimization_plan_2026-04-29.md` (read 2026-04-30, complete)
- `docs/foundation/agent-capability-matrix.md` (read 2026-04-30, complete)
- `docs/foundation/aria_foundation_blueprint.md` §15 Phase 2, §16 Ten Commandments (read 2026-04-30)

### 10.3 Codice/config ispezionato

- `.aria/kilocode/agents/aria-conductor.md` (main + productivity-mvp, both)
- `.aria/kilocode/agents/search-agent.md`
- `.aria/kilocode/agents/workspace-agent.md` (stub di 25 righe, gap critico)
- `.aria/kilocode/agents/productivity-agent.md` (da productivity-mvp)
- Recent commits via `git log --oneline -25`
- Branch divergence via `git log feature/productivity-agent-mvp ^main`

### 10.4 Context7 verification (eseguita nelle analisi a monte)

Già verificate dalle analisi precedenti:
- `/modelcontextprotocol/modelcontextprotocol` (MCP spec, 2025-06-18)
- `/lastmile-ai/mcp-agent` (multi-agent patterns)
- `/metatool-ai/metamcp` (gateway/aggregator)
- `/cyanheads/pubmed-mcp-server` (rimosso)
- `/benedict2310/scientific-papers-mcp`
- `/microsoft/markitdown` (productivity)

### 10.5 Context7 verification DEFERRED a implementazione

Da verificare al momento della scrittura codice:
- **F2**: `pydantic` (v2 latest) per Handoff/Envelope schema
- **F3**: KiloCode mcp.json schema spec aggiornato
- **F4**: `structlog` per logger structured (versione + best practice 2026)
- **F4**: `prometheus_client` (Python textfile collector pattern)

---

## 11. Appendice A — Capability Matrix v1.0 Enforced

Schema YAML completo per `.aria/config/agent_capability_matrix.yaml`:

```yaml
agents:
  - name: aria-conductor
    type: primary
    allowed_tools:
      - aria-memory/wiki_update_tool
      - aria-memory/wiki_recall_tool
      - aria-memory/wiki_show_tool
      - aria-memory/wiki_list_tool
      - aria-memory/forget
      - aria-memory/stats
      - aria-memory/hitl_ask
      - aria-memory/hitl_list_pending
      - aria-memory/hitl_cancel
      - aria-memory/hitl_approve
      - sequential-thinking/*
      - spawn-subagent
    mcp_dependencies:
      - aria-memory
    delegation_targets:
      - search-agent
      - workspace-agent
      - productivity-agent
    hitl_triggers:
      - destructive
      - costly
      - oauth_consent
    intent_categories: []
    max_tools: 20
    max_spawn_depth: 2

  - name: search-agent
    type: worker
    allowed_tools:
      - aria-memory/wiki_recall_tool
      - aria-memory/wiki_update_tool
      - aria-memory/forget
      - aria-memory/hitl_ask
      - tavily-mcp/*
      - exa-script/*
      - brave-mcp/*
      - fetch/*
      - searxng-script/*
      - reddit-search/*
      - scientific-papers-mcp/*
      - filesystem/read
      - filesystem/write
      - filesystem/search
      - sequential-thinking/*
    mcp_dependencies:
      - aria-memory
      - tavily-mcp
      - exa-script
      - brave-mcp
      - fetch
      - searxng-script
      - reddit-search
      - scientific-papers-mcp
      - filesystem
    delegation_targets: []
    hitl_triggers:
      - costly
    intent_categories:
      - general
      - social
      - academic
      - deep_scrape
    max_tools: 20
    max_spawn_depth: 1

  - name: workspace-agent
    type: worker
    allowed_tools:
      - google_workspace/*
      - filesystem/*
      - aria-memory/wiki_recall_tool
      - aria-memory/wiki_update_tool
    # (completare con tutti i tool Google Workspace)
    mcp_dependencies:
      - google_workspace
      - filesystem
      - aria-memory
    delegation_targets: []
    hitl_triggers:
      - destructive (delete email, delete file)
      - oauth_consent
    intent_categories:
      - gmail
      - calendar
      - drive
      - docs
    max_tools: 20
    max_spawn_depth: 1

  - name: productivity-agent
    type: worker
    allowed_tools:
      - markitdown-mcp/*
      - filesystem/*
      - aria-memory/wiki_recall_tool
      - aria-memory/wiki_update_tool
      - aria-memory/hitl_ask
      - sequential-thinking/*
    mcp_dependencies:
      - markitdown-mcp
      - filesystem
      - aria-memory
    delegation_targets: []
    hitl_triggers:
      - send_email
    intent_categories:
      - office
      - briefing
      - meeting
      - email
    max_tools: 20
    max_spawn_depth: 1
```

---

## 12. Appendice B — Handoff JSON Schema

Modello Pydantic per handoff tra agenti.

```python
from pydantic import BaseModel, Field

class HandoffRequest(BaseModel):
    """Richiesta di handoff tra agenti ARIA.

    Ogni spawn-subagent DEVE includere un HandoffRequest valido.
    Validator runtime rifiuta payload free-form.
    """
    goal: str = Field(
        ...,
        max_length=500,
        description="Obiettivo del task in linguaggio naturale",
    )
    constraints: str | None = Field(
        None,
        description="Vincoli da rispettare (es. fonti, formato, tono)",
    )
    required_output: str | None = Field(
        None,
        description="Formato output atteso",
    )
    timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=300,
        description="Timeout massimo in secondi",
    )
    trace_id: str = Field(
        ...,
        description="Trace ID propagato dal conductor (UUIDv7)",
    )
    parent_agent: str = Field(
        ...,
        description="Nome dell'agente chiamante",
    )
    spawn_depth: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Profondità corrente nella catena di spawn (max 2)",
    )
    envelope_ref: str | None = Field(
        None,
        description="Riferimento al ContextEnvelope condiviso",
    )


class HandoffResult(BaseModel):
    """Risultato dell'esecuzione di un handoff."""
    success: bool
    target_agent: str
    spawn_depth: int
    trace_id: str
    output: str | None = None
    error: str | None = None
```

---

## 13. Appendice C — Trace Context Envelope

```python
from pydantic import BaseModel, Field
from datetime import datetime, UTC, timedelta
from uuid import uuid4

class WikiPageSnapshot(BaseModel):
    """Snapshot di una pagina wiki al momento della creazione dell'envelope."""
    title: str
    slug: str
    content_snippet: str
    confidence: float | None = None


class ContextEnvelope(BaseModel):
    """Contesto condiviso propagato dal conductor a tutti i sub-agent.

    Composto UNA VOLTA dal conductor (single wiki_recall).
    Sub-agent NON rifanno wiki_recall se envelope presente.
    """
    envelope_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    session_id: str
    wiki_pages: list[WikiPageSnapshot] = Field(default_factory=list)
    profile_snapshot: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    def model_post_init(self, _context) -> None:
        if self.expires_at is None:
            self.expires_at = datetime.now(UTC) + timedelta(minutes=5)


def create_envelope(
    trace_id: str,
    session_id: str,
    wiki_pages: list[dict] | None = None,
    profile: str | None = None,
) -> ContextEnvelope:
    """Factory per ContextEnvelope."""
    snapshots = [WikiPageSnapshot(**p) for p in (wiki_pages or [])]
    return ContextEnvelope(
        trace_id=trace_id,
        session_id=session_id,
        wiki_pages=snapshots,
        profile_snapshot=profile,
    )
```

Persistence:
- Storage: `.aria/runtime/envelopes/{envelope_id}.json`
- TTL: 10 minuti
- Cleanup: `cleanup_expired_envelopes()` scheduler task

---

## 14. Appendice D — LLM Routing YAML (esempio)

File `.aria/config/llm_routing.yaml` completo:

```yaml
models:
  opus_4_7:
    id: claude-opus-4-7
    cost_tier: high
    capabilities:
      - orchestration
      - deep_reasoning
      - planning

  sonnet_4_6:
    id: claude-sonnet-4-6
    cost_tier: medium
    capabilities:
      - research
      - synthesis
      - drafting
      - tool_use

  haiku_4_5:
    id: claude-haiku-4-5-20251001
    cost_tier: low
    capabilities:
      - classification
      - triage
      - formatting
      - cheap_calls

routing:
  - agent: aria-conductor
    primary: opus_4_7
    fallback: sonnet_4_6
    cache_strategy: long
    max_tokens: 8192

  - agent: search-agent
    primary: sonnet_4_6
    fallback: haiku_4_5
    cache_strategy: medium
    max_tokens: 4096

  - agent: workspace-agent
    primary: sonnet_4_6
    fallback: haiku_4_5
    cache_strategy: medium
    max_tokens: 4096

  - agent: productivity-agent
    primary: sonnet_4_6
    fallback: haiku_4_5
    cache_strategy: long
    max_tokens: 6144

intent_overrides:
  - intent: triage
    model: haiku_4_5
  - intent: deep_reasoning
    model: opus_4_7

policy:
  budget_gate:
    daily_token_cap_usd: 5.0
    overflow_action: degrade
  fallback_chain_max: 2
```

Router Python (`src/aria/routing/llm_router.py`):
- `select_model(agent, intent)` → primary model (o intent override)
- `apply_fallback(prev_model, error)` → fallback model o None
- `enforce_budget(estimated_tokens, model)` → bool

---

## 15. Appendice E — File da Creare/Aggiornare

### Nuovi file (16)

1. `.aria/config/agent_capability_matrix.yaml` — Capability matrix canonica
2. `.aria/config/mcp_catalog.yaml` — MCP catalog single source of truth
3. `.aria/config/llm_routing.yaml` — LLM routing dichiarativo
4. `src/aria/agents/coordination/handoff.py` — HandoffRequest Pydantic model
5. `src/aria/agents/coordination/envelope.py` — ContextEnvelope + storage
6. `src/aria/agents/coordination/registry.py` — AgentRegistry loader/validator
7. `src/aria/agents/coordination/spawn.py` — spawn wrapper validato
8. `src/aria/mcp/capability_probe.py` — Probe generalizzato
9. `src/aria/launcher/lazy_loader.py` — Lazy bootstrap per intent
10. `src/aria/observability/logger.py` — Logger structured JSON
11. `src/aria/observability/metrics.py` — Metriche Prometheus
12. `src/aria/observability/events.py` — Eventi tipati
13. `src/aria/routing/llm_router.py` — LLM routing
14. `scripts/check_mcp_drift.py` — Drift validator CI
15. `scripts/audit_drift.py` — Audit inventory script
16. `docs/operations/mcp_cutover_rollback.md` — Runbook

### Nuove directory (5)

- `src/aria/agents/coordination/`
- `src/aria/mcp/`
- `src/aria/launcher/`
- `src/aria/observability/`
- `src/aria/routing/`

### File da aggiornare (10)

1. `.aria/kilocode/agents/aria-conductor.md` — Dispatch rules + envelope
2. `.aria/kilocode/agents/search-agent.md` — Handoff in/out, pubmed cleanup
3. `.aria/kilocode/agents/workspace-agent.md` — Da stub a prompt completo
4. `.aria/kilocode/agents/productivity-agent.md` — 2-hop esempi
5. `docs/llm_wiki/wiki/index.md` — Nuove pagine e raw sources
6. `docs/llm_wiki/wiki/log.md` — Entry implementazione
7. `Makefile` — check-drift, check-capability
8. `bin/aria` — Flag --profile, --intent, probe-mcp
9. `.aria/kilocode/mcp.json` — (tramite generatore, mai manuale)
10. `pyproject.toml` — Dipendenze structlog

### Test files (10)

1. `tests/unit/agents/coordination/test_handoff.py` (≥10)
2. `tests/unit/agents/coordination/test_envelope.py` (≥8)
3. `tests/unit/agents/coordination/test_registry.py` (≥8)
4. `tests/unit/agents/coordination/test_spawn.py` (≥8)
5. `tests/integration/coordination/test_handoff_validation.py`
6. `tests/integration/coordination/test_envelope_propagation.py`
7. `tests/integration/coordination/test_spawn_depth_guard.py`
8. `tests/integration/coordination/test_capability_matrix.py`
9. `tests/integration/launcher/test_lazy_loader.py` (≥6)
10. `tests/integration/orchestration/` (4 test cross-agent)
