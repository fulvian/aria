// Package core provides the ARIA Orchestrator - the central brain that
// coordinates all agencies, handles query routing, and manages task execution.
//
// This package implements the Orchestrator interface defined in Blueprint Section 2.2.1.
package core

import (
	"context"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/routing"
)

// Query represents a user input to be processed by ARIA.
type Query struct {
	Text      string
	SessionID string
	UserID    string
	Metadata  map[string]any
}

// Response represents the orchestrator's answer to a Query.
type Response struct {
	Text       string
	Agency     contracts.AgencyName
	Agent      string
	Skills     []string
	Confidence float64
}

// TaskID is a unique identifier for a task.
type TaskID string

// Task represents a task to be scheduled (defined here to avoid import cycles).
type Task struct {
	ID          TaskID
	Name        string
	Description string
	Type        string
	Priority    int
	ScheduledAt *int64 // Unix timestamp
	Status      string
}

// TaskEvent represents events from task execution.
type TaskEvent struct {
	TaskID    TaskID
	Type      string
	Payload   map[string]any
	Timestamp int64
}

// SelfAnalysis contains results from ARIA's self-analysis.
type SelfAnalysis struct {
	Timestamp int64
	Metrics   map[string]any
	Insights  []string
}

// Experience represents a learning experience for ARIA.
type Experience struct {
	TaskID    TaskID
	Outcome   string
	Feedback  string
	Timestamp int64
}

// Suggestion represents a proactive suggestion from ARIA.
type Suggestion struct {
	ID          string
	Description string
	Action      string
	Impact      string
	Reason      string
}

// Orchestrator is the central coordinator for ARIA.
// It receives all user queries, classifies them, routes to appropriate
// agencies/agents, and monitors long-running tasks.
//
// Reference: Blueprint Section 2.2.1
type Orchestrator interface {
	// ProcessQuery handles a user query and returns a response.
	ProcessQuery(ctx context.Context, query Query) (Response, error)

	// RouteToAgency determines which agency should handle the query.
	RouteToAgency(ctx context.Context, query Query) (agency.Agency, error)

	// RouteToAgent determines which agent should handle the query.
	RouteToAgent(ctx context.Context, query Query) (routing.AgentID, error)

	// ScheduleTask schedules a task for future execution.
	ScheduleTask(ctx context.Context, task Task) (TaskID, error)

	// MonitorTasks returns a channel of task events.
	MonitorTasks(ctx context.Context) <-chan TaskEvent

	// AnalyzeSelf performs self-analysis and returns insights.
	AnalyzeSelf(ctx context.Context) (SelfAnalysis, error)

	// Learn processes an experience for learning.
	Learn(ctx context.Context, experience Experience) error

	// GetProactiveSuggestions returns suggestions for proactive behavior.
	GetProactiveSuggestions(ctx context.Context) ([]Suggestion, error)
}

// Classifier returns the routing classifier for debugging/inspection.
func Classifier(orch Orchestrator) routing.QueryClassifier {
	// This is a query method - implementations should expose their classifier
	return nil // TODO: Implement when we have actual orchestrator
}
