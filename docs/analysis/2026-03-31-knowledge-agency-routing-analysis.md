# Analisi Architetturale: Knowledge Agency & Orchestratore ARIA

**Data**: 2026-03-31  
**Versione Report**: 2.0  
**Status**: Critico - Richiede Intervento Immediato  
**Target**: Sistema di Knowledge Agency + Orchestratore  

---

## Executive Summary

L'architettura attuale del Knowledge Agency e dell'Orchestratore presenta **deviazioni significative** dalle best practice SOTA 2026 per sistemi multi-agente. Il problema centrale identificato: **il routing è completamente ordinal-keyword-based**, non intelligente/semantico.

### Valutazione Complessiva

| Componente | Maturità | Criticità |
|------------|----------|-----------|
| Orchestratore (core) | 6/10 | Alta |
| Knowledge Agency Router | 4/10 | Critica |
| Task Supervisor | 5/10 | Alta |
| Synthesis Engine | 5/10 | Media |
| Memory Loop | 3/10 | Critica |
| Governance/Policy | 2/10 | Critica |

### Diagnosi Root Cause

```
Il sistema utilizza string matching keyword-based invece di:
1. Semantic routing (embeddings/similarity)
2. LLM-based intelligent classification  
3. Dynamic capability-based routing
```

---

## 1. Analisi dell'Orchestratore (Core)

### 1.1 Architettura Attuale

```
ProcessQuery Flow:
┌─────────────────────────────────────────────────────────────────────┐
│  Query → Memory Service (context retrieval)                         │
│        → BaselineClassifier (keyword intent/domain detection)        │
│        → PolicyRouter (rules-based routing)                         │
│        → Agency Execute                                             │
│        → Memory LearnFromSuccess/Failure                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 BaselineClassifier - Il Problema Centrale

**File**: `internal/aria/routing/classifier_impl.go`

```go
func (c *BaselineClassifier) classifyIntent(text string) Intent {
    // PROBLEMA: Simple string.Contains - NO semantic understanding
    questionWords := []string{"what", "how", "why", "when", "where", "who", "which", "?"}
    for _, word := range questionWords {
        if strings.Contains(text, word) {  // ← Ordinal matching
            return IntentQuestion
        }
    }
    // ...
}
```

**Limiti**:
- Nessuna comprensione semantica
- Sensibile a variazioni lessicali
- No embeddings/similarity
- Confidence fisso a 0.5 + boost marginale

### 1.3 DefaultRouter - Routing Regola-Based

**File**: `internal/aria/routing/router_impl.go`

```go
func (r *DefaultRouter) matchesRule(rule RoutingRule, class Classification, text string) bool {
    // PROBLEMA: Pattern matching su stringhe lowercase
    if len(rule.QueryPatterns) > 0 {
        found := false
        for _, pattern := range rule.QueryPatterns {
            if strings.Contains(text, strings.ToLower(pattern)) {  // ← Ordinal
                found = true
                break
            }
        }
        // ...
    }
}
```

**Limiti**:
- Routing completamente statico
- Nessuna adattività runtime
- Nessun feedback loop per auto-tuning (nonostante esista `RecordRoutingFeedback`)

### 1.4 Punti di Forza dell'Orchestrator

1. **Feedback Loop esiste** (`RecordRoutingFeedback`, `AdjustRoutingPolicy`)
2. **Memory Service integration** per context retrieval
3. **Capability Registry** per agency/agent capabilities
4. **Policy Router** con struttura extensible
5. **Handoff strutturato** per agent communication

---

## 2. Analisi del Knowledge Agency Supervisor

### 2.1 Architettura Gerarchica Dichiarata

```
KnowledgeAgency:
├── TaskRouter (classificazione task)
├── AgentRegistry (agenti registrati)
├── WorkflowEngine (esecuzione workflow)
├── ResultSynthesizer (aggregazione risultati)
└── Legacy Bridges (researcher/educator/analyst)
```

### 2.2 TaskRouter - Classificazione Keyword-Based

**File**: `internal/aria/agency/knowledge_supervisor.go`

```go
func (r *TaskRouter) classifyTask(task contracts.Task) TaskCategory {
    desc := strings.ToLower(task.Description)
    name := strings.ToLower(task.Name)
    
    // PROBLEMA: Ordinal keyword matching
    if supervisorContainsAny(combined, "arxiv", "pubmed", "semantic scholar", ...) {
        return CategoryAcademic
    }
    if supervisorContainsAny(combined, "news", "current events", "breaking", ...) {
        return CategoryNews
    }
    // ...
}
```

**Funzione di Supporto**:
```go
func supervisorContainsAny(text string, substrs ...string) bool {
    for _, s := range substrs {
        if strings.Contains(text, s) {  // ← Ordinal matching
            return true
        }
    }
    return false
}
```

### 2.3 KnowledgeAgency.Execute - Il Parallelismo Fittizio

**File**: `internal/aria/agency/knowledge.go`

```go
func (a *KnowledgeAgency) executeParallel(ctx context.Context, task contracts.Task, primary *RegisteredAgent) (map[string]any, error) {
    agents := a.registry.GetByCategory(primary.Category)
    
    // PROBLEMA: Iterazione sequenziale, NON parallela!
    var results []map[string]any
    for _, agent := range agents {  // ← For loop, NON goroutines
        result, err := a.executeAgentTask(ctx, task, agent)
        // ...
    }
    // ...
}
```

**Nota**: Il `WorkflowEngine` ha esecuzione parallela reale (`executeParallel` con goroutine), ma `KnowledgeAgency.executeParallel` è sequenziale!

### 2.4 Registry Agenti - Specializzazione Funzionale

```go
// WebSearchAgent - General web search
registry.Register(&RegisteredAgent{
    Name:        AgentWebSearch,
    Category:    CategoryWebSearch,
    Description: "Handles general web search tasks using Tavily, Brave, Wikipedia, DDG",
    Skills:      []string{"web-research", "fact-check"},
})

