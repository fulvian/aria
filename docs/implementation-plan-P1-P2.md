# Knowledge Agency - P1/P2 Implementation Plan

**Branch**: `feature/knowledge-agency-semantic-routing`
**Worktree**: `.worktrees/knowledge-agency-routing`
**Status**: IN PROGRESS
**Started**: 2026-04-01

---

## P1: LLM-Based Query Classifier

### Problem
`BaselineClassifier` usa keyword matching per determinare Intent/Domain/Complexity. Non capisce il significato.

### Solution
Implementare `LLMClassifier` che usa LLM per classificazione intelligente.

### Files to Create

1. **`internal/aria/routing/llm_classifier.go`**
   - `LLMClassifier` struct
   - Uses existing LLM provider infrastructure
   - Returns Classification with confidence from LLM

2. **`internal/aria/routing/llm_classifier_test.go`**
   - Mock LLM provider
   - Test classification accuracy

### Implementation

```go
type LLMClassifier struct {
    provider llm.Provider
    systemPrompt string
}

func (c *LLMClassifier) Classify(ctx context.Context, query routing.Query) (routing.Classification, error) {
    prompt := fmt.Sprintf(`Classify this query:
Query: %s
History: %v

Return JSON with:
- intent: one of [question, task, creation, analysis, learning, planning, conversation]
- domain: one of [general, development, knowledge, creative, productivity, personal, analytics]
- complexity: one of [simple, medium, complex]
- urgency: one of [now, soon, eventually]
- confidence: float 0.0-1.0

Example response:
{"intent":"question","domain":"knowledge","complexity":"simple","urgency":"now","confidence":0.9}`, query.Text, query.History)
    
    resp, err := c.provider.Generate(ctx, llm.Request{Messages: []llm.Message{{Role: "user", Content: prompt}}})
    if err != nil {
        return routing.Classification{}, err
    }
    
    return parseClassification(resp.Content)
}
```

### Acceptance Criteria
- [ ] LLMClassifier classifies queries with intent, domain, complexity
- [ ] Confidence score from LLM reasoning
- [ ] Fallback to BaselineClassifier on LLM failure
- [ ] Test coverage ≥ 80%

---

## P1: Planner/Critic Pattern for Knowledge Agency

### Problem
Nessun quality gate prima della delivery. Output può essere low-quality.

### Solution
Implementare `KnowledgeCritic` per quality assessment con:
- Confidence scoring
- Citation validation
- Contradiction detection

### Files to Create

1. **`internal/aria/agency/knowledge_critic.go`**
   - `KnowledgeCritic` struct
   - `Review()` method con quality scoring
   - `QualityGate` per pass/fail decision

2. **`internal/aria/agency/knowledge_critic_test.go`**

### Implementation

```go
type KnowledgeCritic struct{}

type ReviewResult struct {
    QualityScore float64  // 0.0-1.0
    Confidence   float64
    Contradictions []string
    CitationsValid bool
    Unknowns      []string
    Pass          bool
    Reasons       []string
}

func (c *KnowledgeCritic) Review(task contracts.Task, result map[string]any) *ReviewResult {
    score := c.calculateQualityScore(result)
    confidence := c.assessConfidence(result)
    contradictions := c.detectContradictions(result)
    citationsValid := c.validateCitations(result)
    unknowns := c.identifyUnknowns(result)
    
    pass := score >= 0.7 && len(contradictions) == 0 && citationsValid
    
    return &ReviewResult{
        QualityScore: score,
        Confidence: confidence,
        Contradictions: contradictions,
        CitationsValid: citationsValid,
        Unknowns: unknowns,
        Pass: pass,
        Reasons: c.explain(score, contradictions, citationsValid),
    }
}

func (c *KnowledgeCritic) calculateQualityScore(result map[string]any) float64 {
    score := 0.5
    // Boost for presence of evidence/citations
    if results, ok := result["results"].([]any); ok && len(results) > 0 {
        score += 0.1 * math.Min(float64(len(results)), 3)
    }
    // Boost for summary
    if _, ok := result["summary"].(string); ok {
        score += 0.1
    }
    // Cap at 1.0
    return math.Min(score, 1.0)
}
```

### Acceptance Criteria
- [ ] Critic reviews results and assigns quality score
- [ ] Contradiction detection between sources
- [ ] Citation validation
- [ ] Pass/fail gate at 0.7 quality threshold

---

## P2: Memory-Driven Routing Adaptation

### Problem
Feedback loop esiste (`RecordRoutingFeedback`) ma non modifica il routing behavior.

### Solution
Chiudere il loop: success/failure learnings → routing policy adjustment.

### Files to Modify

1. **`internal/aria/core/orchestrator_impl.go`**
   - `AdjustRoutingBasedOnMemory()` method
   - Periodic adjustment using memory episodes

2. **`internal/aria/memory/feedback_analyzer.go`** (new)
   - Analyze routing patterns from memory
   - Generate routing improvements

