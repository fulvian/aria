# Orchestrator Enhancement — TDD Technical Design

**Data:** 2026-03-30  
**Autore:** General Manager (Architect)  
**Stato:** TDD READY FOR IMPLEMENTATION  
**Branch:** `feature/orchestrator-enhancement`  
**Milestone Focus:** O1 (Decision Core Hardening) → O2 (Planner/Executor/Reviewer)  

---

## 1. Panoramica Architetturale

### 1.1 Pipeline Operativa Target

```
User Query
  │
  ▼
┌─────────────────────────────┐
│  Phase A: Intake            │ ← Context recovery, session history
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  Phase B: Classification     │ ← Intent, Domain, Complexity (existing)
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  Phase C: Decision Engine    │ ← NEW: ComplexityScore, RiskScore, PathChoice
│  (Fast vs Deep Path)        │
└─────────────┬───────────────┘
              ▼
         ┌────┴────┐
         │         │
    Fast Path   Deep Path
         │         │
         │    ┌────▼────────────────┐
         │    │  Planner (delibera) │
         │    │  sequential-thinking │
         │    └────┬────────────────┘
         │         ▼
         │    ┌────▼────────┐
         │    │   Plan      │
         │    └────┬────────┘
         │         ▼
         │    ┌────▼────────┐
         │    │  Executor    │
         │    │  (agisce)   │
         │    └────┬────────┘
         │         ▼
         │    ┌────▼────────┐
         │    │  Reviewer   │
         │    │  (verifica) │
         │    └────┬────────┘
         │         │
         └────┬────┘
              ▼
┌─────────────────────────────┐
│  Phase E: Review Gate       │ ← Acceptance score check
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  Phase F: Response + Memory │ ← Writeback, metrics
└─────────────────────────────┘
```

### 1.2 Principio Fondamentale

**Planner, Executor, Reviewer sono fasi logiche (co-routine) interne all'Orchestrator, NON agenti autonomi.**

---

## 2. Package Layout

```
internal/aria/core/
  ├── orchestrator.go              # Existing: interface Orchestrator
  ├── orchestrator_impl.go         # Existing: BasicOrchestrator
  │
  ├── decision/                     # NEW (O1)
  │   ├── decision_engine.go        # Decision Engine interface + implementation
  │   ├── complexity_analyzer.go    # Complexity scoring (0-100)
  │   ├── risk_analyzer.go          # Risk scoring (0-100)
  │   ├── trigger_policy.go         # sequential-thinking gating
  │   └── path_selector.go          # Fast vs Deep path selection
  │
  ├── plan/                        # NEW (O2)
  │   ├── plan_types.go             # Plan, PlanStep, Handoff structs
  │   ├── planner.go                # Planner interface + implementation
  │   ├── executor.go               # Executor interface + implementation
  │   └── reviewer.go               # Reviewer interface + implementation
  │
  ├── pipeline/                    # NEW (O1+O2)
  │   └── orchestrator_pipeline.go  # Phase A-F orchestration glue
  │
  └── config/                      # NEW (O1)
      └── orchestrator_config.go    # OrchestratorConfig v2

internal/aria/routing/
  ├── router.go                    # Existing
  ├── classifier.go                 # Existing
  ├── policy_router.go              # NEW (O3): confidence calibration, policy override
  └── capability_registry.go        # NEW (O3): agency/agent capability registry

internal/llm/prompt/
  ├── orchestrator_planner.go      # NEW (O4): planner prompts
  ├── orchestrator_executor.go      # NEW (O4): executor prompts
  └── orchestrator_reviewer.go      # NEW (O4): reviewer prompts

internal/aria/agency/
  └── agency.go                     # Existing: Agency interface
```

---

## 3. O1 — Decision Core Hardening

### 3.1 ComplexityAnalyzer

**Responsabilità**: Calcolare complexity score (0-100) per una query.

```go
// internal/aria/core/decision/complexity_analyzer.go

// ComplexityAnalyzer calcola uno score di complessità (0-100).
type ComplexityAnalyzer interface {
    Analyze(ctx context.Context, query routing.Query, class routing.Classification) (ComplexityScore, error)
}

// ComplexityScore rappresenta il livello di complessità.
type ComplexityScore struct {
    Value       int       // 0-100
    Factors     []ComplexityFactor  // fattori che hanno contribuito
    Explanation string    // spiegazione leggibile
}

// ComplexityFactor identifica un fattore di complessità.
type ComplexityFactor struct {
    Name   string
    Weight int    // contributo in punti (0-100)
    Reason string
}
```

