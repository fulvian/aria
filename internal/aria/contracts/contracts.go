// Package contracts defines shared types for the ARIA agency system.
// This package provides neutral ground for types shared between
// agency and agent packages, preventing import cycles.
//
// Reference: Blueprint Section 2.2
package contracts

import (
	"time"
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

// AgentName identifies a specific agent.
type AgentName string

// AgencyEvent represents events emitted by an agency.
type AgencyEvent struct {
	AgencyID  AgencyName
	Type      string
	Payload   map[string]any
	AgentID   string
	Timestamp time.Time
}

// AgentEvent represents events emitted by an agent.
type AgentEvent struct {
	AgentID string
	Type    string
	Payload map[string]any
	TaskID  string
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

// Feedback represents user or system feedback on agent action.
type Feedback struct {
	TaskID   string
	Type     string // positive, negative, suggestion
	Content  string
	Metadata map[string]any
}

// Event represents streaming events from agent execution.
type Event struct {
	Type    string
	Content string
	Delta   string // For streaming
}

// AgentState represents the current state of an agent.
type AgentState struct {
	AgentID   string
	Status    string // idle, busy, error
	TasksDone int64
	Metrics   map[string]any
}

// Capability represents what an agent can do.
type Capability struct {
	Name        string
	Description string
	Tools       []string // Required tool names
}
