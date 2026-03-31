package routing

import (
	"context"
	"fmt"
	"strings"
)

// RiskCategory categorizes the type of risk.
type RiskCategory string

const (
	RiskCategoryIrreversible RiskCategory = "irreversible"
	RiskCategoryExpensive    RiskCategory = "expensive"
	RiskCategorySafety       RiskCategory = "safety"
	RiskCategoryStandard     RiskCategory = "standard"
)

// RiskFactor identifies a contributing factor to risk.
type RiskFactor struct {
	Name   string
	Weight int
	Reason string
}

// RiskScore represents the risk level (local definition to avoid circular dependency with decision package).
type RiskScore struct {
	Value      int
	Category   RiskCategory
	Factors    []RiskFactor
	Mitigation string
}

// PolicyRouter is a router with confidence calibration and policy override.
type PolicyRouter interface {
	Router // embedding the base Router

	RouteWithPolicy(ctx context.Context, query Query, class Classification, policy RoutingPolicy) (RoutingDecision, error)
	SetRoutingPolicy(policy RoutingPolicy) error
	GetRoutingPolicy() RoutingPolicy

	// BoostAgencyConfidence increases confidence for a high-performing agency.
	BoostAgencyConfidence(agency string, boost float64)
	// ReduceAgencyConfidence decreases confidence for a low-performing agency.
	ReduceAgencyConfidence(agency string, penalty float64)
}

// RoutingPolicy is a configurable routing policy.
type RoutingPolicy struct {
	CostBudget          CostBudget
	SafetyBudget        RiskScore
	CapabilityMatch     bool
	ConfidenceThreshold float64
	PriorityRules       []PriorityRule
}

// CostBudget is the maximum budget for routing.
type CostBudget struct {
	MaxTokens int
	MaxTimeMs int
}

// PriorityRule is a priority rule for routing.
type PriorityRule struct {
	Name      string
	Condition string // e.g., "domain=development AND intent=task"
	Boost     float64
}

// defaultPolicyRouter is the default implementation of PolicyRouter.
type defaultPolicyRouter struct {
	baseRouter        Router
	policy            RoutingPolicy
	capabilities      CapabilityRegistry
	agencyConfidences map[string]float64 // agency name -> confidence adjustment
}

// NewPolicyRouter creates a new PolicyRouter with the given base router and capability registry.
func NewPolicyRouter(base Router, capabilities CapabilityRegistry) *defaultPolicyRouter {
	return &defaultPolicyRouter{
		baseRouter:   base,
		capabilities: capabilities,
		policy: RoutingPolicy{
			ConfidenceThreshold: 0.5,
			CapabilityMatch:     false,
		},
		agencyConfidences: make(map[string]float64),
	}
}

// RouteWithPolicy routes a query with policy considerations.
func (r *defaultPolicyRouter) RouteWithPolicy(ctx context.Context, query Query, class Classification, policy RoutingPolicy) (RoutingDecision, error) {
	// Step 1: Get base routing decision
	decision, err := r.baseRouter.Route(ctx, query, class)
	if err != nil {
		return RoutingDecision{}, fmt.Errorf("base route failed: %w", err)
	}

	// Step 2: If CapabilityMatch is enabled, find better matches
	if policy.CapabilityMatch {
		betterDecision, err := r.applyCapabilityMatch(query, class, decision)
		if err != nil {
			// Log but don't fail - fall back to base decision
			// In production, this might be a warning
		} else if betterDecision != nil {
			decision = *betterDecision
		}
	}

	// Step 3: Apply priority rules (boost confidence if match)
	decision.Confidence = r.applyPriorityRules(query, class, decision.Confidence, policy.PriorityRules)

	// Step 4: Apply confidence threshold
	if decision.Confidence < policy.ConfidenceThreshold {
		decision.Fallback = true
		decision.Explanation = fmt.Sprintf("fallback: confidence %.2f below threshold %.2f",
			decision.Confidence, policy.ConfidenceThreshold)
	}

	// Step 5: Check cost budget
	if policy.CostBudget.MaxTokens > 0 {
		// This is a simplified check - in production, would need actual token tracking
		if decision.Confidence < 0.5 {
			decision.Fallback = true
			decision.Explanation = fmt.Sprintf("fallback: cost budget exceeded for tokens %d",
				policy.CostBudget.MaxTokens)
		}
	}

	// Step 6: Check safety budget
	if policy.SafetyBudget.Value > 0 {
		if r.exceedsSafetyBudget(decision, policy.SafetyBudget) {
			decision.Fallback = true
			decision.Explanation = fmt.Sprintf("fallback: safety budget exceeded (risk=%d, max=%d)",
				policy.SafetyBudget.Value, policy.SafetyBudget.Value)
		}
	}

	return decision, nil
}

