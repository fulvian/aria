# ARIA Implementation Plan

## Current Status
**FASE 1: COMPLETE ✅**
**FASE 2: Memory & Learning - IN PROGRESS**
**FASE 3: Scheduling - COMPLETE ✅**
**FASE 4: Proactivity & Guardrails - STARTING**

### FASE 1 Completion Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Orchestrator | 100% | ScheduleTask, MonitorTasks, AnalyzeSelf, Learn implemented |
| Agency System | 100% | Registry, Lifecycle (Start/Stop/Pause/Resume) complete |
| Enhanced Agent | 100% | LegacyAgentWrapper with all interface methods |
| Skill System | 100% | Real tool execution (grep, glob, view, write, edit) |
| Routing System | 100% | Baseline complete, complexity analyzer deferred |
| CLI Integration | 100% | Complete |

---

## FASE 2: Memory & Learning

**Durata**: 6-8 settimane  
**Obiettivo**: Implementare sistema di memoria evolutivo

### Overview

FASE 2 implementa il sistema di memoria che permette ad ARIA di:
- Memorizzare il contesto della sessione corrente (working memory)
- Registrare le interazioni passate (episodic memory)
- Memorizzare conoscenze e fatti (semantic memory)
- Imparare workflow riutilizzabili (procedural memory)
- Analizzare le proprie performance e migliorare (self-analysis)

### Current State

| Componente | Stato | Note |
|------------|-------|------|
| Database Schema | ✅ Pronto | Tabelle episodes, facts, procedures esistenti |
| SQL Queries | ✅ Pronte | sqlc-generated, CRUD completo |
| Type Definitions | ✅ Pronti | Solo interfacce, implementazione mancante |
| MemoryService | ❌ Da implementare | Solo interfaccia in memory/memory.go |
| SelfAnalysisService | ❌ Da implementare | Solo interfaccia in analysis/self_analysis.go |
| Learning Loop | ❌ Da implementare | Pattern extraction, procedure generation |
| Vector Storage | ⚠️ Opzionale | sqlite-vec per embeddings (MVP fallback keyword) |

### 2.1 Tasks: Memory Service Implementation

#### 2.1.1 Core Memory Service (CRITICAL)
- [ ] Creare `internal/aria/memory/service.go`
- [ ] Struct `memoryService` con db, workingMemory, embeddings
- [ ] Constructor `NewMemoryService()`

#### 2.1.2 Working Memory (CRITICAL)
- [ ] `GetContext(ctx, sessionID)` - recupera contesto sessione
- [ ] `SetContext(ctx, sessionID, context)` - salva contesto sessione
- [ ] Usare `sync.Map` per storage in-memory

#### 2.1.3 Episodic Memory (CRITICAL)
- [ ] `RecordEpisode(ctx, episode)` - registra interazione
- [ ] `SearchEpisodes(ctx, query)` - cerca con keyword
- [ ] `GetSimilarEpisodes(ctx, situation)` - cerca similarità (embedding o fallback)

#### 2.1.4 Semantic Memory (HIGH)
- [ ] `StoreFact(ctx, fact)` - memorizza fatto
- [ ] `GetFacts(ctx, domain)` - recupera fatti per dominio
- [ ] `QueryKnowledge(ctx, query)` - cerca nella knowledge base

#### 2.1.5 Procedural Memory (HIGH)
- [ ] `SaveProcedure(ctx, procedure)` - salva workflow appreso
- [ ] `GetProcedure(ctx, name)` - recupera workflow
- [ ] `FindApplicableProcedures(ctx, task)` - trova workflow applicabili

### 2.2 Tasks: Learning Loop

#### 2.2.1 Learning from Experience
- [ ] `LearnFromSuccess(ctx, action, outcome)` - registra successo
- [ ] `LearnFromFailure(ctx, action, err)` - registra fallimento
- [ ] Pattern: stesse azioni + esito positivo → aggiorna procedure

#### 2.2.2 Pattern Extraction
- [ ] `ExtractPatterns(episodes)` - trova workflow ricorrenti
- [ ] `DetectRecurringTasks(episodes)` - trova task ripetitivi

#### 2.2.3 Procedure Generation
- [ ] `GenerateProcedure(episode)` - genera nuova procedura
- [ ] Trigger: stesso task type + stesse azioni + 3+ successi consecutivi
- [ ] `ImproveProcedure(procedure, feedback)` - migliora procedura esistente

### 2.3 Tasks: Self-Analysis

#### 2.3.1 Self-Analysis Service
- [ ] Creare `internal/aria/analysis/service.go`
- [ ] `RunPeriodicAnalysis(ctx)` - esegue analisi periodica
- [ ] `AnalyzePerformance(ctx, timeRange)` - analizza performance
- [ ] `AnalyzePatterns(ctx)` - analizza pattern
- [ ] `AnalyzeFailures(ctx)` - analizza fallimenti
- [ ] `GenerateImprovements(ctx)` - genera suggerimenti
- [ ] `ApplyInsights(ctx, insights)` - applica miglioramenti

