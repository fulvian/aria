# ARIA Production-Ready Implementation Plan

**Data**: 2026-03-30  
**Stato**: Proposed  
**Input baseline**: `docs/analysis/2026-03-30-architettura-implementazione-report.md` + `docs/foundation/BLUEPRINT.md` (v1.14.0-DRAFT)

---

## 1. Obiettivo

Portare ARIA a livello **production-ready** con:

1. Architettura orchestrator completa (no skeleton/placeholder nel percorso critico).
2. Qualità operativa enterprise (affidabilità, osservabilità, sicurezza, rollback).
3. Coverage funzionale completa sulle capability blueprint (incluse agencies, agents, tools governance).
4. Rilascio controllato con KPI/SLO e gate di qualità misurabili.

---

## 2. Definition of Done (Production-Ready)

ARIA è considerato production-ready quando tutte le condizioni seguenti sono vere:

- ✅ `go build ./...`, `go vet ./...`, `go test ./...` verdi in CI su branch release.
- ✅ Pipeline orchestrator Fast/Deep pienamente reale (no output simulati, no skeleton path).
- ✅ Lifecycle robusto per tutti i servizi long-running (start/stop idempotente, no leak).
- ✅ Guardrail/permission/audit persistiti e recuperabili su riavvio.
- ✅ Routing policy + capability matching in esercizio con metriche di accuratezza.
- ✅ Agencies core previste dal blueprint implementate e testate end-to-end.
- ✅ Tool governance (Native > Direct API > MCP) applicata con policy costo/rischio.
- ✅ Observability completa: logs strutturati, metriche, eventi, alerting.
- ✅ Security baseline: gestione segreti, least privilege, audit trail, data retention.
- ✅ Runbook operativi, rollback plan, release checklist, documentazione utente/admin.

---

## 3. KPI/SLO target

## 3.1 KPI di prodotto
- RoutingAccuracy ≥ **85%**
- ResponseSuccessRate ≥ **95%**
- ReplanRate ≤ **12%**
- FallbackRate ≤ **10%**
- ToolMisuseRate ≤ **5%**

## 3.2 SLO operativi
- Availability orchestrator runtime: **99.5%**
- p95 Fast Path latency: **≤ 2.5s**
- p95 Deep Path latency: **≤ 12s**
- MTTR incidenti P1: **< 60 min**
- Crash-free sessions: **≥ 99.9%**

---

## 4. Piano di implementazione (workstreams)

## WS-A — Core Orchestrator Completion (P0)
**Priorità**: Critica

### Scope
- Completare `internal/aria/core/pipeline/orchestrator_pipeline.go` eliminando skeleton flow.
- Integrare realmente DecisionEngine → Planner → Executor → Reviewer nel percorso primario.
- Rimuovere risposte placeholder e usare output verificato.

### Deliverable
- Pipeline A→F eseguibile in runtime.
- Test integrati fast/deep/replan/fallback.

### Acceptance
- Nessun TODO/placeholder nei path core orchestrator.
- 1 test E2E architetturale completo con deep path e review gate.

---

## WS-B — Executor/Reviewer Hardening (P0)
**Priorità**: Critica

### Scope
- Sostituire esecuzione simulata in `core/plan/executor.go` con adapter runtime reali.
- Rafforzare reviewer: criterio rischio con evidenze reali (non placeholder).
- Standardizzare handoff record e failure taxonomy.

### Deliverable
- Executor reale con contract test.
- Reviewer con scoring robusto e motivazioni deterministiche.

### Acceptance
- `simulated=true` eliminato dai risultati operativi.
- Coverage unit/integration di planner-executor-reviewer ≥ 80%.

---

## WS-C — Service Lifecycle & Concurrency Safety (P0)
**Priorità**: Critica

### Scope
- Memory GC: introdurre `Close()/Shutdown()` e stop controllato.
- Analysis service: stop idempotente (`sync.Once`).
- Audit race scan su path concorrenti (state, broker, memory slices).

### Deliverable
- Lifecycle uniforme su tutti i servizi long-running.
- No leak/no panic su stop multipli.

### Acceptance
- `go test -race ./...` verde.
- Test di shutdown ripetuto e restart verdi.

---

## WS-D — Persistence & Governance Durability (P1)
**Priorità**: Alta

### Scope
- Persistenza rules/requests/responses per permission service.
- Persistenza budget/preferences/audit per guardrail service.
- Migrazioni DB + query sqlc + recovery startup.

### Deliverable
- Stato governance persistente cross-restart.
- Audit completo tracciabile.

### Acceptance
- Reboot test: stato ricostruito senza perdita.
- Query audit/filter con latenza accettabile.

---

## WS-E — Routing 2.0 Operationalization (P1)
**Priorità**: Alta

### Scope
- PolicyRouter in produzione (threshold, priority rules, policy override).
- CapabilityRegistry popolato dinamicamente (health + cost + risk).
- Feedback loop su decisioni per auto-tuning soglie.

### Deliverable
- Routing policy-driven e misurabile.
- Dashboard KPI routing.

### Acceptance
- RoutingAccuracy ≥ 85% in ambiente staging.
- Regression test su routing policy.

---

## WS-F — Agencies/Agents Rollout Completo (P1/P2)
**Priorità**: Alta

### Scope
- Implementare agencies blueprint mancanti:
  - Knowledge
  - Creative
  - Productivity
  - Personal
  - Analytics
