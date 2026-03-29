package decision

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestPathSelector_FastPath(t *testing.T) {
	t.Parallel()

	selector := NewPathSelector()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 30}
	risk := RiskScore{Value: 20, Category: RiskStandard}
	trigger := Decision{UseDeepPath: false}

	path, err := selector.SelectPath(ctx, complexity, risk, trigger)

	assert.NoError(t, err)
	assert.Equal(t, PathFast, path, "Low complexity + low risk should select fast path")
}

func TestPathSelector_DeepPath(t *testing.T) {
	t.Parallel()

	selector := NewPathSelector()
	ctx := context.Background()

	// High complexity OR high risk triggers deep path
	complexity := ComplexityScore{Value: 75}
	risk := RiskScore{Value: 30, Category: RiskStandard}
	trigger := Decision{UseDeepPath: false}

	path, err := selector.SelectPath(ctx, complexity, risk, trigger)

	assert.NoError(t, err)
	assert.Equal(t, PathDeep, path, "High complexity should select deep path")
}

func TestPathSelector_DeepPathViaTrigger(t *testing.T) {
	t.Parallel()

	selector := NewPathSelector()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 40}
	risk := RiskScore{Value: 30, Category: RiskStandard}
	trigger := Decision{UseDeepPath: true} // Explicit trigger

	path, err := selector.SelectPath(ctx, complexity, risk, trigger)

	assert.NoError(t, err)
	assert.Equal(t, PathDeep, path, "Triggered deep path should be selected")
}

func TestPathSelector_HighRiskDeepPath(t *testing.T) {
	t.Parallel()

	selector := NewPathSelector()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 30}
	risk := RiskScore{Value: 70, Category: RiskExpensive}
	trigger := Decision{UseDeepPath: false}

	path, err := selector.SelectPath(ctx, complexity, risk, trigger)

	assert.NoError(t, err)
	assert.Equal(t, PathDeep, path, "High risk (>=70) should select deep path")
}

func TestPathSelector_ThresholdBoundary(t *testing.T) {
	t.Parallel()

	selector := NewPathSelector()
	ctx := context.Background()

	tests := []struct {
		name       string
		complexity int
		risk       int
		trigger    bool
		expected   ExecutionPath
	}{
		{
			name:       "Complexity at 71 is deep",
			complexity: 71,
			risk:       30,
			trigger:    false,
			expected:   PathDeep,
		},
		{
			name:       "Complexity at 70 is fast",
			complexity: 70,
			risk:       30,
			trigger:    false,
			expected:   PathFast,
		},
		{
			name:       "Risk at 70 is deep",
			complexity: 30,
			risk:       70,
			trigger:    false,
			expected:   PathDeep,
		},
		{
			name:       "Risk at 69 is fast",
			complexity: 30,
			risk:       69,
			trigger:    false,
			expected:   PathFast,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			complexity := ComplexityScore{Value: tt.complexity}
			risk := RiskScore{Value: tt.risk, Category: RiskStandard}
			trigger := Decision{UseDeepPath: tt.trigger}

			path, err := selector.SelectPath(ctx, complexity, risk, trigger)

			assert.NoError(t, err)
			assert.Equal(t, tt.expected, path)
		})
	}
}

func TestPathSelector_MediumComplexity(t *testing.T) {
	t.Parallel()

	selector := NewPathSelector()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 50}
	risk := RiskScore{Value: 35, Category: RiskStandard}
	trigger := Decision{UseDeepPath: false}

	path, err := selector.SelectPath(ctx, complexity, risk, trigger)

	assert.NoError(t, err)
	assert.Equal(t, PathFast, path, "Medium complexity without trigger should be fast")
}
