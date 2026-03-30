# ARIA Orchestrator Enhancement Master Plan

**Data:** 2026-03-30  
**Autore:** General Manager (piano strategico)  
**Stato:** PROPOSTA PRD/TDD READY  
**Scope:** Definire il piano completo di evoluzione dell’Orchestrator come “cervello” centrale ARIA (controllo end-to-end di ogni query/interazione)

---

## 1) Obiettivo

Rendere l’Orchestrator il componente centrale e sempre attivo in ogni interazione utente, con capacità di:

1. **Intent understanding robusto** (classificazione intento, dominio, complessità, rischio)
2. **Decisione esplicita del flusso** (agency/agent/tool routing + strategia di esecuzione)
3. **Deliberazione controllata** (uso selettivo di `sequential-thinking`, non indiscriminato)
4. **Execution governance** (guardrail, permission, fallback, recovery)
5. **Verifica dell’esito prima della risposta finale**
6. **Memoria e apprendimento continuo** (episodic/procedural/routing feedback)

---

## 2) Stato attuale sintetico (baseline repository)

Riferimenti principali:
- `internal/aria/core/orchestrator.go`
- `internal/aria/core/orchestrator_impl.go`
- `internal/aria/routing/router.go`
- `internal/aria/routing/router_impl.go`
- `docs/foundation/BLUEPRINT.md` (v1.12.0-DRAFT)

Situazione corrente:
- Orchestrator già presente (`BasicOrchestrator`) con classify → route → agency execute → response.
- Routing prevalentemente rules-based con fallback.
- Integrazione memoria già presente in `ProcessQuery` (context, episodes, procedures).
- Mancano ancora:
  - policy decisionale avanzata (planner/executor/reviewer separati)
  - gating formale per l’uso di `sequential-thinking`
  - protocollo standardizzato multi-agency/multi-agent
  - validazione finale strutturata con score e criteria
  - telemetria completa del ciclo decisionale orchestrator

---

## 3) Principi architetturali target

1. **Orchestrator-first**: ogni query passa da Orchestrator.
2. **Deliberazione a costo variabile**: reasoning profondo solo se necessario.
3. **Separation of concerns**:
   - Planner (decide)
   - Executor (agisce)
   - Reviewer (verifica)
4. **Determinismo operativo + adattività**:
   - policy configurabile
   - fallback robusti
5. **Evidence-based response**: nessuna chiusura senza verifica minima.
6. **Backward compatibility**: percorso legacy sempre disponibile in fallback.

---

## 4) Ruolo di `sequential-thinking` in ARIA

### 4.1 Posizionamento corretto
`sequential-thinking` va usato come **modulo di deliberazione dell’orchestrator/planner**, non come tool standard per agenti esecutivi.

### 4.2 Trigger Policy (quando attivarlo)
Attivare `sequential-thinking` solo se una o più condizioni sono vere:

- task richiede **>=2 tool**
- task richiede **>=2 agenti** o **>=1 agency + handoff**
- query ambigua / vincoli in conflitto
- rischio elevato (azioni irreversibili o costose)
- failure recovery o postmortem decisionale

### 4.3 Non-Trigger Policy (quando evitarlo)
Non usarlo per:
- query semplici Q&A
- singola operazione deterministica
- skill atomiche già definite e a basso rischio

### 4.4 Output atteso dal planner con sequential thinking
- obiettivo normalizzato
- ipotesi operative
- piano step-by-step
- rischi/precondizioni/fallback
- criterio di done

---

## 5) Modello operativo target (pipeline)

```
User Query
  -> Phase A: Intake + Context Recovery
  -> Phase B: Intent/Risk/Complexity Classification
  -> Phase C: Decision Engine
       - Fast Path (no sequential thinking)
       - Deep Path (with sequential thinking)
  -> Phase D: Execution Orchestration (agency/agent/tool)
  -> Phase E: Review & Verification Gate
  -> Phase F: Final Response + Memory Writeback + Metrics
```

### 5.1 Fast Path
Usato per task semplici: classifica, instrada, esegue, verifica minima, rispondi.

### 5.2 Deep Path
Usato per task complessi: planner deliberativo (`sequential-thinking`) → executor → reviewer → risposta.

---

## 6) Design dei componenti da introdurre/evolvere

## 6.1 Orchestrator Decision Engine
Nuove responsabilità:
- complexity score (0-100)
- risk score (0-100)
- confidence-aware routing policy
- scelta tra Fast/Deep Path

Artefatti previsti:
- `internal/aria/core/decision_policy.go`
- `internal/aria/core/complexity_analyzer.go`
- `internal/aria/core/risk_analyzer.go`

## 6.2 Planner / Executor / Reviewer pattern

### Planner
- costruisce execution plan
- usa `sequential-thinking` solo con trigger policy
- produce piano strutturato serializzabile

### Executor
- esegue step del piano
- gestisce handoff agency/agent
- applica permission/guardrail

### Reviewer
- verifica output vs obiettivo/vincoli
- richiede retry o replan se necessario

Artefatti previsti:
- `internal/aria/core/planner.go`
- `internal/aria/core/executor.go`
- `internal/aria/core/reviewer.go`
- `internal/aria/core/plan_types.go`

## 6.3 Routing 2.0
Evoluzione di classifier/router:
- routing con confidence calibration
- policy-based override (es. cost budget, safety budget)
- capability matching (agency/agent availability)

Artefatti previsti:
- `internal/aria/routing/policy_router.go`
- `internal/aria/routing/capability_registry.go`

## 6.4 Tool Governance Layer
Normalizzare selezione tool:
- Native Tool first
- Direct API second
- MCP third (se necessario)