- Formalizzare catalogo agenti per ogni agency con capability contracts.
- Test cross-agency handoff.

### Deliverable
- 5+ agencies operative e registrate.
- Matrice capability completa.

### Acceptance
- Scenario E2E per ciascuna agency.
- Cross-domain workflow multi-agency verde.

---

## WS-G — Tool Governance & Cost Control (P1/P2)
**Priorità**: Alta

### Scope
- Implementare tool governance layer:
  - Native-first
  - Direct API second
  - MCP last resort
- Cost model token/time/risk.
- Policy di deny/require-approval per tool ad alto impatto.

### Deliverable
- Decisione tool deterministicamente tracciata.
- Budget enforcement con fallback.

### Acceptance
- ToolMisuseRate ≤ 5% su staging.
- Log di scelta tool con motivazione policy.

---

## WS-H — Observability, Ops & Incident Readiness (P1)
**Priorità**: Alta

### Scope
- Standardizzare logging strutturato (no `fmt.Printf` operativo).
- Metriche Prometheus-style (o equivalente) + alerting.
- Tracing su pipeline query (query_id/plan_id/task_id).
- Runbook incident (P1/P2), health checks e diagnostics commands.

### Deliverable
- Stack osservabilità completa.
- Playbook incident response.

### Acceptance
- Drill di incidente con MTTR < 60 min.
- Alert validati (noisy rate sotto soglia).

---

## WS-I — Security, Privacy, Compliance Baseline (P1)
**Priorità**: Alta

### Scope
- Secret management (mai in repo; env/secure store).
- Least-privilege per azioni critiche.
- Data retention policy applicata e verificabile.
- Hardening input validation / injection-safe paths.

### Deliverable
- Security baseline documentata e testata.
- Audit e retention enforcement automatizzati.

### Acceptance
- Security checklist 100% compliant.
- Nessun secret leak nei controlli CI.

---

## WS-J — Release Engineering & Rollout (P2)
**Priorità**: Media-Alta

### Scope
- Branch protection + quality gates obbligatori.
- Release train: dev → staging → canary → prod.
- Feature flags per deep-path, agencies, policy router.
- Rollback automatizzabile.

### Deliverable
- Pipeline CI/CD robusta con gate multi-step.
- Procedura rollback validata.

### Acceptance
- Canary 24h senza regressioni P1.
- Rollback testato con successo.

---

## 5. Sequenza esecutiva consigliata

1. **P0 (immediato)**: WS-A, WS-B, WS-C  
2. **P1 (stabilizzazione)**: WS-D, WS-E, WS-H, WS-I  
3. **P1/P2 (capability complete)**: WS-F, WS-G  
4. **P2 (go-live readiness)**: WS-J  

Dipendenze principali:
- WS-A/WS-B prima di tuning KPI reale.
- WS-C prima di carichi lunghi/stress test.
- WS-D prima di validare governance production-grade.
- WS-F/WS-G necessari per claim “full ARIA capabilities”.

---

## 6. Piano test & quality gates

## 6.1 Test strategy
- Unit tests: ogni package critico (core/routing/memory/scheduler/guardrail/permission/analysis).
- Integration tests: orchestrator pipeline + DB persistence + policy router.
- E2E tests:
  - Fast path low-risk
  - Deep path high-complexity con replan
  - Multi-agency workflow
  - Governance deny/approve path
- Non-functional:
  - load test
  - race test
  - soak test (long-running)

## 6.2 Gate minimi di merge
- Build/vet/test verdi.
- Coverage globale area `internal/aria` ≥ 75% (target 80%).
- No TODO/placeholder nei package core production path.
- Lint statici sicurezza/config passing.

---

## 7. Milestones e stima

## Milestone M1 — Core closure (2-3 settimane)
- WS-A/B/C completati.

## Milestone M2 — Governance + routing ops (2 settimane)
- WS-D/E/H/I completati in staging.

## Milestone M3 — Capability complete (3-5 settimane)
- WS-F/G completati e test cross-domain.

## Milestone M4 — Production rollout (1-2 settimane)
- WS-J + canary + go-live.

**Stima totale**: ~8-12 settimane (in base a dimensione team e parallelizzazione).

---

## 8. Rischi principali e mitigazioni

1. **Complessità integrazione orchestrator**  
   Mitigazione: feature flags + rollout incrementale per Fast/Deep path.

2. **Regressioni su routing/policy**  
   Mitigazione: suite regression su decision matrix + canary monitorato.

3. **Leak concorrenti/lifecycle**  
   Mitigazione: test `-race`, soak test, shutdown contract tests.

4. **Cost overrun tool/MCP**  
   Mitigazione: tool governance + budget policy + telemetry token usage.

5. **Adozione incompleta agencies**  
   Mitigazione: onboarding progressivo, contratti capability obbligatori.

---

## 9. Deliverable finali obbligatori

- Documento architettura aggiornata (BLUEPRINT + delta release).
- Matrice capabilities agencies/agents/skills/tools aggiornata.
- Runbook operativi (incident, rollout, rollback, DR).
- Dashboard KPI/SLO in produzione.
- Report di certificazione production-readiness (evidenze test + SLO + security).

---

## 10. Criterio di go-live

Go-live autorizzato solo se:
- tutti i P0/P1 sono completati,
- KPI/SLO baseline rispettati per almeno 7 giorni in staging/canary,
- nessun blocker P1/P0 aperto,
- report di readiness firmato (engineering + QA + operations).
