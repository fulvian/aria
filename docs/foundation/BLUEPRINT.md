# ARIA: Autonomous Reasoning & Intelligent Assistant
## Foundation Blueprint Document

> **Version**: 1.10.0-DRAFT  
> **Date**: 2026-03-29  
> **Status**: IN_PROGRESS (FASE 0-4 COMPLETE, FASE 5 IN PROGRESS ~5%)  
> **Base Project**: ARIA CLI (Isola Autonoma rispetto a OpenCode/KiloCode)  

---

## Executive Summary

Questo documento definisce l'architettura fondazionale per **ARIA** (Autonomous Reasoning & Intelligent Assistant), un assistente AI personale a 360 gradi capace di operare in tutti gli ambiti dello scibile umano.

ARIA sarà caratterizzato da:
- **Organizzazione gerarchica**: Agencies → Agents → Skills → Tools/MCP
- **Intelligenza distribuita**: Auto-routing delle query all'entità più appropriata
- **Persistenza temporale**: Task scheduling e gestione di compiti a lungo termine
- **Memoria evolutiva**: Apprendimento dalla storia, auto-analisi periodica
- **Proattività controllata**: Comportamento proattivo con guardrail di autorizzazione

---

## Parte I: Analisi del Sistema Esistente (OpenCode CLI)

### 1.1 Architettura Corrente

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenCode CLI                              │
├─────────────────────────────────────────────────────────────────┤
│  cmd/                     │  Entry point (Cobra CLI)             │
│  internal/app/            │  Application orchestration           │
│  internal/llm/agent/      │  Agent implementation                │
│  internal/llm/provider/   │  LLM providers (Anthropic, OpenAI..) │
│  internal/llm/tools/      │  Native tools (bash, edit, grep...)  │
│  internal/llm/prompt/     │  System prompts per agent type       │
│  internal/config/         │  Configuration (Viper + JSON)        │
│  internal/session/        │  Session management                  │
│  internal/message/        │  Message domain model                │
│  internal/permission/     │  Permission service                  │
│  internal/pubsub/         │  Event-driven communication          │
│  internal/db/             │  SQLite persistence (sqlc)           │
│  internal/tui/            │  Terminal UI (Bubble Tea)            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Componenti Chiave Esistenti

#### 1.2.1 Agent System (`internal/llm/agent/`)

L'attuale sistema di agenti è **flat** (non gerarchico):

```go
type AgentName string

const (
    AgentCoder      AgentName = "coder"      // Main coding agent
    AgentSummarizer AgentName = "summarizer" // Conversation summarization
    AgentTask       AgentName = "task"       // Sub-task execution
    AgentTitle      AgentName = "title"      // Title generation
)
```

**Punti di forza da preservare:**
- Pattern Pub/Sub per eventi (`pubsub.Broker[T]`)
- Interfaccia `Service` con `Run()`, `Cancel()`, `Subscribe()`
- Gestione concorrente con `sync.Map` per active requests
- Tool interface unificata (`BaseTool` con `Info()` e `Run()`)

#### 1.2.2 MCP Integration (`internal/llm/agent/mcp-tools.go`)

Supporto esistente per Model Control Protocol:
- Tipo `MCPStdio` (comando locale)
- Tipo `MCPSse` (Server-Sent Events)
- Wrapping dinamico di tools MCP esterni

#### 1.2.3 Permission System (`internal/permission/`)

Sistema di autorizzazione granulare:
- `Request()` → richiede permesso
- `Grant()` / `Deny()` → risposta utente
- `GrantPersistant()` → permesso persistente per sessione
- `AutoApproveSession()` → bypass per non-interactive mode

#### 1.2.4 Persistence Layer (`internal/db/`)

SQLite con sqlc per:
- Sessions (conversazioni)
- Messages (storia chat)
- Files (cronologia modifiche)

---

## Parte II: Architettura Target ARIA

### 2.1 Gerarchia Organizzativa

```
                    ┌─────────────────────┐
                    │   ARIA CORE         │
                    │   (Orchestrator)    │
                    └─────────┬───────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │   AGENCY A    │ │   AGENCY B    │ │   AGENCY N    │
    │  (Knowledge)  │ │ (Development) │ │    (...)      │
    └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
            │                 │                 │
     ┌──────┴──────┐   ┌──────┴──────┐   ┌──────┴──────┐
     │             │   │             │   │             │
     ▼             ▼   ▼             ▼   ▼             ▼
┌─────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Agent 1 │  │ Agent 2 │ │ Agent 3 │ │ Agent 4 │ │ Agent N │
│(Research│  │(Writing)│ │(Coding) │ │(Review) │ │  (...)  │
└────┬────┘  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     │            │           │           │           │
     ▼            ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SKILLS LAYER                              │
│  • code-review  • web-research  • data-analysis             │
│  • writing      • planning      • scheduling                │
│  • math         • language      • creative                  │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    TOOLS / MCP LAYER                         │
│  • bash         • edit          • grep         • fetch      │
│  • browser      • email         • calendar     • database   │
│  • APIs         • file-system   • git          • search     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Definizioni Entità

#### 2.2.1 ARIA Core (Orchestrator)

Il cervello centrale che:
- Riceve tutte le query utente
- Classifica l'intent e determina il routing
- Coordina le Agencies per task complessi
- Gestisce la memoria globale
- Monitora task a lungo termine
- Esegue auto-analisi periodica

```go
// internal/aria/core/orchestrator.go
type Orchestrator interface {
    // Query processing
    ProcessQuery(ctx context.Context, query Query) (Response, error)
    
    // Routing
    RouteToAgency(ctx context.Context, query Query) (Agency, error)
    RouteToAgent(ctx context.Context, query Query) (Agent, error)
    
    // Task management
    ScheduleTask(ctx context.Context, task Task) (TaskID, error)
    MonitorTasks(ctx context.Context) <-chan TaskEvent
    
    // Self-improvement
    AnalyzeSelf(ctx context.Context) (SelfAnalysis, error)
    Learn(ctx context.Context, experience Experience) error
    
    // Proactive behavior
    GetProactiveSuggestions(ctx context.Context) ([]Suggestion, error)
}
```

#### 2.2.2 Agency

Organizzazione specializzata che:
- Gestisce un dominio di competenza
- Coordina più Agents
- Mantiene stato per task duraturi
- Ha memoria di dominio specifica

```go
// internal/aria/agency/agency.go
type Agency interface {
    pubsub.Subscriber[AgencyEvent]
    
    // Identity
    Name() AgencyName
    Domain() string
    Description() string
    
    // Agent management
    Agents() []Agent
    GetAgent(name AgentName) (Agent, error)
    
    // Task execution
    Execute(ctx context.Context, task Task) (Result, error)
    
    // State management
    GetState() AgencyState
    SaveState(state AgencyState) error
    
    // Domain memory
    Memory() DomainMemory
}

type AgencyName string