**Segnali di complessità** (valori cumulativi):

| Segnale | Punti | Note |
|---------|-------|------|
| Query length > 200 chars | +10 | |
| History length > 5 | +15 | |
| Contains "and then", "also", "plus" | +20 | multi-step |
| Contains "refactor", "migrate", "architecture" | +25 | architectural |
| Contains "multiple", "several", "all" | +20 | multi-target |
| Intent = Analysis | +15 | |
| ComplexityLevel existing = complex | +20 | |
| RequiresState = true | +15 | |
| Domain = development + contains code terms | +10 | |

**Soglie**:
- 0-35:   Simple   (Fast Path)
- 36-70:  Medium   (Fast Path, optionally Deep)
- 71-100: Complex  (Deep Path)

### 3.2 RiskAnalyzer

**Responsabilità**: Calcolare risk score (0-100) per una query.

```go
// internal/aria/core/decision/risk_analyzer.go

// RiskAnalyzer calcola uno score di rischio (0-100).
type RiskAnalyzer interface {
    Analyze(ctx context.Context, query routing.Query, class routing.Classification) (RiskScore, error)
}

// RiskScore rappresenta il livello di rischio.
type RiskScore struct {
    Value       int
    Category    RiskCategory          // IRREVERSIBLE, EXPENSIVE, SAFETY, STANDARD
    Factors     []RiskFactor
    Mitigation  string    // strategia di mitigazione se rischio alto
}

// RiskCategory enum.
type RiskCategory string

const (
    RiskIrreversible RiskCategory = "irreversible"  // azioni non revertibili
    RiskExpensive   RiskCategory = "expensive"      // alto consumo risorse
    RiskSafety      RiskCategory = "safety"         // azioni potenzialmente pericolose
    RiskStandard    RiskCategory = "standard"       // rischio normale
)

// RiskFactor identifica un fattore di rischio.
type RiskFactor struct {
    Name   string
    Weight int
    Reason string
}
```

**Segnali di rischio** (valori cumulativi):

| Segnale | Punti | Note |
|---------|-------|------|
| Contains "delete", "drop", "remove" | +30 | distruzione dati |
| Contains "deploy", "push", "submit" | +25 | modifiche esterne |
| Contains "rm -rf", "sudo", "kill" | +40 | commandi pericolosi |
| Contains "password", "secret", "api_key" | +20 | informazioni sensibili |
| Intent = Creation + Domain = development | +15 | |
| Contains file path (indicates target) | +10 | |
| Query about production environment | +20 | |

**Soglie**:
- 0-39:   Standard (nessuna mitigazione extra)
- 40-69:  Elevated (richiede conferma o guardrail)
- 70-100: High (richiede Reviewer gate + fallback)

### 3.3 TriggerPolicy

**Responsabilità**: Determinare SE attivare `sequential-thinking`.

```go
// internal/aria/core/decision/trigger_policy.go

// TriggerPolicy decide quando usare sequential-thinking.
type TriggerPolicy interface {
    ShouldUseDeepPath(ctx context.Context, complexity ComplexityScore, risk RiskScore, class routing.Classification) (Decision, error)
}

// Decision contiene la decisione del policy.
type Decision struct {
    UseDeepPath    bool
    Reason         string
    TriggeredBy    []TriggerReason  // quali condizioni hanno triggerato
    MaxThoughts    int             // max pensieri consentiti
    TimeoutMs      int             // timeout in millisecondi
}

// TriggerReason identifica perché è stata presa una decisione.
type TriggerReason struct {
    Rule    string  // nome della regola
    Matched bool    // se la regola è stata matchata
    Weight  int     // contributo
}
```

**Trigger Policy Rules** (attiva Deep Path se ALMENO UNA condizione è vera):

| Condizione | Peso | Note |
|------------|------|------|
| ComplexityScore.Value >= complexityThreshold (default 55) | 100 | |
| RiskScore.Value >= riskThreshold (default 40) | 100 | |
| class.Complexity == ComplexityComplex | 80 | |
| class.Intent IN [Analysis, Planning] | 60 | |
| Query requires >= 2 tools (da capability) | 90 | |
| Query requires >= 2 agents OR agency+handoff | 95 | |
| Ambiguous query (contiene "or" o conflitti) | 70 | |
| RiskScore.Category IN [Irreversible, Expensive] | 85 | |

