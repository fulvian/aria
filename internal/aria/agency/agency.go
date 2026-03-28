// Package agency provides the Agency system - specialized organizations
// of agents for specific domains (development, knowledge, creative, etc.).
//
// This package implements the Agency interface defined in Blueprint Section 2.2.2.
package agency

import (
	"context"
)

// AgencyName identifies a specific agency.
type AgencyName string

// Agency state constants
const (
	AgencyKnowledge    AgencyName = "knowledge"    // Research, learning, Q&A
	AgencyDevelopment  AgencyName = "development"  // Coding, devops, testing
	AgencyCreative     AgencyName = "creative"     // Writing, design, art
	AgencyProductivity AgencyName = "productivity" // Planning, scheduling, organization
	AgencyPersonal     AgencyName = "personal"     // Health, finance, lifestyle
	AgencyAnalytics    AgencyName = "analytics"    // Data analysis, visualization
)

// AgencyEvent represents events emitted by an agency.
type AgencyEvent struct {
	AgencyID AgencyName
	Type     string
	Payload  map[string]any
	AgentID  string
}

// AgencyState represents the persistent state of an agency.
type AgencyState struct {
	AgencyID   AgencyName
	Status     string
	LastTaskID string
	Metrics    map[string]any
	UpdatedAt  int64
}

// Task represents a unit of work to be executed by an agency.
type Task struct {
	ID          string
	Name        string
	Description string
	Parameters  map[string]any
	Skills      []string
	Priority    int
}

// Result represents the outcome of a task execution.
type Result struct {
	TaskID     string
	Success    bool
	Output     map[string]any
	Error      string
	DurationMs int64
}

// DomainMemory represents an agency's domain-specific memory.
type DomainMemory interface {
	// GetContext returns relevant context for a query.
	GetContext(ctx context.Context, query string) (map[string]any, error)

	// AddExperience records a new experience.
	AddExperience(ctx context.Context, exp map[string]any) error

	// GetRelevant returns relevant memories for a task.
	GetRelevant(ctx context.Context, task Task) ([]map[string]any, error)
}

// Subscriber defines the subscription interface for receiving events.
// This matches the pattern used in internal/pubsub/broker.go.
type Subscriber[T any] interface {
	Subscribe(ctx context.Context) <-chan T
}

// Agency coordinates multiple agents for a specific domain.
// It manages agent lifecycle, task routing within the agency,
// and maintains domain-specific state and memory.
//
// Reference: Blueprint Section 2.2.2
type Agency interface {
	Subscriber[AgencyEvent]

	// Identity
	Name() AgencyName
	Domain() string
	Description() string

	// Agent management
	Agents() []string                  // Returns agent names
	GetAgent(name string) (any, error) // Returns agent implementation

	// Task execution
	Execute(ctx context.Context, task Task) (Result, error)

	// State management
	GetState() AgencyState
	SaveState(state AgencyState) error

	// Domain memory
	Memory() DomainMemory
}
