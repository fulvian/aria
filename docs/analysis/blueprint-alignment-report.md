# ARIA Codebase vs BLUEPRINT Alignment Report

**Generated**: 2026-03-29 20:15:00 +02:00  
**Analyzer**: ChatGPT Codex 5.3  
**Blueprint Version**: 1.10.0-DRAFT  
**Repository**: `/home/fulvio/coding/aria`  
**Scope**: `internal/aria/*`, DB migrations/queries, build/vet/test verification

---

## Executive Summary

This report analyzes the ARIA implementation against `docs/foundation/BLUEPRINT.md` (v1.10.0-DRAFT), with explicit verification of phase deliverables, interface compliance, database schema, and implementation quality.

### Overall Alignment Snapshot

- **FASE 0 (Foundation)**: **92%** aligned
- **FASE 1 (Core System)**: **81%** aligned
- **FASE 2 (Memory & Learning)**: **86%** aligned
- **FASE 3 (Scheduling)**: **88%** aligned
- **FASE 4 (Proactivity)**: **84%** aligned
- **FASE 5 (Agencies)**: **15%** aligned (consistent with “early progress” expectation)

### Key Conclusions

1. **Core architecture exists and compiles**, including orchestrator, agency registry/service, skill implementations, memory/scheduler/guardrail/permission services.
2. **Important interface drift exists** from BLUEPRINT signatures (notably Orchestrator, Agency, Agent, MemoryService, GuardrailService).
3. **Database baseline is largely aligned** with expected ARIA tables and SQL accessors.
4. **Functional quality gaps remain** in concurrency safety, API contract strictness, test coverage in core packages, and no-op behaviors.
5. **One concrete failing test in repository-wide suite** indicates regression risk outside `internal/aria` package boundaries.

### Critical Risk Summary

- **High risk**: Interface contract drift can block future phase integrations and multi-agency orchestration.
- **High risk**: Event broker implementation is not true pub/sub broadcast (subscriber competition).
- **Medium risk**: Scheduler `UpdateSchedule` validates input but does not persist schedule updates.
- **Medium risk**: Long-lived goroutine lifecycle management is incomplete in memory GC and event brokers.
- **Medium risk**: Missing tests in several critical ARIA packages increases regression probability.

---

## Analysis Methodology

1. Loaded blueprint and handoff documents:
   - `docs/foundation/BLUEPRINT.md`
   - `docs/analysis/00-handoff-prompt.md`
2. Enumerated files under `internal/aria/`.
3. Inspected interface and implementation files for:
   - Signature compliance
   - Behavioral completeness
   - Error handling and concurrency patterns
4. Verified DB schema and sqlc query files:
   - `internal/db/migrations/*.sql`
   - `internal/db/sql/*.sql`
5. Executed repository verification commands:
   - `go build ./...` ✅
   - `go vet ./...` ✅
   - `go test ./...` ❌ (one failing package)

---

## Phase-by-Phase Analysis

### FASE 0: Foundation

**Status**: **92% Complete**

**Expected (Blueprint)**:
- Directory structure under `internal/aria/`
- Base interfaces defined
- DB schema extension
- Baseline test scaffolding

**Findings**:
- ✅ `internal/aria/` contains expected core domains:
  - `core/`, `agency/`, `agent/`, `skill/`, `routing/`, `memory/`, `scheduler/`, `permission/`, `guardrail/`, `analysis/`, plus `config/`.
- ✅ DB baseline migration created (`20260328120000_aria_baseline.sql`) with expected ARIA entities.
- ✅ Working-memory persistence migration exists (`20260328130000_working_memory_contexts.sql`).
- ⚠️ Several interfaces are present but **signature-divergent** from blueprint.
- ❌ Test scaffolding is incomplete for multiple core packages (`core`, `routing`, `agency`, `agent`, `skill` have no tests).

**Assessment**:
- Foundation is structurally in place; contractual and test completeness is the main shortfall.

---

### FASE 1: Core System

**Status**: **81% Complete**

**Expected (Blueprint)**:
- Full Orchestrator interface and implementation
- Agency system and registry
- Development Agency
- Enhanced Agent with Legacy wrapper
- Skill system (CodeReview, TDD, Debugging)
- Routing baseline

**Findings**:
- ✅ Orchestrator implementation exists:
  - `internal/aria/core/orchestrator.go`
  - `internal/aria/core/orchestrator_impl.go`
- ⚠️ Orchestrator interface drift:
  - `RouteToAgent` returns `string` instead of `Agent`.
- ✅ Agency registry exists with default implementation:
  - `internal/aria/agency/registry.go`
- ✅ Development Agency exists:
  - `internal/aria/agency/development.go`
- ⚠️ Agency interface drift:
  - `Agents() []string` vs `[]Agent`
  - `GetAgent(name string) (any, error)` vs typed contract
- ✅ Legacy wrapper exists:
  - `internal/aria/agent/legacy_wrapper.go`
- ⚠️ Agent interface renamed to `EnhancedAgent` and drifted from blueprint.
- ✅ Skill interface and registry exist.
- ✅ CodeReview/TDD/Debugging skills have concrete implementations.
- ✅ Routing classifier/router baseline exists.
- ⚠️ `core.Classifier()` helper returns `nil` TODO (`orchestrator.go` line ~109-112).

**Assessment**:
- Functional baseline exists and works for MVP, but interface-level drift is significant technical debt.

---

### FASE 2: Memory & Learning

**Status**: **86% Complete**

**Expected (Blueprint)**:
- Memory service with working/episodic/semantic/procedural memory
- Working memory TTL + GC
- Episodic retrieval filters
- Semantic governance
- Procedural scoring/discovery
- Self-analysis service

**Findings**:
- ✅ `internal/aria/memory/service.go` provides broad memory operations.
- ✅ Working memory persistence and TTL support implemented (`working_memory_contexts`).
- ✅ Episodic/semantic/procedural operations implemented with sqlc-backed queries.
- ✅ Discovery/scoring logic for procedures exists.
- ✅ Self-analysis service exists (`internal/aria/analysis/service.go`).
- ⚠️ Signature drift:
  - `FindApplicableProcedures(ctx, task map[string]any)` instead of `task Task`.
  - `GenerateInsights(ctx) ([]string, error)` vs blueprint’s structured insights model.
- ⚠️ GC loop (`runGC`) has no service shutdown path and can leak goroutine.
- ⚠️ Concurrency/data assumptions in similarity ranking and internal maps require hardening.