**Non-trigger** (forza Fast Path anche se altri trigger匹配):

| Condizione | Peso | Note |
|-----------|------|------|
| ComplexityScore.Value <= 20 | -100 | triviale |
| Query semplice Q&A (< 30 chars, 0 history) | -100 | |
| Intent = Question AND Complexity = Simple | -100 | |
| Skill atomica nota e a basso rischio | -80 | |

**Configurazione default**:
```go
TriggerConfig {
    ComplexityThreshold: 55,
    RiskThreshold:       40,
    MaxThoughts:         12,
    TimeoutMs:           12000,
}
```

### 3.4 PathSelector

**Responsabilità**: Selezionare Fast o Deep Path basandosi su complexity, risk e trigger.

```go
// internal/aria/core/decision/path_selector.go

// PathSelector sceglie tra Fast e Deep Path.
type PathSelector interface {
    SelectPath(ctx context.Context, complexity ComplexityScore, risk RiskScore, trigger TriggerPolicyDecision) (ExecutionPath, error)
}

// ExecutionPath enum.
type ExecutionPath string

const (
    PathFast ExecutionPath = "fast"    // direct classification → routing → execute → respond
    PathDeep ExecutionPath = "deep"   // planner → executor → reviewer → respond
)
```

### 3.5 DecisionEngine

**Responsabilità**: Coordina complexity analyzer, risk analyzer, trigger policy e path selector.

```go
// internal/aria/core/decision/decision_engine.go

// DecisionEngine è il componente centrale che decide il percorso di esecuzione.
type DecisionEngine interface {
    // Decide determina il percorso di esecuzione per una query.
    Decide(ctx context.Context, query routing.Query, class routing.Classification) (ExecutionDecision, error)
    
    // GetConfig restituisce la configurazione corrente.
    GetConfig() DecisionEngineConfig
}

// ExecutionDecision contiene la decisione completa.
type ExecutionDecision struct {
    Path           ExecutionPath
    Complexity     ComplexityScore
    Risk           RiskScore
    Trigger        TriggerPolicyDecision
    RoutingHint    *RoutingHint   // hint opzionale per il routing
    Explanation    string         // spiegazione leggibile della decisione
}

// RoutingHint suggerimenti per il routing.
type RoutingHint struct {
    PreferAgency  *string  // agency preferita
    PreferAgent   *string  // agente preferito
    AvoidAgents   []string // agenti da evitare
    BudgetTokenMax int     // budget massimo di token
}

// DecisionEngineConfig configurazione del decision engine.
type DecisionEngineConfig struct {
    ComplexityAnalyzer ComplexityAnalyzer
    RiskAnalyzer       RiskAnalyzer
    TriggerPolicy      TriggerPolicy
    PathSelector       PathSelector
    
    // Thresholds
    ComplexityThreshold int  // default 55
    RiskThreshold       int  // default 40
}
```

### 3.6 O1 — Interfacce e Contratti

**Flusso di chiamata O1**:
```
ProcessQuery (orchestrator_impl.go)
    │
    ▼
DecisionEngine.Decide()
    │
    ├──► ComplexityAnalyzer.Analyze() → ComplexityScore
    │
    ├──► RiskAnalyzer.Analyze() → RiskScore
    │
    ├──► TriggerPolicy.ShouldUseDeepPath() → TriggerPolicyDecision
    │
    ▼
PathSelector.SelectPath() → ExecutionPath
    │
    ▼
ExecutionDecision { Path, Complexity, Risk, Trigger, Explanation }
```

**Test necessari per O1**:

| Test | Descrizione |
|------|-------------|
| TestComplexityAnalyzer_Simple | query semplice → score < 36 |
| TestComplexityAnalyzer_MultiStep | query con "and then" → score >= 55 |
| TestComplexityAnalyzer_Architectural | query con "refactor" → score >= 70 |
| TestRiskAnalyzer_Standard | query normale → score < 40 |
| TestRiskAnalyzer_Destructive | query con "delete" → score >= 30 |
| TestTriggerPolicy_DeepPath | complexity 60 + risk 45 → use deep |
| TestTriggerPolicy_FastPath | complexity 20 → force fast |
| TestTriggerPolicy_NonTrigger | Q&A semplice → force fast |
| TestPathSelector_FastPath | low complexity + low risk → fast |
| TestPathSelector_DeepPath | high complexity OR high risk → deep |
| TestDecisionEngine_Integration | full flow → correct path + scores |