#### 2.3.2 Metrics Collection
- [ ] Query task table per metriche
- [ ] Calcola: total tasks, success rate, average duration
- [ ] Raggruppa per agency, agent, skill

#### 2.3.3 Periodic Jobs
- [ ] Analisi ogni 24 ore (configurabile)
- [ ] Store insights come facts in semantic memory

### 2.4 Tasks: Vector Storage (Optional MVP)

#### 2.4.1 Embedder Interface
- [ ] `Embed(ctx, text)` - genera embedding vector
- [ ] `SearchSimilar(ctx, collection, query, limit)` - cerca similarità

#### 2.4.2 SQLite-Vec Integration
- [ ] `SQLiteVecEmbedder` implementation
- [ ] Virtual table per embeddings
- [ ] Fallback: keyword similarity search

---

## FASE 2 Deliverables

- [ ] MemoryService completo (working, episodic, semantic, procedural)
- [ ] Learning loop base (experience recording, pattern extraction, procedure generation)
- [ ] SelfAnalysisService con analisi performance, pattern, failures
- [ ] Self-analysis reports
- [ ] Unit tests

---

## Technical Notes

### Dependencies
- `internal/db.Queries` (sqlc-generated)
- `internal/aria/agency.AgencyName`
- `internal/aria/skill.SkillName`

### Risks
1. **Performance**: Query senza indici proper potrebbero essere lente
   - Mitigation: Usare indici esistenti nella episodes table
2. **Vector storage**: sqlite-vec richiede setup aggiuntivo
   - Mitigation: Keyword fallback per MVP
3. **Learning quality**: Procedure auto-generate potrebbero non essere utili
   - Mitigation: Richiedere 3+ successi, human review flag

---

## Verification Plan

1. `go build -o /tmp/aria-test ./main.go` - Must pass
2. `go test ./internal/aria/memory/...` - Memory service tests
3. `go test ./internal/aria/analysis/...` - Self-analysis tests
4. Manual test: Usare ARIA e verificare che contesto venga memorizzato

---

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | LegacyAgentWrapper pattern | Mantiene retrocompatibilità con agent esistente |
| 2026-03-28 | FASE 1 COMPLETE | Tutti i componenti core implementati con tool reali |
| 2026-03-28 | FASE 2 Planning | Memory Service, Learning Loop, Self-Analysis |

---

## Next Phase (After FASE 2)
**FASE 3: Scheduling** - Task scheduler con task persistenti, scheduling cron-like, dipendenze

---

## FASE 3: Scheduling (Implementation Started: 2026-03-28)

**Durata**: 14-21 giorni lavorativi
**Obiettivo**: Sistema di scheduling persistente, robusto e recuperabile

### Overview

FASE 3 implementa il sistema di scheduling che permette ad ARIA di:
- Gestire task persistenti che sopravvivono a restart
- Supportare scheduling con priorità e dipendenze
- Eseguire task ricorrenti (cron, interval, one-time)
- Monitorare progress e history in tempo reale
- UI per gestione task (list/detail/actions)

### Riferimenti
- Piano dettagliato: `docs/plans/2026-03-28-fase3-scheduling-implementation-plan.md`
- Blueprint: Parte IV (4.1, 4.2, 4.3), Parte II (2.2.1), Parte IX (9.1, 9.2, 9.3)

### 3.1 Tasks: Core Scheduler Persistente

- [x] Creare `internal/aria/scheduler/service.go` - Implementazione concreta Scheduler interface
- [x] Creare `internal/aria/scheduler/mapper.go` - Conversioni db/task JSON-safe
- [x] Implementare `Schedule()` con validazioni e persistenza
- [x] Implementare `GetTask/ListTasks/GetProgress`
- [x] Implementare `Subscribe()` per eventi real-time
- [x] Unit tests per core scheduler

### 3.2 Tasks: Dispatcher, Priorità e Dipendenze

- [x] Creare `internal/aria/scheduler/dispatcher.go`
- [x] Ciclo dispatcher periodico (500ms-2s configurabile)
- [x] Dependency resolution (tutte le dipendenze completed)
- [x] Priority ordering (priority DESC, created_at ASC)
- [x] Promozione a queued + evento
- [x] Gestione backpressure (maxConcurrentTasks)

### 3.3 Tasks: Worker Execution e Lifecycle

- [x] Creare `internal/aria/scheduler/worker.go`
- [x] Worker pool concorrente
- [x] Transizioni di stato complete (created→queued→running→completed/failed)
- [x] Implementare Cancel/Pause/Resume
- [x] UpdateTaskProgress e GetProgress

### 3.4 Tasks: Recurring Scheduling

- [x] Creare `internal/aria/scheduler/recurring.go`
- [x] Parser cron/interval/specific_times
- [x] Recurring planner loop
- [x] Idempotency key per evitare duplicazioni
- [x] UpdateSchedule implementation

### 3.5 Tasks: Recovery & Resilienza

- [x] Creare `internal/aria/scheduler/recovery.go`
- [x] Startup reconciliation (running→queued/failed)
- [x] Ripristino recurring planner state
- [x] Test crash/restart scenarios

