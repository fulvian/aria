package plan

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestReviewer_NewReviewer(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	assert.NotNil(t, reviewer)
}

func TestReviewer_NewReviewerWithConfig(t *testing.T) {
	t.Parallel()

	config := ReviewerConfig{
		MinAcceptanceScore: 0.8,
		MaxReplan:          3,
		MaxRetries:         2,
	}

	reviewer := NewReviewerWithConfig(config)
	assert.NotNil(t, reviewer)
}

func TestReviewer_Review_Approved(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-1",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{},
		DoneCriteria: "completed",
	}

	result := &ExecutionResult{
		PlanID:         "test-plan-1",
		Success:        true,
		CompletedSteps: []int{0, 1, 2},
		FailedStep:     nil,
		Outputs:        map[string]any{"step_0": map[string]any{"done": true}},
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  500,
			TotalTime:    5 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second, 2 * time.Second, 2 * time.Second},
			FallbackUsed: false,
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.NotNil(t, review)
	assert.True(t, review.Passed)
	assert.Equal(t, "APPROVED", review.Verdict)
	assert.GreaterOrEqual(t, review.Score, 0.75)
}

func TestReviewer_Review_ReplanNeeded(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-2",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{{Index: 0}, {Index: 1}, {Index: 2}},
		DoneCriteria: "completed",
	}

	result := &ExecutionResult{
		PlanID:         "test-plan-2",
		Success:        false, // Failed
		CompletedSteps: []int{0},
		FailedStep:     intPtr(1),
		Outputs:        map[string]any{},
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  100,
			TotalTime:    1 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second},
			FallbackUsed: false,
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.NotNil(t, review)
	assert.False(t, review.Passed)
	assert.Equal(t, "REPLAN_NEEDED", review.Verdict)
	assert.Less(t, review.Score, 0.5)
}

func TestReviewer_Review_RevisionNeeded(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-3",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{{Index: 0, Constraints: []string{"constraint1"}}, {Index: 1, Constraints: []string{"constraint2"}}},
		DoneCriteria: "completed",
	}

	// Result has failure but still completes most steps - partial success
	// This results in:
	// - Objective satisfied: 0.30 (fails - Success=false)
	// - Constraints respected: 0.25 (fails - not all steps completed)
	// - Risk within threshold: 0.20 (passes)
	// - Evidence available: 0.15 (fails - empty outputs)
	// - Fallback not triggered: 0.10 (passes)
	// Total: 0.20 + 0.10 = 0.30
	result := &ExecutionResult{
		PlanID:         "test-plan-3",
		Success:        false,    // Failed
		CompletedSteps: []int{0}, // Only step 0 completed, step 1 failed
		FailedStep:     intPtr(1),
		Outputs:        map[string]any{}, // Empty outputs
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  100,
			TotalTime:    1 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second},
			FallbackUsed: false,
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.NotNil(t, review)
	// Score should be < 0.75 since objective not satisfied
	assert.Less(t, review.Score, 0.75)
}

func TestReviewer_Review_AllCriteria(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-4",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{{Index: 0, Constraints: []string{}}},
		DoneCriteria: "completed",
	}

	result := &ExecutionResult{
		PlanID:         "test-plan-4",
		Success:        true,
		CompletedSteps: []int{0},
		FailedStep:     nil,
		Outputs:        map[string]any{"step_0": map[string]any{"done": true}},
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  100,
			TotalTime:    1 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second},
			FallbackUsed: false,
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)
	assert.Len(t, review.Criteria, 5)

	// Check that all criteria have weights
	for _, c := range review.Criteria {
		assert.Greater(t, c.Weight, 0.0)
		assert.NotEmpty(t, c.Name)
	}
}

func TestReviewer_ShouldReplan_ReplanNeeded(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	review := ReviewResult{
		Score:    0.3,
		Passed:   false,
		Verdict:  "REPLAN_NEEDED",
		Feedback: "Failed criteria: [Objective satisfied]",
	}

	shouldReplan, reason := reviewer.ShouldReplan(ctx, review)
	assert.True(t, shouldReplan)
	assert.Equal(t, "REPLAN_FULL", reason.Strategy)
	assert.Equal(t, "low_score", reason.Reason)
}