const (
    AgencyKnowledge   AgencyName = "knowledge"    // Research, learning, Q&A
    AgencyDevelopment AgencyName = "development"  // Coding, devops, testing
    AgencyCreative    AgencyName = "creative"     // Writing, design, art
    AgencyProductivity AgencyName = "productivity" // Planning, scheduling, organization
    AgencyPersonal    AgencyName = "personal"     // Health, finance, lifestyle
    AgencyAnalytics   AgencyName = "analytics"    // Data analysis, visualization
)
```

#### 2.2.3 Agent (Enhanced)

Estensione dell'attuale Agent:

```go
// internal/aria/agent/agent.go
type Agent interface {
    pubsub.Subscriber[AgentEvent]
    
    // Identity
    Name() AgentName
    Agency() AgencyName
    Capabilities() []Capability
    
    // Execution
    Run(ctx context.Context, task Task) (Result, error)
    Stream(ctx context.Context, task Task) <-chan Event
    
    // Skills
    Skills() []Skill
    HasSkill(name SkillName) bool
    
    // Learning
    LearnFromFeedback(feedback Feedback) error
    
    // State
    GetState() AgentState
}
```

#### 2.2.4 Skill

Capacità modulare riutilizzabile:

```go
// internal/aria/skill/skill.go
type Skill interface {
    Name() SkillName
    Description() string
    
    // Requirements
    RequiredTools() []ToolName
    RequiredMCPs() []MCPName
    
    // Execution
    Execute(ctx context.Context, params SkillParams) (SkillResult, error)
    
    // Validation
    CanExecute(ctx context.Context) (bool, string)
}

type SkillName string

const (
    // Knowledge skills
    SkillWebResearch    SkillName = "web-research"
    SkillDocAnalysis    SkillName = "document-analysis"
    SkillFactCheck      SkillName = "fact-check"
    
    // Development skills
    SkillCodeReview     SkillName = "code-review"
    SkillTDD            SkillName = "test-driven-dev"
    SkillDebugging      SkillName = "systematic-debugging"
    SkillRefactoring    SkillName = "refactoring"
    
    // Creative skills
    SkillWriting        SkillName = "creative-writing"
    SkillSummarization  SkillName = "summarization"
    SkillTranslation    SkillName = "translation"
    
    // Productivity skills
    SkillPlanning       SkillName = "planning"
    SkillScheduling     SkillName = "scheduling"
    SkillReminders      SkillName = "reminders"
    
    // Analytics skills
    SkillDataAnalysis   SkillName = "data-analysis"
    SkillVisualization  SkillName = "visualization"
)
```

### 2.3 Sistema di Routing delle Query

#### 2.3.1 Query Classification

```go
// internal/aria/routing/classifier.go
type QueryClassifier interface {
    Classify(ctx context.Context, query string) (Classification, error)
}

type Classification struct {
    Intent       Intent           // Cosa vuole l'utente
    Domain       DomainName       // Dominio di competenza
    Complexity   ComplexityLevel  // Simple, Medium, Complex
    RequiresState bool            // Richiede contesto persistente?
    Urgency      UrgencyLevel     // Now, Soon, Eventually
    
    // Routing suggestion
    SuggestedTarget RoutingTarget // Agency, Agent, or Skill
}

type Intent string

const (
    IntentQuestion     Intent = "question"      // Domanda semplice
    IntentTask         Intent = "task"          // Compito da eseguire
    IntentCreation     Intent = "creation"      // Creare qualcosa
    IntentAnalysis     Intent = "analysis"      // Analizzare dati
    IntentLearning     Intent = "learning"      // Imparare/spiegare
    IntentPlanning     Intent = "planning"      // Pianificare
    IntentConversation Intent = "conversation"  // Chiacchierata
)
```

#### 2.3.2 Routing Decision Tree

```
Query Received
     │
     ▼
┌────────────────┐
│ Classification │ ← Intent, Domain, Complexity
└───────┬────────┘
        │
        ▼
┌───────────────────┐
│ Complexity Check  │
└───────┬───────────┘
        │
        ├── Simple (Single-turn) ──────────► Direct Agent Response
        │
        ├── Medium (Multi-step) ───────────► Agent with Skills
        │
        └── Complex (Long-running) ────────► Agency Coordination
                    │
                    ▼
            ┌───────────────────┐
            │ Agency Selection  │
            └───────┬───────────┘
                    │
                    ├── Single Domain ────────► Single Agency
                    │
                    └── Cross-Domain ─────────► Multi-Agency
                                                Orchestration
```

#### 2.3.3 Router Implementation

```go
// internal/aria/routing/router.go
type Router interface {
    Route(ctx context.Context, query Query) (RoutingDecision, error)
}

type RoutingDecision struct {
    Target      RoutingTarget
    Agency      *AgencyName       // If routed to agency
    Agent       *AgentName        // If routed to agent
    Skills      []SkillName       // Skills to use
    Confidence  float64           // 0.0 - 1.0
    Explanation string            // Why this routing
}

type RoutingTarget string

const (
    TargetOrchestrator RoutingTarget = "orchestrator"
    TargetAgency       RoutingTarget = "agency"
    TargetAgent        RoutingTarget = "agent"
    TargetSkill        RoutingTarget = "skill"
)
```

---

## Parte III: Sistema di Memoria e Apprendimento

### 3.1 Architettura della Memoria

```
┌─────────────────────────────────────────────────────────────────┐
│                      MEMORIA ARIA                                │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  WORKING        │   EPISODIC      │        SEMANTIC             │
│  MEMORY         │   MEMORY        │        MEMORY               │
│                 │                 │                             │
│  • Contesto     │  • Conversazioni│  • Knowledge base           │
│    corrente     │  • Task passati │  • Facts & preferences      │
│  • Task attivo  │  • Successi/fail│  • Domain expertise         │
│  • Stato temp   │  • Feedback     │  • Learned patterns         │
│                 │                 │                             │
├─────────────────┴─────────────────┴─────────────────────────────┤
│                     PROCEDURAL MEMORY                            │
│                                                                  │
│  • Workflows appresi    • Best practices    • Automazioni       │
│  • Pattern ricorrenti   • Shortcuts         • Scripts salvati   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Memory Service Interface

