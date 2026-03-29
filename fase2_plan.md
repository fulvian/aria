# ARIA FASE 2: Memory & Learning - Implementation Plan

## Executive Summary

**FASE 2** implementa il sistema di memoria evolutivo di ARIA, permettendo all'assistente di apprendere dalle interazioni passate, memorizzare conoscenze, e migliorare continuamente.

## Current State Analysis

### Already in Place (from FASE 1 completion)
- ✅ Database schema with `episodes`, `facts`, `procedures` tables
- ✅ SQL queries for CRUD operations (sqlc generated)
- ✅ Type definitions in `internal/aria/memory/memory.go` (interface only)
- ✅ Self-analysis types in `internal/aria/analysis/self_analysis.go` (interface only)
- ✅ Blueprint Section 3.2 defines `MemoryService` interface
- ✅ Blueprint Section 6.1 defines `SelfAnalysisService` interface

### What Needs to Be Built
1. **MemoryService implementation** - No implementation exists
2. **SelfAnalysisService implementation** - No implementation exists
3. **Learning loop** - Pattern extraction and procedure generation
4. **Vector storage** - SQLite-vec integration for embeddings (optional MVP)

---

## Detailed Task Breakdown

### Phase 2.1: Memory Service Implementation

#### Task 2.1.1: Core Memory Service Structure
**File**: `internal/aria/memory/service.go` (NEW)
**Priority**: CRITICAL
**Estimate**: 4-6 hours

```go
type memoryService struct {
    db           *db.Queries
    workingMemory sync.Map  // sessionID -> Context
    embeddings   Embedder   // interface for vector operations
}

func NewMemoryService(db *db.Queries, embedder Embedder) *memoryService
```

**Deliverables**:
- [ ] `memoryService` struct with db, workingMemory, embeddings
- [ ] `NewMemoryService()` constructor
- [ ] Working memory implementation (in-memory map with session context)
- [ ] Integration with existing `internal/db/querier.go` for episodic/semantic/procedural

#### Task 2.1.2: Working Memory Implementation
**File**: `internal/aria/memory/service.go`
**Priority**: CRITICAL
**Estimate**: 2-3 hours

**Methods to implement**:
```go
func (m *memoryService) GetContext(ctx context.Context, sessionID string) (Context, error)
func (m *memoryService) SetContext(ctx context.Context, sessionID string, context Context) error
```

**Implementation notes**:
- Use `sync.Map` for thread-safe in-memory storage
- Session context includes: messages, files being edited, current task, metadata
- No persistence for working memory (ephemeral per session)

#### Task 2.1.3: Episodic Memory Implementation
**File**: `internal/aria/memory/service.go`
**Priority**: CRITICAL
**Estimate**: 3-4 hours

**Methods to implement**:
```go
func (m *memoryService) RecordEpisode(ctx context.Context, episode Episode) error
func (m *memoryService) SearchEpisodes(ctx context.Context, query EpisodeQuery) ([]Episode, error)
func (m *memoryService) GetSimilarEpisodes(ctx context.Context, situation Situation) ([]Episode, error)
```

**Implementation notes**:
- Use `db.CreateEpisode()`, `db.SearchEpisodes()` from querier
- For similarity search (GetSimilarEpisodes), use embedding-based search if available
- Fallback to keyword search using `db.SearchEpisodes()`

#### Task 2.1.4: Semantic Memory Implementation
**File**: `internal/aria/memory/service.go`
**Priority**: HIGH
**Estimate**: 2-3 hours

**Methods to implement**:
```go
func (m *memoryService) StoreFact(ctx context.Context, fact Fact) error
func (m *memoryService) GetFacts(ctx context.Context, domain string) ([]Fact, error)
func (m *memoryService) QueryKnowledge(ctx context.Context, query string) ([]KnowledgeItem, error)
```

**Implementation notes**:
- Use `db.CreateFact()`, `db.ListFactsByDomain()`, `db.SearchFacts()`
- Increment `use_count` on `GetFacts()` for frequently used facts
- `QueryKnowledge()` uses full-text search on facts

#### Task 2.1.5: Procedural Memory Implementation
**File**: `internal/aria/memory/service.go`
**Priority**: HIGH
**Estimate**: 2-3 hours

