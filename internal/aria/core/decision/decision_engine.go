package decision

import (
	"context"
	"fmt"

	"github.com/fulvian/aria/internal/aria/routing"
)

// DecisionEngine is the central component that decides the execution path.
type DecisionEngine interface {
	// Decide determines the execution path for a query.
	Decide(ctx context.Context, query routing.Query, class routing.Classification) (ExecutionDecision, error)

	// GetConfig returns the current configuration.
	GetConfig() DecisionEngineConfig
}

// ExecutionDecision contains the complete decision.
type ExecutionDecision struct {
	Path        ExecutionPath
	Complexity  ComplexityScore
	Risk        RiskScore
	Trigger     Decision
	RoutingHint *RoutingHint
	Explanation string
}

// RoutingHint provides suggestions for routing.
type RoutingHint struct {
	PreferAgency   *string
	PreferAgent    *string
	AvoidAgents    []string
	BudgetTokenMax int
}

// DecisionEngineConfig contains the configuration for the decision engine.
type DecisionEngineConfig struct {
	ComplexityAnalyzer  ComplexityAnalyzer
	RiskAnalyzer        RiskAnalyzer
	TriggerPolicy       TriggerPolicy
	PathSelector        PathSelector
	ComplexityThreshold int
	RiskThreshold       int
}

// DefaultDecisionEngine is the default implementation of DecisionEngine.
type DefaultDecisionEngine struct {
	config DecisionEngineConfig
}

// NewDecisionEngine creates a new DefaultDecisionEngine.
func NewDecisionEngine(
	complexityAnalyzer ComplexityAnalyzer,
	riskAnalyzer RiskAnalyzer,
	triggerPolicy TriggerPolicy,
	pathSelector PathSelector,
	complexityThreshold int,
	riskThreshold int,
) *DefaultDecisionEngine {
	return &DefaultDecisionEngine{
		config: DecisionEngineConfig{
			ComplexityAnalyzer:  complexityAnalyzer,
			RiskAnalyzer:        riskAnalyzer,
			TriggerPolicy:       triggerPolicy,
			PathSelector:        pathSelector,
			ComplexityThreshold: complexityThreshold,
			RiskThreshold:       riskThreshold,
		},
	}
}

// NewDecisionEngineWithDefaults creates a new DefaultDecisionEngine with default components.
func NewDecisionEngineWithDefaults() *DefaultDecisionEngine {
	return &DefaultDecisionEngine{
		config: DecisionEngineConfig{
			ComplexityAnalyzer:  NewComplexityAnalyzer(),
			RiskAnalyzer:        NewRiskAnalyzer(),
			TriggerPolicy:       NewDefaultTriggerPolicy(),
			PathSelector:        NewPathSelector(),
			ComplexityThreshold: 55,
			RiskThreshold:       40,
		},
	}
}

// Decide determines the execution path for a query.
func (e *DefaultDecisionEngine) Decide(ctx context.Context, query routing.Query, class routing.Classification) (ExecutionDecision, error) {
	// Analyze complexity
	complexity, err := e.config.ComplexityAnalyzer.Analyze(ctx, query, class)
	if err != nil {
		return ExecutionDecision{}, fmt.Errorf("complexity analysis failed: %w", err)
	}

	// Analyze risk
	risk, err := e.config.RiskAnalyzer.Analyze(ctx, query, class)
	if err != nil {
		return ExecutionDecision{}, fmt.Errorf("risk analysis failed: %w", err)
	}

	// Determine trigger
	trigger, err := e.config.TriggerPolicy.ShouldUseDeepPath(ctx, complexity, risk, class)
	if err != nil {
		return ExecutionDecision{}, fmt.Errorf("trigger policy failed: %w", err)
	}

	// Select path
	path, err := e.config.PathSelector.SelectPath(ctx, complexity, risk, trigger)
	if err != nil {
		return ExecutionDecision{}, fmt.Errorf("path selection failed: %w", err)
	}

	// Build routing hint based on classification
	hint := buildRoutingHint(class, complexity, risk)

	// Build explanation
	explanation := buildExecutionExplanation(path, complexity, risk, trigger)

	return ExecutionDecision{
		Path:        path,
		Complexity:  complexity,
		Risk:        risk,
		Trigger:     trigger,
		RoutingHint: hint,
		Explanation: explanation,
	}, nil
}

// GetConfig returns the current configuration.
func (e *DefaultDecisionEngine) GetConfig() DecisionEngineConfig {
	return e.config
}

// buildRoutingHint creates routing hints based on classification and scores.
func buildRoutingHint(class routing.Classification, complexity ComplexityScore, risk RiskScore) *RoutingHint {
	hint := &RoutingHint{}

	// Set budget based on complexity
	if complexity.Value >= 70 {
		hint.BudgetTokenMax = 8000
	} else if complexity.Value >= 40 {
		hint.BudgetTokenMax = 4000
	} else {
		hint.BudgetTokenMax = 2000
	}

	// High risk suggests avoiding certain agents
	if risk.Value >= 50 {
		hint.AvoidAgents = []string{}
	}

	return hint
}

// buildExecutionExplanation creates a human-readable explanation.
func buildExecutionExplanation(path ExecutionPath, complexity ComplexityScore, risk RiskScore, trigger Decision) string {
	return fmt.Sprintf(
		"Selected %s path (complexity=%d, risk=%d, trigger=%v)",
		path,
		complexity.Value,
		risk.Value,
		trigger.UseDeepPath,
	)
}