```go
// internal/aria/memory/memory.go
type MemoryService interface {
    // Working memory
    GetContext(ctx context.Context, sessionID string) (Context, error)
    SetContext(ctx context.Context, sessionID string, context Context) error
    
    // Episodic memory
    RecordEpisode(ctx context.Context, episode Episode) error
    SearchEpisodes(ctx context.Context, query EpisodeQuery) ([]Episode, error)
    GetSimilarEpisodes(ctx context.Context, situation Situation) ([]Episode, error)
    
    // Semantic memory
    StoreFact(ctx context.Context, fact Fact) error
    GetFacts(ctx context.Context, domain string) ([]Fact, error)
    QueryKnowledge(ctx context.Context, query string) ([]KnowledgeItem, error)
    
    // Procedural memory
    SaveProcedure(ctx context.Context, procedure Procedure) error
    GetProcedure(ctx context.Context, name string) (Procedure, error)
    FindApplicableProcedures(ctx context.Context, task Task) ([]Procedure, error)
    
    // Learning
    LearnFromSuccess(ctx context.Context, action Action, outcome Outcome) error
    LearnFromFailure(ctx context.Context, action Action, error error) error
    
    // Self-analysis
    GetPerformanceMetrics(ctx context.Context, timeRange TimeRange) (Metrics, error)
    GenerateInsights(ctx context.Context) ([]Insight, error)
}

type Episode struct {
    ID          string
    Timestamp   time.Time
    SessionID   string
    AgencyID    AgencyName
    AgentID     AgentName
    Task        Task
    Actions     []Action
    Outcome     Outcome
    Feedback    *Feedback
    Embedding   []float32 // For similarity search
}

type Fact struct {
    ID          string
    Domain      string
    Category    string
    Content     string
    Source      string
    Confidence  float64
    CreatedAt   time.Time
    LastUsed    time.Time
    UseCount    int64
}

type Procedure struct {
    ID          string
    Name        string
    Description string
    Trigger     TriggerCondition
    Steps       []ProcedureStep
    SuccessRate float64
    UseCount    int64
}
```

### 3.3 Storage Backend

```go
// internal/aria/memory/store/store.go
type MemoryStore interface {
    // Vector storage for embeddings
    StoreEmbedding(ctx context.Context, id string, embedding []float32, metadata map[string]any) error
    SearchSimilar(ctx context.Context, query []float32, limit int) ([]SimilarityResult, error)
    
    // Structured storage
    StoreDocument(ctx context.Context, collection string, doc Document) error
    GetDocument(ctx context.Context, collection string, id string) (Document, error)
    QueryDocuments(ctx context.Context, collection string, query Query) ([]Document, error)
    
    // Time-series storage
    StoreMetric(ctx context.Context, metric Metric) error
    GetMetrics(ctx context.Context, name string, range TimeRange) ([]Metric, error)
}
```

---

## Parte IV: Sistema di Task Scheduling

### 4.1 Task Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ CREATED  │───►│ QUEUED   │───►│ RUNNING  │───►│COMPLETED │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │               │               │               │
     ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│CANCELLED │    │ DEFERRED │    │  PAUSED  │    │  FAILED  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                     │               │               │
                     └───────────────┴───────────────┘
                                     │
                                     ▼
                              ┌──────────┐
                              │  RETRY   │
                              └──────────┘
```

### 4.2 Task Scheduler Interface

```go
// internal/aria/scheduler/scheduler.go
type Scheduler interface {
    // Task management
    Schedule(ctx context.Context, task Task) (TaskID, error)
    Cancel(ctx context.Context, taskID TaskID) error
    Pause(ctx context.Context, taskID TaskID) error
    Resume(ctx context.Context, taskID TaskID) error
    
    // Queries
    GetTask(ctx context.Context, taskID TaskID) (Task, error)
    ListTasks(ctx context.Context, filter TaskFilter) ([]Task, error)
    
    // Monitoring
    Subscribe(ctx context.Context) <-chan TaskEvent
    GetProgress(ctx context.Context, taskID TaskID) (Progress, error)
    
    // Recurring tasks
    ScheduleRecurring(ctx context.Context, task RecurringTask) (TaskID, error)
    UpdateSchedule(ctx context.Context, taskID TaskID, schedule Schedule) error
}

type Task struct {
    ID          TaskID
    Name        string
    Description string
    Type        TaskType
    Priority    Priority
    
    // Scheduling
    ScheduledAt   *time.Time
    Deadline      *time.Time
    Schedule      *Schedule // For recurring tasks
    
    // Execution
    Agency        AgencyName
    Agent         AgentName
    Skills        []SkillName
    Parameters    map[string]any
    
    // State
    Status        TaskStatus
    Progress      float64 // 0.0 - 1.0
    CreatedAt     time.Time
    StartedAt     *time.Time
    CompletedAt   *time.Time
    
    // Dependencies
    DependsOn     []TaskID
    Blocks        []TaskID
    
    // Results
    Result        *TaskResult
    Error         *TaskError
}

type TaskType string

const (
    TaskTypeImmediate   TaskType = "immediate"   // Execute now
    TaskTypeScheduled   TaskType = "scheduled"   // Execute at specific time
    TaskTypeRecurring   TaskType = "recurring"   // Repeat on schedule
    TaskTypeBackground  TaskType = "background"  // Low-priority background work
    TaskTypeDependent   TaskType = "dependent"   // Wait for dependencies
)

type Schedule struct {
    Type       ScheduleType // cron, interval, specific_times
    Expression string       // Cron expression or interval
    Timezone   string
    StartDate  *time.Time
    EndDate    *time.Time
}
```

### 4.3 Task Persistence

```sql
-- migrations/004_tasks.sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    
    scheduled_at INTEGER,
    deadline INTEGER,
    schedule_expr TEXT,
    
    agency TEXT,
    agent TEXT,
    skills TEXT, -- JSON array
    parameters TEXT, -- JSON object
    
    status TEXT NOT NULL DEFAULT 'created',
    progress REAL DEFAULT 0.0,
    
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER,
    
    result TEXT, -- JSON
    error TEXT   -- JSON
);

CREATE TABLE task_dependencies (
    task_id TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (depends_on) REFERENCES tasks(id)
);

CREATE TABLE task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT, -- JSON
    created_at INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

---

## Parte V: Sistema di Autorizzazione e Guardrail

### 5.1 Permission Model Esteso

```go
// internal/aria/permission/permission.go
type PermissionLevel int

const (
    PermissionNone        PermissionLevel = 0  // Nessun permesso
    PermissionAsk         PermissionLevel = 1  // Chiedi sempre
    PermissionNotify      PermissionLevel = 2  // Notifica ma esegui
    PermissionAuto        PermissionLevel = 3  // Esegui automaticamente
)

type PermissionScope string

const (
    ScopeSession      PermissionScope = "session"       // Solo sessione corrente
    ScopeTask         PermissionScope = "task"          // Solo task corrente
    ScopePermanent    PermissionScope = "permanent"     // Permanente
    ScopeTemporary    PermissionScope = "temporary"     // Con scadenza
)

type PermissionRule struct {
    ID          string
    Action      ActionType
    Resource    ResourcePattern
    Level       PermissionLevel
    Scope       PermissionScope
    ExpiresAt   *time.Time
    Conditions  []Condition
}

type ActionType string

const (
    ActionRead       ActionType = "read"
    ActionWrite      ActionType = "write"
    ActionExecute    ActionType = "execute"
    ActionDelete     ActionType = "delete"
    ActionNetwork    ActionType = "network"
    ActionSchedule   ActionType = "schedule"
    ActionNotify     ActionType = "notify"
)
```

### 5.2 Guardrail per Comportamento Proattivo

