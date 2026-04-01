# Analisi Knowledge Agency (ARIA)

**Data**: 2026-03-31  
**Scope**: valutazione architetturale/operativa della Knowledge Agency come organizzazione gerarchica `Agency → Agents → Skills → Tools`  
**Target**: verificare se la configurazione attuale sfrutta pienamente una organizzazione complessa di agenti AI + tool/API, con raccomandazioni **SOTA 2026** e orientamento **OpenCode CLI**.

---

## 1) Executive summary

La Knowledge Agency è già su una base tecnica solida (router, registry, workflow engine, provider chain, test estesi), ma **non sta ancora sfruttando pienamente il modello organizzativo gerarchico complesso** descritto nel blueprint.

### Valutazione sintetica

- **Maturità architettura gerarchica**: **7/10**
- **Maturità operativa multi-agent reale**: **5.5/10**
- **Maturità governance/tool-safety (stile OpenCode/MCP)**: **4.5/10**
- **Readiness SOTA 2026**: **5/10**

### Diagnosi principale

La struttura c’è, ma oggi è in parte “nominale”:
- gerarchia implementata a livello di componenti,
- ma con **drift tra design e runtime**,
- **parallelismo non effettivo** in alcuni path,
- **memory loop poco integrato**,
- **governance/tool-permissions non hardenizzata**,
- e **rischi security critici** (API key hardcoded in config/test).

---

## 2) Metodo e fonti

## 2.1 Artefatti analizzati (codebase)

- `internal/aria/agency/knowledge.go`
- `internal/aria/agency/knowledge_agents.go`
- `internal/aria/agency/knowledge_supervisor.go`
- `internal/aria/agency/knowledge_execution.go`
- `internal/aria/agency/knowledge_synthesis.go`
- `internal/aria/agency/knowledge_task_state.go`
- `internal/aria/config/knowledge.go`
- `internal/app/aria_integration.go`
- `internal/aria/skill/registry.go`
- `internal/aria/skill/web_research.go`
- `internal/aria/skill/knowledge/provider.go`
- `internal/aria/agency/catalog.go`
- `docs/plans/knowledge-agency-implementation-plan.md`
- `docs/foundation/BLUEPRINT.md`

## 2.2 Riferimenti best practice esterni

- OpenCode Agents docs: separazione primary/subagent, delega e isolamento contesti
- OpenCode Permissions docs: modello `allow/ask/deny`, granularità per tool e command pattern
- MCP Specification (2025-06-18): capability negotiation, consenso utente, tool safety, trust boundaries
- Pattern 2026 multi-agent (planner/executor/critic, evidence-first, governance-by-policy)

---

## 3) Stato attuale rispetto alla gerarchia Agency → Agents → Skills → Tools

## 3.1 Agency level

**Positivo**
- Agency completa con lifecycle (`Start/Stop/Pause/Resume`), eventi, stato.
- Componenti gerarchici espliciti: `TaskRouter`, `AgentRegistry`, `WorkflowEngine`, `ResultSynthesizer`.

**Limiti**
- Inizializzazione in `initARIA` non usa `knowledgeCfg.IsConfigured()` (a differenza di Weather/Nutrition).
- Divergenza tra agency runtime e catalogo dichiarativo (vedi §4.1).

## 3.2 Agent level

**Positivo**
- Buona specializzazione funzionale: `web-search`, `academic`, `news`, `code-research`, `historical`.
- Fallback tra agenti previsto.

**Limiti**
- Blueprint/plan originale prevedeva triade `researcher/educator/analyst`; in runtime prevale una tassonomia diversa.
- `educator`/`analyst` rimangono soprattutto bridge legacy con logica placeholder.

## 3.3 Skill level

**Positivo**
- `WebResearchSkill` esiste e usa provider chain.
- Skill naming coerente con dominio knowledge.

**Limiti**
- `SetupDefaultSkills()` registra solo skill development (code-review/tdd/debugging), non knowledge.
- Workflow step `validation` non ha implementazione skill dedicata nel path mostrato.

## 3.4 Tools/Provider level

**Positivo**
- Provider chain ricca e multi-tier con fallback.
- Primo tentativo di classificazione errori recoverable/non-recoverable.

**Limiti**
- Manca governance policy-driven per tool invocation (budget/risk/consenso per classe di tool).
- Mancano circuit breaker, adaptive rate limit orchestration, quality-based provider selection.

---

## 4) Punti di forza

