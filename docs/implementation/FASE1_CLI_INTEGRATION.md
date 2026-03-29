# ARIA FASE 1: CLI Integration Implementation Plan

> **Status**: ✅ COMPLETE  
> **Started**: 2026-03-28  
> **Completed**: 2026-03-28  
> **Goal**: Complete CLI Integration to wire ARIA mode to prompt loop

## Background

From BLUEPRINT.md Section 8.3 (FASE 1 - Core System):
- **Status**: IN PROGRESS (~20%)
- **Next Milestone**: CLI Integration - wire ARIA mode to prompt loop
- **Blocking Items**: Task execution flow not implemented

## Current State Analysis

### Completed Components
| Component | File(s) | Status |
|-----------|---------|--------|
| Orchestrator Interface | `internal/aria/core/orchestrator.go` | ✅ Complete |
| BasicOrchestrator | `internal/aria/core/orchestrator_impl.go` | ✅ Complete (stub) |
| Agency Interface | `internal/aria/agency/agency.go` | ✅ Complete |
| DevelopmentAgency | `internal/aria/agency/development.go` | ✅ Complete (stub) |
| Skill Interface | `internal/aria/skill/skill.go` | ✅ Complete |
| Skill Registry | `internal/aria/skill/registry.go` | ✅ Complete |
| CodeReview Skill | `internal/aria/skill/code_review.go` | ✅ Stub |
| TDDSkill | `internal/aria/skill/tdd.go` | ✅ Stub |
| DebuggingSkill | `internal/aria/skill/debugging.go` | ✅ Stub |
| QueryClassifier | `internal/aria/routing/classifier_impl.go` | ✅ Complete |
| DefaultRouter | `internal/aria/routing/router_impl.go` | ✅ Complete |
| Config Integration | `internal/config/config.go` | ✅ Complete |
| App Integration | `internal/app/aria_integration.go` | ✅ Init complete |

### Missing/Broken Components

1. **Orchestrator.ProcessQuery()** - Only returns routing metadata, no execution
2. **CoderBridge.RunTask()** - Returns placeholder, doesn't call legacy agent
3. **Skills** - Return hardcoded results, no tool execution
4. **Response.Text** - Always empty

## Implementation Tasks

### Task 1: Implement Task Execution Flow
**Files to modify**: `internal/aria/core/orchestrator_impl.go`

**Current behavior**:
```go
func (o *BasicOrchestrator) ProcessQuery(...) (Response, error) {
    // Classifies query
    // Routes query  
    // Returns only metadata (Agency, Skills, Confidence) - NO CONTENT
}
```

**Required behavior**:
```go
func (o *BasicOrchestrator) ProcessQuery(...) (Response, error) {
    // Classify query
    // Route query
    // Create Task from routing decision
    // Execute Task through Agency
    // Get result and generate Response.Text
    // Return Response with content
}
```

**Changes needed**:
1. Add `ExecuteTask()` method to orchestrator
2. After routing, create `agency.Task` with parameters
3. Get target agency from registry
4. Call `agency.Execute(ctx, task)`
5. Convert `agency.Result` to `Response.Text`

### Task 2: Complete CoderBridge Integration
**Files to modify**: `internal/aria/agency/development.go`

**Current behavior**:
```go
func (b *CoderBridge) RunTask(ctx context.Context, task Task) (map[string]any, error) {
    // Returns placeholder with "delegated_to_legacy" status
    return map[string]any{
        "status": "delegated_to_legacy",
        "note":   "CoderBridge integration pending...",
    }, nil
}
```

**Required behavior**:
```go
func (b *CoderBridge) RunTask(ctx context.Context, task Task) (map[string]any, error) {
    // Extract session ID and prompt from task parameters
    // Call legacy coder agent via agent.Run(ctx, sessionID, prompt)
    // Handle streaming response
    // Return actual result
}
```

**Challenges**:
- Legacy agent uses `agent.Run()` which returns `<-chan AgentEvent` (streaming)
- Need to handle async streaming within sync `RunTask` interface
- May need to create internal session for ARIA tasks

**Solution approach**:
1. Store `*App` reference in CoderBridge for access to `CoderAgent`
2. Create a session for the task
3. Run agent and collect events
4. Return structured result

### Task 3: Skill Tool Integration
**Files to modify**: `internal/aria/skill/code_review.go`, `skill/tdd.go`, `skill/debugging.go`

