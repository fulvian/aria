# Piano di Implementazione Robusta — Knowledge Agency (Opzione A)

**Data**: 2026-03-31  
**Stato**: Proposto (pronto per esecuzione)  
**Baseline**: `docs/analysis/2026-03-31-knowledge-agency-hierarchical-assessment.md`  
**Blueprint di riferimento**: `docs/foundation/BLUEPRINT.md` (v1.17.0-DRAFT)

---

## 1) Obiettivo

Eseguire un riallineamento completo e robusto della Knowledge Agency secondo **Opzione A**:

- mantenere la catena gerarchica esplicita `Agency → Agents → Skills → Tools`,
- standardizzare la tassonomia a livello organizzativo,
- chiudere i gap emersi (security, governance, parallelismo, memory-loop, synthesis quality),
- aggiornare blueprint/documentazione/runtime/catalogo/test in modo coerente e verificabile.

---

## 2) Decisione architetturale confermata (Opzione A)

## 2.1 Tassonomia target

La Knowledge Agency adotta due livelli:

1. **Macro-agent gerarchici (canonici)**
   - `researcher`
   - `educator`
   - `analyst`

2. **Specialist sub-agents (operativi)**
   - `web-search`
   - `academic`
   - `news`
   - `code-research`
   - `historical`
   - (eventuali futuri specialisti)

## 2.2 Regola di orchestrazione

- I macro-agent sono i **ruoli ufficiali** (contratto organizzativo, blueprint, catalogo).
- I specialist sono **unità operative delegabili** dal macro-agent.
- Ogni task entra da macro-agent e può fan-out su specialist.

---

## 3) Scope del piano

## 3.1 In scope

1. **Allineamento tassonomico** (blueprint + catalog + runtime + routing)
2. **Security hardening** (segreti, policy tool/API)
3. **Execution hardening** (parallelismo reale, retry/circuit-breaker)
4. **Memory operational loop** (retrieve → reason → writeback)
5. **Synthesis 2.0** (evidence-first, confidence, conflict handling)
6. **Observability 2.0** (KPI/SLO, audit, tracce stato)
7. **Skill registry knowledge-aware**
8. **Test strategy e rollout controllato**

## 3.2 Out of scope (per questa iterazione)

- Nuovo vector DB proprietario (si usa memory system esistente)
- Migrazione cross-agency non knowledge
- Refactor globale orchestrator fuori knowledge domain

---

## 4) Workstreams e deliverable

## WS-A — Allineamento tassonomia e contratti

### Deliverable
- Blueprint aggiornato con tassonomia Opzione A (macro + specialist)
- Catalogo agenzie/agenti/skill/provider coerente con runtime
- Mapping univoco ruolo→specialist→skill

### File target
- `docs/foundation/BLUEPRINT.md`
- `internal/aria/agency/catalog.go`
- `internal/aria/agency/knowledge.go`
- `internal/aria/agency/knowledge_supervisor.go`

### Criteri di accettazione
- Nessun drift tra blueprint/catalog/runtime
- Route deterministico: macro-agent ingress + delega specialist coerente

---

## WS-B — Security & governance hardening (priorità massima)

### Deliverable
1. **Secret hygiene**
   - rimozione API key hardcoded da default config e test
   - sola lettura da env/secret provider
2. **Permission matrix stile OpenCode/MCP**
   - policy `allow/ask/deny` per tool class e command pattern per ruolo agente
3. **Risk gate**
   - tool ad alto rischio sempre `ask`/`deny` by default

### File target
- `internal/aria/config/knowledge.go`
- test knowledge che includono key inline
- eventuale modulo policy toolgovernance + wiring su knowledge agency

### Criteri di accettazione
- 0 segreti hardcoded in repo
- policy enforcement verificabile su chiamate tool/provider
- audit trail di decisione policy presente

---

## WS-C — Execution engine robusto (parallelismo reale)

### Deliverable
- `executeParallel()` realmente concorrente (goroutine + semaphore + cancellation)
- timeout, fallback e partial-failure handling coerenti
- limiti di concorrenza configurabili

### File target
- `internal/aria/agency/knowledge.go`
- `internal/aria/agency/knowledge_execution.go`

### Criteri di accettazione
- riduzione p95 latenza su task fan-out
- assenza di race/leak in test concorrenza
- comportamento deterministico su failure parziali

---

## WS-D — Task state machine end-to-end

### Deliverable
- integrazione completa `TaskStateMachine` nel flusso `Execute`
- stato persistibile e tracciabile per replay/debug

### File target
- `internal/aria/agency/knowledge_task_state.go`
- `internal/aria/agency/knowledge.go`

### Criteri di accettazione
- transizioni stato valide e complete per ogni task
- audit timeline disponibile per task id

---

## WS-E — Memory loop operativo

### Deliverable
- pre-step retrieval (episodi/fatti top-k)
- post-step writeback con confidence/provenance threshold
- query normalization per cache hit

### File target
- bridge/skill knowledge path (`knowledge.go`, `web_research.go`, skill correlate)
- eventuale integrazione memory service in knowledge agency constructor/wiring

### Criteri di accettazione
- memory reuse rate misurabile
- facts/episodes salvati con provenienza

---

## WS-F — Synthesis 2.0 (SOTA 2026)

### Deliverable
- ranking multi-fattore (trust, recency, evidence density, contradiction penalty)
- output strutturato:
  - `confidence`
  - `evidence[]`
  - `conflicts[]`
  - `unknowns[]`
- policy “no evidence → uncertainty explicit”