1. **Architettura modulare già pronta per scaling**: router/registry/executor/synthesizer separati.
2. **Copertura test ampia**: routing, lifecycle, workflow, synthesis, concorrenza, integrazione provider.
3. **Ecosistema provider molto ricco**: web, academic, news, historical, docs.
4. **Fallback già presente** sia intra-agent che inter-provider.
5. **Event-driven lifecycle** utile per osservabilità e auditing.

---

## 5) Debolezze (con impatto)

## 5.1 Drift strutturale tra blueprint/catalogo/runtime

- `catalog.go` presenta Knowledge Agency con agenti `researcher/educator/analyst` e skill set parziale.
- Runtime agency usa `web-search/academic/news/code/historical`.

**Impatto**: governance confusa, routing cross-layer incoerente, osservabilità non allineata.

## 5.2 Parallelismo non realmente sfruttato in path chiave

- In `KnowledgeAgency.executeParallel()` l’esecuzione è iterativa (for-loop), non concorrente.

**Impatto**: latenza alta, scarso leverage del multi-agent fanout.

## 5.3 State machine task non integrata nel flusso principale

- `TaskStateMachine` esiste ma non è usata sistematicamente in `Execute()`.

**Impatto**: perdita di tracciabilità operativa fine-grained e recovery semantico.

## 5.4 Memory integration incompleta

- Config memory presente (`EnableMemory`, `SaveFacts`, etc.), ma nel path principale non emerge ciclo robusto retrieve→reason→writeback.

**Impatto**: scarsa continuità cognitiva, ripetizione lavoro, ridotto apprendimento organizzativo.

## 5.5 Sintesi risultati troppo debole per standard 2026

- Ranking euristico minimale (campi presenti/non presenti).
- Nessun confidence model robusto, conflict resolution, citation scoring, provenance hardening.

**Impatto**: qualità di output variabile, rischio di synthesis hallucination.

## 5.6 Governance tool/API non hardenizzata (OpenCode/MCP style)

- Mancano policy esplicite stile `allow/ask/deny` per classe agente e comando tool.
- Assenza di gate formali per tool ad alto rischio.

**Impatto**: superficie rischio elevata (security/compliance).

## 5.7 Criticità security grave: segreti hardcoded

- In `DefaultKnowledgeConfig()` e test compaiono API key valorizzate di default.

**Impatto**: leakage segreti, non conformità security baseline, rischio compromissione account/provider.

---

## 6) Gap rispetto best practice OpenCode CLI + MCP + SOTA 2026

## 6.1 OpenCode-oriented gap

Best practice OpenCode (2026):
- agenti con **permission profile dedicato**,
- planner read-only,
- executor tool-scoped,
- reviewer senza write,
- task delegation controllata.

Stato attuale Knowledge Agency:
- gerarchia presente ma **senza policy matrix esplicita per ruolo agente**.

## 6.2 MCP-oriented gap

MCP raccomanda:
- consenso esplicito per azioni ad alto impatto,
- capability negotiation,
- trust boundaries chiare tool/server.

Stato attuale:
- integrazione provider buona, ma governance/consent/risk boundary non completa.

## 6.3 SOTA 2026 multi-agent gap

Pattern maturi 2026:
- **Planner → Executor → Critic** con ruoli antagonisti,
- evidence-first con citations/confidence,
- policy-based orchestration,
- runtime eval loop continuo.

Stato attuale:
- componenti esistono, ma critic loop e eval-quality gates non sono ancora first-class nel runtime knowledge.

---

## 7) Interventi migliorativi proposti (SOTA 2026 compliant)

## 7.1 Priorità P0 (immediata, 1-2 settimane)

1. **Rimozione segreti hardcoded**
   - API key solo da env/secret manager.
   - Rotazione credenziali attuali.

2. **Allineamento modello organizzativo unico**
   - Decidere e consolidare naming/ruoli ufficiali:
     - Opzione A: `researcher/educator/analyst` come ruoli macro + specialist subagents.
     - Opzione B: mantenere specialisti correnti e aggiornare catalogo/blueprint/routing.

3. **Parallelismo reale**
   - Rifattorizzare `executeParallel()` con goroutine + bounded semaphore + context cancellation + timeout policy.

4. **Gate di configurazione in bootstrap**
   - In `aria_integration`: knowledge agency solo se `Enabled && IsConfigured()`.

## 7.2 Priorità P1 (breve termine, 2-6 settimane)