// AcademicResearchAgent - Scientific/academic research
registry.Register(&RegisteredAgent{
    Name:        AgentAcademic,
    Category:    CategoryAcademic,
    Description: "Handles academic research using PubMed, arXiv, SemanticScholar, OpenAlex",
    Skills:      []string{"academic-search", "web-research"},
})
```

---

## 3. Analisi del Sistema di Synthesis

### 3.1 Ranking Euristico

**File**: `internal/aria/agency/knowledge_synthesis.go`

```go
func (s *ResultSynthesizer) rankResults(results []map[string]any) []map[string]any {
    scored := make([]struct{...}, len(results))
    for i, r := range results {
        score := 0
        if _, ok := r["description"]; ok {
            score += 5  // ← Euristica molto semplice
        }
        if _, ok := r["content"]; ok {
            score += 3
        }
        // ...
    }
}
```

**Limiti**:
- Nessun confidence model
- Nessun citation scoring
- Nessun contradiction detection
- Ranking basato solo su presence/absence di campi

---

## 4. Reference: KiloKit Multi-Agent Orchestration

### 4.1 Pattern Gerarchico KiloKit

```
General Manager (Orchestrator)
    ├── Planning Cell (planner, no-tools, decomposizione task)
    ├── Research Cell (web/academic/news/historical executors)
    ├── Synthesis & QA Cell (critic/reviewer)
    └── Memory Cell (retrieve/writeback governance)
```

### 4.2 Best Practice KiloKit

1. **Clear Boundaries**: Responsabilità distinct per ogni cell
2. **Explicit Handoffs**: Documentazione handoff con contesto
3. **Quality Gates**: Enforcement a ogni transizione di fase
4. **Parallelize Wisely**: Solo task indipendenti parallelizzati
5. **Monitor Progress**: Tracking continuo di agent progress

### 4.3 Differenza Chiave

| KiloKit Pattern | ARIA Attuale |
|-----------------|--------------|
| LLM-based task decomposition | Keyword classification |
| Planner → Executor → Critic loop | Direct execution |
| Quality gates formali | Nessun gate strutturato |
| Explicit handoff protocol | Handoff implicito |
| Memory-aware execution | Memory retrieve presente ma writeback debole |

---

## 5. Best Practice SOTA 2026 - Ricerca

### 5.1 Microsoft Azure AI Agent Patterns

```
Sequential Pattern:
Requirements → Design → Development → Testing → Deployment

Parallel Pattern:
         ┌→ Frontend Agent ─┐
Design →├→ Backend Agent  ─┼→ Integration → QA → Deploy
         └→ Data Agent ────┘