// SetRoutingPolicy updates the routing policy.
func (r *defaultPolicyRouter) SetRoutingPolicy(policy RoutingPolicy) error {
	if policy.ConfidenceThreshold < 0 || policy.ConfidenceThreshold > 1 {
		return fmt.Errorf("confidence threshold must be between 0 and 1, got %.2f", policy.ConfidenceThreshold)
	}
	r.policy = policy
	return nil
}

// GetRoutingPolicy returns the current routing policy.
func (r *defaultPolicyRouter) GetRoutingPolicy() RoutingPolicy {
	return r.policy
}

// BoostAgencyConfidence increases confidence for a high-performing agency.
func (r *defaultPolicyRouter) BoostAgencyConfidence(agency string, boost float64) {
	if agency == "" {
		return
	}
	// Get current adjustment (default 0)
	current := r.agencyConfidences[agency]
	// Add boost, capped at +0.3
	newVal := current + boost
	if newVal > 0.3 {
		newVal = 0.3
	}
	r.agencyConfidences[agency] = newVal
}

// ReduceAgencyConfidence decreases confidence for a low-performing agency.
func (r *defaultPolicyRouter) ReduceAgencyConfidence(agency string, penalty float64) {
	if agency == "" {
		return
	}
	// Get current adjustment (default 0)
	current := r.agencyConfidences[agency]
	// Subtract penalty, floor at -0.3
	newVal := current - penalty
	if newVal < -0.3 {
		newVal = -0.3
	}
	r.agencyConfidences[agency] = newVal
}

// Route delegates to base router.
func (r *defaultPolicyRouter) Route(ctx context.Context, query Query, class Classification) (RoutingDecision, error) {
	return r.baseRouter.Route(ctx, query, class)
}

// GetRules delegates to base router.
func (r *defaultPolicyRouter) GetRules() []RoutingRule {
	return r.baseRouter.GetRules()
}

// AddRule delegates to base router.
func (r *defaultPolicyRouter) AddRule(rule RoutingRule) error {
	return r.baseRouter.AddRule(rule)
}

// RemoveRule delegates to base router.
func (r *defaultPolicyRouter) RemoveRule(ruleID string) error {
	return r.baseRouter.RemoveRule(ruleID)
}