**Assessment**:
- Memory-learning system is materially present, but lifecycle management and strict contract fidelity need work.

---

### FASE 3: Scheduling

**Status**: **88% Complete**

**Expected (Blueprint)**:
- Scheduler service and queue
- Persistence
- Recurring tasks (cron/interval)
- Monitoring/events

**Findings**:
- ✅ Scheduler interface and concrete service exist:
  - `internal/aria/scheduler/scheduler.go`
  - `internal/aria/scheduler/service.go`
- ✅ Task DB persistence and task event logging implemented.
- ✅ Recurring scheduling entrypoints implemented (`ScheduleRecurring`, recurring helpers in package).
- ✅ Subscribe/event integration present.
- ⚠️ `UpdateSchedule` validates but does **not persist update** (explicit TODO/no-op behavior).
- ⚠️ Error-return semantics from `RemoveRule`-style methods in ecosystem may hide failures.

**Assessment**:
- Strong implementation base with one important functional gap in schedule update persistence.

---

### FASE 4: Proactivity

**Status**: **84% Complete**

**Expected (Blueprint)**:
- Guardrail service
- Extended permission service
- Budget tracking
- Auto-approve rules
- QuietHours/ActiveHours

**Findings**:
- ✅ Guardrail service implemented:
  - `internal/aria/guardrail/service.go`
- ✅ Permission service implemented:
  - `internal/aria/permission/service.go`
- ✅ Budget tracking, action checks, quiet/active hours validation present.
- ✅ Auto-approve rules supported for low-impact actions.
- ⚠️ Guardrail interface drift:
  - `LogAction(... outcome string)` vs blueprint conceptual `Outcome` type.
- ⚠️ Permission rule scoping uses `CreatedBy` as agency key fallback (`global`), which is semantically weak.
- ⚠️ No persistence layer for permissions/guardrail audit (in-memory only) in current design.

**Assessment**:
- Operationally useful, but long-term reliability and governance require persistence and stronger typing.

---

### FASE 5: Agencies

**Status**: **15% Complete**

**Expected (Blueprint)**:
- Agency persistence service
- Weather Agency POC
- Other specialized agencies not started

**Findings**:
- ✅ `AgencyService` persistence layer exists with CRUD + state persistence.
- ✅ Weather Agency POC implemented:
  - `internal/aria/agency/weather.go`
  - weather skills files exist.
- ⚠️ Remaining agencies (Knowledge, Creative, Productivity, Personal, Analytics) are not implemented.
- ⚠️ Agency event broker implementation in development/weather pathways is not robust pub/sub broadcast.

**Assessment**:
- Current progress is directionally consistent with blueprint narrative (early FASE 5).

---

### FASE 6: Polish & Expand

**Status**: **0% (not expected yet)**

**Findings**:
- No inconsistency with blueprint expectations.

---

## Interface Compliance Matrix

| Interface | File | Status | Notes |
|-----------|------|--------|-------|
| Orchestrator | `internal/aria/core/orchestrator.go` + `orchestrator_impl.go` | ⚠️ Partial | `RouteToAgent` type mismatch (`string` vs `Agent`) |
| Agency | `internal/aria/agency/agency.go` | ⚠️ Partial | Agent typing drift (`[]string`, `any`) |
| Agent | `internal/aria/agent/agent.go` | ❌ Drifted | Interface name/signatures diverge; no canonical `Agent` with blueprint task types |
| Skill | `internal/aria/skill/skill.go` | ✅ Mostly | Matches blueprint intent and methods |
| MemoryService | `internal/aria/memory/memory.go` | ⚠️ Partial | Signature/model drifts (`task map[string]any`, insights typing) |
| Scheduler | `internal/aria/scheduler/scheduler.go` | ✅ Mostly | Core methods align well |
| GuardrailService | `internal/aria/guardrail/guardrail.go` | ⚠️ Partial | `LogAction` outcome typed as string; model drift |
| SelfAnalysisService | `internal/aria/analysis/self_analysis.go` | ✅ Mostly | Method set aligns with blueprint intent |

---

## Gap Analysis

### Critical Gaps

1. **[GAP-001] Interface Contract Drift Across Core Entities**
   - **Impact**: High
   - **Location**: `internal/aria/core/`, `agency/`, `agent/`, `memory/`, `guardrail/`
   - **Fix**:
     1. Introduce blueprint-aligned canonical domain types (`Task`, `Agent`, `Outcome`, `Insight`) in shared package.
     2. Refactor interfaces to exact blueprint signatures.
     3. Add adapters where legacy compatibility is required.
     4. Add compile-time interface assertions.

2. **[GAP-002] Missing Tests in Several Critical Packages**
   - **Impact**: High
   - **Location**: `internal/aria/core`, `internal/aria/routing`, `internal/aria/agency`, `internal/aria/agent`, `internal/aria/skill`
   - **Fix**:
     1. Add unit tests for interface behavior and edge cases.
     2. Add race-oriented tests for event paths and agency lifecycle.
     3. Add contract tests against blueprint method expectations.

3. **[GAP-003] Event Distribution Semantics Are Not True Pub/Sub Broadcast**
   - **Impact**: High
   - **Location**: `internal/aria/agency/development.go` (`AgencyEventBroker`)
   - **Fix**:
     1. Replace custom channel broker with `pubsub.Broker[AgencyEvent]`.
     2. Ensure each subscriber receives all events.
     3. Add tests with multiple subscribers asserting identical event streams.

4. **[GAP-004] Scheduler Schedule Update Not Persisted**
   - **Impact**: High
   - **Location**: `internal/aria/scheduler/service.go` lines ~505-535
   - **Fix**:
     1. Add SQL query `UpdateTaskScheduleExpr`.
     2. Serialize and persist updated schedule.
     3. Emit `schedule_updated` event.
     4. Add roundtrip test (`UpdateSchedule` then `GetTask`).

### Minor Gaps

1. **[GAP-101] Orchestrator Helper `Classifier()` Returns Nil TODO**
   - **Impact**: Medium
   - **Location**: `internal/aria/core/orchestrator.go` lines ~109-112
   - **Fix**: Expose classifier from implementation or remove helper.

2. **[GAP-102] In-memory Permission/Guardrail State Not Persisted**
   - **Impact**: Medium
   - **Location**: `internal/aria/permission/service.go`, `guardrail/service.go`
   - **Fix**: Add persistence tables and load/save cycle on startup/shutdown.