Hierarchical Pattern:
Supervisor → Agent Groups → Specialized Agents
(Best for: complex workflows, enterprise operations)
```

### 5.2 Semantic vs Keyword Routing

**Ricerca DeepChecks/RH**:

| Metric | Keyword Matching | Semantic Routing |
|--------|------------------|------------------|
| Similarity Score | 0.35 | 0.74 |
| Context Understanding | None | High |
| Robustness to Variations | Low | High |
| Speed | Fast | Medium |

**Conclusione**: Semantic routing with embeddings achieves **2x better** similarity matching vs keyword-based.

### 5.3 LLM-Based Routing vs Rules-Based

**Red Hat Developer Guide**:
- **Rules-based**: Fast but brittle, misses intent variations
- **LLM-based**: Understands nuance, handles edge cases, but slower
- **Semantic routing**: Best of both - fast similarity + better understanding

### 5.4 Planner/Executor/Critic Pattern (SOTA)

```
┌─────────────┐
│   Planner   │ ← Task decomposition, no execution
└──────┬──────┘
       │ produces Plan
       ▼
┌─────────────┐
│  Executor   │ ← Tool/API execution only
└──────┬──────┘
       │ produces Result
       ▼
┌─────────────┐
│   Critic    │ ← Quality assessment, can veto
└─────────────┘
```

**BOLAA/MAKER Research**: Questo pattern reduce error accumulation in million-step reasoning chains.

---

## 6. Criticità Identificate

### 6.1 Critica - Routing Keyword-Based

**Problema**: L'intero sistema di routing si basa su `strings.Contains()` invece di semantic similarity.

**Impatto**:
- "cercalo su arxiv" → funziona (keyword match)
- "trova paper scientifici recenti su machine learning" → potrebbe fallire (no "arxiv" keyword)
- "vorrei approfondire la teoria dietro i transformers" → routing ambiguity

**Soluzione Raccomandata**: Implementare Semantic Router con embeddings.

### 6.2 Critica - Parallelismo Fittizio

**Problema**: `KnowledgeAgency.executeParallel()` è un for-loop sequenziale.

**Codice Attuale**:
```go
for _, agent := range agents {
    result, err := a.executeAgentTask(ctx, task, agent)  // Sequential!
}
```

**Soluzione Raccomandata**: Usare goroutine con bounded semaphore come in `WorkflowEngine.executeParallel()`.

### 6.3 Critica - Memory Loop Incompleto

**Problema**: `RecordEpisode` viene chiamato ma `LearnFromSuccess`/`LearnFromFailure` non modificano il routing behavior.

**Flusso Attuale**:
```
Query → Memory retrieve → Execute → Record Episode
                                    ↓
                           LearnFromSuccess/Failure
                                    ↓
                           (no routing adjustment)
```

**Soluzione Raccomandata**: Chiudere il loop - usare feedback perAdjustRoutingPolicy.

### 6.4 Critica - Governance Assente

**Problema**: Nessun policy engine per tool invocation.

**KiloKit Reference**:
```json
{
  "agent": "research-executor",
  "allowed_tools": ["fetch", "search"],
  "risky_tools": "ask",  // Gate before execution
  "forbidden_tools": ["bash", "write"]
}
```

---

## 7. Raccomandazioni Prioritarie

### P0 - Immediato (1-2 settimane)

#### 7.1 Semantic Routing per TaskRouter

**Obiettivo**: Sostituire keyword matching con similarity-based routing.

**Implementazione**:
```go
type SemanticTaskRouter struct {
    embeddings embedding.Model
    agentEmbeddings map[AgentName][]float32
    threshold float32
}

func (r *SemanticTaskRouter) Route(task contracts.Task) (*RegisteredAgent, error) {
    taskEmbedding := r.embeddings.Encode(task.Description)
    
    var bestAgent *RegisteredAgent
    var bestScore float32
    
    for name, agentEmbedding := range r.agentEmbeddings {
        score := cosineSimilarity(taskEmbedding, agentEmbedding)
        if score > r.threshold && score > bestScore {
            bestScore = score
            bestAgent = r.getAgent(name)
        }
    }
    // Fallback to keyword if no semantic match above threshold
}
```

**Provider Supportati**:
- OpenAI embeddings (`text-embedding-3-small`)
- VertexAI embeddings
- Local embeddings (Nomic, MiniLM)

#### 7.2 Parallelismo Reale in KnowledgeAgency

**Obiettivo**: Farlo matchare con `WorkflowEngine.executeParallel()`.

**Fix**:
```go
func (a *KnowledgeAgency) executeParallel(ctx context.Context, task contracts.Task, primary *RegisteredAgent) (map[string]any, error) {
    agents := a.registry.GetByCategory(primary.Category)
    
    // Bounded semaphore for concurrency control
    sem := make(chan struct{}, maxConcurrentAgents)
    var wg sync.WaitGroup
    mu := sync.Mutex{}
    results := []map[string]any{}
    var lastErr error
    
    for _, agent := range agents {
        wg.Add(1)
        go func(ag *RegisteredAgent) {
            defer wg.Done()
            sem <- struct{}{}
            defer func() { <-sem }()
            
            result, err := a.executeAgentTask(ctx, task, ag)
            mu.Lock()
            if err != nil {
                lastErr = err
            } else {
                results = append(results, result)
            }
            mu.Unlock()
        }(agent)
    }
    wg.Wait()
    
    // Synthesis of all results
    return a.synthesizer.Synthesize(task.ID, results, DefaultSynthesisOptions())
}
```

### P1 - Breve Termine (2-4 settimane)

#### 7.3 LLM-Based Query Classifier

**Obiettivo**: Sostituire `BaselineClassifier` con LLM-based classification.

**Implementazione**:
```go
type LLMClassifier struct {
    provider llm.Provider
    systemPrompt string
}