---

## 4. O2 — Planner / Executor / Reviewer

### 4.1 Plan Types

**Schema del piano di esecuzione**.

```go
// internal/aria/core/plan/plan_types.go

// Plan rappresenta un piano di esecuzione strutturato.
type Plan struct {
    ID          string
    Query       string
    Objective   string              // obiettivo normalizzato
    Steps       []PlanStep          // step sequenziali
    Hypotheses  []Hypothesis        // ipotesi operative (per deep path)
    Risks       []PlanRisk          // rischi identificati
    Fallbacks   []FallbackStrategy  // strategie di fallback
    DoneCriter  string              // criterio di completamento
    CreatedAt   time.Time
    Metadata    map[string]any
}

// PlanStep rappresenta un singolo step del piano.
type PlanStep struct {
    Index       int
    Action      string              // cosa fare
    Target      string              // su cosa (agency/agent/tool)
    Inputs      map[string]any      // parametri di input
    ExpectedOut map[string]any      // output atteso
    Constraints []string            // vincoli da rispettare
    Timeout     time.Duration       // timeout per questo step
}

// Hypothesis rappresenta un'ipotesi operativa.
type Hypothesis struct {
    Description string
    Confidence  float64
    Conditions  []string
}

// PlanRisk identifica un rischio nel piano.
type PlanRisk struct {
    Description string
    Probability float64
    Impact      string
    Mitigation  string
}

// FallbackStrategy strategia di fallback per uno step.
type FallbackStrategy struct {
    Condition string          // quando attivare
    Action    string         // azione alternativa
    Target    string          // target alternativo
}

// Handoff rappresenta un passaggio tra agenti.
type Handoff struct {
    From        AgentID
    To          AgentID
    Reason      string           // perché questo handoff
    ExpectedOut string           // outcome atteso
    Constraints []string         // vincoli durante handoff
    Budget      HandoffBudget    // timeout/token budget
}

// HandoffBudget budget per un handoff.
type HandoffBudget struct {
    Timeout    time.Duration
    TokenLimit int
}
```

### 4.2 Planner

**Responsabilità**: Costruisce il piano di esecuzione. Può usare `sequential-thinking` se trigger attivo.

```go
// internal/aria/core/plan/planner.go

// Planner costruisce un piano di esecuzione per una query.
type Planner interface {
    // CreatePlan genera un piano per la query.
    CreatePlan(ctx context.Context, query routing.Query, class routing.Classification, decision ExecutionDecision) (*Plan, error)
    
    // CreatePlanWithThinking genera un piano usando sequential-thinking (deep path).
    CreatePlanWithThinking(ctx context.Context, query routing.Query, class routing.Classification, decision ExecutionDecision) (*Plan, error)
}
```

**Flusso Planner**:
1. Se Deep Path → usa `sequential-thinking` MCP tool per deliberazione
2. Estrae objective normalizzato dalla query
3. Identifica step necessari (agency/agent/tools)
4. Genera ipotesi operative
5. Identifica rischi e fallback
6. Definisce criterio di done
7. Restituisce Plan serializzabile

**Output atteso con sequential-thinking** (sezione 4.4 del piano):
- Obiettivo normalizzato
- Ipotesi operative
- Piano step-by-step
- Rischi/precondizioni/fallback
- Criterio di done

### 4.3 Executor

**Responsabilità**: Esegue gli step del piano, gestisce handoff, applica permission/guardrail.