3. **[GAP-103] Logging via `fmt.Printf` in service paths**
   - **Impact**: Medium
   - **Location**: multiple files (`orchestrator_impl.go`, `registry.go`, `agency/service.go`)
   - **Fix**: replace with structured logging package.

4. **[GAP-104] Weather location extraction placeholder always empty**
   - **Impact**: Low
   - **Location**: `internal/aria/agency/weather.go` line ~339-343
   - **Fix**: implement regex/NLP extraction fallback.

5. **[GAP-105] Shared mutable state without lock in agency memory path**
   - **Impact**: Medium
   - **Location**: `internal/aria/agency/development.go` (`AgencyMemory.experiences`)
   - **Fix**: protect with `sync.RWMutex`.

---

## Critical Issues

### CRIT-001: Orchestrator Interface Mismatch (`RouteToAgent`)

**Severity**: High  
**Location**: `internal/aria/core/orchestrator.go:90`  
**Description**: Blueprint requires `RouteToAgent(ctx, query Query) (Agent, error)`, but implementation exposes `(string, error)`.

**Reproduction**:
1. Open `internal/aria/core/orchestrator.go`.
2. Compare signature to BLUEPRINT section 2.2.1.
3. Confirm return type mismatch.

**Fix**:
1. Define/alias canonical `Agent` type in ARIA domain package.
2. Change interface and implementation to return typed agent.
3. Update call sites and adapters.
4. Add compile-time assertion.

---

### CRIT-002: Agency Interface Uses Untyped Agent Access (`any`)

**Severity**: High  
**Location**: `internal/aria/agency/agency.go:120-121`  
**Description**: `Agents() []string` and `GetAgent(name string) (any, error)` break type-safety and drift from blueprint `[]Agent` / typed lookup.

**Reproduction**:
1. Open `agency.go`.
2. Inspect `Agency` interface agent methods.
3. Compare with BLUEPRINT section 2.2.2.

**Fix**:
1. Import/use `agent.Agent` interface in agency package (or shared contract package to avoid cycles).
2. Replace string/any methods with typed versions.
3. Add adapters for legacy bridge.

---

### CRIT-003: Event Broker Is Not Broadcast-safe for Multiple Subscribers

**Severity**: High  
**Location**: `internal/aria/agency/development.go:286-322`  
**Description**: Custom `AgencyEventBroker` uses one underlying channel; subscribers consume from same stream competitively instead of each getting all events.

**Reproduction**:
1. Create two subscribers via `Subscribe(ctx)`.
2. Publish one event.
3. Observe only one subscriber receives event (or order-dependent behavior).

**Fix**:
1. Replace with `pubsub.Broker[AgencyEvent]`.
2. Publish typed events through broker.
3. Validate with multi-subscriber test.

---

### CRIT-004: Scheduler `UpdateSchedule` Does Not Persist Update

**Severity**: High  
**Location**: `internal/aria/scheduler/service.go:505-535`  
**Description**: Method validates schedule but only logs; no database update occurs.

**Reproduction**:
1. Create recurring task.
2. Call `UpdateSchedule` with new expression.
3. Fetch task; schedule expression unchanged.

**Fix**:
1. Add SQL update query for `schedule_expr`.
2. Persist serialized schedule.
3. Emit update event.

---

### CRIT-005: Agent Interface Drift (`EnhancedAgent` vs Blueprint `Agent`)

**Severity**: High  
**Location**: `internal/aria/agent/agent.go:79-100`  
**Description**: Interface naming and method signatures diverge materially (task and result typing, missing canonical `Cancel` in interface contract).

**Reproduction**:
1. Compare `internal/aria/agent/agent.go` to blueprint section 2.2.3.
2. Observe differences in type system and method list.

**Fix**:
1. Reintroduce canonical `Agent` interface matching blueprint.
2. Keep `EnhancedAgent` as compatibility alias or adapter layer only.
3. Update wrappers to satisfy canonical interface.

---

### CRIT-006: Memory Service API Drift in Procedure Matching and Insights

**Severity**: Medium  
**Location**: `internal/aria/memory/memory.go:152,160`  
**Description**: `FindApplicableProcedures` accepts untyped map task; `GenerateInsights` returns `[]string` not structured `[]Insight`.

**Reproduction**:
1. Inspect interface definitions in file.
2. Compare to blueprint section 3.2.

**Fix**:
1. Use typed task and insight models.
2. Add conversion/adaptation where needed.

---

### CRIT-007: Long-lived GC Goroutine Has No Stop Path

**Severity**: Medium  
**Location**: `internal/aria/memory/service.go:132-147`  
**Description**: `runGC` loops forever on ticker without cancellation channel/context tied to service lifecycle.

**Reproduction**:
1. Instantiate memory service in tests repeatedly.
2. Observe goroutines accumulate over process lifetime.

**Fix**:
1. Add `ctx/cancel` to memory service.
2. Stop GC loop on service shutdown.
3. Add `Close()` method and tests.

---

### CRIT-008: Unstructured Error Output in Core Paths

**Severity**: Medium  
**Location**:
- `internal/aria/core/orchestrator_impl.go:214`
- `internal/aria/agency/registry.go:162,176,203`
- `internal/aria/agency/service.go:332`

**Description**: direct `fmt.Printf` used in service paths; bypasses structured logging and observability policy.

**Reproduction**:
1. Trigger persistence/loggable error.
2. Observe stdout text instead of structured log records.

**Fix**:
1. Replace with `logging.Error`/`logging.Warn`.
2. Include stable keys for correlation (`agency`, `task_id`, `err`).

---

## Bug Report

### BUG-001: Repository Test Failure in `internal/llm/tools` (`config not loaded` panic)

**Severity**: High  
**Location**: `internal/llm/tools/ls.go:99`, `internal/llm/tools/ls_test.go:139`  
**Description**: `go test ./...` fails due to panic in `TestLsTool_Run/handles_empty_path_parameter` when `config.WorkingDirectory()` is called without loaded config.

**Root Cause**:
- Test path invokes production code requiring loaded global config singleton.
- Missing test setup or missing defensive fallback in ls tool.

**Reproduction Steps**:
1. Run `go test ./...`.
2. Observe panic stack trace containing `config not loaded`.

**Fix Instructions**:
```go
// BEFORE (ls.go, simplified):
wd := config.WorkingDirectory() // panics when config not loaded

// AFTER (defensive approach):
wd, err := config.TryWorkingDirectory()
if err != nil || wd == "" {
    wd = "."
}
```
Or in test:
```go
// Initialize minimal config fixture before invoking ls tool
config.LoadForTest(...)
```