func (c *LLMClassifier) Classify(ctx context.Context, query Query) (Classification, error) {
    prompt := fmt.Sprintf(`Classify this query:
Query: %s
History: %v

Return JSON with intent, domain, complexity, urgency.`, 
        query.Text, query.History)
    
    resp, err := c.provider.Generate(ctx, prompt)
    // Parse JSON response
    // Return Classification with confidence from LLM
}
```

#### 7.4 Planner/Executor/Critic per Knowledge Agency

**Obiettivo**: Implementare quality gates prima della delivery.

```go
type KnowledgeCritic struct{}

func (c *KnowledgeCritic) Review(task contracts.Task, result map[string]any) *ReviewResult {
    return &ReviewResult{
        QualityScore: c.calculateQualityScore(result),
        Confidence: c.assessConfidence(result),
        Contradictions: c.detectContradictions(result),
        CitationsValid: c.validateCitations(result),
        Pass: qualityScore >= 0.7 && len(contradictions) == 0,
    }
}
```

### P2 - Medio Termine (1-2 mesi)

#### 7.5 Memory-Driven Routing Adaptation

**Obiettivo**: Chiudere il loop tra success/failure e routing policy.

```go
func (o *BasicOrchestrator) AdjustRoutingBasedOnMemory() {
    // Analizza ultimi 100 task
    episodes := o.memoryService.GetRecentEpisodes(100)
    
    // Calcola success rate per agency/domain
    stats := calculateSuccessStats(episodes)
    
    // Auto-boost high-performing agencies
    for agency, rate := range stats {
        if rate > 0.9 {
            o.policyRouter.BoostAgencyConfidence(agency, 0.1)
        } else if rate < 0.5 {
            o.policyRouter.ReduceAgencyConfidence(agency, 0.1)
        }
    }
}
```

#### 7.6 Policy Engine per Tool Governance

**Obiettivo**: Implementare allow/ask/deny per classi di tool.

```go
type ToolPolicy struct {
    AllowList []string
    AskList   []string  // Requires user confirmation
    DenyList  []string
}

type PolicyEngine struct {
    agentPolicies map[AgentName]ToolPolicy
}

func (e *PolicyEngine) CheckTool(tool string, agent AgentName) (Decision, error) {
    policy := e.agentPolicies[agent]
    switch {
    case contains(policy.DenyList, tool):
        return DecisionDeny, nil
    case contains(policy.AskList, tool):
        return DecisionAsk, nil
    default:
        return DecisionAllow, nil
    }
}
```

---

## 8. KPI per Misurare Miglioramento

| KPI | Target | Misura |
|-----|--------|--------|
| Routing Accuracy | >85% | % task routed to correct agency |
| Semantic Match Rate | >80% | % queries matched semantically vs fallback keyword |
| Parallel Execution Real | 100% | % parallel tasks using goroutines |
| Memory Loop Closure | >70% | % success learnings affecting future routing |
| Citation Coverage | >90% | % results with verifiable sources |
| Fallback Rate | <15% | % queries falling back to keyword routing |
| Latency P50/P95 | <500ms/<2s | End-to-end task completion |

---

## 9. Blueprint Target - Architettura Intelligente

```
                    ┌─────────────────────────────────────────┐
                    │         ORCHESTRATOR (Director)         │
                    │  ┌─────────────────────────────────┐   │
                    │  │  LLM Classifier (semantic)       │   │
                    │  │  + Feedback-adaptive Policy      │   │
                    │  └─────────────────────────────────┘   │
                    └──────────────────┬──────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   Knowledge Agency │   │ Development Agency │   │   Nutrition Agency  │