**Current behavior**:
```go
func (s *CodeReviewSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
    // Returns hardcoded findings
    return SkillResult{
        Output: map[string]any{
            "findings": []map[string]any{{...hardcoded...}},
        },
    }, nil
}
```

**Required behavior**:
```go
func (s *CodeReviewSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
    // 1. Get tools from context (or create tool instances)
    // 2. Use glob tool to find files
    // 3. Use grep tool to search patterns
    // 4. Use view tool to read file contents
    // 5. Perform analysis
    // 6. Return actual findings
}
```

**Tool access options**:
- Option A: Pass tools through SkillParams.Context
- Option B: Create skill-specific tool instances
- Option C: Use existing tool implementations

### Task 4: Response Content Generation
**Files to modify**: `internal/aria/core/orchestrator_impl.go`

**Required**: Generate meaningful text response from task execution result

```go
func generateResponse(result agency.Result) string {
    // Format result into human-readable text
    // Include task outcome, findings, errors
    // Use templates or string formatting
}
```

## File Dependency Graph

```
app.go (runARIA)
    │
    ├── orchestrator.ProcessQuery()
    │       │
    │       ├── classifier.Classify()
    │       ├── router.Route()
    │       │
    │       └── [NEW] ExecuteThroughAgency()
    │               │
    │               └── agency.Execute()
    │                       │
    │                       ├── DeveloperAgency.GetAgent()
    │                       │       │
    │                       │       └── [NEW] CoderBridge.RunTask()
    │                       │               │
    │                       │               └── [NEW] InvokeLegacyAgent()
    │                       │                       │
    │                       │                       └── agent.Run() → AgentEvent
    │                       │
    │                       └── [NEW] SkillExecutor
    │                               │
    │                               └── skill.Execute()
    │                                       │
    │                                       └── [NEW] ToolInvocation
    │
    └── format.Output()
```

## Implementation Order

1. **Phase 1A**: Fix CoderBridge to call legacy agent (stub first)
2. **Phase 1B**: Add agency execution to orchestrator
3. **Phase 1C**: Wire response generation
4. **Phase 2**: Real skill tool integration
5. **Phase 3**: TUI ARIA mode

## Testing Strategy

1. **Unit tests**: Test each component in isolation
2. **Integration tests**: Test full flow in non-interactive mode
3. **Manual verification**: Test `-p "prompt"` flag

## Success Criteria

- [x] `go build -o opencode ./main.go` succeeds
- [x] `go vet ./...` passes with no issues
- [x] Orchestrator.ProcessQuery executes task through Agency
- [x] CoderBridge.RunTask calls legacy agent and returns content
- [x] Response.Text populated from task execution result
- [ ] Full E2E test: `go run ./main.go -p "review my code"` produces output (requires LLM API key)
- [ ] Full E2E test: `go run ./main.go -p "debug this bug"` produces output (requires LLM API key)
- [ ] Full E2E test: `go run ./main.go -p "write tests"` produces output (requires LLM API key)

## Implementation Summary

### Completed Implementation

**1. CoderBridge (development.go)**
- Updated to accept actual `agent.Service`, `session.Service`, `message.Service` (not `any`)
- `RunTask()` now:
  - Extracts prompt from task parameters
  - Creates a new session for the task
  - Calls legacy agent's `Run()` method
  - Collects streaming events to get the response
  - Returns structured result with actual content

**2. DevelopmentAgency**
- `NewDevelopmentAgency()` now accepts and passes services to CoderBridge
- Full integration with session management

**3. Orchestrator (orchestrator_impl.go)**
- `ProcessQuery()` now:
  - Creates `agency.Task` from query after routing
  - Gets target agency from registry
  - Calls `agency.Execute()` 
  - Extracts response content from `result.Output["response"]`
  - Falls back to legacy mode if agency not found

**4. App Integration (aria_integration.go)**
- `initARIA()` passes `app.Sessions` and `app.Messages` to `NewDevelopmentAgency()`

### Files Modified

1. `/home/fulvio/coding/aria/internal/aria/agency/development.go`
2. `/home/fulvio/coding/aria/internal/app/aria_integration.go`
3. `/home/fulvio/coding/aria/internal/aria/core/orchestrator_impl.go`

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| N/A | - | - |

## Change Log

| Date | Change | Notes |
|------|--------|-------|
| 2026-03-28 | Initial plan | Created based on BLUEPRINT.md analysis |