---

### BUG-002: `UpdateSchedule` Behavior Is Silent No-op

**Severity**: High  
**Location**: `internal/aria/scheduler/service.go:525-535`  
**Description**: API contract suggests schedule update, but method only validates and logs.

**Root Cause**:
- Missing SQL query/migration support and implementation deferred.

**Reproduction Steps**:
1. Create recurring task.
2. Call `UpdateSchedule` with different cron expression.
3. Fetch DB row; `schedule_expr` unchanged.

**Fix**:
- Implement DB query and apply update transactionally.

---

### BUG-003: Subscriber Event Loss Under Multiple Agency Subscribers

**Severity**: High  
**Location**: `internal/aria/agency/development.go:307-321`  
**Description**: Fan-out is not implemented; subscribers race for same channel events.

**Root Cause**:
- Single channel consumer model used as pseudo-broker.

**Reproduction Steps**:
1. Create two subscribers.
2. Publish N events.
3. Compare received counts and payloads; mismatch occurs.

**Fix**:
- Replace with proper broker that copies events per subscriber.

---

### BUG-004: Potential Data Race on Agency State and Memory Slices

**Severity**: Medium  
**Location**:
- `internal/aria/agency/development.go:180-183` (state writes)
- `internal/aria/agency/development.go:377-379` (`experiences` append)

**Description**: shared mutable state accessed without synchronization.

**Root Cause**:
- No mutex around state/memory collections.

**Reproduction Steps**:
1. Run concurrent execute/save/get operations.
2. Run with `-race`; observe race warnings.

**Fix**:
- Add `sync.RWMutex` guards around state and experiences.

---

### BUG-005: Stop Channel Double-close Panic Risk in Analysis Service

**Severity**: Medium  
**Location**: `internal/aria/analysis/service.go:57-59`  
**Description**: `Stop()` closes channel unguarded; calling twice panics.

**Root Cause**:
- No idempotent shutdown guard.

**Reproduction Steps**:
1. Create service.
2. Call `Stop()` twice.
3. Observe panic: `close of closed channel`.

**Fix**:
```go
type selfAnalysisService struct {
    stopOnce sync.Once
    stopCh chan struct{}
}

func (s *selfAnalysisService) Stop() {
    s.stopOnce.Do(func() { close(s.stopCh) })
}
```

---

## Detailed Issue Cards (Actionable Fix Format)

### GAP-001: Core Interface Contract Drift

**Type**: Gap  
**Severity**: High  
**Category**: correctness

**Location**:
- File: `internal/aria/core/orchestrator.go`
- Line: ~90
- Function: `Orchestrator.RouteToAgent`

**Description**:
`RouteToAgent` returns `string` identifier, not typed `Agent` as in blueprint.

**Expected Behavior**:
Typed agent contract across orchestrator routing pipeline.

**Actual Behavior**:
String return creates weak coupling and runtime ambiguity.

**Impact**:
Harder to enforce compile-time compatibility and multi-agent composition.

**Reproduction Steps**:
1. Compare interface declaration with blueprint.
2. Trace call sites relying on string IDs.

**Fix Instructions**:
```go
// BEFORE
type Orchestrator interface {
    RouteToAgent(ctx context.Context, query Query) (string, error)
}

// AFTER
type Orchestrator interface {
    RouteToAgent(ctx context.Context, query Query) (agent.Agent, error)
}
```

**Estimated Effort**: 4-6 hours  
**Prerequisites**: shared type package to avoid import cycles.

---

### GAP-002: Agency API Not Type-safe

**Type**: Gap  
**Severity**: High  
**Category**: maintainability

**Location**:
- File: `internal/aria/agency/agency.go`
- Line: ~120-121
- Function: `Agents`, `GetAgent`

**Description**:
Uses `[]string` and `any`; this bypasses contract guarantees.

**Expected Behavior**:
`Agents() []Agent`, `GetAgent(name AgentName) (Agent, error)`.

**Actual Behavior**:
Untyped values require runtime assertion.

**Impact**:
Increases runtime errors and reduces IDE/static tooling value.

**Reproduction Steps**:
1. Attempt to call typed methods on return value from `GetAgent`.
2. Add wrong type accidentally; compile still succeeds.

**Fix Instructions**:
```go
// BEFORE
Agents() []string
GetAgent(name string) (any, error)

// AFTER
Agents() []agent.Agent
GetAgent(name agent.AgentName) (agent.Agent, error)
```

**Estimated Effort**: 1 day  
**Prerequisites**: cycle-safe package boundaries.

---

### GAP-003: Memory Service `GenerateInsights` Structure

**Type**: Gap  
**Severity**: Medium  
**Category**: maintainability

**Location**:
- File: `internal/aria/memory/memory.go`
- Line: ~160
- Function: `GenerateInsights`

**Description**:
Returns `[]string`, loses metadata and attribution context.

**Expected Behavior**:
Return structured `[]Insight`.

**Actual Behavior**:
Plain text list with no schema.

**Impact**:
Hard to drive automated improvement loops.

**Reproduction Steps**:
1. Consume insights in higher-level code.
2. Observe inability to sort/filter by category/confidence.

**Fix Instructions**:
```go
type Insight struct {
    Category   string
    Message    string
    Confidence float64
    Evidence   []string
}

GenerateInsights(ctx context.Context) ([]Insight, error)
```

**Estimated Effort**: 4 hours  
**Prerequisites**: update analysis and orchestrator consumers.

---

### GAP-004: Scheduler Update Schedule Persistence

**Type**: Bug  
**Severity**: High  
**Category**: correctness

**Location**:
- File: `internal/aria/scheduler/service.go`
- Line: ~525-535
- Function: `UpdateSchedule`

**Description**:
Method intentionally no-op after validation.

**Expected Behavior**:
Persist schedule expression update.

**Actual Behavior**:
No DB mutation.

**Impact**:
User-visible mismatch between API and stored state.

**Reproduction Steps**:
1. Create recurring task.
2. Call update.
3. Query task row.

**Fix Instructions**:
```go
// BEFORE
logging.Info("schedule update validated", ...)
return nil

// AFTER
err := s.db.UpdateTaskScheduleExpr(ctx, db.UpdateTaskScheduleExprParams{...})
if err != nil { return fmt.Errorf("update schedule: %w", err) }
s.eventBroker.Publish(pubsub.UpdatedEvent, TaskEvent{Type: "schedule_updated", ...})
return nil
```