```go
// internal/aria/core/plan/executor.go

// Executor esegue un piano di esecuzione.
type Executor interface {
    // Execute esegue il piano e restituisce il risultato.
    Execute(ctx context.Context, plan *Plan) (*ExecutionResult, error)
    
    // ExecuteStep esegue un singolo step (per streaming/interactive).
    ExecuteStep(ctx context.Context, step PlanStep) (*StepResult, error)
}

// ExecutionResult risultato dell'esecuzione completa del piano.
type ExecutionResult struct {
    PlanID       string
    Success      bool
    CompletedSteps []int           // indici degli step completati
    FailedStep   *int              // step fallito (se applica)
    Outputs      map[string]any     // output raccolti
    Handoffs     []HandoffRecord   // record degli handoff
    Metrics      ExecutionMetrics   // metriche di esecuzione
    Error        error
}

// StepResult risultato di un singolo step.
type StepResult struct {
    StepIndex int
    Success   bool
    Output    map[string]any
    Error     error
}

// HandoffRecord record di un handoff eseguito.
type HandoffRecord struct {
    Handoff  Handoff
    FromOutput map[string]any
    ToInput    map[string]any
    Completed  bool
    Duration   time.Duration
}

// ExecutionMetrics metriche di esecuzione.
type ExecutionMetrics struct {
    TotalTokens int
    TotalTime   time.Duration
    StepsTime   []time.Duration
    FallbackUsed bool
}
```

**Flusso Executor**:
1. Per ogni step nel piano:
   a. Verifica precondizioni
   b. Applica permission check
   c. Esegue tramite agency/agent
   d. Registra output
   e. Se handoff → passa contesto con constraints
2. Se step fallisce → applica fallback strategy
3. Se fallimento finale → ritorna errore
4. Restituisce ExecutionResult

### 4.4 Reviewer

**Responsabilità**: Verifica che l'output soddisfi i criteri di accettazione.

```go
// internal/aria/core/plan/reviewer.go

// Reviewer verifica l'output contro gli obiettivi.
type Reviewer interface {
    // Review valuta se il risultato soddisfa i criteri.
    Review(ctx context.Context, plan *Plan, result *ExecutionResult) (*ReviewResult, error)
    
    // ShouldReplan determina se è necessario un replan.
    ShouldReplan(ctx context.Context, review ReviewResult) (bool, ReplanReason)
}

// ReviewResult risultato della review.
type ReviewResult struct {
    Score         float64              // 0.0 - 1.0
    Passed        bool                  // true se score >= minAcceptanceScore
    Criteria      []AcceptanceCriterion // criteria check results
    Verdict       string                // "APPROVED", "REVISION_NEEDED", "REPLAN_NEEDED"
    Feedback      string                // feedback leggibile
}

// AcceptanceCriterion singolo criterio di accettazione.
type AcceptanceCriterion struct {
    Name      string
    Passed    bool
    Evidence  string   // log/evidence che dimostra il passaggio
    Weight    float64  // peso per il calcolo dello score
}

// ReplanReason ragione per il replan.
type ReplanReason struct {
    Reason   string
    Strategy string   // "RETRY", "FALLBACK", "REPLAN_FULL"
}
```

**Acceptance Criteria** (devono tutti passare per APPROVED):

| Criterio | Weight | Check |
|----------|--------|-------|
| Objective satisfied | 0.30 | output matches objective |
| Constraints respected | 0.25 | no constraint violation |
| Risk within threshold | 0.20 | risk <= threshold |
| Evidence available | 0.15 | logs/metrics present |
| Fallback not triggered excessively | 0.10 | fallbackCount <= maxReplan |

**Verdict Logic**:
- Score >= 0.75 AND all critical criteria passed → "APPROVED"
- Score >= 0.50 with minor failures → "REVISION_NEEDED"
- Score < 0.50 OR critical failure → "REPLAN_NEEDED"

**Configurazione**:
```go
ReviewerConfig {
    MinAcceptanceScore: 0.75,
    MaxReplan:          2,
    MaxRetries:         1,
}
```

### 4.5 O2 — Interfacce e Contratti

**Flusso O2 completo**:
```
Deep Path Decision
    │
    ▼
Planner.CreatePlanWithThinking()
    │ (sequential-thinking MCP)
    ▼
Plan { Objective, Steps[], Risks[], Fallbacks[], DoneCriteria }
    │
    ▼
Executor.Execute()
    │
    ├──► Step 0: permission check → agency.Execute()
    ├──► Step 1: handoff to another agent
    ├──► Step 2: ...
    │
    ▼
ExecutionResult { Success, Outputs, Handoffs, Metrics }
    │
    ▼
Reviewer.Review()
    │
    ├──► Acceptance Gate Check
    │
    ▼
ReviewResult { Score, Passed, Verdict }
    │
    ├──► if REPLAN_NEEDED and replanCount < MaxReplan → Planner.CreatePlanWithThinking() again
    ├──► if APPROVED → proceed to response
    │
    ▼
Final Response + Memory Writeback
```

