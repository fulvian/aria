# ARIA Implementation Plan - P0 Critical Remediation

## Current Status
**P0 CRITICAL REMEDIATION - IN PROGRESS**

---

## Executive Summary (from Blueprint Alignment Report)

The blueprint alignment analysis identified **5 Critical Issues** and **4 High-Severity Bugs** that must be fixed before proceeding with FASE 5 or phase hardening:

| Priority | Issue | Severity | Impact |
|----------|-------|----------|--------|
| P0 | GAP-001: Interface Contract Drift (Orchestrator, Agency, Agent) | High | Blocks multi-agency orchestration |
| P0 | GAP-005: Non-broadcast Event Broker | High | Event loss in multi-subscriber scenarios |
| P0 | GAP-004: Scheduler UpdateSchedule No-op | High | User-visible API/state mismatch |
| P0 | BUG-001: Test panic in internal/llm/tools | High | CI failure |
| P1 | GAP-002/003: Type safety, structured insights | Medium | Maintainability |
| P1 | BUG-004/005: Data races, double-close panic | Medium | Stability |

---

## P0 Critical Fixes (Must Complete First)

### P0-1: Interface Contract Drift

**Status: PLAN DELIVERED**

- Handoff executed and full remediation plan generated in:
  - `docs/plans/P0-1-INTERFACE-CONTRACT-DRIFT-PLAN.mmd`
- Plan includes:
  1. Import-cycle resolution strategy (recommended shared contracts/types package)
  2. Interface gap analysis vs blueprint Sections 2.2.2 and 2.2.3
  3. Stub completeness report for Reviewer/Architect/Coder bridge paths
  4. Call-site inventory and phased migration path
  5. Risks, mitigations, success criteria, and Mermaid diagrams

**Next Execution Gate**: implement the approved plan in phased commits with full verification (`build`, `vet`, `test`, `race`).

### P0-2: Event Broker Is Not Broadcast-safe

**Files Affected:**
- `internal/aria/agency/development.go` lines 286-322

**Tasks:**
- [ ] Replace custom `AgencyEventBroker` with `pubsub.Broker[AgencyEvent]`
- [ ] Ensure each subscriber receives all events (broadcast, not competition)
- [ ] Add multi-subscriber test validating identical event streams

### P0-3: Scheduler UpdateSchedule Not Persisted

**Files Affected:**
- `internal/aria/scheduler/service.go` lines 505-535

**Tasks:**
- [ ] Add SQL query `UpdateTaskScheduleExpr` in `internal/db/sql/tasks.sql`
- [ ] Run `sqlc generate`
- [ ] Implement actual persistence in `UpdateSchedule` method
- [ ] Emit `schedule_updated` event
- [ ] Add roundtrip test

### P0-4: Fix Failing Test Panic

**Files Affected:**
- `internal/llm/tools/ls.go:99`
- `internal/llm/tools/ls_test.go:139`

**Tasks:**
- [ ] Add defensive fallback in `config.TryWorkingDirectory()` or similar
- [ ] OR initialize minimal config fixture in test
- [ ] Verify `go test ./...` passes

---

## P1 Near-Term Fixes

### P1-1: Add Missing Tests

**Packages without tests:**
- `internal/aria/core`
- `internal/aria/routing`
- `internal/aria/agency`
- `internal/aria/agent`
- `internal/aria/skill`

**Tasks:**
- [ ] Create `orchestrator_test.go` - route decisions, fallback behavior
- [ ] Create `router_test.go` - rule priority, fallback correctness
- [ ] Create `agency_event_broker_test.go` - multi-subscriber broadcast
- [ ] Create `legacy_wrapper_test.go` - event forwarding, cancel semantics
- [ ] Create skill tests - CanExecute, tool failure handling

### P1-2: Replace fmt.Printf with Structured Logging

**Files Affected:**
- `internal/aria/core/orchestrator_impl.go:214`
- `internal/aria/agency/registry.go:162,176,203`
- `internal/aria/agency/service.go:332`

**Tasks:**
- [ ] Replace `fmt.Printf` with `logging.Error`/`logging.Warn`
- [ ] Include stable keys for correlation

### P1-3: Lifecycle Shutdown Issues

**Files Affected:**
- `internal/aria/memory/service.go:132-147` (GC goroutine)
- `internal/aria/analysis/service.go:57-59` (double-close panic)

**Tasks:**
- [ ] Add `ctx/cancel` to memory service
- [ ] Stop GC loop on service shutdown
- [ ] Add `Close()` method to memory service
- [ ] Add `sync.Once` guard for analysis service stop

### P1-4: Data Race Fixes

**Files Affected:**
- `internal/aria/agency/development.go:180-183, 377-379`

**Tasks:**
- [ ] Add `sync.RWMutex` guards around state and experiences

---

## P2 Medium-Term

### P2-1: Type-safe Domain Models
- Introduce shared typed domain contracts package
- Align `task Task` vs `task map[string]any` drift
- Align `GenerateInsights` return type (structured vs `[]string`)

### P2-2: Persist Permission/Guardrail State
- Add persistence tables
- Load/save cycle on startup/shutdown

---

## Verification Gates

Before proceeding to FASE 5, these must all pass:

| Check | Command | Expected |
|-------|---------|----------|
| Build | `go build ./...` | PASS |
| Vet | `go vet ./...` | PASS |
| Tests | `go test ./...` | PASS |
| Race | `go test -race ./internal/aria/...` | PASS |

---

## Phase Status (from Blueprint Alignment Report)

| Fase | Alignment Report | Note |
|------|------------------|------|
| FASE 0: Foundation | 92% ✅ | Tests incomplete |
| FASE 1: Core System | 81% ⚠️ | Interface drift |
| FASE 2: Memory & Learning | 86% ⚠️ | GC lifecycle |
| FASE 3: Scheduling | 88% ⚠️ | UpdateSchedule no-op |
| FASE 4: Proactivity | 84% ⚠️ | In-memory only |
| FASE 5: Agencies | 15% ⚠️ | Blocked by P0 |
| FASE 6: Polish | 0% | Not started |

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | P0 remediation before FASE 5 | Blueprint alignment report reveals blocking issues |
| 2026-03-29 | Interface contract fix first | Foundation must be solid before scaling |
| 2026-03-29 | Broadcast broker fix second | Event loss affects monitoring/analytics |
| 2026-03-29 | UpdateSchedule persistence third | User-visible correctness issue |
