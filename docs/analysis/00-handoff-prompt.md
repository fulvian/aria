# ARIA Codebase Analysis Handoff Prompt

**For**: ChatGPT Codex 5.3  
**Purpose**: Comprehensive codebase analysis vs BLUEPRINT.md specifications  
**Output**: `docs/analysis/blueprint-alignment-report.md`  
**Generated**: 2026-03-29

---

## CONTEXT

### Project Overview
**ARIA** (Autonomous Reasoning & Intelligent Assistant) is a terminal-based AI coding assistant built in Go, featuring a TUI built with Bubble Tea. ARIA is transforming from the OpenCode CLI into a multi-agency AI system with hierarchical organization: Agencies → Agents → Skills → Tools/MCP.

### Current BLUEPRINT Status
- **Version**: 1.10.0-DRAFT
- **Status**: FASE 0-4 COMPLETE, FASE 5 IN PROGRESS (~10%)
- **Completed Phases**: FASE 0 (Foundation), FASE 1 (Core System), FASE 2 (Memory & Learning), FASE 3 (Scheduling), FASE 4 (Proactivity)
- **Current Focus**: FASE 5 (Agencies) - Weather Agency POC complete

### Key BLUEPRINT References
- Full specification: `docs/foundation/BLUEPRINT.md`
- FASE 5 plan: `docs/plans/2026-03-29-fase5-agencies-implementation-plan.md`
- Entity creation guide: `docs/guides/aria-entity-creation-guide.md`

---

## YOUR TASK

### 1. VERIFY CODEBASE ALIGNMENT

Analyze the actual codebase implementation against BLUEPRINT.md specifications. For each section, verify:

#### Phase 0 (Foundation) - Should be 100% Complete
- [ ] Directory structure matches blueprint (`internal/aria/`)
- [ ] All interfaces defined as specified
- [ ] Database schema extended correctly

#### Phase 1 (Core System) - Should be 100% Complete
- [ ] Orchestrator implementation matches interface
- [ ] Agency system with registry
- [ ] Development Agency implemented
- [ ] Enhanced Agent system with LegacyAgentWrapper
- [ ] Skill system with CodeReview, TDD, Debugging skills
- [ ] Routing baseline implemented

#### Phase 2 (Memory & Learning) - Should be 100% Complete
- [ ] MemoryService with all memory types
- [ ] Working memory with TTL/GC
- [ ] Episodic memory with full filters
- [ ] Semantic memory with governance
- [ ] Procedural memory with scoring
- [ ] SelfAnalysisService

#### Phase 3 (Scheduling) - Should be 100% Complete
- [ ] SchedulerService with task queue
- [ ] Task persistence
- [ ] Recurring tasks (cron/interval)
- [ ] Task events and monitoring

#### Phase 4 (Proactivity) - Should be 100% Complete
- [ ] GuardrailService
- [ ] ExtendedPermissionService
- [ ] Budget tracking
- [ ] Auto-approve rules
- [ ] QuietHours/ActiveHours

#### Phase 5 (Agencies) - Should be ~10% Complete
- [ ] AgencyService persistence layer
- [ ] Weather Agency POC
- [ ] Remaining agencies NOT started (Knowledge, Creative, Productivity, Personal, Analytics)

---

### 2. DETAILED CODEBASE ANALYSIS

#### A. Interface Compliance Check

For each interface defined in BLUEPRINT, verify the actual Go implementation:

1. **`Orchestrator` interface** (`internal/aria/core/`)
   - ProcessQuery, RouteToAgency, RouteToAgent
   - ScheduleTask, MonitorTasks
   - AnalyzeSelf, Learn
   - GetProactiveSuggestions

2. **`Agency` interface** (`internal/aria/agency/`)
   - Name, Domain, Description
   - Agents, GetAgent
   - Execute
   - GetState, SaveState
   - Memory

3. **`Agent` interface** (`internal/aria/agent/`)
   - Name, Agency, Capabilities
   - Run, Stream, Cancel
   - Skills, HasSkill
   - LearnFromFeedback
   - GetState

4. **`Skill` interface** (`internal/aria/skill/`)
   - Name, Description
   - RequiredTools, RequiredMCPs
   - Execute
   - CanExecute

5. **`MemoryService` interface** (`internal/aria/memory/`)
   - GetContext, SetContext
   - RecordEpisode, SearchEpisodes
   - StoreFact, GetFacts, QueryKnowledge
   - SaveProcedure, GetProcedure, FindApplicableProcedures
   - LearnFromSuccess, LearnFromFailure
   - GetPerformanceMetrics, GenerateInsights

