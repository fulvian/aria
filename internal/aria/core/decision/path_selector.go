package decision

import (
	"context"
)

// PathSelector chooses between Fast and Deep execution paths.
type PathSelector interface {
	SelectPath(ctx context.Context, complexity ComplexityScore, risk RiskScore, trigger Decision) (ExecutionPath, error)
}

// ExecutionPath represents the selected execution path.
type ExecutionPath string

const (
	PathFast ExecutionPath = "fast" // Direct classification → routing → execute → respond
	PathDeep ExecutionPath = "deep" // Planner → Executor → Reviewer → respond
)

// DefaultPathSelector is the default implementation of PathSelector.
type DefaultPathSelector struct{}

// NewPathSelector creates a new DefaultPathSelector.
func NewPathSelector() *DefaultPathSelector {
	return &DefaultPathSelector{}
}

// SelectPath selects the appropriate execution path based on complexity, risk, and trigger.
func (s *DefaultPathSelector) SelectPath(ctx context.Context, complexity ComplexityScore, risk RiskScore, trigger Decision) (ExecutionPath, error) {
	// If trigger says use deep path, use deep
	if trigger.UseDeepPath {
		return PathDeep, nil
	}

	// Otherwise, check complexity and risk thresholds
	// Complexity >= 71 OR Risk >= 70 → deep
	if complexity.Value >= 71 || risk.Value >= 70 {
		return PathDeep, nil
	}

	// Default to fast
	return PathFast, nil
}