**Methods to implement**:
```go
func (m *memoryService) SaveProcedure(ctx context.Context, procedure Procedure) error
func (m *memoryService) GetProcedure(ctx context.Context, name string) (Procedure, error)
func (m *memoryService) FindApplicableProcedures(ctx context.Context, task map[string]any) ([]Procedure, error)
```

**Implementation notes**:
- Use `db.CreateProcedure()`, `db.GetProcedureByName()`, `db.SearchProcedures()`
- `FindApplicableProcedures()` matches task type/context against trigger patterns
- Update `success_rate` after each procedure use

---

### Phase 2.2: Learning Loop

#### Task 2.2.1: Learning from Experience
**File**: `internal/aria/memory/learning.go` (NEW)
**Priority**: HIGH
**Estimate**: 4-5 hours

**Methods to implement**:
```go
func (m *memoryService) LearnFromSuccess(ctx context.Context, action Action, outcome string) error
func (m *memoryService) LearnFromFailure(ctx context.Context, action Action, err error) error
```

**Learning algorithm**:
1. Record the action in episodic memory
2. If success pattern detected (same action + positive outcome):
   - Update procedure success rate
   - Potentially extract new procedure if not exists
3. If failure detected:
   - Record failure details
   - Suggest fix in next analysis

#### Task 2.2.2: Pattern Extraction
**File**: `internal/aria/memory/patterns.go` (NEW)
**Priority**: MEDIUM
**Estimate**: 3-4 hours

**Functions**:
```go
// ExtractPatterns analyzes episodes to find recurring patterns
func ExtractPatterns(episodes []Episode) ([]WorkflowPattern, error)

// DetectRecurringTasks finds tasks that repeat over time
func DetectRecurringTasks(episodes []Episode) ([]RecurringPattern, error)
```

**Implementation notes**:
- Look for sequences of actions that appear repeatedly
- Group by task type and outcome
- Calculate success rates per pattern

#### Task 2.2.3: Procedure Generation
**File**: `internal/aria/memory/procedures.go` (NEW)
**Priority**: MEDIUM
**Estimate**: 2-3 hours

**Functions**:
```go
// GenerateProcedure creates a new procedure from successful episode sequence
func GenerateProcedure(episode Episode) (Procedure, error)

// ImproveProcedure updates procedure based on feedback
func ImproveProcedure(procedure Procedure, feedback Feedback) (Procedure, error)
```

**Implementation notes**:
- Trigger: Same task type + same actions + 3+ consecutive successes
- Steps extracted from episode actions
- Success rate starts at 0.75 for auto-generated procedures

---

### Phase 2.3: Self-Analysis Service

#### Task 2.3.1: Self-Analysis Service Implementation
**File**: `internal/aria/analysis/service.go` (NEW)
**Priority**: CRITICAL
**Estimate**: 5-6 hours

```go
type selfAnalysisService struct {
    memory  memory.MemoryService
    tasks   scheduler.SchedulerService  // or direct DB access
    agencies agency.Registry
}

func NewSelfAnalysisService(memory memory.MemoryService, ...) *selfAnalysisService
```

**Methods to implement**:
```go
func (s *selfAnalysisService) RunPeriodicAnalysis(ctx context.Context) error
func (s *selfAnalysisService) AnalyzePerformance(ctx context.Context, timeRange TimeRange) (PerformanceReport, error)
func (s *selfAnalysisService) AnalyzePatterns(ctx context.Context) (PatternReport, error)
func (s *selfAnalysisService) AnalyzeFailures(ctx context.Context) (FailureReport, error)
func (s *selfAnalysisService) GenerateImprovements(ctx context.Context) ([]Improvement, error)
func (s *selfAnalysisService) ApplyInsights(ctx context.Context, insights []Improvement) error
```

#### Task 2.3.2: Performance Metrics Collection
**File**: `internal/aria/analysis/metrics.go` (NEW)
**Priority**: HIGH
**Estimate**: 3-4 hours

**Implementation**:
- Query `tasks` table for completed tasks in time range
- Calculate: total tasks, success rate, average duration
- Group by agency, agent, skill using task records
- Identify trends by comparing consecutive time periods

#### Task 2.3.3: Periodic Analysis Jobs
**File**: `internal/aria/analysis/scheduler.go` (NEW)
**Priority**: MEDIUM
**Estimate**: 2-3 hours