**Test necessari per O2**:

| Test | Descrizione |
|------|-------------|
| TestPlan_Structure | CreatePlan → valid Plan with all fields |
| TestPlan_Serialization | Plan → JSON → Plan (roundtrip) |
| TestPlanner_DeepPath | complexity 70 → uses sequential-thinking |
| TestPlanner_FastPath | CreatePlan without sequential-thinking |
| TestExecutor_SingleStep | single step → correct output |
| TestExecutor_MultiStep | multiple steps → correct sequence |
| TestExecutor_Handoff | handoff between agents → context passed |
| TestExecutor_Fallback | step fails → fallback executed |
| TestReviewer_Approved | high quality result → score >= 0.75 |
| TestReviewer_Replan | low quality result → REPLAN_NEEDED |
| TestReviewer_MaxReplan | exceeded MaxReplan → force fallback |
| TestIntegration_PlannerExecutorReviewer | full deep path → end-to-end |

---

## 5. O3 — Routing 2.0 + Capability Governance

### 5.1 CapabilityRegistry

```go
// internal/aria/routing/capability_registry.go

// CapabilityRegistry registra e match capabilities di agency/agent.
type CapabilityRegistry interface {
    // RegisterAgency registra capabilities di un'agency.
    RegisterAgency(cap AgencyCapability) error
    
    // RegisterAgent registra capabilities di un agente.
    RegisterAgent(agencyName string, cap AgentCapability) error
    
    // FindAgents trova agenti che matchano i requisiti.
    FindAgents(req CapabilityRequest) []AgentCapability
    
    // FindAgencies trova agencies che matchano i requisiti.
    FindAgencies(req CapabilityRequest) []AgencyCapability
    
    // GetHealth restituisce health status di agenti/agencies.
    GetHealth() HealthStatus
}

// AgencyCapability capabilities di un'agency.
type AgencyCapability struct {
    Name        AgencyName
    Domain      DomainName
    Skills      []SkillName
    Agents      []AgentName
    CostHint    CostHint
    RiskClass   RiskClass
    Health      HealthIndicator
}

// AgentCapability capabilities di un agente.
type AgentCapability struct {
    Name        AgentName
    Agency      AgencyName
    Skills      []SkillName
    Tools       []string
    CostHint    CostHint
    RiskClass   RiskClass
    Health      HealthIndicator
}

// CapabilityRequest requisiti per il matching.
type CapabilityRequest struct {
    Domain      DomainName
    Skills      []SkillName
    MinHealth   HealthLevel
    MaxCost     CostHint
    MaxRisk     RiskClass
}

// CostHint indicazione di costo.
type CostHint struct {
    TokenBudget  int
    TimeBudgetMs int
}

// RiskClass classificazione di rischio.
type RiskClass string

const (
    RiskClassLow    RiskClass = "low"
    RiskClassMedium RiskClass = "medium"
    RiskClassHigh   RiskClass = "high"
)
```

### 5.2 PolicyRouter

```go
// internal/aria/routing/policy_router.go

// PolicyRouter router con confidence calibration e policy override.
type PolicyRouter interface {
    Router  // embedding del Router base
    
    // RouteWithPolicy route con considerazioni di policy.
    RouteWithPolicy(ctx context.Context, query routing.Query, class routing.Classification, policy RoutingPolicy) (RoutingDecision, error)
    
    // SetRoutingPolicy aggiorna la policy di routing.
    SetRoutingPolicy(policy RoutingPolicy) error
}

// RoutingPolicy policy di routing configurabile.
type RoutingPolicy struct {
    // CostBudget budget massimo per il routing (token/time)
    CostBudget CostBudget
    
    // SafetyBudget soglia massima di rischio accettabile
    SafetyBudget RiskScore
    
    // CapabilityMatch se true, forza matching con capability registry
    CapabilityMatch bool
    
    // ConfidenceThreshold soglia minima di confidence
    ConfidenceThreshold float64
    
    // PriorityRules regole di priorità
    PriorityRules []PriorityRule
}

// PriorityRule regola di priorità per il routing.
type PriorityRule struct {
    Name      string
    Condition string  // e.g., "domain=development AND intent=task"
    Boost     float64 // boost alla confidence se match
}
```