**Estimated Effort**: 6-8 hours  
**Prerequisites**: sql query + sqlc regenerate.

---

### GAP-005: Non-broadcast Event Broker

**Type**: Critical Issue  
**Severity**: High  
**Category**: correctness

**Location**:
- File: `internal/aria/agency/development.go`
- Line: ~286-322
- Function: `AgencyEventBroker`

**Description**:
Single-channel fan-in/out leads to non-deterministic event delivery across subscribers.

**Expected Behavior**:
Each subscriber receives full event stream.

**Actual Behavior**:
Subscribers compete for events.

**Impact**:
Monitoring/UI/analytics listeners can miss events.

**Reproduction Steps**:
1. Attach two subscribers.
2. Publish fixed sequence.
3. Compare results.

**Fix Instructions**:
```go
// Replace custom broker with shared pubsub broker
broker *pubsub.Broker[AgencyEvent]

func Subscribe(ctx context.Context) <-chan AgencyEvent {
    out := make(chan AgencyEvent, 64)
    sub := broker.Subscribe(ctx)
    go forwardEachSubscriber(sub, out)
    return out
}
```

**Estimated Effort**: 4-6 hours  
**Prerequisites**: add tests with two subscribers.

---

### GAP-006: Logging Strategy Inconsistency

**Type**: Improvement  
**Severity**: Medium  
**Category**: maintainability

**Location**:
- File: multiple
- Function: multiple

**Description**:
Use of `fmt.Printf` in non-interactive service code.

**Expected Behavior**:
Structured logging for diagnostics and observability.

**Actual Behavior**:
Stdout prints with inconsistent formats.

**Impact**:
Harder triage and log aggregation.

**Reproduction Steps**:
1. Trigger DB warning paths.
2. Observe plain print output.

**Fix Instructions**:
```go
// BEFORE
fmt.Printf("warning: failed to persist agency: %v\n", err)

// AFTER
logging.Warn("failed to persist agency", "error", err, "agency", ag.Name())
```

**Estimated Effort**: 2-3 hours  
**Prerequisites**: none.

---

## Database Schema Verification

### Expected Tables vs Actual

| Table | Expected | Found in Migration | SQL Accessors Present | Status |
|-------|----------|--------------------|-----------------------|--------|
| `agencies` | yes | ✅ `20260328120000_aria_baseline.sql` | ✅ `agencies.sql` | ✅ |
| `agency_states` | yes | ✅ | ✅ `agencies.sql` (upsert/get/delete) | ✅ |
| `tasks` | yes | ✅ | ✅ `tasks.sql` | ✅ |
| `task_dependencies` | yes | ✅ | ✅ `tasks.sql` | ✅ |
| `task_events` | yes | ✅ | ✅ `task_events.sql` | ✅ |
| `episodes` | yes | ✅ | ✅ `episodes.sql`, `episodes_adv.sql` | ✅ |
| `facts` | yes | ✅ | ✅ `facts.sql` | ✅ |
| `procedures` | yes | ✅ | ✅ `procedures.sql` | ✅ |
| `working_memory_contexts` | yes | ✅ `20260328130000_working_memory_contexts.sql` | ✅ `memory.sql` | ✅ |

### Schema Notes

- `agencies` includes all expected fields.
- `agency_states` includes metrics JSON and FK to `agencies`.
- `tasks` includes scheduling, execution metadata, progress and result/error JSON fields.
- `task_dependencies` and `task_events` align with blueprint.
- `working_memory_contexts` includes TTL expiration (`expires_at`).

### DB-Related Caveats

1. `UpdateSchedule` gap is implementation-level, not migration absence alone.
2. Some advanced retention/count operations are still best-effort in memory service.

---

## Implementation Quality Checks

### 1) Error Handling

- ✅ Many errors are wrapped with context via `fmt.Errorf("...: %w", err)`.
- ⚠️ Several paths still log via `fmt.Printf` rather than structured logger.
- ⚠️ A few helper methods return nil on not-found without explicit typed error (`RouteToAgency` can return `(nil,nil)`).

### 2) Concurrency

- ✅ Several services use `sync.RWMutex`/`sync.Map`.
- ⚠️ Custom broker in agency package is not safe for deterministic fan-out.
- ⚠️ Agency state and memory slices are unsynchronized.
- ⚠️ Memory GC goroutine lacks stop lifecycle.

### 3) Testing

- ✅ Tests exist for:
  - `internal/aria/analysis`
  - `internal/aria/memory`
  - `internal/aria/guardrail`
  - `internal/aria/permission`
  - `internal/aria/scheduler`
- ❌ Missing tests for:
  - `internal/aria/core`
  - `internal/aria/routing`
  - `internal/aria/agency`
  - `internal/aria/agent`
  - `internal/aria/skill`

### 4) Documentation

- ✅ Packages contain top-level comments.
- ✅ Most public interfaces/methods have basic comments.
- ⚠️ Contract-level drift means comments may claim blueprint compliance while signatures diverge.

---

## Verification Command Results

### Build Check

```bash
go build ./...
```

**Result**: ✅ PASS

### Vet Check

```bash
go vet ./...
```

**Result**: ✅ PASS

### Test Check

```bash
go test ./...
```

**Result**: ❌ FAIL (one package)

**Failure Summary**:
- Package: `github.com/fulvian/aria/internal/llm/tools`
- Test: `TestLsTool_Run/handles_empty_path_parameter`
- Panic: `config not loaded`
- Stack points to `internal/config/config.go:964` and `internal/llm/tools/ls.go:99`

---

## Recommendations

### Immediate Actions (Critical)

1. Align core interfaces to blueprint signatures (Orchestrator/Agency/Agent/Memory/Guardrail).
2. Replace custom agency event broker with true broadcast pub/sub implementation.
3. Implement real persistence in `SchedulerService.UpdateSchedule`.
4. Fix failing `internal/llm/tools` test to restore green CI baseline.
5. Add missing tests for `core`, `routing`, `agency`, `agent`, `skill`.

### Short-term Improvements

1. Introduce shared domain model package to eliminate map/any drift.
2. Add shutdown lifecycle (`Close`) to memory service GC and similar background loops.
3. Replace all `fmt.Printf` operational logs with structured logging.
4. Harden race-prone fields with mutexes and add `-race` CI target.

### Long-term Enhancements