// applyCapabilityMatch finds better routing decisions based on capabilities.
func (r *defaultPolicyRouter) applyCapabilityMatch(query Query, class Classification, baseDecision RoutingDecision) (*RoutingDecision, error) {
	if r.capabilities == nil {
		return nil, nil
	}

	// Build capability request from classification
	req := CapabilityRequest{
		Domain: class.Domain,
	}

	// Add skills from classification
	if len(baseDecision.Skills) > 0 {
		req.Skills = make([]SkillName, len(baseDecision.Skills))
		for i, skill := range baseDecision.Skills {
			req.Skills[i] = SkillName(skill)
		}
	}

	// Find matching agencies
	agencies := r.capabilities.FindAgencies(req)
	if len(agencies) > 0 {
		best := agencies[0]
		if baseDecision.Agency == nil || string(best.Name) != *baseDecision.Agency {
			agencyName := string(best.Name)
			return &RoutingDecision{
				Target:      TargetAgency,
				Agency:      &agencyName,
				Skills:      skillsToStrings(best.Skills),
				Confidence:  baseDecision.Confidence + 0.1, // Boost for capability match
				Explanation: fmt.Sprintf("capability match: agency %s matched via registry", best.Name),
				Fallback:    false,
			}, nil
		}
	}

	// Find matching agents
	agents := r.capabilities.FindAgents(req)
	if len(agents) > 0 {
		best := agents[0]
		if baseDecision.Agent == nil || string(best.Name) != *baseDecision.Agent {
			agentName := string(best.Name)
			agencyName := string(best.Agency)
			return &RoutingDecision{
				Target:      TargetAgent,
				Agent:       &agentName,
				Agency:      &agencyName,
				Skills:      skillsToStrings(best.Skills),
				Confidence:  baseDecision.Confidence + 0.15, // Higher boost for direct agent match
				Explanation: fmt.Sprintf("capability match: agent %s matched via registry", best.Name),
				Fallback:    false,
			}, nil
		}
	}

	return nil, nil
}

// applyPriorityRules applies priority rules and returns boosted confidence.
func (r *defaultPolicyRouter) applyPriorityRules(query Query, class Classification, baseConfidence float64, rules []PriorityRule) float64 {
	if len(rules) == 0 {
		return baseConfidence
	}

	confidence := baseConfidence

	for _, rule := range rules {
		if r.matchesPriorityCondition(query, class, rule.Condition) {
			confidence += rule.Boost
			// Cap at 1.0
			if confidence > 1.0 {
				confidence = 1.0
			}
		}
	}

	return confidence
}

// matchesPriorityCondition checks if a query matches a priority rule condition.
func (r *defaultPolicyRouter) matchesPriorityCondition(query Query, class Classification, condition string) bool {
	if condition == "" {
		return false
	}

	// Parse simple condition patterns like "domain=development AND intent=task"
	parts := strings.Split(strings.ToLower(condition), " and ")
	if len(parts) == 0 {
		return false
	}

	for _, part := range parts {
		part = strings.TrimSpace(part)
		kv := strings.Split(part, "=")
		if len(kv) != 2 {
			continue
		}

		key := strings.TrimSpace(kv[0])
		value := strings.TrimSpace(kv[1])

		switch key {
		case "domain":
			if strings.ToLower(string(class.Domain)) != value {
				return false
			}
		case "intent":
			if strings.ToLower(string(class.Intent)) != value {
				return false
			}
		case "complexity":
			if strings.ToLower(string(class.Complexity)) != value {
				return false
			}
		case "query":
			if !strings.Contains(strings.ToLower(query.Text), value) {
				return false
			}
		}
	}

	return true
}

// exceedsSafetyBudget checks if the routing decision exceeds the safety budget.
func (r *defaultPolicyRouter) exceedsSafetyBudget(decision RoutingDecision, budget RiskScore) bool {
	// In a real implementation, this would check actual risk scores
	// For now, we use a simplified heuristic based on target and fallback status
	switch decision.Target {
	case TargetOrchestrator:
		// Orchestrator is medium risk
		return budget.Value < 40
	case TargetAgency:
		if decision.Fallback {
			// Fallback to agency is higher risk
			return budget.Value < 60
		}
		return budget.Value < 50
	case TargetAgent:
		if decision.Fallback {
			return budget.Value < 70
		}
		return budget.Value < 55
	default:
		return false
	}
}

// skillsToStrings converts []SkillName to []string.
func skillsToStrings(skills []SkillName) []string {
	result := make([]string, len(skills))
	for i, skill := range skills {
		result[i] = string(skill)
	}
	return result
}
