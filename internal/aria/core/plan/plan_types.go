// Package plan provides the Planner, Executor, and Reviewer components
// for the ARIA Orchestrator's Deep Path execution.
package plan

import (
	"time"

	"github.com/fulvian/aria/internal/aria/routing"
)

// Plan represents a structured execution plan.
type Plan struct {
	ID           string
	Query        string
	Objective    string
	Steps        []PlanStep
	Hypotheses   []Hypothesis
	Risks        []PlanRisk
	Fallbacks    []FallbackStrategy
	DoneCriteria string
	CreatedAt    time.Time
	Metadata     map[string]any
}

// PlanStep represents a single step in the plan.
type PlanStep struct {
	Index       int
	Action      string
	Target      string
	Inputs      map[string]any
	ExpectedOut map[string]any
	Constraints []string
	Timeout     time.Duration
}

// Hypothesis represents an operational hypothesis.
type Hypothesis struct {
	Description string
	Confidence  float64
	Conditions  []string
}

// PlanRisk identifies a risk in the plan.
type PlanRisk struct {
	Description string
	Probability float64
	Impact      string
	Mitigation  string
}

// FallbackStrategy is a fallback strategy for a step.
type FallbackStrategy struct {
	Condition string
	Action    string
	Target    string
}

// Handoff represents a handover between agents.
type Handoff struct {
	From        routing.AgentID
	To          routing.AgentID
	Reason      string
	ExpectedOut string
	Constraints []string
	Budget      HandoffBudget
}

// HandoffBudget is the budget for a handover.
type HandoffBudget struct {
	Timeout    time.Duration
	TokenLimit int
}
