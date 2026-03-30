package plan

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPlanner_NewPlanner(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	assert.NotNil(t, planner)
}

func TestPlanner_CreatePlan_FastPath(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Simple question",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{},
	}

	class := routing.Classification{
		Intent:     routing.IntentQuestion,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexitySimple,
		Confidence: 0.9,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathFast,
		Complexity: decision.ComplexityScore{
			Value: 20,
		},
		Risk: decision.RiskScore{
			Value: 10,
		},
	}

	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)
	assert.NotNil(t, plan)

	// Fast path should have simple steps
	assert.NotEmpty(t, plan.ID)
	assert.Equal(t, query.Text, plan.Query)
	assert.NotEmpty(t, plan.Objective)
	assert.NotEmpty(t, plan.DoneCriteria)
	assert.True(t, len(plan.Steps) >= 1)
}

func TestPlanner_CreatePlan_MediumComplexity(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Do this and then do that",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{"previous message"},
	}

	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
		Confidence: 0.7,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathFast,
		Complexity: decision.ComplexityScore{
			Value: 50,
		},
		Risk: decision.RiskScore{
			Value: 20,
		},
	}

	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)
	assert.NotNil(t, plan)

	// Medium complexity should have 2 steps
	assert.Len(t, plan.Steps, 2)
}

func TestPlanner_CreatePlan_Complex(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Refactor the entire architecture and migrate to new system",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{"msg1", "msg2", "msg3", "msg4", "msg5", "msg6"},
	}

	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex,
		Confidence: 0.6,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 80,
		},
		Risk: decision.RiskScore{
			Value: 50,
		},
	}

	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)
	assert.NotNil(t, plan)

	// Complex should have multiple steps (detailed steps)
	assert.True(t, len(plan.Steps) >= 3)
}

func TestPlanner_CreatePlanWithThinking_DeepPath(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Complex multi-agent task with refactoring",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{"msg1", "msg2"},
	}

	class := routing.Classification{
		Intent:     routing.IntentPlanning,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex,
		Confidence: 0.7,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 75,
		},
		Risk: decision.RiskScore{
			Value: 45,
		},
	}

	plan, err := planner.CreatePlanWithThinking(ctx, query, class, decision_)
	require.NoError(t, err)
	assert.NotNil(t, plan)

	// Deep path should have detailed steps
	assert.True(t, len(plan.Steps) >= 3)
	assert.True(t, len(plan.Hypotheses) >= 2)
	assert.True(t, len(plan.Risks) >= 2)
	assert.True(t, len(plan.Fallbacks) >= 2)

	// Should have deep path metadata
	assert.Equal(t, "deep", plan.Metadata["path"])
	assert.True(t, plan.Metadata["used_thinking"].(bool))
}

func TestPlanner_CreatePlan_HypothesesPopulated(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Test query",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{},
	}

	class := routing.Classification{
		Intent:     routing.IntentQuestion,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexitySimple,
		Confidence: 0.8,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathFast,
		Complexity: decision.ComplexityScore{
			Value: 15,
		},
		Risk: decision.RiskScore{
			Value: 5,
		},
	}

	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)

	// Should have at least one hypothesis
	assert.NotEmpty(t, plan.Hypotheses)
}

func TestPlanner_CreatePlan_RisksPopulated(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Delete all files",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{},
	}

	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
		Confidence: 0.6,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathFast,
		Complexity: decision.ComplexityScore{
			Value: 40,
		},
		Risk: decision.RiskScore{
			Value: 30,
		},
	}

	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)

	// Should have risk entries
	assert.NotEmpty(t, plan.Risks)
}

func TestPlanner_CreatePlan_FallbacksPopulated(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Execute task",
		SessionID: "session-1",
		UserID:    "user-1",
		History:   []string{},
	}

	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexitySimple,
		Confidence: 0.8,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathFast,
		Complexity: decision.ComplexityScore{
			Value: 20,
		},
		Risk: decision.RiskScore{
			Value: 10,
		},
	}

	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)

	// Should have at least one fallback
	assert.NotEmpty(t, plan.Fallbacks)
}

func TestExtractObjective(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "Simple query",
			input:    "What is the weather?",
			expected: "What is the weather?",
		},
		{
			name:     "Query with trailing spaces",
			input:    "Test query   ",
			expected: "Test query",
		},
		{
			name:     "Query with trailing newline",
			input:    "Test query\n",
			expected: "Test query",
		},
		{
			name:     "Query with trailing spaces and newline",
			input:    "Test query  \n  ",
			expected: "Test query",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			result := extractObjective(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}
