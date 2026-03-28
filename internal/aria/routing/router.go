package routing

import (
	"context"
)

// RoutingDecision contains the routing decision for a query.
type RoutingDecision struct {
	// Target is where the query should be routed.
	Target RoutingTarget

	// Agency is the target agency (if TargetAgency).
	Agency *string

	// Agent is the target agent (if TargetAgent).
	Agent *string

	// Skills are the skills to use for execution.
	Skills []string

	// Confidence is the confidence in this routing (0.0 - 1.0).
	Confidence float64

	// Explanation describes why this routing was chosen.
	Explanation string

	// Fallback indicates if this is a fallback routing.
	Fallback bool
}

// Router makes routing decisions for queries.
//
// Reference: Blueprint Section 2.3.3
type Router interface {
	// Route determines where to send a query.
	Route(ctx context.Context, query Query, class Classification) (RoutingDecision, error)

	// GetRules returns the current routing rules (for debugging).
	GetRules() []RoutingRule

	// AddRule adds a routing rule.
	AddRule(rule RoutingRule) error

	// RemoveRule removes a routing rule.
	RemoveRule(ruleID string) error
}

// RoutingRule defines a single routing rule.
type RoutingRule struct {
	ID          string
	Priority    int // Higher priority rules are evaluated first
	Name        string
	Description string

	// Conditions (all must match for rule to apply)
	Intents       []Intent
	Domains       []DomainName
	Complexities  []ComplexityLevel
	QueryPatterns []string // Simple string patterns to match in query

	// Action
	Target     RoutingTarget
	Agency     *string
	Agent      *string
	Skills     []string
	Confidence float64
}

// DefaultRouter is a simple rules-based router for initial implementation.
type DefaultRouter struct {
	rules []RoutingRule
}

// NewDefaultRouter creates a router with baseline deterministic rules.
func NewDefaultRouter() *DefaultRouter {
	return &DefaultRouter{
		rules: baselineRules(),
	}
}

// baselineRules returns the initial routing rules.
func baselineRules() []RoutingRule {
	return []RoutingRule{
		{
			ID:            "dev-code-review",
			Priority:      100,
			Name:          "Code Review",
			Description:   "Route code review requests to development agency",
			Intents:       []Intent{IntentTask, IntentAnalysis},
			Domains:       []DomainName{DomainDevelopment},
			QueryPatterns: []string{"review", "code review", "check code"},
			Target:        TargetAgency,
			Agency:        ptrString("development"),
			Skills:        []string{"code-review"},
			Confidence:    0.9,
		},
		{
			ID:            "dev-debug",
			Priority:      100,
			Name:          "Debug Request",
			Description:   "Route debugging requests to development agency",
			Intents:       []Intent{IntentTask},
			Domains:       []DomainName{DomainDevelopment},
			QueryPatterns: []string{"debug", "fix", "error", "bug", "crash"},
			Target:        TargetAgency,
			Agency:        ptrString("development"),
			Skills:        []string{"systematic-debugging"},
			Confidence:    0.85,
		},
		{
			ID:            "dev-tdd",
			Priority:      90,
			Name:          "TDD Request",
			Description:   "Route TDD requests to development agency",
			Intents:       []Intent{IntentCreation, IntentTask},
			Domains:       []DomainName{DomainDevelopment},
			QueryPatterns: []string{"test", "tdd", "unit test", "write test"},
			Target:        TargetAgency,
			Agency:        ptrString("development"),
			Skills:        []string{"test-driven-dev"},
			Confidence:    0.85,
		},
		{
			ID:           "simple-question",
			Priority:     50,
			Name:         "Simple Question",
			Description:  "Route simple questions to direct answer",
			Intents:      []Intent{IntentQuestion},
			Complexities: []ComplexityLevel{ComplexitySimple},
			Target:       TargetSkill,
			Skills:       []string{"fact-check"},
			Confidence:   0.7,
		},
	}
}

func ptrString(s string) *string {
	return &s
}