```go
// internal/aria/guardrail/guardrail.go
type GuardrailService interface {
    // Check before action
    CanExecute(ctx context.Context, action ProactiveAction) (bool, string, error)
    
    // Rate limiting
    GetActionBudget(ctx context.Context, actionType ActionType) (Budget, error)
    ConsumeAction(ctx context.Context, action ProactiveAction) error
    
    // User preferences
    GetUserPreferences(ctx context.Context) (ProactivePreferences, error)
    UpdatePreferences(ctx context.Context, prefs ProactivePreferences) error
    
    // Audit
    LogAction(ctx context.Context, action ProactiveAction, outcome Outcome) error
    GetAuditLog(ctx context.Context, filter AuditFilter) ([]AuditEntry, error)
}

type ProactivePreferences struct {
    // What ARIA can do proactively
    AllowedActions      []ActionType
    ForbiddenActions    []ActionType
    
    // When ARIA can act
    QuietHours          []TimeRange
    ActiveHours         []TimeRange
    
    // How ARIA should notify
    NotificationLevel   NotificationLevel
    NotifyChannels      []NotifyChannel
    
    // Limits
    MaxDailyActions     int
    MaxPendingSuggestions int
    
    // Auto-approval rules
    AutoApprovePatterns []AutoApproveRule
}

type ProactiveAction struct {
    ID          string
    Type        ActionType
    Description string
    Impact      ImpactLevel // Low, Medium, High, Critical
    Reversible  bool
    Reason      string
    Context     map[string]any
}
```

### 5.3 Approval Workflow

```
┌─────────────────┐
│ Proactive Action│
│   Generated     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Impact Analysis │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────────┐
│ Low   │ │ Med/High  │
└───┬───┘ └─────┬─────┘
    │           │
    ▼           ▼
┌───────────┐ ┌─────────────┐
│Auto-check │ │User Approval│
│ Rules     │ │  Required   │
└─────┬─────┘ └──────┬──────┘
      │              │
      ├──────────────┤
      │              │
      ▼              ▼
┌───────────┐  ┌───────────┐
│  Execute  │  │   Queue   │
│   Now     │  │  for User │
└───────────┘  └───────────┘
```

---

## Parte VI: Self-Analysis e Learning System

### 6.1 Auto-Analisi Periodica

```go
// internal/aria/analysis/self_analysis.go
type SelfAnalysisService interface {
    // Scheduled analysis
    RunPeriodicAnalysis(ctx context.Context) error
    
    // On-demand analysis
    AnalyzePerformance(ctx context.Context, timeRange TimeRange) (PerformanceReport, error)
    AnalyzePatterns(ctx context.Context) (PatternReport, error)
    AnalyzeFailures(ctx context.Context) (FailureReport, error)
    
    // Improvement suggestions
    GenerateImprovements(ctx context.Context) ([]Improvement, error)
    
    // Learning from analysis
    ApplyInsights(ctx context.Context, insights []Insight) error
}

type PerformanceReport struct {
    Period          TimeRange
    TotalTasks      int64
    SuccessRate     float64
    AverageTime     time.Duration
    
    ByAgency        map[AgencyName]AgencyMetrics
    ByAgent         map[AgentName]AgentMetrics
    BySkill         map[SkillName]SkillMetrics
    
    Trends          []Trend
    Anomalies       []Anomaly
}

type PatternReport struct {
    RecurringTasks      []RecurringPattern
    CommonWorkflows     []WorkflowPattern
    UserPreferences     []PreferencePattern
    OptimizationOpps    []Optimization
}

type Improvement struct {
    ID          string
    Type        ImprovementType
    Description string
    Impact      ImpactEstimate
    Confidence  float64
    AutoApply   bool
    AppliedAt   *time.Time
}
```

### 6.2 Learning Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    LEARNING CYCLE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │EXPERIENCE│───►│ REFLECT  │───►│ ABSTRACT │───►│  APPLY   │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │                                               │         │
│        └───────────────────────────────────────────────┘         │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  EXPERIENCE: Execute tasks, receive feedback                    │
│  REFLECT: Analyze outcomes, identify patterns                   │
│  ABSTRACT: Extract generalizable knowledge                      │
│  APPLY: Update procedures, adjust behavior                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Parte VII: Agencies Iniziali

### 7.1 Knowledge Agency

Dominio: Ricerca, apprendimento, Q&A generale

```yaml
name: knowledge
description: "Research, learning, and general knowledge"
agents:
  - researcher:
      description: "Deep research on any topic"
      skills: [web-research, document-analysis, fact-check]
  - educator:
      description: "Explain concepts, teach"
      skills: [summarization, simplification, examples]
  - analyst:
      description: "Analyze information, find connections"
      skills: [data-analysis, comparison, synthesis]
```

### 7.2 Development Agency

Dominio: Coding, DevOps, testing (eredita da OpenCode)

```yaml
name: development
description: "Software development, coding, DevOps"
agents:
  - coder:
      description: "Write and modify code"
      skills: [code-review, tdd, refactoring, debugging]
  - architect:
      description: "Design systems and architectures"
      skills: [system-design, documentation, api-design]
  - devops:
      description: "CI/CD, deployment, infrastructure"
      skills: [docker, kubernetes, monitoring, scripting]
  - reviewer:
      description: "Code review and quality"
      skills: [code-review, security-audit, performance]
```

### 7.3 Creative Agency

Dominio: Scrittura, design, contenuti

```yaml
name: creative
description: "Writing, design, and creative content"
agents:
  - writer:
      description: "Write content of any type"
      skills: [creative-writing, copywriting, editing]
  - translator:
      description: "Translate between languages"
      skills: [translation, localization, transcreation]
  - designer:
      description: "Visual and UX design"
      skills: [mockup, wireframe, brand-design]
```

### 7.4 Productivity Agency

Dominio: Pianificazione, organizzazione, gestione tempo

```yaml
name: productivity
description: "Planning, scheduling, and organization"
agents:
  - planner:
      description: "Plan projects and activities"
      skills: [planning, task-breakdown, prioritization]
  - scheduler:
      description: "Manage calendar and reminders"
      skills: [scheduling, reminders, time-management]
  - organizer:
      description: "Organize information and files"
      skills: [categorization, tagging, search-optimization]
```

### 7.5 Personal Agency

Dominio: Assistenza personale, lifestyle

```yaml
name: personal
description: "Personal assistance and lifestyle"
agents:
  - assistant:
      description: "General personal assistance"
      skills: [email-management, shopping, recommendations]
  - wellness:
      description: "Health and wellness tracking"
      skills: [habit-tracking, exercise, nutrition]
  - finance:
      description: "Financial management"
      skills: [budgeting, expense-tracking, investment]
```

---

## Parte VIII: Roadmap di Implementazione

### 8.1 Overview delle Macro-Fasi