---

## 6. Configurazione

### 6.1 OrchestratorConfig V2

```go
// internal/aria/core/config/orchestrator_config.go

// OrchestratorConfigV2 configurazione estesa per l'orchestrator enhanced.
type OrchestratorConfigV2 struct {
    // Base config (existing)
    EnableFallback       bool
    DefaultAgency       contracts.AgencyName
    ConfidenceThreshold float64
    
    // NEW: Decision Engine
    DecisionEngine DecisionEngineConfig
    
    // NEW: Reviewer
    Reviewer ReviewerConfig
    
    // NEW: Execution paths
    Paths ExecutionPathsConfig
}

// DecisionEngineConfig configurazione del decision engine.
type DecisionEngineConfig struct {
    ComplexityThreshold int  // default 55
    RiskThreshold       int  // default 40
    MaxThoughts         int  // for sequential-thinking, default 12
    TimeoutMs           int  // for sequential-thinking, default 12000
}

// ReviewerConfig configurazione del reviewer.
type ReviewerConfig struct {
    Enabled            bool
    MinAcceptanceScore float64  // default 0.75
    MaxReplan          int      // default 2
    MaxRetries         int      // default 1
}

// ExecutionPathsConfig configurazione dei path di esecuzione.
type ExecutionPathsConfig struct {
    FastPathEnabled bool
    DeepPathEnabled bool
}
```

### 6.2 Config Keys per .opencode.json

```jsonc
{
  "aria": {
    "orchestrator": {
      "mode": "hybrid",           // "fast", "deep", "hybrid"
      "enablePlannerReviewer": true,
      "decisionEngine": {
        "complexityThreshold": 55,
        "riskThreshold": 40,
        "maxThoughts": 12,
        "timeoutMs": 12000
      },
      "verification": {
        "enabled": true,
        "minAcceptanceScore": 0.75,
        "maxReplan": 2,
        "maxRetries": 1
      }
    }
  }
}
```

---

## 7. Integrazione con Componenti Esistenti

### 7.1 Modifiche a orchestrator_impl.go

```go
// BasicOrchestrator — modifiche per O1+O2

type BasicOrchestrator struct {
    // ... existing fields ...
    
    // NEW O1
    decisionEngine DecisionEngine
    
    // NEW O2
    planner   Planner
    executor  Executor
    reviewer  Reviewer
    
    // NEW O1+O2
    pipeline *OrchestratorPipeline
}
```

### 7.2 Pipeline Orchestration

```go
// internal/aria/core/pipeline/orchestrator_pipeline.go

// OrchestratorPipeline coordina le fasi A-F dell'orchestrator.
type OrchestratorPipeline struct {
    decisionEngine DecisionEngine  // O1
    planner        Planner          // O2
    executor       Executor         // O2
    reviewer       Reviewer         // O2
    router         routing.Router   // existing
    memorySvc      memory.MemoryService  // existing
}

// Run esegue la pipeline completa per una query.
func (p *OrchestratorPipeline) Run(ctx context.Context, query Query) (Response, error) {
    // Phase A: Intake + Context Recovery (existing memory integration)
    
    // Phase B: Classification (existing)
    class := p.classifier.Classify(...)
    
    // Phase C: Decision Engine
    decision, err := p.decisionEngine.Decide(ctx, query, class)
    if err != nil {
        return Response{}, err
    }
    
    if decision.Path == PathFast {
        // Fast Path: existing flow
        return p.runFastPath(ctx, query, class, decision)
    }
    
    // Deep Path: Planner → Executor → Reviewer
    return p.runDeepPath(ctx, query, class, decision)
}

func (p *OrchestratorPipeline) runDeepPath(ctx context.Context, query Query, class Classification, decision ExecutionDecision) (Response, error) {
    // Planner
    plan, err := p.planner.CreatePlanWithThinking(ctx, query, class, decision)
    if err != nil {
        // Fallback to fast if planning fails
        return p.runFastPath(ctx, query, class, decision)
    }
    
    // Executor
    result, err := p.executor.Execute(ctx, plan)
    if err != nil {
        return Response{}, err
    }
    
    // Reviewer
    review, err := p.reviewer.Review(ctx, plan, result)
    if err != nil {
        return Response{}, err
    }
    
    // Check if replan needed
    if review.Verdict == "REPLAN_NEEDED" {
        shouldReplan, reason := p.reviewer.ShouldReplan(ctx, review)
        if shouldReplan && reason.Strategy == "REPLAN_FULL" {
            // Retry with new plan
            plan, err = p.planner.CreatePlanWithThinking(ctx, query, class, decision)
            if err == nil {
                result, err = p.executor.Execute(ctx, plan)
                if err == nil {
                    review, _ = p.reviewer.Review(ctx, plan, result)
                }
            }
        }
    }
    
    // Build response from review result
    return p.buildResponse(review, result)
}
```