1. Add contract tests that assert blueprint-required method signatures and behavior semantics.
2. Add migration/query lint checks to ensure feature methods are never left no-op.
3. Expand FASE 5 agencies using typed contracts first, then capability growth.
4. Persist guardrail and permission state for restart durability.

---

## Appendix

### A. File Checklist

#### Expected Core Files

| Expected File | Exists | Completeness | Notes |
|---------------|--------|--------------|-------|
| `internal/aria/core/orchestrator.go` | ✅ | ⚠️ Partial | interface drift in method types |
| `internal/aria/core/orchestrator_impl.go` | ✅ | ✅ | main implementation present |
| `internal/aria/agency/agency.go` | ✅ | ⚠️ Partial | untyped agent API |
| `internal/aria/agency/registry.go` | ✅ | ✅ | default registry + persistence wrapper |
| `internal/aria/agency/service.go` | ✅ | ✅ | DB persistence service |
| `internal/aria/agency/weather.go` | ✅ | ✅ | weather agency POC |
| `internal/aria/agency/development.go` | ✅ | ✅ | development agency |
| `internal/aria/agent/agent.go` | ✅ | ⚠️ Partial | interface naming/signature drift |
| `internal/aria/agent/legacy_wrapper.go` | ✅ | ✅ | compatibility wrapper |
| `internal/aria/skill/skill.go` | ✅ | ✅ | skill interface and constants |
| `internal/aria/skill/registry.go` | ✅ | ✅ | registry and defaults |
| `internal/aria/skill/code_review.go` | ✅ | ✅ | concrete implementation |
| `internal/aria/skill/tdd.go` | ✅ | ✅ | concrete implementation |
| `internal/aria/skill/debugging.go` | ✅ | ✅ | concrete implementation |
| `internal/aria/routing/router.go` | ✅ | ✅ | router interface |
| `internal/aria/routing/router_impl.go` | ✅ | ✅ | baseline router |
| `internal/aria/routing/classifier.go` | ✅ | ✅ | classifier interface |
| `internal/aria/routing/classifier_impl.go` | ✅ | ✅ | baseline classifier |
| `internal/aria/memory/memory.go` | ✅ | ⚠️ Partial | type drift in signatures |
| `internal/aria/memory/service.go` | ✅ | ✅ | full service implementation |
| `internal/aria/scheduler/scheduler.go` | ✅ | ✅ | scheduler interface |
| `internal/aria/scheduler/service.go` | ✅ | ⚠️ Partial | `UpdateSchedule` no-op |
| `internal/aria/permission/permission.go` | ✅ | ✅ | extended permission model |
| `internal/aria/permission/service.go` | ✅ | ✅ | in-memory implementation |
| `internal/aria/guardrail/guardrail.go` | ✅ | ⚠️ Partial | outcome typing drift |
| `internal/aria/guardrail/service.go` | ✅ | ✅ | guardrail implementation |
| `internal/aria/analysis/self_analysis.go` | ✅ | ✅ | self-analysis interface |
| `internal/aria/analysis/service.go` | ✅ | ✅ | self-analysis implementation |

#### Additional Relevant Files Found

- `internal/aria/skill/weather_current.go`
- `internal/aria/skill/weather_forecast.go`
- `internal/aria/skill/weather_alerts.go`
- `internal/aria/config/config.go`
- `internal/aria/config/weather.go`

#### Missing Expected-by-Contract Test Files

| Package | Expected Tests | Found | Status |
|---------|----------------|-------|--------|
| `internal/aria/core` | yes | none | ❌ |
| `internal/aria/routing` | yes | none | ❌ |
| `internal/aria/agency` | yes | none | ❌ |
| `internal/aria/agent` | yes | none | ❌ |
| `internal/aria/skill` | yes | none | ❌ |

---

### B. Interface Method Checklist

#### B.1 Orchestrator Interface (Blueprint 2.2.1)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `ProcessQuery(ctx, query) (Response, error)` | required | present | ✅ | `core/orchestrator.go:84`, impl at `orchestrator_impl.go:65` |
| `RouteToAgency(ctx, query) (Agency, error)` | required | present | ✅ | `core/orchestrator.go:87`, impl at `orchestrator_impl.go:233` |
| `RouteToAgent(ctx, query) (Agent, error)` | required | `(string, error)` | ❌ | `core/orchestrator.go:90`, impl `orchestrator_impl.go:262` |
| `ScheduleTask(ctx, task) (TaskID, error)` | required | present | ✅ | `core/orchestrator.go:93`, impl `orchestrator_impl.go:289` |
| `MonitorTasks(ctx) <-chan TaskEvent` | required | present | ✅ | `core/orchestrator.go:96`, impl `orchestrator_impl.go:304` |
| `AnalyzeSelf(ctx) (SelfAnalysis, error)` | required | present | ✅ | `core/orchestrator.go:99`, impl `orchestrator_impl.go:336` |
| `Learn(ctx, experience) error` | required | present | ✅ | `core/orchestrator.go:102`, impl `orchestrator_impl.go:369` |
| `GetProactiveSuggestions(ctx) ([]Suggestion, error)` | required | present | ⚠️ Partial | returns empty TODO in impl `orchestrator_impl.go:380-383` |

#### B.2 Agency Interface (Blueprint 2.2.2)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `Subscribe(ctx) <-chan AgencyEvent` | required | present | ✅ | `agency/agency.go:112` |
| `Name() AgencyName` | required | present | ✅ | `agency/agency.go:115` |
| `Domain() string` | required | present | ✅ | `agency/agency.go:116` |
| `Description() string` | required | present | ✅ | `agency/agency.go:117` |
| `Agents() []Agent` | required | `[]string` | ❌ | `agency/agency.go:120` |
| `GetAgent(name AgentName) (Agent, error)` | required | `(name string) (any, error)` | ❌ | `agency/agency.go:121` |
| `Execute(ctx, task) (Result, error)` | required | present | ✅ | `agency/agency.go:124` |
| `GetState() AgencyState` | required | present | ✅ | `agency/agency.go:127` |
| `SaveState(state) error` | required | present | ✅ | `agency/agency.go:128` |
| `Memory() DomainMemory` | required | present | ✅ | `agency/agency.go:131` |