```
┌─────────────────────────────────────────────────────────────────┐
│                    ROADMAP ARIA                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FASE 0: FOUNDATION         ████████████████████████████████  (100%)│
│  [Mese 1-2]                 COMPLETE ✓                          │
│                                                                  │
│  FASE 1: CORE SYSTEM        ████████████████████████████████  (100%)│
│  [Mese 2-4]                 COMPLETE ✓                          │
│                             - Orchestrator ✓                     │
│                             - Development Agency ✓              │
│                             - Agency Registry ✓                  │
│                             - Agency Lifecycle ✓                 │
│                             - Skill System ✓ (real tools)       │
│                             - Routing baseline ✓                  │
│                             - Enhanced Agent ✓                   │
│                             - CLI integration ✓                  │
│                                                                  │
│  FASE 2: MEMORY & LEARNING  ████████████████████████████████  (100%)│
│  [Mese 4-6]                 Memory system, learning loop        │
│                             - MemoryService ✓                     │
│                             - Storage backend ✓                   │
│                             - Learning loop ✓                    │
│                             - Self-analysis ✓                    │
│                             - WS1-WS8 complete ✓                │
│                             - E2E test ✓                          │
│                                                                  │
│  FASE 3: SCHEDULING         ████████████████████████████████  (100%)│
│  [Mese 6-7]                 Task scheduler, persistence         │
│                             - SchedulerService ✓                  │
│                             - Task persistence ✓                  │
│                             - Recurring tasks ✓                  │
│                             - TUI integration ✓                  │
│                                                                  │
│  FASE 4: PROACTIVITY        ████████████████████████████████  (100%)│
│  [Mese 7-8]                 Proactive behavior, guardrails       │
│                             - GuardrailService ✓                  │
│                             - ExtendedPermissionService ✓        │
│                             - Budget tracking ✓                  │
│                             - Auto-approve rules ✓               │
│                             ⚠️ Suggestion engine DEFERRED        │
│                                                                  │
│  FASE 5: AGENCIES           ███░░░░░░░░░░░░░░░░░░░░░░░  (10%)   │
│  [Mese 8-12]                Weather Agency POC ✓                │
│                             AgencyService persistence ✓          │
│                             - Weather Agency ✓ (POC)            │
│                             - Knowledge Agency (planning)        │
│                             - Creative Agency (planning)        │
│                             - Productivity Agency (planning)     │
│                             - Personal Agency (planning)        │
│                             - Analytics Agency (planning)       │
│                                                                  │
│  FASE 6: POLISH & EXPAND    ░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
│  [Ongoing]                  Refinement, new capabilities        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 FASE 0: Foundation (Setup e Preparazione)

**Durata**: 4-6 settimane  
**Obiettivo**: Preparare la codebase per l'espansione

#### 8.2.1 Task

1. **Refactoring directory structure**
   ```
   internal/
   ├── aria/                    # NEW: ARIA core system
   │   ├── core/               # Orchestrator
   │   ├── agency/             # Agency system
   │   ├── agent/              # Enhanced agents
   │   ├── skill/              # Skills system
   │   ├── routing/            # Query routing
   │   ├── memory/             # Memory system
   │   ├── scheduler/          # Task scheduling
   │   ├── permission/         # Enhanced permissions
   │   └── analysis/           # Self-analysis
   ├── llm/                    # KEEP: LLM infrastructure
   ├── db/                     # EXTEND: Add new tables
   └── ...
   ```

2. **Database schema extension**
   - Nuove tabelle per agencies, tasks, memory
   - Migrazioni SQLite

3. **Configuration extension**
   - Nuovo formato config per agencies
   - Skills configuration
   - Scheduler configuration

4. **Base interfaces definition**
   - Definire tutte le interfacce core
   - Test scaffolding

#### 8.2.2 Deliverables
- [x] Nuova struttura directory
- [x] Schema database esteso
- [x] Interfacce Go definite
- [ ] Test suite base
- [x] Documentazione architetturale

---

### 8.3 FASE 1: Core System

**Durata**: 6-8 settimane  
**Obiettivo**: Implementare il sistema Agency/Agent
**Stato**: COMPLETE ✅

#### 8.3.1 Task

1. **Orchestrator implementation** ✅ COMPLETE
   - [x] Query processing pipeline
   - [x] Basic routing logic
   - [x] Agency/Agent coordination
   - [x] ScheduleTask (in-memory queue)
   - [x] MonitorTasks (periodic events)
   - [x] AnalyzeSelf (basic metrics)
   - [x] Learn (experience storage)

2. **Agency system** ✅ COMPLETE
   - [x] Agency interface implementation
   - [x] Agency registry (DefaultAgencyRegistry)
   - [x] Development Agency implementation
   - [x] Agency lifecycle management (Start/Stop/Pause/Resume)

3. **Enhanced Agent system** ✅ COMPLETE
   - [x] LegacyAgentWrapper implementation
   - [x] Skills integration
   - [x] Run/Stream/Cancel methods
   - [x] Subscribe for events

4. **Skill system** ✅ COMPLETE
   - [x] Skill interface
   - [x] Skill registry
   - [x] CodeReviewSkill with real tool integration (grep, glob, view)
   - [x] TDDSkill with real TDD workflow
   - [x] DebuggingSkill with systematic debugging

5. **Routing system** ✅ MVP COMPLETE
   - [x] Intent classifier
   - [x] Baseline rules
   - [ ] Complexity analyzer improvements (deferred to FASE 2)

6. **CLI Integration** ✅ COMPLETE
   - [x] Wire ARIA mode to prompt loop
   - [x] Task execution flow (Orchestrator → Agency → Agent → Skill)
   - [x] Agent bridge to legacy coder

#### 8.3.2 Deliverables
- [x] Orchestrator funzionante
- [x] 1+ Agency implementata (Development)
- [x] 3+ Skills con esecuzione reale (CodeReview, TDD, Debugging)
- [x] Routing base funzionante
- [x] CLI updated per nuova architettura
- [x] Agency Registry per gestione multiple agencies
- [x] Agency Lifecycle (Start/Stop/Pause/Resume)

---

### 8.4 FASE 2: Memory & Learning

**Durata**: 6-8 settimane  
**Obiettivo**: Implementare sistema di memoria evolutivo
**Stato**: COMPLETE ✅

#### 8.4.1 Task

1. **Memory service** ✅ COMPLETE
   - [x] Working memory (session context) with sync.Map
   - [x] Episodic memory (conversation history)
   - [x] Semantic memory (knowledge base)
   - [x] Procedural memory (learned workflows)

2. **Storage backend** ✅ COMPLETE
   - [x] SQLite extensions (episodes, facts, procedures tables)
   - [x] working_memory_contexts table for context persistence
   - [x] Memory indexing e retrieval

3. **Learning loop** ✅ COMPLETE
   - [x] Experience recording (LearnFromSuccess/LearnFromFailure)
   - [x] Pattern extraction (DiscoverProcedures)
   - [x] Procedure generation with scoring
   - [x] Feedback integration

4. **Self-analysis** ✅ COMPLETE
   - [x] Performance metrics collection (AnalyzePerformance)
   - [x] Time-range aware analysis
   - [x] Periodic analysis jobs (RunPeriodicAnalysis)
   - [x] Insight generation (GenerateImprovements)

#### 8.4.2 Deliverables
- [x] Memory service completo (internal/aria/memory/service.go)
- [x] Storage backend funzionante (usa DB/sqlc esistente)
- [x] Learning loop base (LearnFromSuccess/LearnFromFailure)
- [x] Self-analysis reports (internal/aria/analysis/service.go)
- [x] **WS1**: Integration backbone (MemoryService + AnalysisService wired to runtime)
- [x] **WS2**: Working memory durability (TTL, GC, context persistence)
- [x] **WS3**: Episodic retrieval 2.0 (full filters + ranking)
- [x] **WS4**: Semantic memory governance (usage tracking, dedup)
- [x] **WS5**: Procedural learning engine (scoring, discovery)
- [x] **WS6**: Self-analysis hardening (time-range, persistence)
- [x] **WS7**: Privacy/Retention (configurable policies)
- [x] **WS8**: Quality gates (tests and benchmarks)
- [x] E2E integration test (TestE2E_MemoryLearningFlow with real DB)

---

### 8.5 FASE 3: Scheduling

**Durata**: 4-6 settimane  
**Obiettivo**: Task scheduling persistente
**Stato**: COMPLETE ✅

#### 8.5.1 Task

1. **Scheduler service** ✅ COMPLETE
   - [x] Task queue management
   - [x] Priority handling
   - [x] Dependency resolution

2. **Persistence layer** ✅ COMPLETE
   - [x] Task storage
   - [x] State management
   - [x] Recovery dopo restart

3. **Recurring tasks** ✅ COMPLETE
   - [x] Cron-like scheduling
   - [x] Interval-based tasks
   - [x] One-time scheduled tasks

4. **Monitoring** ✅ COMPLETE
   - [x] Progress tracking
   - [x] Event notifications
   - [x] Task history

#### 8.5.2 Deliverables
- [x] Scheduler service completo (internal/aria/scheduler/service.go)
- [x] Task persistence (tasks table, task_events table)
- [x] Recurring tasks (recurring.go with cron/interval parsing)
- [x] TUI per task management (internal/tui/page/tasks_page.go)

---

### 8.6 FASE 4: Proactivity

**Durata**: 4-6 settimane  
**Obiettivo**: Comportamento proattivo controllato
**Stato**: COMPLETE ✅ (Guardrails/permissions) - Proactive engine DEFERRED

#### 8.6.1 Task

1. **Proactive engine** ⚠️ DEFERRED to FASE 5+
   - Suggestion generation (deferred to future phase)
   - Action planning (deferred)
   - User notification (deferred)

2. **Guardrails** ✅ COMPLETE
   - [x] Permission levels
   - [x] Rate limiting
   - [x] Audit logging

3. **User preferences** ✅ COMPLETE
   - [x] Quiet hours
   - [x] Action budgets
   - [x] Auto-approval rules

4. **Notification system** ⚠️ DEFERRED to FASE 5+
   - TUI notifications (deferred)
   - External notifications (deferred)

#### 8.6.2 Deliverables
- [x] GuardrailService (internal/aria/guardrail/service.go)
- [x] ExtendedPermissionService (internal/aria/permission/service.go)
- [x] Budget tracking in-memory with window reset
- [x] Audit log with retention
- [x] QuietHours and ActiveHours validation
- [x] AutoApproveRules for low-impact actions

---

### 8.7 FASE 5: Agencies

**Durata**: 8-12 settimane  
**Obiettivo**: Implementare agencies specializzate
**Stato**: IN PROGRESS (~10%) - Weather Agency POC complete

#### Implementation Order

1. **Weather Agency** ✅ COMPLETE (POC) - Direct API integration, ~100 tokens/call
2. **Knowledge Agency** (Settimana 1-2) - Research, web search, Q&A
3. **Creative Agency** (Settimana 3-4) - Writing, translation, content
4. **Productivity Agency** (Settimana 5-7) - Planning, calendar, organization
5. **Personal Agency** (Settimana 7-8) - Assistant, wellness, finance
6. **Analytics Agency** (Settimana 9-11) - Data analysis, visualization

#### 8.7.1 Task

1. **Agency Persistence Layer** ✅ COMPLETE
   - [x] AgencyService with CRUD operations
   - [x] Load/SaveAgencyState for full state persistence
   - [x] agency_states table with metrics JSON support
   - [x] PersistableAgencyRegistry for auto-persist

2. **Weather Agency** ✅ COMPLETE (POC)
   - [x] Direct OpenWeatherMap API integration (~100 tokens/call vs ~350 for MCP)
   - [x] Skills: weather-current, weather-forecast, weather-alerts
   - [x] Tool: internal/llm/tools/weather.go
   - [x] Bridge pattern for agency integration

3. **Knowledge Agency** ⚠️ NOT STARTED
   - Web research integration
   - Document analysis
   - Q&A capabilities

4. **Creative Agency** ⚠️ NOT STARTED
   - Writing tools
   - Translation
   - Content generation

5. **Productivity Agency** ⚠️ NOT STARTED
   - Planning tools
   - Calendar integration
   - Task management

6. **Personal Agency** ⚠️ NOT STARTED
   - Personal assistant features
   - Lifestyle tracking
   - Recommendations

7. **Analytics Agency** ⚠️ NOT STARTED
   - Data analysis
   - Visualization
   - Reporting

#### 8.7.2 Deliverables
- [ ] 5+ agencies funzionanti
- [ ] 20+ skills implementati
- [ ] MCP integrations per external tools
- [ ] Comprehensive testing

**Piano dettagliato**: `docs/plans/2026-03-29-fase5-agencies-implementation-plan.md`

---

### 8.8 FASE 6: Polish & Expand

**Durata**: Ongoing  
**Obiettivo**: Raffinamento e espansione

#### 8.8.1 Task

1. **Performance optimization**
2. **UX improvements**
3. **New capabilities**
4. **Community features**
5. **Plugin system**

---

## Parte IX: Technical Decisions

### 9.1 Scelte Architetturali

| Decisione | Scelta | Motivazione |
|-----------|--------|-------------|
| Database | SQLite + sqlc | Già in uso, zero dependencies, embedded |
| Vector storage | SQLite-vec | Keep everything in SQLite |
| Event system | Pub/Sub pattern | Già implementato, funziona bene |
| Configuration | Viper + JSON + Env Vars | OpenCode uses Viper, ARIA uses env vars (ARIA_*) |
| CLI framework | Cobra | Già in uso |
| TUI framework | Bubble Tea | Già in uso |
| LLM providers | Multi-provider | Già supportati 10+ providers |
| MCP | Standard MCP | Già supportato |
| ARIA Config | Separated env vars | `ARIA_*` prefix, completely independent from opencode config |

### 9.2 Tool Integration Pattern (Best Practices)

### 9.2.1 Problem: MCP Token Overhead

MCP (Model Context Protocol) è dispendioso in termini di token di contesto:

| Pattern | Token/Call | 1000 Calls | Overhead |
|---------|------------|------------|----------|
| Native Tool | ~50 | 50K | Baseline |
| Direct API | ~100 | 100K | +100% |
| MCP | ~350 | 350K | +600% |

### 9.2.2 Solution: Hybrid Tool Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL INTEGRATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│   │  Native Tools   │  │  Direct APIs    │  │   MCP Servers   │   │
│   │  (internal)    │  │  (external)     │  │   (last resort) │   │
│   │                │  │                  │  │                  │   │
│   │  • bash       │  │  • Weather API  │  │  • Enterprise   │   │
│   │  • grep       │  │  • Calendar API   │  │    (Slack,     │   │
│   │  • edit       │  │  • Search API    │  │    Jira)        │   │
│   │  • glob       │  │  • Database      │  │  • Dynamic      │   │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                  │
│   LEGEND:                                                         │
│   ──────                                                          │
│   Native Tools: Direct Function Calling - lowest overhead          │
│   Direct APIs: HTTP calls from Skills - efficient                │
│   MCP Servers: Only for enterprise + dynamic discovery           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2.3 When to Use Each Pattern

| Scenario | Pattern | Reason |
|----------|---------|--------|
| bash, grep, edit, glob | Native Function Calling | Fixed interface, already implemented |
| Weather, Calendar, Search | Direct API from Skill | Known endpoints, no discovery needed |
| Slack, Jira, Enterprise | MCP | Tool discovery, enterprise governance |
| Filesystem | Native (existing) | Already implemented |

### 9.2.4 Decision Matrix

| Criteria | Native | Direct API | MCP |
|----------|--------|-----------|-----|
| Token cost | Lowest | Medium | High |
| Latency | Lowest | Medium | Medium-High |
| Tool discovery | No | No | Yes |
| Enterprise governance | No | No | Yes |
| Best for | Core tools | External services | Dynamic tools |

### 9.2.5 MCP is NOT appropriate for:

1. **Fixed APIs**: Weather, Calendar, Search (known endpoints)
2. **Token-sensitive operations**: High-volume tool calls
3. **Simple integrations**: Direct HTTP is more efficient

### 9.2.6 MCP is appropriate when:

1. **Enterprise governance required**: Centralized tool management
2. **Dynamic tool discovery**: Tools that change or are added frequently
3. **Multi-agent scenarios**: Agent-to-agent communication
4. **Community plugins**: External tool providers

---

## 9.3 L'Isola di ARIA: Architettura di Isolamento

ARIA è progettato come **isola autonoma** all'interno dell'ecosistema OpenCode/KiloCode. Questo approccio garantisce:

#### 9.2.1 Configurazione Completamente Separata

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARIA ISLAND (Isola Autonoma)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  internal/aria/config/  (ARIA_ prefixed env vars ONLY)   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  internal/aria/*  (Namespace isolato)                    │   │
│   │  - core/          - agency/      - agent/              │   │
│   │  - skill/         - routing/     - memory/             │   │
│   │  - scheduler/     - permission/  - guardrail/          │   │
│   │  - analysis/                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  internal/db/migrations/004_aria_* (Tabelle isolate)    │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
              │                                    │
              │         SHARED INFRASTRUCTURE      │
              │                                    │
┌─────────────────────────────────────────────────────────────────┐
│  internal/llm/provider/*  (LLM providers condivisi)             │
│  internal/llm/tools/*    (Tools condivisi)                      │
│  internal/tui/*          (UI condivisa)                         │
│  internal/db/*           (DB engine condiviso, schema isolato) │
└─────────────────────────────────────────────────────────────────┘
```

