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
	QueryPatterns []string // Simple String patterns to match in query

	// Action
	Target     RoutingTarget
	Agency     *string
	Agent      *string
	Skills     []string
	Confidence float64
}