#### B.3 Agent Interface (Blueprint 2.2.3)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| Interface name `Agent` | required | `EnhancedAgent` | ❌ | `agent/agent.go:79` |
| `Subscribe(ctx) <-chan AgentEvent` | required | present | ✅ | `agent/agent.go:80`, wrapper `legacy_wrapper.go:249` |
| `Name() AgentName` | required | present | ✅ | `agent/agent.go:83` |
| `Agency() AgencyName` | required | present | ✅ | `agent/agent.go:84` |
| `Capabilities() []Capability` | required | present | ✅ | `agent/agent.go:85` |
| `Run(ctx, task Task) (Result, error)` | required | `Run(ctx, task map[string]any) (map[string]any, error)` | ❌ | `agent/agent.go:88` |
| `Stream(ctx, task Task) <-chan Event` | required | returns `(<-chan Event, error)` with map task | ❌ | `agent/agent.go:89` |
| `Cancel(...)` | required by prompt checklist | not in interface | ❌ | absent in `agent/agent.go` |
| `Skills() []Skill` | required | present | ✅ | `agent/agent.go:92` |
| `HasSkill(name SkillName) bool` | required | present | ✅ | `agent/agent.go:93` |
| `LearnFromFeedback(feedback) error` | required | present | ✅ | `agent/agent.go:96` |
| `GetState() AgentState` | required | present | ✅ | `agent/agent.go:99` |

#### B.4 Skill Interface (Blueprint 2.2.4)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `Name() SkillName` | required | present | ✅ | `skill/skill.go:87` |
| `Description() string` | required | present | ✅ | `skill/skill.go:88` |
| `RequiredTools() []ToolName` | required | present | ✅ | `skill/skill.go:91` |
| `RequiredMCPs() []MCPName` | required | present | ✅ | `skill/skill.go:92` |
| `Execute(ctx, params) (SkillResult, error)` | required | present | ✅ | `skill/skill.go:95` |
| `CanExecute(ctx) (bool, string)` | required | present | ✅ | `skill/skill.go:98` |

#### B.5 MemoryService Interface (Blueprint 3.2)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `GetContext` | required | present | ✅ | `memory/memory.go:136` |
| `SetContext` | required | present | ✅ | `memory/memory.go:137` |
| `RecordEpisode` | required | present | ✅ | `memory/memory.go:140` |
| `SearchEpisodes` | required | present | ✅ | `memory/memory.go:141` |
| `GetSimilarEpisodes` | required | present | ✅ | `memory/memory.go:142` |
| `StoreFact` | required | present | ✅ | `memory/memory.go:145` |
| `GetFacts` | required | present | ✅ | `memory/memory.go:146` |
| `QueryKnowledge` | required | present | ✅ | `memory/memory.go:147` |
| `SaveProcedure` | required | present | ✅ | `memory/memory.go:150` |
| `GetProcedure` | required | present | ✅ | `memory/memory.go:151` |
| `FindApplicableProcedures(ctx, task Task)` | required | `task map[string]any` | ❌ | `memory/memory.go:152` |
| `LearnFromSuccess` | required | present | ✅ | `memory/memory.go:155` |
| `LearnFromFailure` | required | present | ✅ | `memory/memory.go:156` |
| `GetPerformanceMetrics` | required | present | ✅ | `memory/memory.go:159` |
| `GenerateInsights` | required structured insights | returns `[]string` | ⚠️ Partial | `memory/memory.go:160` |

#### B.6 Scheduler Interface (Blueprint 4.2)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `Schedule` | required | present | ✅ | `scheduler/scheduler.go:164`, impl `service.go:48` |
| `Cancel` | required | present | ✅ | `scheduler/scheduler.go:165`, impl `service.go:116` |
| `Pause` | required | present | ✅ | `scheduler/scheduler.go:166`, impl `service.go:160` |
| `Resume` | required | present | ✅ | `scheduler/scheduler.go:167`, impl `service.go:209` |
| `GetTask` | required | present | ✅ | `scheduler/scheduler.go:170`, impl `service.go:258` |
| `ListTasks` | required | present | ✅ | `scheduler/scheduler.go:171`, impl `service.go:286` |
| `Subscribe` | required | present | ✅ | `scheduler/scheduler.go:174`, impl `service.go:363` |
| `GetProgress` | required | present | ✅ | `scheduler/scheduler.go:175`, impl `service.go:388` |
| `ScheduleRecurring` | required | present | ✅ | `scheduler/scheduler.go:178`, impl `service.go:439` |
| `UpdateSchedule` | required | present but no-op | ⚠️ Partial | `scheduler/service.go:505-535` |

#### B.7 GuardrailService Interface (Blueprint 5.2)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `CanExecute` | required | present | ✅ | `guardrail/guardrail.go:132`, impl `service.go:66` |
| `GetActionBudget` | required | present | ✅ | `guardrail/guardrail.go:135`, impl `service.go:130` |
| `ConsumeAction` | required | present | ✅ | `guardrail/guardrail.go:138`, impl `service.go:139` |
| `GetUserPreferences` | required | present | ✅ | `guardrail/guardrail.go:141`, impl `service.go:161` |
| `UpdatePreferences` | required | present | ✅ | `guardrail/guardrail.go:144`, impl `service.go:169` |
| `LogAction` | required | present with `string` outcome | ⚠️ Partial | `guardrail/guardrail.go:147`, impl `service.go:198` |
| `GetAuditLog` | required | present | ✅ | `guardrail/guardrail.go:150`, impl `service.go:222` |

#### B.8 SelfAnalysisService Interface (Blueprint 6.1)

| Method | Blueprint | Actual | Status | Evidence |
|--------|-----------|--------|--------|----------|
| `RunPeriodicAnalysis` | required | present | ✅ | `analysis/self_analysis.go:173`, impl `service.go:38` |
| `AnalyzePerformance` | required | present | ✅ | `analysis/self_analysis.go:175`, impl `service.go:86` |
| `AnalyzePatterns` | required | present | ✅ | `analysis/self_analysis.go:178`, impl `service.go:215` |
| `AnalyzeFailures` | required | present | ✅ | `analysis/self_analysis.go:181`, impl `service.go:309` |
| `GenerateImprovements` | required | present | ✅ | `analysis/self_analysis.go:184`, impl `service.go:398` |
| `ApplyInsights` | required | present | ✅ | `analysis/self_analysis.go:187`, impl `service.go:462` |

---

### C. Test Coverage Summary

#### C.1 Package-Level Test Presence

