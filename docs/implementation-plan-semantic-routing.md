# Knowledge Agency Semantic Routing - Implementation Plan

**Branch**: `feature/knowledge-agency-semantic-routing`
**Worktree**: `.worktrees/knowledge-agency-routing`
**Status**: IN PROGRESS
**Started**: 2026-03-31

---

## Executive Summary

Implementare le raccomandazioni del report `docs/analysis/2026-03-31-knowledge-agency-routing-analysis.md`:
- P0: Semantic Router con embeddings + Fix parallelismo fittizio
- P1: LLM-based Query Classifier (futuro)
- P2: Memory-driven routing + Policy engine (futuro)

---

## P0: Semantic Router Implementation

### Problem
Il TaskRouter usa `strings.Contains()` per classificare i task, causando routing impreciso per query con significati equivalenti ma parole diverse.

### Solution
Implementare `SemanticTaskRouter` che usa embeddings per similarity-based routing.

### Files to Modify/Create

1. **Create**: `internal/aria/agency/semantic_router.go`
   - `SemanticTaskRouter` struct con embeddings model
   - `Route()` method con cosine similarity
   - Fallback a keyword se threshold non raggiunto

2. **Modify**: `internal/aria/agency/knowledge_supervisor.go`
   - Integrare `SemanticTaskRouter` come fallback
   - Mantenere keyword routing per backward compatibility

3. **Create**: `internal/aria/agency/semantic_router_test.go`
   - Test per similarity matching
   - Test per fallback behavior

### Acceptance Criteria
- [ ] Query "trova paper recenti su ML" → CategoryAcademic (non keyword "arxiv")
- [ ] Query "cercalo su arxiv" → CategoryAcademic (keyword fallback funziona)
- [ ] Test coverage ≥ 80%

---

## P0: Fix executeParallel() - True Parallelism

### Problem
`KnowledgeAgency.executeParallel()` usa un for-loop sequenziale invece di goroutine.

### Solution
Usare goroutine con bounded semaphore come in `WorkflowEngine.executeParallel()`.

### Files to Modify

1. **Modify**: `internal/aria/agency/knowledge.go`
   - Rifattorizzare `executeParallel()` con goroutine + sync
   - Bounded semaphore per maxConcurrentAgents

### Acceptance Criteria
- [ ] `executeParallel()` esegue agents in parallelo (verificare con goroutine)
- [ ] Risultati sintetizzati correttamente
- [ ] Test concurrency passano con `go test -race`

---

## P1: LLM-Based Query Classifier (Future)

### Files to Create
- `internal/aria/routing/llm_classifier.go`
- `internal/aria/routing/llm_classifier_test.go`

---

## P2: Memory-Driven Routing (Future)

### Files to Modify
- `internal/aria/core/orchestrator_impl.go`
- Integrare feedback loop con AdjustRoutingBasedOnMemory()

---

## Implementation Notes

### Semantic Router Design

```go
type SemanticTaskRouter struct {
    embeddings model.EmbeddingModel
    agentDescriptions map[TaskCategory][]float32
    threshold float32
    fallbackRouter *TaskRouter  // Keyword-based fallback
}

func (r *SemanticTaskRouter) Route(task contracts.Task) (*RegisteredAgent, error) {
    // 1. Encode task description
    queryVec := r.embeddings.Encode(task.Description)
    
    // 2. Find best matching category by similarity
    bestCategory := TaskCategoryGeneral
    bestScore := float32(0)
    
    for category, descVec := range r.agentDescriptions {
        score := cosineSimilarity(queryVec, descVec)
        if score > r.threshold && score > bestScore {
            bestScore = score
            bestCategory = category
        }
    }
    
    // 3. If no semantic match, fallback to keyword
    if bestScore < r.threshold {
        return r.fallbackRouter.Route(task)
    }
    
    // 4. Return agent for category
    agents := r.registry.GetByCategory(bestCategory)
    return agents[0], nil  // First agent for now
}
```

### Embedding Models Supported
- OpenAI `text-embedding-3-small`
- Local: `nomic-embed-text`, `all-MiniLM-L6-v2`
- Configurable via `EMBEDDING_PROVIDER` env var

---

## Verification Commands

```bash
# Build
cd .worktrees/knowledge-agency-routing
go build ./...

# Test routing
go test ./internal/aria/routing/... -v

# Test agency
go test ./internal/aria/agency/... -v

# Race detection
go test -race ./internal/aria/agency/...

# Benchmark
go test -bench=. ./internal/aria/agency/ -benchtime=1000x
```

---

## Dependencies

- Embedding provider (OpenAI or local via LM Studio)
- `internal/aria/contracts` (already exists)
- `internal/aria/agency/knowledge_supervisor.go` (existing)