6. **`Scheduler` interface** (`internal/aria/scheduler/`)
   - Schedule, Cancel, Pause, Resume
   - GetTask, ListTasks
   - Subscribe, GetProgress
   - ScheduleRecurring, UpdateSchedule

7. **`GuardrailService` interface** (`internal/aria/guardrail/`)
   - CanExecute
   - GetActionBudget, ConsumeAction
   - GetUserPreferences, UpdatePreferences
   - LogAction, GetAuditLog

#### B. File Existence and Completeness

Verify these key files exist AND are complete:

```
internal/aria/
├── core/
│   └── orchestrator.go        # Must implement full Orchestrator interface
├── agency/
│   ├── agency.go             # Must implement Agency interface
│   ├── registry.go           # Must have DefaultAgencyRegistry
│   ├── service.go            # Must have AgencyService with CRUD
│   └── weather.go            # Weather Agency POC
├── agent/
│   └── agent.go             # Must implement Agent interface
├── skill/
│   ├── skill.go             # Must have Skill interface + registry
│   ├── code_review.go       # Real implementation
│   ├── tdd.go               # Real implementation
│   ├── debugging.go          # Real implementation
│   └── *.go                 # Other skills
├── routing/
│   └── router.go            # Must implement Router interface
├── memory/
│   └── service.go           # Must implement MemoryService interface
├── scheduler/
│   ├── service.go           # Must implement Scheduler interface
│   └── *.go                 # Other scheduler components
├── permission/
│   └── service.go           # Must implement ExtendedPermissionService
├── guardrail/
│   └── service.go           # Must implement GuardrailService
└── analysis/
    └── service.go           # Must implement SelfAnalysisService
```

#### C. Database Schema Verification

Verify these tables exist with correct schema:

- [ ] `agencies` - id, name, domain, description, status, created_at, updated_at
- [ ] `agency_states` - id, agency_id, status, last_task_id, metrics, updated_at
- [ ] `tasks` - id, name, type, priority, status, progress, etc.
- [ ] `task_dependencies` - task_id, depends_on
- [ ] `task_events` - id, task_id, event_type, event_data, created_at
- [ ] `episodes` - id, session_id, agency_id, agent_id, task, actions, outcome, etc.
- [ ] `facts` - id, domain, category, content, source, confidence, use_count
- [ ] `procedures` - id, name, description, trigger, steps, success_rate, use_count
- [ ] `working_memory_contexts` - id, session_id, context_json, version, expires_at

#### D. Implementation Quality Checks

1. **Error Handling**: All errors wrapped with context using `fmt.Errorf("...: %w", err)`
2. **Concurrency**: Proper use of sync.Map, RWMutex, channels
3. **Testing**: Each core package has tests
4. **Documentation**: Public APIs documented

---

### 3. OUTPUT FORMAT

Create a comprehensive Markdown report at: **`docs/analysis/blueprint-alignment-report.md`**

### Report Structure:

```markdown
# ARIA Codebase vs BLUEPRINT Alignment Report

**Generated**: [DATE]
**Analyzer**: ChatGPT Codex 5.3
**Blueprint Version**: 1.10.0-DRAFT

## Executive Summary
[High-level overview of alignment status]

## Phase-by-Phase Analysis

### FASE 0: Foundation
**Status**: [X]% Complete
**Findings**:
- [Finding 1]
- [Finding 2]

### FASE 1: Core System
**Status**: [X]% Complete
**Findings**:
- [Finding 1]
- [Finding 2]

[... continue for all phases ...]

## Interface Compliance Matrix

| Interface | File | Status | Notes |
|-----------|------|--------|-------|
| Orchestrator | core/orchestrator.go | ✓/✗ | [notes] |
| Agency | agency/agency.go | ✓/✗ | [notes] |
[...]

## Gap Analysis

### Critical Gaps
1. **[GAP-001]**: [Description]
   - **Impact**: [High/Medium/Low]
   - **Location**: [File/Package]
   - **Fix**: [Detailed fix instructions]

### Minor Gaps
1. **[GAP-XXX]**: [Description]
   - **Impact**: ...
   - **Location**: ...
   - **Fix**: ...

## Critical Issues

### CRIT-001: [Title]
**Severity**: Critical/High/Medium/Low
**Location**: [File:Line]
**Description**: [Detailed description]
**Reproduction**: [How to reproduce]
**Fix**: [Step-by-step fix instructions]

### CRIT-XXX: [Title]
[...]

## Bug Report

### BUG-001: [Title]
**Severity**: Critical/High/Medium/Low
**Location**: [File:Line]
**Description**: [What happens vs what should happen]
**Root Cause**: [If identifiable]
**Fix**: [Fix instructions]

### BUG-XXX: [Title]
[...]

## Recommendations

### Immediate Actions (Critical)
1. [Action 1]
2. [Action 2]

### Short-term Improvements
1. [Improvement 1]
2. [Improvement 2]

### Long-term Enhancements
1. [Enhancement 1]
2. [Enhancement 2]

## Appendix

### A. File Checklist
[List of all expected files with status]

### B. Interface Method Checklist
[List of all expected methods with implementation status]

### C. Test Coverage Summary
[Coverage analysis per package]
```