#### 9.2.2 Principi di Isolamento

1. **Namespace Codice Isolato**: Tutto il codice ARIA vive in `internal/aria/*`, completamente separato da `internal/llm/*`, `internal/tui/*`, etc.

2. **Configurazione Indipendente**: 
   - OpenCode/KiloCode: `internal/config/config.go` con Viper (formati JSON, env vars `OPENCODE_*`)
   - ARIA: `internal/aria/config/config.go` con env vars `ARIA_*` (nessuna dipendenza da Viper)

3. **Opt-in Globale**: 
   - `ARIA_ENABLED=true` attiva la modalità ARIA
   - `ARIA_ENABLED=false` (default) usa il behavior legacy
   - Ogni agency/skill/feature può essere abilitata singolarmente

4. **Database Schema Isolato per Dominio**:
   - Tabelle ARIA: `episodes`, `facts`, `procedures`, `tasks`, `agencies`, `task_events`, `working_memory_contexts`
   - Tabelle OpenCode esistenti: `sessions`, `messages`, `files` (non toccate)

5. **Runtime Condiviso ma Esecuzione Isolata**:
   - LLM providers, tools, TUI sono condivisi
   - L'orchestrator ARIA gestisce solo le query ARIA-mode
   - Fallback automatico al coder legacy quando necessario