│  ┌───────────────┐ │   │  ┌───────────────┐ │   │  ┌───────────────┐ │
│  │Planner (LLM)  │ │   │  │ Planner       │ │   │  │ Planner       │ │
│  └───────┬───────┘ │   │  └───────────────┘ │   │  └───────────────┘ │
│          │         │   │                    │   │                    │
│          ▼         │   │                    │   │                    │
│  ┌───────────────┐ │   │                    │   │                    │
│  │ Supervisor    │ │   │                    │   │                    │
│  │ (semantic     │ │   │                    │   │                    │
│  │  router)      │ │   │                    │   │                    │
│  └───────┬───────┘ │   │                    │   │                    │
│          │         │   │                    │   │                    │
│    ┌─────┼─────┐   │   │                    │   │                    │
│    ▼     ▼     ▼   │   │                    │   │                    │
│  ┌───┐ ┌───┐ ┌───┐ │   │                    │   │                    │
│  │Web│ │Acad│ │News│   │                    │   │                    │
│  │   │ │   │ │   │ │   │                    │   │                    │
│  └───┘ └───┘ └───┘ │   │                    │   │                    │
│          │         │   │                    │   │                    │
│          ▼         │   │                    │   │                    │
│  ┌───────────────┐ │   │                    │   │                    │
│  │ Critic        │ │   │                    │   │                    │
│  │ (quality gate)│ │   │                    │   │                    │
│  └───────┬───────┘ │   │                    │   │                    │
│          │         │   │                    │   │                    │
│          ▼         │   │                    │   │                    │
│  ┌───────────────┐ │   │                    │   │                    │
│  │ Synthesizer   │ │   │                    │   │                    │
│  │ (evidence-    │ │   │                    │   │                    │
│  │  first)       │ │   │                    │   │                    │
│  └───────────────┘ │   │                    │   │                    │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Memory Service     │
│  (episodes +       │
│   learnings loop)   │
└─────────────────────┘
```

---

## 10. Conclusione

Il sistema Knowledge Agency + Orchestratore di ARIA ha una **struttura solida** ma soffre di:

1. **Routing Keyword-Based**: Non capisce il significato, solo pattern matching
2. **Parallelismo Fittizio**: `executeParallel` è sequenziale
3. **Memory Loop Incompleto**: Feedback recorded but not used to adjust routing
4. **Governance Assente**: Nessun policy engine per tool safety

**Road to SOTA 2026**:

1. **Immediato**: Semantic router con embeddings (2x better matching)
2. **Breve**: LLM-based classifier + Planner/Critic pattern
3. **Medio**: Memory-driven routing adaptation + Policy engine

Il report precedente (2026-03-31) identificava già questi problemi a livello strutturale. Questa analisi conferma che la **causa root è nel routing ordinal-keyword-based** che non permette al sistema di operare in modo veramente intelligente.

---

## Appendix A - File Analizzati

| File | Purpose |
|------|---------|
| `internal/aria/core/orchestrator_impl.go` | Core orchestrator with ProcessQuery flow |
| `internal/aria/routing/classifier_impl.go` | BaselineClassifier - keyword-based |
| `internal/aria/routing/router_impl.go` | DefaultRouter - rules-based |
| `internal/aria/agency/knowledge.go` | KnowledgeAgency main |
| `internal/aria/agency/knowledge_supervisor.go` | TaskRouter - keyword classification |
| `internal/aria/agency/knowledge_execution.go` | WorkflowEngine with parallel support |
| `internal/aria/agency/knowledge_synthesis.go` | ResultSynthesizer - heuristic ranking |
| `~/.kilocode/skills/multi-agent-orchestration/SKILL.md` | KiloKit reference |

## Appendix B - Riferimenti Best Practice

- Azure Architecture Center: AI Agent Orchestration Patterns (Microsoft)
- Red Hat Developer: LLM Semantic Router
- DeepChecks: Semantic Router vs Keyword Matching
- MAKER/BOLAA Research: Planner/Executor/Critic pattern
- KiloKit: Multi-Agent Orchestration Skill v200 lines

## Appendix C - Comandi di Verifica

```bash
# Verifica routing attuale
go test -run TestClassifier ./internal/aria/routing/

# Verifica parallelismo
go test -run TestParallel ./internal/aria/agency/

# Benchmark routing
go test -bench=. ./internal/aria/routing/ -benchtime=1000x
```