---

### 4. ANALYSIS INSTRUCTIONS

#### Step 1: Read BLUEPRINT
- Load `docs/foundation/BLUEPRINT.md`
- Understand the target architecture
- Note all interface definitions

#### Step 2: Scan Directory Structure
- List all files in `internal/aria/`
- Verify expected directories exist
- Note any unexpected files

#### Step 3: Interface Analysis
For each interface in BLUEPRINT:
1. Find the actual Go interface definition
2. Compare method signatures
3. Check if methods are implemented
4. Note any deviations

#### Step 4: Implementation Analysis
For each implemented component:
1. Read the implementation
2. Check for proper error handling
3. Check for concurrency safety
4. Verify tests exist

#### Step 5: Database Analysis
1. Check migration files in `internal/db/migrations/`
2. Verify all tables exist
3. Check schema matches blueprint

#### Step 6: Critical Issue Detection
Look for:
- Methods that panic instead of returning errors
- Race conditions
- Resource leaks
- Unhandled error cases
- Missing interface methods
- Inconsistent naming

#### Step 7: Bug Identification
- Run `go build ./...` - note any build errors
- Run `go vet ./...` - note any vet warnings
- Run tests - note failures
- Check for known anti-patterns

---

### 5. FIX INSTRUCTION FORMAT

For each issue found, provide:

```markdown
### [ISSUE-ID]: [Short Title]

**Type**: [Gap|Critical Issue|Bug|Improvement]
**Severity**: [Critical|High|Medium|Low]
**Category**: [correctness|performance|security|maintainability]

**Location**: 
- File: `path/to/file.go`
- Line: ~123
- Function: `FunctionName`

**Description**:
[Clear description of the issue - what it is, why it's a problem]

**Expected Behavior**:
[What should happen according to BLUEPRINT or Go best practices]

**Actual Behavior**:
[What actually happens in the codebase]

**Impact**:
[What breaks or could break due to this issue]

**Reproduction Steps**:
```
1. Step one
2. Step two
3. Step three
```

**Fix Instructions**:
```go
// BEFORE (problematic code):
[code snippet]

// AFTER (fixed code):
[code snippet]
```

**Estimated Effort**: [X hours/X days]
**Prerequisites**: [Any dependencies or context needed]
```

---

### 6. VERIFICATION COMMANDS

Run these to verify your analysis:

```bash
# Build check
cd /home/fulvio/coding/aria
go build ./...

# Vet check
go vet ./...

# Test check  
go test ./... 2>&1 | grep -E "(FAIL|PASS|ok)"

# Interface compliance (example for agency)
grep -r "type.*interface" internal/aria/agency/
grep -r "func.*Agency" internal/aria/agency/ | head -20

# Count implementations
find internal/aria -name "*.go" -exec grep -l "func.*Skill" {} \;
```

---

### 7. OUTPUT REQUIREMENTS

1. **Location**: `docs/analysis/blueprint-alignment-report.md`
2. **Format**: Valid Markdown
3. **Encoding**: UTF-8
4. **Minimum Length**: Comprehensive - no less than 500 lines
5. **Sections**: All sections in template above must be present
6. **Actionability**: Every issue must have clear fix instructions

### Critical Requirements:
- [ ] Every interface from BLUEPRINT is analyzed
- [ ] Every key file is checked for existence
- [ ] Every gap has severity and fix instructions
- [ ] Every bug has reproduction steps
- [ ] Report is comprehensive enough for another developer to fix issues

---

### 8. HANDOFF NOTES

This analysis is being conducted to:
1. Identify deviations from architectural blueprint
2. Find critical bugs before they cause issues
3. Provide actionable fix instructions
4. Enable informed decisions about FASE 5 continuation

**Success Criteria**:
- Report identifies 100% of interface gaps
- Report identifies all critical bugs
- Every issue has actionable fix instructions
- Another developer could fix issues from the report alone

---

## START ANALYSIS

Begin your comprehensive analysis now. Create the report at `docs/analysis/blueprint-alignment-report.md`.

Remember:
- Be thorough - missing issues is worse than over-reporting
- Be precise - exact file paths and line numbers
- Be actionable - every issue needs fix instructions
- Be systematic - follow the phase-by-phase structure

Good luck, Codex. The future of ARIA depends on your analysis.
