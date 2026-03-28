// Package agent provides the enhanced Agent interface that extends
// the legacy flat agent system with skills, agency membership,
// and learning capabilities.
//
// This package implements the Agent interface defined in Blueprint Section 2.2.3.
package agent

import (
	"context"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/skill"
)

// AgentEvent represents events emitted by an agent.
type AgentEvent struct {
	AgentID string
	Type    string
	Payload map[string]any
	TaskID  string
}

// AgentName identifies a specific agent.
type AgentName string

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

// LegacyCoderBridge provides compatibility with the existing
// internal/llm/agent.Agent service.
type LegacyCoderBridge interface {
	// Run executes the legacy coder agent.
	Run(ctx context.Context, task map[string]any) (map[string]any, error)

	// Stream streams the legacy coder agent response.
	Stream(ctx context.Context, task map[string]any) (<-chan Event, error)

	// Cancel cancels the current execution.
	Cancel(taskID string) error
}

// Subscriber defines the subscription interface for receiving events.
// This matches the pattern used in internal/pubsub/broker.go.
type Subscriber[T any] interface {
	Subscribe(ctx context.Context) <-chan T
}

// EnhancedAgent is an agent with skills, agency membership, and learning.
// It extends the legacy flat agent system with the new ARIA architecture.
//
// Reference: Blueprint Section 2.2.3
type EnhancedAgent interface {
	Subscriber[AgentEvent]

	// Identity
	Name() AgentName
	Agency() agency.AgencyName
	Capabilities() []Capability

	// Execution - legacy compatible
	Run(ctx context.Context, task map[string]any) (map[string]any, error)
	Stream(ctx context.Context, task map[string]any) (<-chan Event, error)

	// Skills
	Skills() []skill.Skill
	HasSkill(name skill.SkillName) bool

	// Learning
	LearnFromFeedback(feedback Feedback) error

	// State
	GetState() AgentState
}

// LegacyAgentWrapper wraps an existing internal/llm/agent.Agent
// to conform to the EnhancedAgent interface.
type LegacyAgentWrapper struct {
	// agent is the wrapped legacy agent
	agent any // TODO: internal/llm/agent.Agent
	// agencyName is the agency this agent belongs to
	agencyName agency.AgencyName
	// skills are the skills available to this agent
	skills []skill.Skill
}

// NewLegacyAgentWrapper creates a wrapper around a legacy agent.
func NewLegacyAgentWrapper(agent any, agencyName agency.AgencyName, skills []skill.Skill) *LegacyAgentWrapper {
	return &LegacyAgentWrapper{
		agent:      agent,
		agencyName: agencyName,
		skills:     skills,
	}
}