### Implementation

```go
func (o *BasicOrchestrator) AdjustRoutingBasedOnMemory() {
    if o.memoryService == nil {
        return
    }
    
    // Get recent episodes from memory
    episodes := o.memoryService.GetRecentEpisodes(ctx, 100)
    if len(episodes) < 10 {
        return
    }
    
    // Calculate success rate by agency
    stats := calculateAgencyStats(episodes)
    
    // Adjust routing policy based on performance
    for agency, rate := range stats.successRates {
        if rate > 0.9 {
            // Boost confidence for high-performer
            o.policyRouter.BoostAgencyConfidence(agency, 0.1)
        } else if rate < 0.5 {
            // Reduce confidence for low-performer
            o.policyRouter.ReduceAgencyConfidence(agency, 0.1)
        }
    }
}

func calculateAgencyStats(episodes []memory.Episode) AgencyStats {
    stats := make(map[string]*AgencyStat)
    for _, ep := range episodes {
        agency := ep.AgencyID
        if stats[agency] == nil {
            stats[agency] = &AgencyStat{}
        }
        stats[agency].total++
        if ep.Outcome != "failure" {
            stats[agency].successes++
        }
    }
    return stats
}
```

### Acceptance Criteria
- [ ] Routing policy auto-adjusts based on success rates
- [ ] Memory episodes analyzed for routing patterns
- [ ] High-performers boosted, low-performers penalized
- [ ] Configurable adaptation threshold

---

## P2: Policy Engine for Tool Governance

### Problem
Nessun policy engine per tool invocation. Tool ad alto rischio eseguiti senza gate.

### Solution
Implementare `ToolPolicyEngine` con:
- Allow/Ask/Deny per classi di tool
- Risk-based gating
- User confirmation per ask

### Files to Create

1. **`internal/aria/agency/tool_policy.go`**
   - `ToolPolicy` struct
   - `PolicyEngine` interface
   - `Decision` enum (Allow, Ask, Deny)

2. **`internal/aria/agency/tool_policy_test.go`**

### Implementation

```go
type ToolPolicy struct {
    AllowList []string  // Tools always allowed
    AskList   []string  // Tools requiring confirmation
    DenyList  []string  // Tools always denied
}

type Decision string
const (
    DecisionAllow Decision = "allow"
    DecisionAsk  Decision = "ask"
    DecisionDeny Decision = "deny"
)

type PolicyEngine struct {
    agentPolicies map[string]*ToolPolicy
    riskClassifier RiskClassifier
}

func (e *PolicyEngine) CheckTool(tool string, agent string) (Decision, error) {
    policy, ok := e.agentPolicies[agent]
    if !ok {
        policy = e.defaultPolicy
    }
    
    switch {
    case contains(policy.DenyList, tool):
        return DecisionDeny, nil
    case contains(policy.AskList, tool):
        return DecisionAsk, nil
    case contains(policy.AllowList, tool):
        return DecisionAllow, nil
    default:
        // Use risk classifier for unknown tools
        risk := e.riskClassifier.Classify(tool)
        if risk >= RiskHigh {
            return DecisionAsk, nil
        }
        return DecisionAllow, nil
    }
}

type RiskClassifier struct{}

func (c *RiskClassifier) Classify(tool string) RiskLevel {
    // Heuristic risk classification
    highRisk := []string{"bash", "write", "edit", "delete", "exec", "sudo"}
    for _, t := range highRisk {
        if strings.Contains(strings.ToLower(tool), t) {
            return RiskHigh
        }
    }
    return RiskLow
}
```

### Acceptance Criteria
- [ ] ToolPolicyEngine with Allow/Ask/Deny decisions
- [ ] Risk-based gating for unknown tools
- [ ] Agent-specific policies
- [ ] Default policies for new agents

---

## Implementation Order

1. **P1-A**: LLM-based Query Classifier (priority: high)
2. **P1-B**: Knowledge Critic with quality gates (priority: high)
3. **P2-A**: Memory-driven routing adaptation (priority: medium)
4. **P2-B**: Policy engine for tool governance (priority: medium)

---

## Verification Commands

```bash
cd .worktrees/knowledge-agency-routing

# Build
go build ./...

# Test individual packages
go test ./internal/aria/routing/... -v
go test ./internal/aria/agency/... -v

# Full test suite with race
go test -race ./internal/aria/...

# Benchmarks
go test -bench=. ./internal/aria/agency/... -benchtime=100x
```

---

## Dependencies

- LLM provider (existing in `internal/llm/provider/`)
- Memory service (existing in `internal/aria/memory/`)
- Policy router (existing in `internal/aria/routing/`)

---

## Notes

### TDD Approach
1. Write failing test first
2. Implement minimal code to pass
3. Refactor for clarity
4. Verify all tests still pass

### YAGNI
- Focus on current requirements
- Don't speculatively add features
- Simple implementation first, optimize later
