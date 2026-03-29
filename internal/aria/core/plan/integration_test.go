package plan

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestIntegration_PlannerExecutorReviewer(t *testing.T) {
	t.Parallel()

	// Setup
	planner := NewPlanner()
	executor := NewExecutor()
	reviewer := NewReviewer()
	ctx := context.Background()

	// Query
	query := routing.Query{
		Text:      "Complex multi-step task",
		SessionID: "session-integration-1",
		UserID:    "user-1",
		History:   []string{"msg1", "msg2"},
	}

	// Classification
	class := routing.Classification{
		Intent:     routing.IntentPlanning,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex,
		Confidence: 0.7,
	}

	// Decision
	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 75,
		},
		Risk: decision.RiskScore{
			Value: 45,
		},
	}

	// Step 1: Create Plan
	plan, err := planner.CreatePlanWithThinking(ctx, query, class, decision_)
	require.NoError(t, err)
	assert.NotNil(t, plan)
	assert.NotEmpty(t, plan.Steps)
	assert.NotEmpty(t, plan.Hypotheses)
	assert.NotEmpty(t, plan.Risks)

	// Step 2: Execute Plan
	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotNil(t, result)

	// Step 3: Review Result
	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.NotNil(t, review)

	// Verify the integration produced a valid result
	assert.NotEmpty(t, review.Verdict)
	assert.GreaterOrEqual(t, review.Score, 0.0)
	assert.LessOrEqual(t, review.Score, 1.0)
}

func TestIntegration_PlannerExecutorReviewer_FastPath(t *testing.T) {
	t.Parallel()

	// Setup
	planner := NewPlanner()
	executor := NewExecutor()
	reviewer := NewReviewer()
	ctx := context.Background()

	// Simple query - fast path
	query := routing.Query{
		Text:      "Simple question?",
		SessionID: "session-fast-1",
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
			Value: 15,
		},
		Risk: decision.RiskScore{
			Value: 5,
		},
	}

	// Create Plan (fast path)
	plan, err := planner.CreatePlan(ctx, query, class, decision_)
	require.NoError(t, err)
	assert.NotNil(t, plan)
	assert.NotEmpty(t, plan.Steps)

	// Execute
	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotNil(t, result)
	assert.True(t, result.Success)

	// Review
	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.NotNil(t, review)
}

func TestIntegration_FullDeepPath(t *testing.T) {
	t.Parallel()

	// Setup
	planner := NewPlanner()
	executor := NewExecutor()
	reviewer := NewReviewer()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Plan a refactoring of the entire codebase",
		SessionID: "session-deep-1",
		UserID:    "user-1",
		History:   []string{"msg1", "msg2", "msg3", "msg4"},
	}

	class := routing.Classification{
		Intent:     routing.IntentPlanning,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex,
		Confidence: 0.6,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 85,
		},
		Risk: decision.RiskScore{
			Value: 55,
		},
	}

	// Create detailed plan
	plan, err := planner.CreatePlanWithThinking(ctx, query, class, decision_)
	require.NoError(t, err)

	// Verify plan has detailed structure
	assert.Len(t, plan.Steps, 4) // context, plan, execute, verify
	assert.Len(t, plan.Hypotheses, 3)
	assert.Len(t, plan.Risks, 4)
	assert.Len(t, plan.Fallbacks, 4)
	assert.Equal(t, "deep", plan.Metadata["path"])
	assert.True(t, plan.Metadata["used_thinking"].(bool))

	// Execute all steps
	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.True(t, result.Success)
	assert.Len(t, result.CompletedSteps, 4)
	assert.Nil(t, result.FailedStep)

	// Review
	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.NotNil(t, review)

	// Should be approved or revision needed (not replan needed for successful exec)
	assert.NotEqual(t, "REPLAN_NEEDED", review.Verdict)
}

func TestIntegration_ShouldReplan_AfterReview(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	executor := NewExecutor()
	reviewer := NewReviewer()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Task that will partially fail",
		SessionID: "session-replan-1",
		UserID:    "user-1",
		History:   []string{},
	}

	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
		Confidence: 0.5,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 60,
		},
		Risk: decision.RiskScore{
			Value: 35,
		},
	}

	plan, err := planner.CreatePlanWithThinking(ctx, query, class, decision_)
	require.NoError(t, err)

	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)

	// Check should replan
	shouldReplan, reason := reviewer.ShouldReplan(ctx, *review)
	_ = shouldReplan
	_ = reason

	// Verify that replan logic is consistent
	if review.Verdict == "REPLAN_NEEDED" {
		assert.True(t, shouldReplan)
		assert.Equal(t, "REPLAN_FULL", reason.Strategy)
	}
}

func TestIntegration_MultipleStepsWithHandoffs(t *testing.T) {
	t.Parallel()

	planner := NewPlanner()
	executor := NewExecutor()
	reviewer := NewReviewer()
	ctx := context.Background()

	query := routing.Query{
		Text:      "Complex task with handoffs",
		SessionID: "session-handoff-1",
		UserID:    "user-1",
		History:   []string{"msg1", "msg2", "msg3"},
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

	plan, err := planner.CreatePlanWithThinking(ctx, query, class, decision_)
	require.NoError(t, err)

	// Execute
	result, err := executor.Execute(ctx, plan)
	require.NoError(t, err)
	assert.NotNil(t, result)

	// Review
	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)

	// Integration works end-to-end
	assert.NotEmpty(t, review.Verdict)
}