Artefatti previsti:
- `internal/aria/core/tool_governance.go`
- `internal/aria/core/tool_cost_model.go`

## 6.5 Prompt System dedicato orchestrator
Prompts separati per:
- planner
- executor
- reviewer
- escalation/report

Artefatti previsti:
- `internal/llm/prompt/orchestrator_planner.go`
- `internal/llm/prompt/orchestrator_executor.go`
- `internal/llm/prompt/orchestrator_reviewer.go`

---

## 7) Configurazione e integrazione OpenCode/MCP

## 7.1 Config keys da introdurre in `.opencode.json` / config ARIA

```jsonc
{
  "aria": {
    "orchestrator": {
      "mode": "hybrid",
      "enablePlannerReviewer": true,
      "sequentialThinking": {
        "enabled": true,
        "complexityThreshold": 55,
        "riskThreshold": 40,
        "maxThoughts": 12,
        "timeoutMs": 12000
      },
      "verification": {
        "enabled": true,
        "minAcceptanceScore": 0.75,
        "maxReplan": 2
      }
    }
  },
  "mcp": {
    "sequential-thinking": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
      "enabled": true
    }
  }
}
```

## 7.2 Slash Commands operativi suggeriti
- `/decide-agent` → invoca Decision Engine
- `/plan` → genera piano (forza planner)
- `/debug-plan` → postmortem deliberativo
- `/review-response` → reviewer su output candidato

---

## 8) Gestione agencies/agents (governance)

## 8.1 Contratto operativo standard
Ogni agency/agent deve esporre:
- capability declaration
- cost hint (token/time)
- risk class
- expected inputs/outputs

## 8.2 Handoff protocol
Ogni handoff include:
- reason
- expected outcome
- constraints
- timeout/budget

## 8.3 Registry & health
- health status realtime per agency/agent
- degrado controllato se agent non disponibile
- auto-fallback verso agent equivalente

---

## 9) Verifica qualità e criteri di accettazione

## 9.1 Acceptance gates per risposta finale
Prima della risposta utente:
1. obiettivo soddisfatto
2. vincoli rispettati
3. rischio entro soglia
4. evidence/log disponibili

## 9.2 KPI orchestrator
- routing accuracy
- fallback rate
- replan rate
- tool misuse rate
- response success rate
- avg latency fast path vs deep path

## 9.3 Test strategy
- unit: decision policy, trigger policy, reviewer scoring
- integration: planner→executor→reviewer
- e2e: query multi-agency complesse
- chaos/failure: tool fail, agent unavailable, timeout

---

## 10) Piano implementativo incrementale (roadmap)

## Milestone O1 — Decision Core Hardening
- complexity/risk analyzers
- trigger policy sequential thinking
- Fast vs Deep path switch

Deliverable:
- Decision Engine stabile
- test unit + integration base

## Milestone O2 — Planner/Executor/Reviewer
- nuovi componenti core
- plan schema standard
- reviewer acceptance gate

Deliverable:
- pipeline completa con replan controllato

## Milestone O3 — Routing 2.0 + Capability Governance
- capability registry
- policy router con confidence calibration

Deliverable:
- routing robusto e spiegabile

## Milestone O4 — Prompt & Command Layer
- prompt dedicati orchestrator
- slash commands `/plan`, `/decide-agent`, `/debug-plan`

Deliverable:
- UX operativa per debug/controllo orchestrazione

## Milestone O5 — Telemetria, memory feedback loop
- metriche orchestrator
- learning da outcome (success/failure)

Deliverable:
- miglioramento continuo misurabile

---

## 11) Mapping al BLUEPRINT.md

- **Parte II, 2.2.1 Orchestrator**: estensione capacità decisionali e controllo end-to-end
- **Parte II, 2.3 Routing System**: evoluzione in policy router con confidence e capability
- **Parte III Memory System**: writeback strutturato post-esecuzione
- **Parte V Guardrails/Permission**: gating pre-esecuzione e pre-response
- **Parte VI Self-Analysis**: KPI + feedback loop orchestrator

---

## 12) Rischi principali e mitigazioni

1. **Overhead latenza da reasoning profondo**  
   Mitigazione: trigger policy rigorosa + maxThoughts + timeout.

2. **Aumento complessità architetturale**  
   Mitigazione: milestone incrementali e feature flags.

3. **Drift tra piano e implementazione reale**  
   Mitigazione: contract tests + acceptance gates + review obbligatoria.

4. **Tool sprawl / decisioni non consistenti**  
   Mitigazione: Tool Governance Layer e catalogo capability versionato.

---

## 13) Deliverable finali di questo piano

1. Piano master orchestrator enhancement (questo documento)
2. Backlog tecnico milestone-based per implementazione
3. Schema config orchestrator + sequential-thinking
4. Pattern planner/executor/reviewer standard
5. Criteri di accettazione e KPI pronti per QA

---

## 14) Prossimi passi esecutivi suggeriti

1. Convertire questo piano in **PRD formale** (Milestone 1 HitL)
2. Produrre **TDD tecnico** con package design e interface contracts (Milestone 2 HitL)
3. Avviare implementazione O1 su branch dedicato con test gates obbligatori

---

## Appendix A — Fonti esterne considerate

- MCP Sequential Thinking (modelcontextprotocol/servers)
- OpenCode Config Docs (`mcp`, `agent`, `command`, `default_agent`, `permission`)
- Best practices multi-agent orchestration (Planner/Executor/Reviewer patterns)

Nota: le fonti sono usate come supporto di design; le decisioni finali sono allineate alla codebase e al `docs/foundation/BLUEPRINT.md` corrente.
