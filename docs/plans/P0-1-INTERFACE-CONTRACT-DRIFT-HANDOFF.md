# Handoff Prompt: P0-1 Interface Contract Drift — Full Resolution Plan

**Generated**: 2026-03-29 21:49:00 +02:00  
**Author**: Claude (General Manager)  
**Priority**: P0 — CRITICAL  
**Status**: PARTIAL (RouteToAgent fixed, Agency/Agent interfaces remain)  
**Destination**: `docs/plans/P0-1-INTERFACE-CONTRACT-DRIFT-PLAN.mmd`

---

## Executive Summary

The P0-1 interface contract drift between the ARIA blueprint and implementation **remains partially unresolved**. While `RouteToAgent` has been fixed to return `routing.AgentID`, the `Agency.Agents()` and `Agency.GetAgent()` methods still return untyped `[]string` and `any`, which violates blueprint Section 2.2.2 contract.

**This is blocking FASE 5 expansion and multi-agency orchestration.**

---

## Background: What Was Done

### Completed in Previous Sessions

1. **P0-2 Event Broker** ✅
   - Replaced custom single-channel broker with `pubsub.Broker[AgencyEvent]`
   - Files: `internal/aria/agency/development.go`

2. **P0-3 UpdateSchedule Persistence** ✅
   - Manually added `UpdateTaskScheduleExpr` to sqlc-generated code
   - Files: `internal/db/sql/tasks.sql`, `internal/db/tasks.sql.go`, `internal/db/db.go`, `internal/db/querier.go`, `internal/aria/scheduler/service.go`

3. **P0-4 Test Panic** ✅
   - Added `config.TryWorkingDirectory()` with defensive fallback
   - Files: `internal/config/config.go`, `internal/llm/tools/ls.go`

4. **P0-1 Partial (RouteToAgent)** ✅
   - Created `routing.AgentID` type with `Name`, `Agency`, `Skills` fields
   - Updated `Orchestrator.RouteToAgent` to return `routing.AgentID` instead of `string`
   - Files: `internal/aria/routing/router.go`, `internal/aria/core/orchestrator.go`, `internal/aria/core/orchestrator_impl.go`

---

## Problem Statement: Remaining P0-1 Issue

### Current State vs Blueprint

| Interface | Method | Blueprint Signature | Actual Signature |
|----------|--------|---------------------|------------------|
| `Agency` | `Agents()` | `[]Agent` | `[]string` |
| `Agency` | `GetAgent()` | `(AgentName) (Agent, error)` | `(string) (any, error)` |
| `Agent` | Interface name | `Agent` | `EnhancedAgent` |

### Impact

1. **Type Safety Violated**: Runtime `any` casting removes compile-time safety
2. **Blueprint Non-Compliance**: Interface signatures don't match Section 2.2.2/2.2.3
3. **Multi-Agency Blocked**: Cannot safely compose agencies without typed agent references
4. **Stub Implementations**: `ReviewerAgent`, `ArchitectAgent` are incomplete stubs

### Root Cause Analysis

**Import Cycle Problem**:
```
internal/aria/agent/agent.go
  └── imports "github.com/fulvian/aria/internal/aria/agency" (for AgencyName)

If agency imports Agent from agent:
  agency → agent (for Agent type)
  agent → agency (for AgencyName type)
  ❌ IMPORT CYCLE
```

**Stub Agents**:
```go
// Current ReviewerAgent — MISSING required methods:
// - Name(), Agency(), Capabilities()
// - Run(), Stream()
// - Skills(), HasSkill()
// - LearnFromFeedback()
// - GetState()
// - Subscribe()

type ReviewerAgent struct{}
func (a *ReviewerAgent) Review(ctx context.Context, task Task) (map[string]any, error) {...}
```

---

## Required Analysis Tasks

### 1. Import Cycle Resolution Strategy

Analyze and recommend ONE of these approaches:

**Option A: Shared Types Package**
- Create `internal/aria/types.go` with `AgencyName`, `AgentName` constants
- Both `agent` and `agency` import from `types` instead of each other

**Option B: Interface-Based Decoupling**
- Keep `AgencyName` in `agency`, `AgentName` in `agent`
- Use interfaces for cross-package references (Go allows importing types used only in interfaces)

**Option C: Type Aliases in routing Package**
- Use `routing.AgentID` for agent identification
- Keep actual agent implementations decoupled from interfaces

### 2. Stub Implementation Completeness

For each stub agent, document required methods:

| Agent | Current State | Required Interface Methods |
|-------|---------------|---------------------------|
| `ReviewerAgent` | `Review()` only | Full `EnhancedAgent` interface |
| `ArchitectAgent` | `Design()` only | Full `EnhancedAgent` interface |
| `CoderBridge` | `RunTask()` only | Full `EnhancedAgent` interface |

### 3. Call Site Analysis

Identify all usages that must be updated:

```bash
# Find usages of old signatures
grep -r "Agents\(\)" internal/aria/
grep -r "GetAgent(" internal/aria/
grep -r "EnhancedAgent" internal/aria/
```