5. **Task State Machine integrata end-to-end**
   - Ogni task passa per stati persistiti: `pending→validating→running→synthesizing→completed/failed`.
   - Audit log e replay.

6. **Memory loop operativo completo**
   - Pre-step: retrieve top-k episodi/fatti per query normalizzata.
   - Post-step: writeback con confidence threshold e provenance.

7. **Synthesis 2.0**
   - Ranking multi-fattore (recency, source trust, citation density, contradiction penalty).
   - Output con `confidence`, `evidence[]`, `conflicts[]`, `unknowns[]`.

8. **Skill registry knowledge-aware**
   - Registrare skill knowledge nel registry default (feature flag + capability check).

## 7.3 Priorità P2 (medio termine, 1-2 trimestri)

9. **Policy-driven agent governance (stile OpenCode)**
   - Matrice permessi per ruolo agente:
     - Planner: no write/no execution,
     - Research Executor: fetch/search allow, risky tools ask,
     - Critic: read-only,
     - Escalation agent: ask-first.

10. **Planner/Executor/Critic formalizzati**
    - Introduzione ruolo critic con scorecard qualità e veto su output low-confidence.

11. **Provider orchestration avanzata**
    - Dynamic provider routing per costo/latenza/qualità.
    - Circuit breaker + budget manager.

12. **Continuous eval & red-team harness**
    - Benchmark per factuality, freshness, citation accuracy, tool safety compliance.

---

## 8) Blueprint organizzativo consigliato (target)

```text
Knowledge Agency Director
├── Planning Cell (planner, no-tools, decomposizione task)
├── Research Cell (web/academic/news/historical/code executors)
├── Synthesis & QA Cell (critic/reviewer, citation/conflict checks)
└── Memory Cell (retrieve/writeback governance)

Cross-cutting:
- Tool Governance Policy Engine (allow/ask/deny + risk classes)
- Observability & Eval Engine (SLO + quality gates)
```

Questo modello conserva la specializzazione già implementata e introduce una catena gerarchica esplicita con responsabilità verificabili.

---

## 9) KPI/SLO raccomandati (per misurare miglioramento reale)

1. **Task success rate** (overall e per categoria agente)
2. **Median/95p latency** (single, workflow, parallel)
3. **Citation coverage** (% risposte con evidenze verificabili)
4. **Conflict detection rate** (sintesi multi-sorgente)
5. **Memory reuse rate** (% task con retrieve utile)
6. **Fallback efficiency** (degrado controllato vs errore terminale)
7. **Security posture** (0 secret hardcoded, 100% risky tool calls gated)
8. **Human override rate** (segnale di trust/calibrazione)

---

## 10) Conclusione

La Knowledge Agency ha una base buona e già “enterprise-shape”, ma **non è ancora una organizzazione multi-agent pienamente matura** secondo gli standard 2026.

Il valore maggiore, nel breve, arriva da:
1) hardening security/governance,  
2) allineamento organizzativo unico (naming/ruoli/catalogo/runtime),  
3) parallelismo reale + memory loop operativo + synthesis evidence-first.

Con questi interventi, la Knowledge Agency può passare rapidamente da una gerarchia prevalentemente strutturale a una gerarchia **operativa, governata e misurabile**, coerente con paradigma OpenCode CLI e best practice MCP/SOTA 2026.

---

## Appendix A — Evidenze puntuali (code-level)

- `knowledge.go`: architettura gerarchica dichiarata e lifecycle/eventing presenti.
- `knowledge_supervisor.go`: routing keyword-based, fallback su category/web.
- `knowledge_execution.go`: workflow engine robusto; path paralleli presenti nel motore.
- `knowledge.go::executeParallel()`: implementazione sequenziale (gap).
- `knowledge_task_state.go`: state machine completa ma poco agganciata all’execute principale.
- `config/knowledge.go`: flags estesi ma presenza di default API keys (critical).
- `skill/registry.go`: setup default non include skill knowledge.
- `app/aria_integration.go`: knowledge agency init non condizionato a `IsConfigured()`.
- `agency/catalog.go`: mismatch tra catalog entry e agenti reali runtime.

## Appendix B — Riferimenti esterni usati

- OpenCode Docs — Agents: https://opencode.ai/docs/agents/
- OpenCode Docs — Permissions: https://opencode.ai/docs/permissions/
- MCP Spec (2025-06-18): https://modelcontextprotocol.io/specification/2025-06-18