### 3.6 Tasks: Integrazione Orchestrator + App

- [x] Aggiornare `internal/app/aria_integration.go` - wiring scheduler
- [x] Refactor `ScheduleTask/MonitorTasks` in orchestrator_impl.go
- [x] Mantenere fallback behavior

### 3.7 Tasks: TUI Task Management

- [x] Creare `internal/tui/page/tasks.go`
- [x] Lista task con filtro status/agency
- [x] Dettaglio task (result/error/event history)
- [x] Azioni: cancel/pause/resume
- [x] Refresh real-time o polling breve

### FASE 3 Deliverables

- [x] Scheduler service concreto usato in runtime
- [x] Task persistenti che sopravvivono a restart
- [x] Dependency + priority funzionanti con test
- [x] Recurring scheduling operativo
- [x] Orchestrator usa scheduler persistente (no queue in-memory)
- [x] TUI task management disponibile
- [x] Test suite scheduler/integration green
- [x] BLUEPRINT aggiornato

### Technical Notes

#### Dependencies
- `internal/db.Querier` (sqlc-generated)
- `internal/aria/scheduler.Scheduler` (interface esistente)
- `internal/aria/core.Orchestrator` (da integrare)
- `internal/config.SchedulerConfig` (da estendere)

#### Key Files to Create
- `internal/aria/scheduler/service.go`
- `internal/aria/scheduler/dispatcher.go`
- `internal/aria/scheduler/worker.go`
- `internal/aria/scheduler/recurring.go`
- `internal/aria/scheduler/recovery.go`
- `internal/aria/scheduler/mapper.go`
- `internal/tui/page/tasks.go`

#### Key Files to Modify
- `internal/aria/core/orchestrator_impl.go`
- `internal/app/aria_integration.go`
- `internal/config/config.go`

### Verification Plan

1. `go build -o /tmp/aria-test ./main.go` - Must pass
2. `go test ./internal/aria/scheduler/...` - Scheduler tests
3. `go test ./internal/aria/...` - All ARIA tests
4. `go vet ./...` - Must pass
5. Manual test: Task scheduling survives restart

---

## FASE 4: Proactivity & Guardrails (Implementation Started: 2026-03-28)

**Durata**: 4-6 settimane
**Obiettivo**: Comportamento proattivo controllato con guardrail

### Overview

FASE 4 implementa il sistema di guardrail e proattività che permette ad ARIA di:
- Controllare azioni proattive con permission levels
- Rate limiting per evitare abusi
- Audit logging per tracciabilità
- User preferences (quiet hours, auto-approval)
- Notification system per TUI

### Riferimenti
- Blueprint: Parte V (5.1, 5.2, 5.3)

### 4.1 Tasks: GuardrailService Implementation

- [x] Creare `internal/aria/guardrail/service.go` - Implementazione concreta GuardrailService
- [x] Implementare `CanExecute()` con check su preferenze e budget
- [x] Implementare `GetActionBudget()` con rate limiting
- [x] Implementare `ConsumeAction()` per aggiornare budget
- [x] Implementare `GetUserPreferences()` con defaults
- [x] Implementare `UpdatePreferences()`
- [x] Implementare `LogAction()` per audit
- [x] Implementare `GetAuditLog()`
- [x] Unit tests

### 4.2 Tasks: ExtendedPermissionService

- [x] Verificare `internal/permission/` package esistente
- [x] Implementare ExtendedPermissionService o integrare con esistente
- [x] Implementare `Request()`, `Grant()`, `Deny()`
- [x] Implementare `Check()` per verify permissions
- [x] Implementare rules management

### 4.3 Tasks: User Preferences

- [x] Default preferences struttura
- [x] Persistenza preferences su DB (in-memory per MVP)
- [x] Validazione preferences

### 4.4 Tasks: Budget & Rate Limiting

- [x] Budget tracking in-memory
- [x] Reset automatico alla fine della finestra
- [x] Consuntivo azioni

### 4.5 Tasks: Audit Logging

- [x] Audit entries in-memory
- [x] Query con filtri
- [x] Retention policy (max entries)

### 4.6 Tasks: App Integration

- [x] Wire guardrail service in aria_integration.go
- [x] Shutdown graceful

### FASE 4 Deliverables

- [x] GuardrailService concreto implementato
- [x] Budget/rate limiting funzionante
- [x] Audit logging completo
- [x] User preferences persistente (in-memory)
- [x] Test suite green

### Technical Notes

#### Dependencies
- `internal/aria/guardrail.GuardrailService` (interface esistente)
- `internal/aria/permission.ExtendedPermissionService` (interface esistente)
- `internal/config.GuardrailsConfig` (esistente)

#### Key Files to Create
- `internal/aria/guardrail/service.go`
- `internal/aria/guardrail/budget.go`
- `internal/aria/guardrail/preferences.go`

#### Key Files to Modify
- `internal/app/aria_integration.go`

### Verification Plan

1. `go build -o /tmp/aria-test ./main.go` - Must pass
2. `go test ./internal/aria/guardrail/...` - Guardrail tests
3. `go vet ./...` - Must pass