**Implementation**:
- Run analysis every 24 hours (configurable)
- Generate insights automatically
- Store insights in semantic memory as facts
- Could use existing scheduler from FASE 3 or simple goroutine

---

### Phase 2.4: Vector Storage (Optional MVP)

#### Task 2.4.1: Embedder Interface
**File**: `internal/aria/memory/embedder.go` (NEW)
**Priority**: MEDIUM (needed for similarity search)
**Estimate**: 2-3 hours

```go
type Embedder interface {
    // Embed generates embedding vector for text
    Embed(ctx context.Context, text string) ([]float32, error)
    
    // SearchSimilar finds similar items using cosine similarity
    SearchSimilar(ctx context.Context, collection string, query []float32, limit int) ([]SimilarityResult, error)
}

// SQLiteVecEmbedder implements Embedder using sqlite-vec
type SQLiteVecEmbedder struct {
    db *sql.DB
}
```

#### Task 2.4.2: SQLite-Vec Integration
**File**: `internal/aria/memory/embedder.go`
**Priority**: MEDIUM
**Estimate**: 4-5 hours

**Implementation notes**:
- Use `github.com/nicola-spb/sqlite-vec` or similar
- Create `embeddings` virtual table in SQLite
- Store episode embeddings for similarity search
- For MVP: could use simple keyword similarity instead of vectors

---

## Deliverables Checklist

### Phase 2.1: Memory Service
- [ ] `internal/aria/memory/service.go` - Core MemoryService implementation
- [ ] Working memory (GetContext/SetContext)
- [ ] Episodic memory (RecordEpisode/SearchEpisodes/GetSimilarEpisodes)
- [ ] Semantic memory (StoreFact/GetFacts/QueryKnowledge)
- [ ] Procedural memory (SaveProcedure/GetProcedure/FindApplicableProcedures)

### Phase 2.2: Learning Loop
- [ ] `internal/aria/memory/learning.go` - Learning implementation
- [ ] `internal/aria/memory/patterns.go` - Pattern extraction
- [ ] `internal/aria/memory/procedures.go` - Procedure generation
- [ ] LearnFromSuccess / LearnFromFailure methods

### Phase 2.3: Self-Analysis
- [ ] `internal/aria/analysis/service.go` - SelfAnalysisService implementation
- [ ] `internal/aria/analysis/metrics.go` - Metrics collection
- [ ] Periodic analysis job
- [ ] All analysis methods implemented

### Phase 2.4: Vector Storage
- [ ] `internal/aria/memory/embedder.go` - Embedder interface (if time permits)
- [ ] SQLite-vec integration (optional, can fallback to keyword search)

### Testing
- [ ] Unit tests for memory service methods
- [ ] Unit tests for learning algorithms
- [ ] Integration tests with database

---

## Technical Notes

### Dependencies
- Uses existing `internal/db.Queries` from sqlc-generated code
- Uses existing `internal/aria/agency.AgencyName` types
- Uses existing `internal/aria/skill.SkillName` types
- No new external dependencies for MVP (vector storage optional)

### Risks
1. **Performance**: Episodic memory queries without proper indexing could be slow
   - Mitigation: Use existing indexes in episodes table
2. **Vector storage**: sqlite-vec may require additional setup
   - Mitigation: Implement keyword fallback for MVP
3. **Learning quality**: Auto-generated procedures may not be useful
   - Mitigation: Require 3+ successes before procedure generation, human review flag

---

## Timeline Estimate

| Task | Estimate |
|------|----------|
| 2.1.1-2.1.5 Memory Service | 13-19 hours |
| 2.2.1-2.2.3 Learning Loop | 9-12 hours |
| 2.3.1-2.3.3 Self-Analysis | 10-13 hours |
| 2.4.1-2.4.2 Vector Storage (optional) | 6-8 hours |
| Testing | 8-10 hours |
| **Total** | **40-54 hours** (6-8 weeks at ~8h/week) |

---

## Next Steps After FASE 2

**FASE 3: Scheduling** - Task scheduler with persistent tasks, cron-like scheduling, dependencies

---

## Decisions Required

1. **Vector storage approach**: Use sqlite-vec (requires native library) or keyword fallback?
2. **Learning aggressiveness**: Auto-apply procedure improvements or require confirmation?
3. **Analysis frequency**: Run analysis on fixed schedule or event-driven?