| Package | Test Files Found | Status |
|---------|------------------|--------|
| `internal/aria/analysis` | `service_test.go` | ✅ |
| `internal/aria/memory` | `service_test.go`, `integration_test.go`, `benchmark_test.go` | ✅ |
| `internal/aria/guardrail` | `service_test.go` | ✅ |
| `internal/aria/permission` | `service_test.go` | ✅ |
| `internal/aria/scheduler` | `dispatcher_test.go`, `worker_test.go`, `recovery_test.go`, `recurring_test.go`, `mapper_test.go` | ✅ |
| `internal/aria/core` | none | ❌ |
| `internal/aria/routing` | none | ❌ |
| `internal/aria/agency` | none | ❌ |
| `internal/aria/agent` | none | ❌ |
| `internal/aria/skill` | none | ❌ |

#### C.2 Test Execution Outcome

- `go test ./...` overall: ❌
- ARIA subpackages with tests: mostly passing
- Global failure: `internal/llm/tools` panic in `TestLsTool_Run`

#### C.3 Recommended Test Additions

1. `internal/aria/core/orchestrator_test.go`
   - route decisions
   - fallback behavior
   - memory integration hooks
2. `internal/aria/routing/router_test.go`
   - rule priority
   - fallback correctness
3. `internal/aria/agency/agency_event_broker_test.go`
   - multi-subscriber broadcast determinism
4. `internal/aria/agent/legacy_wrapper_test.go`
   - event forwarding
   - cancel semantics
5. `internal/aria/skill/*_test.go`
   - CanExecute and deterministic result shape
   - tool failure handling

---

## Additional Observations

1. `core.Classifier(orch Orchestrator)` currently returns `nil` and is effectively dead utility; remove or implement.
2. `memory.GetSimilarEpisodes` sorts using score recomputation referencing `recentEpisodes[i]`/`[j]` while sorting `bestEpisodes` (index-coupling risk).
3. `orchestrator_impl.go` uses fallback text marker `FALLBACK_TO_LEGACY` in response body; better modeled via enum/flag.
4. `weather.go` `jsonConvert` ignores marshal errors; should return `(string,error)`.
5. `dbAgencyWrapper.Execute` returns empty successful result and nil error; should probably return explicit unsupported error.

---

## Prioritized Remediation Plan

### P0 (Immediate, block next phase hardening)

1. Fix interface drifts for Orchestrator, Agency, Agent.
2. Replace custom `AgencyEventBroker` with robust pub/sub broker.
3. Implement `SchedulerService.UpdateSchedule` persistence.
4. Fix failing `internal/llm/tools` test panic.

### P1 (Near-term)

1. Add missing tests for core/routing/agency/agent/skill.
2. Remove/replace `fmt.Printf` in service paths.
3. Add lifecycle shutdown for memory GC and analysis stop idempotence.

### P2 (Medium-term)

1. Introduce shared typed domain contracts package.
2. Persist permission and guardrail data.
3. Add blueprint contract checker tests.

---

## Compliance Verdict

- **Architectural Direction**: ✅ Correct
- **Contract Fidelity to BLUEPRINT**: ⚠️ Partial
- **Functional Readiness for FASE 5 Expansion**: ⚠️ Conditional (requires P0 remediation)
- **Database Alignment**: ✅ Strong
- **Quality Gate (build/vet/tests)**: ⚠️ Not fully green due to non-ARIA test failure

The codebase is materially aligned with blueprint intent and phase progression, but contract drift and a handful of high-impact implementation gaps should be addressed before scaling additional agencies.

---

## Line-by-Line Checklist (Expanded)

### Phase 0 Checklist (Expanded)

- [x] `internal/aria/` directory exists.
- [x] `internal/aria/core` exists.
- [x] `internal/aria/agency` exists.
- [x] `internal/aria/agent` exists.
- [x] `internal/aria/skill` exists.
- [x] `internal/aria/routing` exists.
- [x] `internal/aria/memory` exists.
- [x] `internal/aria/scheduler` exists.
- [x] `internal/aria/permission` exists.
- [x] `internal/aria/guardrail` exists.
- [x] `internal/aria/analysis` exists.
- [x] baseline migration created.
- [x] working-memory migration created.
- [x] sql files for agencies/tasks/memory/episodes/facts/procedures present.
- [ ] complete base test suite across all ARIA packages.

### Phase 1 Checklist (Expanded)

- [x] Orchestrator interface exists.
- [x] Orchestrator implementation exists.
- [x] Agency registry exists.
- [x] Development agency exists.
- [x] Legacy agent wrapper exists.
- [x] Skill registry exists.
- [x] Code review skill exists.
- [x] TDD skill exists.
- [x] Debugging skill exists.
- [x] Routing classifier exists.
- [x] Routing router exists.
- [ ] Strict blueprint signature conformance (all interfaces).

### Phase 2 Checklist (Expanded)

- [x] Working memory get/set.
- [x] Working memory persistence.
- [x] Working memory TTL and cleanup query.
- [x] Episodic record/search.
- [x] Similar episode retrieval.
- [x] Semantic fact store/query.
- [x] Semantic usage tracking.
- [x] Procedure save/get/find.
- [x] Procedure discovery scoring.
- [x] LearnFromSuccess.
- [x] LearnFromFailure.
- [x] Performance metrics function.
- [x] Generate insights function.
- [ ] Structured insight typing alignment.
- [ ] Service lifecycle stop for GC loop.

### Phase 3 Checklist (Expanded)

- [x] Schedule task.
- [x] Cancel task.
- [x] Pause task.
- [x] Resume task.
- [x] Get task.
- [x] List tasks with filters.
- [x] Subscribe to task events.
- [x] Progress computation.
- [x] Recurring task schedule creation.
- [ ] Recurring schedule update persistence.

### Phase 4 Checklist (Expanded)

- [x] Guardrail `CanExecute`.
- [x] Guardrail budget tracking.
- [x] Guardrail consume action.
- [x] User preferences read/update.
- [x] Quiet hours check.
- [x] Active hours check.
- [x] Auto approve low-impact path.
- [x] Audit log in memory.
- [x] Extended permission request/grant/deny/check.
- [ ] Persistent guardrail/permission storage.

### Phase 5 Checklist (Expanded)

- [x] AgencyService persistence.
- [x] Agency state persistence.
- [x] Persistable registry wrapper.
- [x] Weather agency POC.
- [x] Weather skills present.
- [ ] Knowledge agency implementation.
- [ ] Creative agency implementation.
- [ ] Productivity agency implementation.
- [ ] Personal agency implementation.
- [ ] Analytics agency implementation.

---

## End of Report