Expected impact:
- `internal/aria/agency/development.go`
- `internal/aria/agency/weather.go`
- `internal/aria/agency/service.go`
- `internal/app/aria_integration.go`

### 4. Migration Path

Determine backward compatibility requirements:
- Can we use type aliases (`EnhancedAgent = Agent`) temporarily?
- Should we deprecate old methods with warnings?
- What's the breaking change impact on external callers?

---

## Implementation Plan Template

The resulting `.mmd` file should include:

### 1. Problem Summary (as above)

### 2. Detailed Analysis

```
## 2.1 Import Cycle Analysis
   - Current import graph
   - Recommended resolution approach
   - Pros/cons of each option

## 2.2 Interface Gap Analysis
   - Blueprint Section 2.2.2 Agency interface (exact signatures)
   - Blueprint Section 2.2.3 Agent interface (exact signatures)
   - Current vs expected methods

## 2.3 Stub Completeness Report
   - For each stub: missing methods, estimated effort
   - Method signatures from EnhancedAgent interface

## 2.4 Call Site Inventory
   - All files using old signatures
   - Required changes per file
```

### 3. Implementation Steps

```
## 3.1 Phase 1: Break Import Cycle
   - Step-by-step with file changes
   - Validation commands

## 3.2 Phase 2: Update Agency Interface
   - Change Agents() return type
   - Change GetAgent() signature
   - Update all implementations

## 3.3 Phase 3: Complete Stub Agents
   - ReviewerAgent implementation
   - ArchitectAgent implementation
   - CoderBridge wrapper (if needed)

## 3.4 Phase 4: Update Call Sites
   - agency/development.go
   - agency/weather.go
   - agency/service.go
   - app/aria_integration.go

## 3.5 Phase 5: Testing & Validation
   - go build ./...
   - go test ./...
   - go test -race ./internal/aria/...
   - Manual testing checklist
```

### 4. Risk Assessment

```
## 4.1 Migration Risks
   - Breaking changes
   - Regression potential
   - Test coverage gaps

## 4.2 Mitigation Strategies
   - Backup branch recommended
   - Incremental commits
   - Feature flags if needed
```

### 5. Success Criteria

```
## 5.1 Compile-Time Contract
   - go build passes
   - No interface conformance errors

## 5.2 Runtime Contract  
   - All tests pass
   - No race conditions (-race flag)

## 5.3 Blueprint Compliance
   - Interface signatures match Section 2.2.2
   - Interface signatures match Section 2.2.3
```

### 6. Files Reference

| File | Current State | Target State |
|------|---------------|---------------|
| `internal/aria/agency/agency.go` | `Agents() []string`, `GetAgent() (any,err)` | `Agents() []Agent`, `GetAgent() (Agent,err)` |
| `internal/aria/agent/agent.go` | `EnhancedAgent` interface | `Agent` interface (rename) |
| `internal/aria/agency/development.go` | Stub implementations | Full implementations |
| `internal/aria/agency/weather.go` | Stub implementation | Must implement Agent |
| `internal/aria/agency/service.go` | dbAgencyWrapper stubs | Update signatures |
| `internal/app/aria_integration.go` | Uses old signatures | Update to new signatures |

---

## Deliverable Requirements

**File**: `docs/plans/P0-1-INTERFACE-CONTRACT-DRIFT-PLAN.mmd`

**Format**: Markdown with Mermaid diagrams where appropriate

**Sections Required**:
1. Executive Summary
2. Problem Statement
3. Detailed Analysis (import cycle, interface gaps, stubs, call sites)
4. Implementation Plan (step-by-step phases)
5. Risk Assessment
6. Success Criteria
7. Files Reference

**Diagrams to Include**:
- Import cycle diagram (current state)
- Recommended import graph (target state)
- Interface conformance diagram

---

## Validation Commands

After implementation, ALL must pass:

```bash
go build ./...                          # Must compile without errors
go vet ./...                            # No vet warnings
go test ./...                           # All tests pass
go test -race ./internal/aria/...      # No race conditions
```

---

## Notes for Codex

1. **This is a HIGH-RISK refactoring** — changes affect core interfaces used across 4+ packages
2. **Test coverage is incomplete** for `core`, `agency`, `agent`, `routing`, `skill` packages
3. **sqlc was unavailable** during P0-3 — generated code was manually edited (will be overwritten on `sqlc generate`)
4. **The alias approach** (`EnhancedAgent = Agent`) was used as partial mitigation

---

## Reference Documents

- `docs/foundation/BLUEPRINT.md` — Section 2.2.2 (Agency), 2.2.3 (Agent)
- `docs/analysis/blueprint-alignment-report.md` — Full gap analysis (lines 238-410)
- `internal/aria/agency/agency.go` — Current Agency interface
- `internal/aria/agent/agent.go` — Current EnhancedAgent interface
- `internal/aria/routing/router.go` — AgentID type (already implemented)

---

**END OF HANDOFF**
