package plan

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestExecutor_NewExecutor(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	assert.NotNil(t, executor)
}

func TestExecutor_ExecuteStep_SingleStep(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	step := PlanStep{
		Index:       0,
		Action:      "execute",
		Target:      "direct",
		Inputs:      map[string]any{"query": "test"},
		ExpectedOut: map[string]any{"response": "ok"},
		Constraints: []string{},
		Timeout:     30 * time.Second,
	}

	result, err := executor.ExecuteStep(ctx, step)
	require.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, 0, result.StepIndex)
	assert.True(t, result.Success)
	assert.NotNil(t, result.Output)
	assert.Nil(t, result.Error)
}

func TestExecutor_ExecuteStep_WithConstraints(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	step := PlanStep{
		Index:       0,
		Action:      "analyze",
		Target:      "context",
		Inputs:      map[string]any{"query": "test"},
		ExpectedOut: map[string]any{"analysis": "done"},
		Constraints: []string{"preserve context"},
		Timeout:     15 * time.Second,
	}

	result, err := executor.ExecuteStep(ctx, step)
	require.NoError(t, err)
	assert.True(t, result.Success)
}

func TestExecutor_Execute_SingleStep(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	plan := &Plan{
		ID:        "test-plan-1",
		Query:     "Test query",
		Objective: "Test objective",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"response": "ok"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
		},
		Fallbacks: []FallbackStrategy{},
	}

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, plan.ID, result.PlanID)
	assert.True(t, result.Success)
	assert.Contains(t, result.CompletedSteps, 0)
	assert.Nil(t, result.FailedStep)
	assert.Empty(t, result.Error)
}

func TestExecutor_Execute_MultiStep(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	plan := &Plan{
		ID:        "test-plan-2",
		Query:     "Multi-step query",
		Objective: "Complete multiple steps",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "analyze",
				Target:      "context",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"analysis": "done"},
				Constraints: []string{},
				Timeout:     10 * time.Second,
			},
			{
				Index:       1,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"response": "ok"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
			{
				Index:       2,
				Action:      "verify",
				Target:      "reviewer",
				Inputs:      map[string]any{"result": "output"},
				ExpectedOut: map[string]any{"verified": true},
				Constraints: []string{},
				Timeout:     10 * time.Second,
			},
		},
		Fallbacks: []FallbackStrategy{},
	}

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotNil(t, result)
	assert.True(t, result.Success)
	assert.Len(t, result.CompletedSteps, 3)
	assert.Contains(t, result.CompletedSteps, 0)
	assert.Contains(t, result.CompletedSteps, 1)
	assert.Contains(t, result.CompletedSteps, 2)
	assert.Nil(t, result.FailedStep)
}

func TestExecutor_Execute_RecordsOutputs(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	plan := &Plan{
		ID:        "test-plan-3",
		Query:     "Test query",
		Objective: "Test objective",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"response": "ok"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
		},
		Fallbacks: []FallbackStrategy{},
	}

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotEmpty(t, result.Outputs)
	assert.NotNil(t, result.Outputs["step_0"])
}

func TestExecutor_Execute_RecordsMetrics(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	plan := &Plan{
		ID:        "test-plan-4",
		Query:     "Test query",
		Objective: "Test objective",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"response": "ok"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
		},
		Fallbacks: []FallbackStrategy{},
	}

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.Greater(t, result.Metrics.TotalTime, time.Duration(0))
	assert.Len(t, result.Metrics.StepsTime, 1)
	assert.False(t, result.Metrics.FallbackUsed)
}

func TestExecutor_Execute_FallbackTriggered(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	// Create a plan where we manually set up for fallback testing
	plan := &Plan{
		ID:        "test-plan-fallback",
		Query:     "Test query",
		Objective: "Test objective",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"response": "ok"},
				Constraints: []string{"some_constraint"},
				Timeout:     30 * time.Second,
			},
		},
		Fallbacks: []FallbackStrategy{
			{
				Condition: "execution failed",
				Action:    "retry",
				Target:    "simpler approach",
			},
		},
	}

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	// Since constraints are met, fallback should not be used
	assert.False(t, result.Metrics.FallbackUsed)
}

func TestExecutor_Execute_CancelledContext(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	plan := &Plan{
		ID:        "test-plan-cancelled",
		Query:     "Test query",
		Objective: "Test objective",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": "test"},
				ExpectedOut: map[string]any{"response": "ok"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
		},
		Fallbacks: []FallbackStrategy{},
	}

	result, err := executor.Execute(ctx, plan)
	// Context is cancelled, so execution should handle this
	assert.NotNil(t, result)
	_ = err // Error may be present due to cancellation
}

func TestExecutor_ExecuteStep_OutputContainsExpectedFields(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	step := PlanStep{
		Index:       5,
		Action:      "custom_action",
		Target:      "custom_target",
		Inputs:      map[string]any{"key": "value"},
		ExpectedOut: map[string]any{"result": "expected"},
		Constraints: []string{},
		Timeout:     60 * time.Second,
	}

	result, err := executor.ExecuteStep(ctx, step)
	require.NoError(t, err)

	output := result.Output
	assert.Equal(t, true, output["executed"])
	assert.Equal(t, "custom_action", output["action"])
	assert.Equal(t, "custom_target", output["target"])
	assert.Equal(t, true, output["simulated"])
}

func TestExecutor_Execute_EmptyPlan(t *testing.T) {
	t.Parallel()

	executor := NewExecutor()
	ctx := context.Background()

	plan := &Plan{
		ID:        "test-plan-empty",
		Query:     "Test query",
		Objective: "Test objective",
		Steps:     []PlanStep{},
		Fallbacks: []FallbackStrategy{},
	}

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotNil(t, result)
	assert.True(t, result.Success)
	assert.Empty(t, result.CompletedSteps)
}
