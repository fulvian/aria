# ARIA: Autonomous Reasoning & Intelligent Assistant
## Foundation Blueprint Document

> **Version**: 1.0.0-DRAFT  
> **Date**: 2025-03-28  
> **Status**: FOUNDATIONAL  
> **Base Project**: ARIA CLI  

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
│  FASE 0: FOUNDATION         ████████████████░░░░░░░░░░░  (40%)  │
│  [Mese 1-2]                 Setup, refactoring base             │
│                                                                  │
│  FASE 1: CORE SYSTEM        ░░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
│  [Mese 2-4]                 Agency/Agent architecture           │
│                                                                  │
│  FASE 2: MEMORY & LEARNING  ░░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
│  [Mese 4-6]                 Memory system, learning loop        │
│                                                                  │
│  FASE 3: SCHEDULING         ░░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
│  [Mese 6-7]                 Task scheduler, persistence         │
│                                                                  │
│  FASE 4: PROACTIVITY        ░░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
│  [Mese 7-8]                 Proactive behavior, guardrails      │
│                                                                  │
│  FASE 5: AGENCIES           ░░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
│  [Mese 8-12]                Implement specialized agencies      │
│                                                                  │
│  FASE 6: POLISH & EXPAND    ░░░░░░░░░░░░░░░░░░░░░░░░░░░  (0%)   │
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
- [ ] Nuova struttura directory
- [ ] Schema database esteso
- [ ] Interfacce Go definite
- [ ] Test suite base
- [ ] Documentazione architetturale

---

### 8.3 FASE 1: Core System

**Durata**: 6-8 settimane  
**Obiettivo**: Implementare il sistema Agency/Agent

#### 8.3.1 Task

1. **Orchestrator implementation**
   - Query processing pipeline
   - Basic routing logic
   - Agency/Agent coordination

2. **Agency system**
   - Agency interface implementation
   - Agency registry
   - Agency lifecycle management

3. **Enhanced Agent system**
   - Extend current agent
   - Add skills integration
   - Multi-LLM support per agent

4. **Skill system**
   - Skill interface
   - Skill registry
   - Built-in skills migration (da tools)

5. **Routing system**
   - Intent classifier
   - Complexity analyzer
   - Routing decision engine

#### 8.3.2 Deliverables
- [ ] Orchestrator funzionante
- [ ] 1+ Agency implementata (Development)
- [ ] 3+ Skills migrati da tools
- [ ] Routing base funzionante
- [ ] CLI updated per nuova architettura

---

### 8.4 FASE 2: Memory & Learning

**Durata**: 6-8 settimane  
**Obiettivo**: Implementare sistema di memoria

#### 8.4.1 Task

1. **Memory service**
   - Working memory (session context)
   - Episodic memory (conversation history)
   - Semantic memory (knowledge base)
   - Procedural memory (learned workflows)

2. **Storage backend**
   - SQLite extensions per full-text search
   - Optional: SQLite-vec per embeddings
   - Memory indexing e retrieval

3. **Learning loop**
   - Experience recording
   - Pattern extraction
   - Procedure generation
   - Feedback integration

4. **Self-analysis**
   - Performance metrics collection
   - Periodic analysis jobs
   - Insight generation

#### 8.4.2 Deliverables
- [ ] Memory service completo
- [ ] Storage backend funzionante
- [ ] Learning loop base
- [ ] Self-analysis reports

---

### 8.5 FASE 3: Scheduling

**Durata**: 4-6 settimane  
**Obiettivo**: Task scheduling persistente

#### 8.5.1 Task

1. **Scheduler service**
   - Task queue management
   - Priority handling
   - Dependency resolution

2. **Persistence layer**
   - Task storage
   - State management
   - Recovery dopo restart

3. **Recurring tasks**
   - Cron-like scheduling
   - Interval-based tasks
   - One-time scheduled tasks

4. **Monitoring**
   - Progress tracking
   - Event notifications
   - Task history

#### 8.5.2 Deliverables
- [ ] Scheduler service completo
- [ ] Task persistence
- [ ] Recurring tasks
- [ ] TUI per task management

---

### 8.6 FASE 4: Proactivity

**Durata**: 4-6 settimane  
**Obiettivo**: Comportamento proattivo controllato

#### 8.6.1 Task

1. **Proactive engine**
   - Suggestion generation
   - Action planning
   - User notification

2. **Guardrails**
   - Permission levels
   - Rate limiting
   - Audit logging

3. **User preferences**
   - Quiet hours
   - Action budgets
   - Auto-approval rules

4. **Notification system**
   - TUI notifications
   - Optional: external notifications

#### 8.6.2 Deliverables
- [ ] Proactive engine
- [ ] Guardrails system
- [ ] User preferences UI
- [ ] Notification system

---

### 8.7 FASE 5: Agencies

**Durata**: 8-12 settimane  
**Obiettivo**: Implementare agencies specializzate

#### 8.7.1 Task

1. **Knowledge Agency**
   - Web research integration
   - Document analysis
   - Q&A capabilities

2. **Creative Agency**
   - Writing tools
   - Translation
   - Content generation

3. **Productivity Agency**
   - Planning tools
   - Calendar integration
   - Task management

4. **Personal Agency**
   - Personal assistant features
   - Lifestyle tracking
   - Recommendations

5. **Analytics Agency**
   - Data analysis
   - Visualization
   - Reporting

#### 8.7.2 Deliverables
- [ ] 5+ agencies funzionanti
- [ ] 20+ skills implementati
- [ ] MCP integrations per external tools
- [ ] Comprehensive testing

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
| Configuration | Viper + JSON | Già in uso |
| CLI framework | Cobra | Già in uso |
| TUI framework | Bubble Tea | Già in uso |
| LLM providers | Multi-provider | Già supportati 10+ providers |
| MCP | Standard MCP | Già supportato |

### 9.2 Principi di Design

1. **Backward Compatibility**: Mantenere compatibilità con configurazioni OpenCode esistenti
2. **Opt-in Complexity**: Features avanzate opt-in, behavior di default semplice
3. **Offline-First**: Funzionalità core senza dipendenze internet
4. **Privacy-First**: Dati locali, nessuna telemetria senza consenso
5. **Extensibility**: Plugin system per estensioni community

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
| 1.0.0-DRAFT | 2025-03-28 | Initial foundation document |

---

## Conclusioni

Questo documento stabilisce le fondamenta architetturali per la trasformazione di OpenCode CLI in ARIA. L'approccio incrementale per fasi permette di:

1. **Validare** le decisioni architetturali progressivamente
2. **Preservare** la funzionalità esistente durante l'evoluzione
3. **Iterare** rapidamente basandosi sul feedback
4. **Estendere** le capabilities senza riscritture massive

La prossima fase (FASE 0) si concentrerà sulla preparazione della codebase e sulla definizione dettagliata delle interfacce core. Ogni fase successiva verrà pianificata nel dettaglio man mano che si avanza nel progetto.