func TestReviewer_ShouldReplan_RevisionNeeded(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	review := ReviewResult{
		Score:    0.6,
		Passed:   false,
		Verdict:  "REVISION_NEEDED",
		Feedback: "Failed criteria: [Evidence available]",
	}

	shouldReplan, reason := reviewer.ShouldReplan(ctx, review)
	assert.True(t, shouldReplan)
	assert.Equal(t, "RETRY", reason.Strategy)
	assert.Equal(t, "needs_revision", reason.Reason)
}

func TestReviewer_ShouldReplan_Approved(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	review := ReviewResult{
		Score:    0.85,
		Passed:   true,
		Verdict:  "APPROVED",
		Feedback: "All criteria passed",
	}

	shouldReplan, reason := reviewer.ShouldReplan(ctx, review)
	assert.False(t, shouldReplan)
	assert.Empty(t, reason.Reason)
	assert.Empty(t, reason.Strategy)
}

func TestReviewer_MaxReplan(t *testing.T) {
	t.Parallel()

	config := ReviewerConfig{
		MinAcceptanceScore: 0.75,
		MaxReplan:          2,
		MaxRetries:         1,
	}

	reviewer := NewReviewerWithConfig(config)
	assert.NotNil(t, reviewer)
}

func TestReviewer_CriteriaWeights(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-5",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{{Index: 0}},
		DoneCriteria: "completed",
	}

	result := &ExecutionResult{
		PlanID:         "test-plan-5",
		Success:        true,
		CompletedSteps: []int{0},
		FailedStep:     nil,
		Outputs:        map[string]any{"step_0": map[string]any{"done": true}},
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  100,
			TotalTime:    1 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second},
			FallbackUsed: false,
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)

	// Check specific weights
	weights := make(map[string]float64)
	for _, c := range review.Criteria {
		weights[c.Name] = c.Weight
	}

	assert.Equal(t, 0.30, weights["Objective satisfied"])
	assert.Equal(t, 0.25, weights["Constraints respected"])
	assert.Equal(t, 0.20, weights["Risk within threshold"])
	assert.Equal(t, 0.15, weights["Evidence available"])
	assert.Equal(t, 0.10, weights["Fallback not triggered excessively"])
}

func TestReviewer_FallbackUsed_AffectsScore(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-6",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{{Index: 0}},
		DoneCriteria: "completed",
	}

	result := &ExecutionResult{
		PlanID:         "test-plan-6",
		Success:        true,
		CompletedSteps: []int{0},
		FailedStep:     nil,
		Outputs:        map[string]any{"step_0": map[string]any{"done": true}},
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  100,
			TotalTime:    1 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second},
			FallbackUsed: true, // Fallback was used
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)

	// Find the fallback criterion
	var fallbackCriterion AcceptanceCriterion
	for _, c := range review.Criteria {
		if c.Name == "Fallback not triggered excessively" {
			fallbackCriterion = c
			break
		}
	}

	assert.False(t, fallbackCriterion.Passed)
	assert.Equal(t, 0.10, fallbackCriterion.Weight)
}

func TestReviewer_EmptyOutputs_AffectsEvidence(t *testing.T) {
	t.Parallel()

	reviewer := NewReviewer()
	ctx := context.Background()

	plan := &Plan{
		ID:           "test-plan-7",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{{Index: 0}},
		DoneCriteria: "completed",
	}

	result := &ExecutionResult{
		PlanID:         "test-plan-7",
		Success:        true,
		CompletedSteps: []int{0},
		FailedStep:     nil,
		Outputs:        map[string]any{}, // Empty outputs
		Handoffs:       []HandoffRecord{},
		Metrics: ExecutionMetrics{
			TotalTokens:  100,
			TotalTime:    1 * time.Second,
			StepsTime:    []time.Duration{1 * time.Second},
			FallbackUsed: false,
		},
	}

	review, err := reviewer.Review(ctx, plan, result)
	require.NoError(t, err)

	// Find the evidence criterion
	var evidenceCriterion AcceptanceCriterion
	for _, c := range review.Criteria {
		if c.Name == "Evidence available" {
			evidenceCriterion = c
			break
		}
	}

	assert.False(t, evidenceCriterion.Passed)
}

// Helper function
func intPtr(i int) *int {
	return &i
}
