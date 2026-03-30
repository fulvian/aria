// Package memory provides the memory system for ARIA, including
// working memory, episodic memory, semantic memory, and procedural memory.
//
// This package implements the memory interfaces defined in Blueprint Section 3.2.
package memory

import (
	"context"
	"time"
)

// Context represents the current working context.
type Context struct {
	SessionID string
	TaskID    string
	AgencyID  string
	AgentID   string
	Messages  []Message
	Files     []string
	Metadata  map[string]any
}

// Message represents a message in the context.
type Message struct {
	Role    string
	Content string
	Time    time.Time
}

// EpisodeQuery represents a query for episodic memory search.
type EpisodeQuery struct {
	SessionID string
	AgencyID  string
	AgentID   string
	TaskType  string
	TimeRange *TimeRange
	Limit     int
}

// TimeRange represents a time range for queries.
type TimeRange struct {
	Start time.Time
	End   time.Time
}

// Episode represents a single interaction stored in episodic memory.
type Episode struct {
	ID        string
	Timestamp time.Time
	SessionID string
	AgencyID  string
	AgentID   string
	Task      map[string]any
	Actions   []Action
	Outcome   string
	Feedback  *Feedback
	Embedding []float32 // For similarity search
}

// Action represents an action taken during an episode.
type Action struct {
	Type      string
	Tool      string
	Input     map[string]any
	Output    map[string]any
	Timestamp time.Time
}

// Feedback represents feedback on an episode.
type Feedback struct {
	Type    string
	Content string
}

// Situation represents a situation for finding similar episodes.
type Situation struct {
	Description string
	Context     map[string]any
}

// Fact represents a fact stored in semantic memory.
type Fact struct {
	ID         string
	Domain     string
	Category   string
	Content    string
	Source     string
	Confidence float64
	CreatedAt  time.Time
	LastUsed   time.Time
	UseCount   int64
}

// KnowledgeItem represents an item from the knowledge base.
type KnowledgeItem struct {
	ID       string
	Content  string
	Domain   string
	Tags     []string
	Source   string
	Metadata map[string]any
}

// Procedure represents a learned workflow in procedural memory.
type Procedure struct {
	ID          string
	Name        string
	Description string
	Trigger     TriggerCondition
	Steps       []ProcedureStep
	SuccessRate float64
	UseCount    int64
}

// TriggerCondition represents when a procedure should be triggered.
type TriggerCondition struct {
	Type    string // "query_pattern", "task_type", "context"
	Pattern string
	Params  map[string]any
}

// ProcedureStep represents a step in a procedure.
type ProcedureStep struct {
	Order       int
	Name        string
	Description string
	Action      string
	Params      map[string]any
}

// MemoryService provides the main memory interface for ARIA.
//
// Reference: Blueprint Section 3.2
type MemoryService interface {
	// Close stops the memory service and cleans up resources.
	// It is safe to call multiple times.
	Close() error

	// Working memory - session context
	GetContext(ctx context.Context, sessionID string) (Context, error)
	SetContext(ctx context.Context, sessionID string, context Context) error

	// Episodic memory - conversation history
	RecordEpisode(ctx context.Context, episode Episode) error
	SearchEpisodes(ctx context.Context, query EpisodeQuery) ([]Episode, error)
	GetSimilarEpisodes(ctx context.Context, situation Situation) ([]Episode, error)

	// Semantic memory - knowledge base
	StoreFact(ctx context.Context, fact Fact) error
	GetFacts(ctx context.Context, domain string) ([]Fact, error)
	QueryKnowledge(ctx context.Context, query string) ([]KnowledgeItem, error)

	// Procedural memory - learned workflows
	SaveProcedure(ctx context.Context, procedure Procedure) error
	GetProcedure(ctx context.Context, name string) (Procedure, error)
	FindApplicableProcedures(ctx context.Context, task map[string]any) ([]Procedure, error)

	// Learning
	LearnFromSuccess(ctx context.Context, action Action, outcome string) error
	LearnFromFailure(ctx context.Context, action Action, err error) error

	// Self-analysis
	GetPerformanceMetrics(ctx context.Context, timeRange TimeRange) (Metrics, error)
	GenerateInsights(ctx context.Context) ([]string, error)
}

// Metrics represents performance metrics.
type Metrics struct {
	TotalTasks        int64
	SuccessRate       float64
	AverageDurationMs int64
	BySkill           map[string]SkillMetrics
	ByAgency          map[string]AgencyMetrics
}

// SkillMetrics represents metrics for a specific skill.
type SkillMetrics struct {
	TotalCalls      int64
	SuccessRate     float64
	AverageDuration int64
}

// AgencyMetrics represents metrics for a specific agency.
type AgencyMetrics struct {
	TotalTasks      int64
	SuccessRate     float64
	AverageDuration int64
}
