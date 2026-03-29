// Package agency provides the Agency system - specialized organizations
// of agents for specific domains (development, knowledge, creative, etc.).
//
// This package implements the Agency interface defined in Blueprint Section 2.2.2.
package agency

import (
	"context"

	"github.com/fulvian/aria/internal/aria/contracts"
)

// AgencyStatus represents the current status of an agency.
type AgencyStatus string

// Agency status constants.
const (
	AgencyStatusStopped AgencyStatus = "stopped"
	AgencyStatusRunning AgencyStatus = "running"
	AgencyStatusPaused  AgencyStatus = "paused"
)

// AgencyLifecycle defines lifecycle management for an agency.
type AgencyLifecycle interface {
	// Start starts the agency.
	Start(ctx context.Context) error

	// Stop stops the agency.
	Stop(ctx context.Context) error

	// Pause pauses the agency.
	Pause(ctx context.Context) error

	// Resume resumes the agency.
	Resume(ctx context.Context) error

	// Status returns the current agency status.
	Status() AgencyStatus
}

// AgencyState represents the persistent state of an agency.
type AgencyState struct {
	AgencyID   contracts.AgencyName
	Status     string
	LastTaskID string
	Metrics    map[string]any
	UpdatedAt  int64
}

// DomainMemory represents an agency's domain-specific memory.
type DomainMemory interface {
	// GetContext returns relevant context for a query.
	GetContext(ctx context.Context, query string) (map[string]any, error)

	// AddExperience records a new experience.
	AddExperience(ctx context.Context, exp map[string]any) error

	// GetRelevant returns relevant memories for a task.
	GetRelevant(ctx context.Context, task contracts.Task) ([]map[string]any, error)
}

// Agency coordinates multiple agents for a specific domain.
// It manages agent lifecycle, task routing within the agency,
// and maintains domain-specific state and memory.
//
// Reference: Blueprint Section 2.2.2
type Agency interface {
	// Lifecycle management
	AgencyLifecycle

	// Subscribe returns a channel for receiving agency events.
	Subscribe(ctx context.Context) <-chan contracts.AgencyEvent

	// Identity
	Name() contracts.AgencyName
	Domain() string
	Description() string

	// Agent management
	// Note: Agents() returns agent names, GetAgent returns the agent implementation
	// During Phase 4, this will return the proper agent.Agent type
	Agents() []contracts.AgentName
	GetAgent(name contracts.AgentName) (interface{}, error)

	// Task execution
	Execute(ctx context.Context, task contracts.Task) (contracts.Result, error)

	// State management
	GetState() AgencyState
	SaveState(state AgencyState) error

	// Domain memory
	Memory() DomainMemory
}