#### 9.2.3 Vantaggi dell'Isola

| Vantaggio | Descrizione |
|-----------|-------------|
| **Sicurezza** | Bug in ARIA non compromettono OpenCode e viceversa |
| **Sviluppo Indipendente** | Team diversi possono lavorare su entrambi senza conflitti |
| **Migrazione Graduale** | Nuove features ARIA possono essere aggiunte senza toccare il codice esistente |
| **Rollback Semplice** | Disabilitando `ARIA_ENABLED` si torna al behavior precedente |
| **Test Indipendenti** | Test ARIA non dipendono dalla configurazione OpenCode |

### 9.3 Principi di Design

1. **Backward Compatibility**: Mantenere compatibilità con configurazioni OpenCode esistenti. ARIA è completamente separato e opt-in.
2. **Config Separation**: OpenCode/kilocode e ARIA hanno configurazioni indipendenti. OpenCode usa `config.go` con Viper. ARIA usa `internal/aria/config` con env vars `ARIA_*`.
3. **Opt-in Complexity**: Features avanzate opt-in, behavior di default semplice
4. **Offline-First**: Funzionalità core senza dipendenze internet
5. **Privacy-First**: Dati locali, nessuna telemetria senza consenso
6. **Extensibility**: Plugin system per estensioni community

### 9.3 Testing Strategy

```go
// Test structure
internal/aria/
├── core/
│   ├── orchestrator.go
│   └── orchestrator_test.go      // Unit tests
├── agency/
│   ├── agency.go
│   └── agency_test.go
├── integration/                   // Integration tests
│   ├── routing_test.go
│   ├── memory_test.go
│   └── scheduler_test.go
└── e2e/                          // End-to-end tests
    ├── workflow_test.go
    └── proactive_test.go
```

---

## Parte X: Appendici

### A.1 Glossario