### File target
- `internal/aria/agency/knowledge_synthesis.go`

### Criteri di accettazione
- miglioramento score qualità su benchmark interno
- riduzione hallucination synthesis

---

## WS-G — Skill Registry e routing knowledge-aware

### Deliverable
- registrazione skill knowledge in default setup (feature-gated)
- routing intents/patterns aggiornato su tassonomia Opzione A

### File target
- `internal/aria/skill/registry.go`
- `internal/aria/routing/*`
- `internal/app/aria_integration.go` (gate `IsConfigured`)

### Criteri di accettazione
- skill knowledge visibili e invocabili tramite registry
- bootstrap agency solo se configurata correttamente

---

## WS-H — Observability, KPI, e log quality

### Deliverable
- KPI/SLO knowledge domain
- metriche per macro-agent e specialist
- event schema unificato (task lifecycle + provider attempts + policy decision)

### KPI minimi
- task success rate
- p50/p95 latency
- citation coverage
- fallback success rate
- memory reuse rate
- security-policy compliance rate

### Nota su evidenza esterna (logger.ts)
I log allegati (`logger.ts`) indicano necessità di normalizzazione metadati comando (es. descrizione/shortcut vuoti) e maggiore coerenza semantica eventi. Se il layer Teams/TS è parte del perimetro prodotto, introdurre backlog dedicato di log schema validation e telemetry contract tests.

---

## 5) Piano temporale (fasi)

## Fase 1 — Stabilizzazione critica (P0) [Settimane 1-2]

- WS-B (secret hygiene + baseline policy)
- WS-A (allineamento tassonomico base)
- WS-G (bootstrap `IsConfigured` + first routing alignment)

**Gate uscita**
- 0 segreti hardcoded
- blueprint/catalog/runtime coerenti su tassonomia Opzione A

## Fase 2 — Robustezza operativa (P1) [Settimane 3-5]

- WS-C (parallelismo reale)
- WS-D (state machine integrata)
- WS-E (memory loop)

**Gate uscita**
- miglioramento latenza fan-out
- tracing task completo
- retrieve/writeback memory verificato

## Fase 3 — Qualità e governance avanzata (P1/P2) [Settimane 6-8]

- WS-F (synthesis 2.0)
- WS-H (KPI + observability completa)
- policy matrix completa per tutti i ruoli

**Gate uscita**
- evidence-first responses e confidence score attivi
- dashboard KPI disponibile

## Fase 4 — Hardening finale e release [Settimana 9]

- test end-to-end
- runbook operativo aggiornato
- release notes + change log blueprint

---

## 6) Strategia di test e verifica

## 6.1 Test tecnici

1. **Unit**
   - routing macro→specialist
   - policy `allow/ask/deny`
   - ranking synthesis
2. **Integration**
   - fallback provider chain
   - memory retrieve/writeback
   - state machine execution lifecycle
3. **Concurrency**
   - parallel fan-out load test
   - race detection
4. **Security**
   - secret scanning CI
   - policy bypass tests

## 6.2 Comandi di verifica (baseline)

```bash
go vet ./...
go test ./internal/aria/agency/... -v
go test ./internal/aria/skill/... -v
go test ./internal/aria/routing/... -v
go build -o /tmp/aria-test ./main.go
```

## 6.3 Quality gates

- nessun secret in repository
- pass test suite knowledge/routing/skill
- KPI baseline raccolti e confrontati pre/post

---

## 7) Aggiornamenti documentali obbligatori

1. **Blueprint update**
   - aggiornare sezione Knowledge Agency con Opzione A
   - includere mapping macro-agent/specialist
2. **Version bump blueprint**
   - `MINOR` (nuova strutturazione organizzativa)
3. **Change log blueprint**
   - cosa/why/impatto
4. **Runbook knowledge**
   - fallback, incident, policy override, rollback

---

## 8) Rischi principali e mitigazioni

| Rischio | Impatto | Mitigazione |
|---|---:|---|
| Regressioni routing durante riallineamento tassonomia | Alto | test golden + feature flag per nuovo router |
| Aumento costi/latency da fan-out | Medio | concurrency cap + budget policy + adaptive routing |
| Persistenza memory rumorosa/non affidabile | Medio | confidence threshold + dedup + provenance strict |
| Incoerenza policy tra agenti | Alto | matrice centralizzata + contract tests |
| Gap tra blueprint e codice nel tempo | Medio | checklist PR obbligatoria con traceability |

---

## 9) Rollout e rollback

## Rollout

- Feature flags per:
  - nuovo router Opzione A,
  - synthesis 2.0,
  - memory writeback strict mode.
- Canary interno su subset task categories.

## Rollback

- fallback a router precedente
- disabilitazione synthesis 2.0 via flag
- disabilitazione memory writeback via flag

---

## 10) RACI sintetico

- **Owner tecnico**: ARIA Core/Agency maintainer
- **Security owner**: governance + secret hygiene
- **QA owner**: integrazione + load + policy compliance
- **Doc owner**: blueprint/runbook/change log

---

## 11) Definition of Done complessiva

Il piano è completato quando:

1. tassonomia Opzione A è allineata in blueprint/catalog/runtime/routing,
2. non esistono segreti hardcoded,
3. parallelismo reale è attivo e misurato,
4. state machine e memory loop sono end-to-end operativi,
5. synthesis 2.0 produce output evidence-first con confidence/conflicts,
6. KPI/SLO knowledge sono monitorati,
7. test/gate tecnici passano e documentazione è aggiornata.
