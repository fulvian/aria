package decision

import (
	"context"
	"strings"

	"github.com/fulvian/aria/internal/aria/routing"
)

// TriggerPolicy determines when to use deep path (sequential-thinking).
type TriggerPolicy interface {
	ShouldUseDeepPath(ctx context.Context, complexity ComplexityScore, risk RiskScore, class routing.Classification) (Decision, error)
}

// Decision contains the trigger policy decision.
type Decision struct {
	UseDeepPath bool
	Reason      string
	TriggeredBy []TriggerReason
	MaxThoughts int
	TimeoutMs   int
}

// TriggerReason identifies why a decision was made.
type TriggerReason struct {
	Rule    string
	Matched bool
	Weight  int
}

// DefaultTriggerPolicy is the default implementation of TriggerPolicy.
type DefaultTriggerPolicy struct {
	ComplexityThreshold int
	RiskThreshold       int
	MaxThoughts         int
	TimeoutMs           int
}

// NewDefaultTriggerPolicy creates a new DefaultTriggerPolicy with default values.
func NewDefaultTriggerPolicy() *DefaultTriggerPolicy {
	return &DefaultTriggerPolicy{
		ComplexityThreshold: 55,
		RiskThreshold:       40,
		MaxThoughts:         12,
		TimeoutMs:           12000,
	}
}

// NewTriggerPolicyWithConfig creates a new DefaultTriggerPolicy with custom config.
func NewTriggerPolicyWithConfig(complexityThreshold, riskThreshold, maxThoughts, timeoutMs int) *DefaultTriggerPolicy {
	return &DefaultTriggerPolicy{
		ComplexityThreshold: complexityThreshold,
		RiskThreshold:       riskThreshold,
		MaxThoughts:         maxThoughts,
		TimeoutMs:           timeoutMs,
	}
}

// ShouldUseDeepPath determines if deep path should be used.
func (p *DefaultTriggerPolicy) ShouldUseDeepPath(ctx context.Context, complexity ComplexityScore, risk RiskScore, class routing.Classification) (Decision, error) {
	decision := Decision{
		TriggeredBy: make([]TriggerReason, 0),
		MaxThoughts: p.MaxThoughts,
		TimeoutMs:   p.TimeoutMs,
	}

	// Check non-trigger conditions first (force fast path)
	if p.isNonTrigger(complexity, class) {
		decision.UseDeepPath = false
		decision.Reason = "Query qualifies for fast path (non-trigger conditions met)"
		return decision, nil
	}

	// Check trigger conditions
	var totalWeight int

	// ComplexityScore.Value >= complexityThreshold: +100
	if complexity.Value >= p.ComplexityThreshold {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "complexity_threshold",
			Matched: true,
			Weight:  100,
		})
		totalWeight += 100
	}

	// RiskScore.Value >= riskThreshold: +100
	if risk.Value >= p.RiskThreshold {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "risk_threshold",
			Matched: true,
			Weight:  100,
		})
		totalWeight += 100
	}

	// class.Complexity == ComplexityComplex: +80
	if class.Complexity == routing.ComplexityComplex {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "complexity_complex",
			Matched: true,
			Weight:  80,
		})
		totalWeight += 80
	}

	// class.Intent IN [Analysis, Planning]: +60
	if class.Intent == routing.IntentAnalysis || class.Intent == routing.IntentPlanning {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "intent_analysis_planning",
			Matched: true,
			Weight:  60,
		})
		totalWeight += 60
	}

	// Query requires >= 2 tools (ambiguous without capability check, use heuristics): +90
	// Heuristic: query contains tool-related patterns
	toolPatterns := []string{" and ", " then ", " after ", " before ", " also "}
	toolCount := 0
	for _, pattern := range toolPatterns {
		toolCount += strings.Count(strings.ToLower(class.Reason), pattern)
	}
	if toolCount >= 1 {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "multi_tool_heuristic",
			Matched: true,
			Weight:  90,
		})
		totalWeight += 90
	}

	// Query requires >= 2 agents OR agency+handoff: +95
	// Heuristic: query mentions multiple agents or handoff
	agentPatterns := []string{"agent", "handoff", "transfer", "delegate"}
	agentCount := 0
	for _, pattern := range agentPatterns {
		if strings.Contains(strings.ToLower(class.Reason), pattern) {
			agentCount++
		}
	}
	if agentCount >= 2 {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "multi_agent_heuristic",
			Matched: true,
			Weight:  95,
		})
		totalWeight += 95
	}

	// Ambiguous query (contains "or" or conflicts): +70
	if strings.Contains(strings.ToLower(class.Reason), "or") || strings.Contains(strings.ToLower(class.Reason), "conflict") {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "ambiguous_query",
			Matched: true,
			Weight:  70,
		})
		totalWeight += 70
	}

	// RiskScore.Category IN [Irreversible, Expensive]: +85
	if risk.Category == RiskIrreversible || risk.Category == RiskExpensive {
		decision.TriggeredBy = append(decision.TriggeredBy, TriggerReason{
			Rule:    "high_risk_category",
			Matched: true,
			Weight:  85,
		})
		totalWeight += 85
	}

	// Determine decision
	if totalWeight >= 60 {
		decision.UseDeepPath = true
		decision.Reason = buildTriggerReason(decision.TriggeredBy)
	} else {
		decision.UseDeepPath = false
		decision.Reason = "Query does not meet deep path trigger criteria"
	}

	return decision, nil
}

// isNonTrigger checks if query should force fast path.
func (p *DefaultTriggerPolicy) isNonTrigger(complexity ComplexityScore, class routing.Classification) bool {
	// ComplexityScore.Value <= 20: -100 (triviale)
	if complexity.Value <= 20 {
		return true
	}

	// Query semplice Q&A (< 30 chars, 0 history): -100
	// This is handled externally via query characteristics

	// Intent = Question AND Complexity = Simple: -100
	if class.Intent == routing.IntentQuestion && class.Complexity == routing.ComplexitySimple {
		return true
	}

	return false
}

// buildTriggerReason creates a summary of trigger reasons.
func buildTriggerReason(triggers []TriggerReason) string {
	if len(triggers) == 0 {
		return "No triggers matched"
	}
	var matched []string
	for _, t := range triggers {
		if t.Matched {
			matched = append(matched, t.Rule)
		}
	}
	return "Deep path triggered by: " + strings.Join(matched, ", ")
}
