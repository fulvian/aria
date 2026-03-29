// Package agent provides the Agent interface that extends
// the legacy flat agent system with skills, agency membership,
// and learning capabilities.
//
// This package implements the Agent interface defined in Blueprint Section 2.2.3.
package agent

import (
	"context"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill"
)

// Subscriber defines the subscription interface for receiving events.
// This matches the pattern used in internal/pubsub/broker.go.
type Subscriber[T any] interface {
	Subscribe(ctx context.Context) <-chan T
}

// Agent is an agent with skills, agency membership, and learning.
// It extends the legacy flat agent system with the new ARIA architecture.
//
// Reference: Blueprint Section 2.2.3
type Agent interface {
	Subscriber[contracts.AgentEvent]

	// Identity
	Name() contracts.AgentName
	Agency() contracts.AgencyName
	Capabilities() []contracts.Capability

	// Execution - legacy compatible
	Run(ctx context.Context, task map[string]any) (map[string]any, error)
	Stream(ctx context.Context, task map[string]any) (<-chan contracts.Event, error)

	// Skills
	Skills() []skill.Skill
	HasSkill(name skill.SkillName) bool

	// Learning
	LearnFromFeedback(feedback contracts.Feedback) error

	// State
	GetState() contracts.AgentState
}

// EnhancedAgent is a compatibility alias for Agent.
// Deprecated: Use Agent directly.
type EnhancedAgent = Agent

// LegacyCoderBridge provides compatibility with the existing
// internal/llm/agent.Agent service.
type LegacyCoderBridge interface {
	// Run executes the legacy coder agent.
	Run(ctx context.Context, task map[string]any) (map[string]any, error)

	// Stream streams the legacy coder agent response.
	Stream(ctx context.Context, task map[string]any) (<-chan contracts.Event, error)

	// Cancel cancels the current execution.
	Cancel(taskID string) error
}