---

## 8. Test Strategy

### 8.1 Unit Tests

**O1 — Decision Core**:
- `TestComplexityAnalyzer_*` (5+ test cases)
- `TestRiskAnalyzer_*` (5+ test cases)
- `TestTriggerPolicy_*` (8+ test cases)
- `TestPathSelector_*` (4+ test cases)
- `TestDecisionEngine_*` (3+ test cases)

**O2 — Planner/Executor/Reviewer**:
- `TestPlan_Structure_*`
- `TestPlanner_*`
- `TestExecutor_*`
- `TestReviewer_*`
- `TestIntegration_*`

### 8.2 Integration Tests

- `TestPipeline_FastPath_EndToEnd`
- `TestPipeline_DeepPath_EndToEnd`
- `TestPlannerExecutorReviewer_Integration`
- `TestReplan_Integration`

### 8.3 Chaos Tests

- `TestToolFailure_Recovery`
- `TestAgentUnavailable_Fallback`
- `TestTimeout_DuringExecution`
- `TestSequentialThinking_Timeout`

---

## 9. Dipendenze Esterne

### 9.1 MCP Sequential Thinking

Il server MCP `sequential-thinking` deve essere configurato come tool del planner:

```go
// Per O1, il planner usa il tool MCP se disponibile
// MCP tool name: "sequential-thinking"
// Parametri: { "thought": string, "nextThoughtNeeded": bool }
```

Configurazione in `.opencode.json`:
```json
{
  "mcp": {
    "sequential-thinking": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
      "enabled": true
    }
  }
}
```

### 9.2 Feature Flag

Tutti i componenti O1/O2 sono dietro feature flag per allow gradual rollout:

```go
type OrchestratorConfigV2 struct {
    // ...
    FeatureFlags FeatureFlags
}

type FeatureFlags struct {
    EnableDecisionEngine   bool  // O1
    EnablePlannerReviewer  bool  // O2
    EnableRoutingV2        bool  // O3
    EnableTelemetrics      bool  // O5
}
```

---

## 10. Milestone Boundaries

| Milestone | Include | Non include |
|-----------|---------|-------------|
| **O1** | Decision Engine, ComplexityAnalyzer, RiskAnalyzer, TriggerPolicy, PathSelector, OrchestratorPipeline skeleton | Planner/Executor/Reviewer |
| **O2** | Planner, Executor, Reviewer, Plan types, OrchestratorPipeline completion | Routing V2, Prompts |
| **O3** | CapabilityRegistry, PolicyRouter | Slash commands, Telemetry |
| **O4** | Orchestrator prompts, Slash commands | Telemetry |
| **O5** | Telemetry, Metrics, Feedback loop | — |

---

## 11. Checklist Pre-Implementazione O1

- [ ] `internal/aria/core/decision/` package creato
- [ ] `ComplexityAnalyzer` interface + implementation
- [ ] `RiskAnalyzer` interface + implementation  
- [ ] `TriggerPolicy` interface + implementation
- [ ] `PathSelector` interface + implementation
- [ ] `DecisionEngine` interface + implementation
- [ ] Unit tests per ogni componente (coverage >= 80%)
- [ ] `OrchestratorPipeline` skeleton con Fast Path
- [ ] Config `OrchestratorConfigV2` aggiornata
- [ ] Feature flag `EnableDecisionEngine`
- [ ] `go vet` passing
- [ ] Build successful

---

## 12. Riferimenti

- Piano master: `docs/plans/2026-03-30-orchestrator-enhancement-master-plan.md`
- Blueprint: `docs/foundation/BLUEPRINT.md` (v1.12.0-DRAFT)
- Existing orchestrator: `internal/aria/core/orchestrator_impl.go`
- Existing routing: `internal/aria/routing/router.go`, `classifier.go`
