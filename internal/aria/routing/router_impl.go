package routing

import (
	"context"
	"sort"
	"strings"
	"sync"
)

// DefaultRouter is a simple rules-based router for initial implementation.
type DefaultRouter struct {
	mu    sync.RWMutex
	rules []RoutingRule
}

// NewDefaultRouter creates a router with baseline deterministic rules.
func NewDefaultRouter() *DefaultRouter {
	return &DefaultRouter{
		rules: baselineRules(),
	}
}

// Route determines where to send a query based on rules.
func (r *DefaultRouter) Route(ctx context.Context, query Query, class Classification) (RoutingDecision, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	text := strings.ToLower(query.Text)

	// Sort rules by priority (highest first)
	sortedRules := make([]RoutingRule, len(r.rules))
	copy(sortedRules, r.rules)
	sort.Slice(sortedRules, func(i, j int) bool {
		return sortedRules[i].Priority > sortedRules[j].Priority
	})

	// Find first matching rule
	for _, rule := range sortedRules {
		if r.matchesRule(rule, class, text) {
			return RoutingDecision{
				Target:      rule.Target,
				Agency:      rule.Agency,
				Agent:       rule.Agent,
				Skills:      rule.Skills,
				Confidence:  rule.Confidence,
				Explanation: rule.Description,
				Fallback:    false,
			}, nil
		}
	}

	// Fallback to default routing
	return r.defaultDecision(class), nil
}

// matchesRule checks if a query matches a routing rule.
func (r *DefaultRouter) matchesRule(rule RoutingRule, class Classification, text string) bool {
	// Check intent match
	if len(rule.Intents) > 0 {
		found := false
		for _, intent := range rule.Intents {
			if intent == class.Intent {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	// Check domain match
	if len(rule.Domains) > 0 {
		found := false
		for _, domain := range rule.Domains {
			if domain == class.Domain {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	// Check complexity match
	if len(rule.Complexities) > 0 {
		found := false
		for _, complexity := range rule.Complexities {
			if complexity == class.Complexity {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	// Check query pattern match
	if len(rule.QueryPatterns) > 0 {
		found := false
		for _, pattern := range rule.QueryPatterns {
			if strings.Contains(text, strings.ToLower(pattern)) {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	return true
}

// defaultDecision returns the default routing decision.
func (r *DefaultRouter) defaultDecision(class Classification) RoutingDecision {
	// For simple questions, route to skill
	if class.Intent == IntentQuestion && class.Complexity == ComplexitySimple {
		return RoutingDecision{
			Target:      TargetSkill,
			Skills:      []string{"fact-check"},
			Confidence:  0.5,
			Explanation: "default routing for simple question",
			Fallback:    true,
		}
	}

	// For development domain, route to development agency
	if class.Domain == DomainDevelopment {
		return RoutingDecision{
			Target:      TargetAgency,
			Agency:      ptrString("development"),
			Skills:      []string{"code-review"},
			Confidence:  0.6,
			Explanation: "default routing for development domain",
			Fallback:    true,
		}
	}

	// Default: route to development agency
	return RoutingDecision{
		Target:      TargetAgency,
		Agency:      ptrString("development"),
		Skills:      []string{},
		Confidence:  0.4,
		Explanation: "default fallback routing",
		Fallback:    true,
	}
}

// GetRules returns the current routing rules.
func (r *DefaultRouter) GetRules() []RoutingRule {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.rules
}

// AddRule adds a new routing rule.
func (r *DefaultRouter) AddRule(rule RoutingRule) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.rules = append(r.rules, rule)
	return nil
}

// RemoveRule removes a routing rule by ID.
func (r *DefaultRouter) RemoveRule(ruleID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	for i, rule := range r.rules {
		if rule.ID == ruleID {
			r.rules = append(r.rules[:i], r.rules[i+1:]...)
			return nil
		}
	}
	return nil
}

func ptrString(s string) *string {
	return &s
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