| Termine | Definizione |
|---------|-------------|
| ARIA | Autonomous Reasoning & Intelligent Assistant |
| Agency | Organizzazione di agents per un dominio specifico |
| Agent | Entità che esegue task usando skills e tools |
| Skill | Capacità modulare riutilizzabile |
| Tool | Operazione atomica (bash, file, API) |
| MCP | Model Control Protocol per tools esterni |
| Orchestrator | Componente centrale di routing e coordinamento |
| Episode | Singola interazione memorizzata |
| Procedure | Workflow appreso e riutilizzabile |
| Guardrail | Controllo su azioni proattive |

### A.2 References

- ARIA CLI: https://github.com/fulvian/aria
- MCP Protocol: https://modelcontextprotocol.io
- Bubble Tea: https://github.com/charmbracelet/bubbletea
- sqlc: https://sqlc.dev
- CoALA Paper: "Cognitive Architectures for Language Agents"

### A.3 Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.9.0-DRAFT | 2026-03-29 | **FASE 2 COMPLETE (100%)** - E2E test added (`TestE2E_MemoryLearningFlow`). **Isola di ARIA Documented**: Added Section 9.2 documenting the architectural concept of ARIA as an autonomous island within the OpenCode/KiloCode ecosystem. Key aspects: (1) Complete code namespace isolation in `internal/aria/*`, (2) Independent config via `ARIA_*` env vars, (3) Shared infrastructure (LLM providers, tools, TUI, DB engine), (4) Database schema isolation per dominio. **Roadmap Updated**: FASE 0-4 COMPLETE, FASE 5 NOT STARTED. **Next**: Proceed to FASE 5 agencies (Knowledge, Creative, Productivity, Personal, Analytics). |
| 1.8.0-DRAFT | 2026-03-29 | **FASE 2 ~85% COMPLETE**: Implemented all WS1-WS8: WS1 (Integration backbone - MemoryService + AnalysisService wired to runtime), WS2 (Working memory durability - TTL, GC, context persistence), WS3 (Episodic retrieval 2.0 - full filters + ranking), WS4 (Semantic memory governance - usage tracking, dedup), WS5 (Procedural learning engine - scoring, discovery), WS6 (Self-analysis hardening - time-range, persistence), WS7 (Privacy/Retention - configurable policies), WS8 (Quality gates - tests, benchmarks). **Config separation**: Created independent `internal/aria/config` package for ARIA configuration via env vars (ARIA_* prefix). Removed ARIA defaults from main config.go. This allows opencode/kilocode and ARIA to run side-by-side without interference. **Next**: FASE 2 E2E testing, then FASE 5 agencies. |
| 1.7.0-DRAFT | 2026-03-28 | **FASE 4 COMPLETE**: Implemented GuardrailService (internal/aria/guardrail/service.go) with CanExecute, GetActionBudget, ConsumeAction, GetUserPreferences, UpdatePreferences, LogAction, GetAuditLog. Budget tracking in-memory with window reset. Audit log in-memory with max limit. QuietHours and ActiveHours validation. AutoApproveRules for low-impact actions. Implemented ExtendedPermissionService (internal/aria/permission/service.go) with Request, Grant, Deny, Check, GetRules, AddRule, RemoveRule, GetEffectiveLevel. App integration wires both services. All tests pass. **Next**: FASE 2 completion and FASE 5 agencies. |
| 1.6.0-DRAFT | 2026-03-28 | **FASE 3 COMPLETE**: Implemented persistent scheduling system: SchedulerService (internal/aria/scheduler/service.go) with Schedule/GetTask/ListTasks/GetProgress/Subscribe, mapper.go for DB conversions, dispatcher.go for eligibility+priority+dependencies, worker.go for pool execution, recurring.go for cron/interval parsing and instance generation, recovery.go for startup reconciliation, executor.go stub. Config extended with DispatchIntervalMs, RecoveryPolicy, RecurringLookaheadMinutes. App integration wires scheduler with dispatcher/worker/recurring planner. TUI TasksPage for task management. All tests pass. **Next**: FASE 2 completion and FASE 4 guardrails. |
| 1.5.0-DRAFT | 2026-03-28 | **FASE 2 IN PROGRESS**: Implemented MemoryService (internal/aria/memory/service.go) with working memory (sync.Map), episodic memory (RecordEpisode, SearchEpisodes, GetSimilarEpisodes with keyword fallback), semantic memory (StoreFact, GetFacts, QueryKnowledge), procedural memory (SaveProcedure, GetProcedure, FindApplicableProcedures), learning hooks (LearnFromSuccess, LearnFromFailure), metrics (GetPerformanceMetrics, GenerateInsights). Implemented SelfAnalysisService (internal/aria/analysis/service.go) with AnalyzePerformance, AnalyzePatterns, AnalyzeFailures, GenerateImprovements (max 3 rule-based), ApplyInsights. All services use existing DB/sqlc queries. Tests pass. **Next**: FASE 2 hardening and integration testing. |
| 1.4.0-DRAFT | 2026-03-28 | **FASE 1 COMPLETE** (~95%): Implemented: LegacyAgentWrapper with full EnhancedAgent interface, real skill execution (CodeReview with grep/glob/view, TDD with write/edit, Debugging with grep/view), Agency Lifecycle (Start/Stop/Pause/Resume), AgencyRegistry for multi-agency management, Orchestrator stub methods completed. Build passes. **Next**: FASE 2 - Memory & Learning system. |
| 1.3.0-DRAFT | 2026-03-28 | **IN_PROGRESS**: FASE 1 ~40% complete. **CLI Integration COMPLETE**: Orchestrator now executes tasks through Agency→Agent→Legacy Agent flow. CoderBridge invokes actual agent.Run() with session management. ProcessQuery returns real content. **Next**: Real skill execution with tool integration. All commits pushed to github.com/fulvian/aria |
| 1.2.0-DRAFT | 2026-03-28 | **IN_PROGRESS**: FASE 1 started. FASE 0 complete. Implemented: namespace internal/aria/*, Development Agency, Orchestrator MVP, Skill System (CodeReview, TDD, Debugging), Routing baseline, Database schema, Config integration, App integration. **Next**: CLI integration to wire ARIA mode to prompt loop. All commits pushed to github.com/fulvian/aria |
| 1.1.0-DRAFT | 2026-03-28 | FASE 0 foundation setup. All commits pushed to github.com/fulvian/aria |
| 1.0.0-DRAFT | 2025-03-28 | Initial foundation document |

---

## Conclusioni

Questo documento stabilisce le fondamenta architetturali per la trasformazione di OpenCode CLI in ARIA. L'approccio incrementale per fasi permette di:

1. **Validare** le decisioni architetturali progressivamente
2. **Preservare** la funzionalità esistente durante l'evoluzione
3. **Iterare** rapidamente basandosi sul feedback
4. **Estendere** le capabilities senza riscritture massive

La prossima fase (FASE 0) si concentrerà sulla preparazione della codebase e sulla definizione dettagliata delle interfacce core. Ogni fase successiva verrà pianificata nel dettaglio man mano che si avanza nel progetto.
