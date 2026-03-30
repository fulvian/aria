package telemetry

import (
	"context"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTelemetryService_RecordDecision(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	event := DecisionEvent{
		Timestamp:     time.Now(),
		QueryID:       "query-1",
		Complexity:    60,
		RiskScore:     45,
		Path:          "deep",
		UseDeepPath:   true,
		TriggerReason: "high_complexity",
	}

	svc.RecordDecision(ctx, event)

	// Verify via GetMetrics
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1, metrics.DecisionMetrics.TotalDecisions)
}

func TestTelemetryService_RecordExecution(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	event := ExecutionEvent{
		Timestamp:    time.Now(),
		QueryID:      "query-1",
		PlanID:       "plan-1",
		Path:         "deep",
		Success:      true,
		StepsTotal:   3,
		StepsFailed:  0,
		Handoffs:     1,
		DurationMs:   1500,
		TokensUsed:   5000,
		FallbackUsed: false,
	}

	svc.RecordExecution(ctx, event)

	// Verify via GetMetrics
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1, metrics.ExecutionMetrics.TotalExecutions)
}

func TestTelemetryService_RecordReview(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	event := ReviewEvent{
		Timestamp:       time.Now(),
		QueryID:         "query-1",
		PlanID:          "plan-1",
		Score:           0.85,
		Verdict:         "APPROVED",
		CriteriaResults: []bool{true, true, true, true, true},
		ReplanCount:     0,
	}

	svc.RecordReview(ctx, event)

	// Verify via GetMetrics
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1, metrics.ReviewMetrics.TotalReviews)
}

func TestTelemetryService_GetMetrics(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Record some decisions
	svc.RecordDecision(ctx, DecisionEvent{
		QueryID:       "q1",
		Complexity:    30,
		RiskScore:     20,
		Path:          "fast",
		UseDeepPath:   false,
		TriggerReason: "low_complexity",
	})
	svc.RecordDecision(ctx, DecisionEvent{
		QueryID:       "q2",
		Complexity:    70,
		RiskScore:     50,
		Path:          "deep",
		UseDeepPath:   true,
		TriggerReason: "high_complexity",
	})
	svc.RecordDecision(ctx, DecisionEvent{
		QueryID:       "q3",
		Complexity:    65,
		RiskScore:     35,
		Path:          "deep",
		UseDeepPath:   true,
		TriggerReason: "high_complexity",
	})

	// Record executions
	svc.RecordExecution(ctx, ExecutionEvent{
		QueryID:      "q1",
		PlanID:       "p1",
		Path:         "fast",
		Success:      true,
		StepsTotal:   2,
		StepsFailed:  0,
		Handoffs:     0,
		DurationMs:   500,
		TokensUsed:   1000,
		FallbackUsed: false,
	})
	svc.RecordExecution(ctx, ExecutionEvent{
		QueryID:      "q2",
		PlanID:       "p2",
		Path:         "deep",
		Success:      true,
		StepsTotal:   4,
		StepsFailed:  0,
		Handoffs:     2,
		DurationMs:   2000,
		TokensUsed:   8000,
		FallbackUsed: false,
	})

	// Record reviews
	svc.RecordReview(ctx, ReviewEvent{
		QueryID:     "q1",
		PlanID:      "p1",
		Score:       0.9,
		Verdict:     "APPROVED",
		ReplanCount: 0,
	})
	svc.RecordReview(ctx, ReviewEvent{
		QueryID:     "q2",
		PlanID:      "p2",
		Score:       0.75,
		Verdict:     "APPROVED",
		ReplanCount: 0,
	})

	// Get metrics
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)

	// Verify decision metrics
	assert.Equal(t, 3, metrics.DecisionMetrics.TotalDecisions)
	assert.Equal(t, 1, metrics.DecisionMetrics.FastPathCount)
	assert.Equal(t, 2, metrics.DecisionMetrics.DeepPathCount)
	assert.InDelta(t, 55, metrics.DecisionMetrics.AvgComplexity, 0.1)
	assert.InDelta(t, 35, metrics.DecisionMetrics.AvgRiskScore, 0.1)

	// Verify execution metrics
	assert.Equal(t, 2, metrics.ExecutionMetrics.TotalExecutions)
	assert.Equal(t, 1.0, metrics.ExecutionMetrics.SuccessRate)
	assert.InDelta(t, 3.0, metrics.ExecutionMetrics.AvgStepsPerPlan, 0.1)
	assert.InDelta(t, 0.0, metrics.ExecutionMetrics.FallbackRate, 0.1)
	assert.InDelta(t, 1.0, metrics.ExecutionMetrics.HandoffRate, 0.1)

	// Verify review metrics
	assert.Equal(t, 2, metrics.ReviewMetrics.TotalReviews)
	assert.Equal(t, 1.0, metrics.ReviewMetrics.ApprovedRate)
	assert.InDelta(t, 0.825, metrics.ReviewMetrics.AvgScore, 0.01)
}

func TestTelemetryService_Reset(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Add some events
	svc.RecordDecision(ctx, DecisionEvent{QueryID: "q1", Complexity: 30, RiskScore: 20, Path: "fast"})
	svc.RecordExecution(ctx, ExecutionEvent{QueryID: "q1", Success: true})
	svc.RecordReview(ctx, ReviewEvent{QueryID: "q1", Score: 0.9, Verdict: "APPROVED"})

	// Verify events were recorded via metrics
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1, metrics.DecisionMetrics.TotalDecisions)
	assert.Equal(t, 1, metrics.ExecutionMetrics.TotalExecutions)
	assert.Equal(t, 1, metrics.ReviewMetrics.TotalReviews)

	// Reset
	err = svc.Reset(ctx)
	require.NoError(t, err)

	// Verify all events were cleared
	metrics, err = svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 0, metrics.DecisionMetrics.TotalDecisions)
	assert.Equal(t, 0, metrics.ExecutionMetrics.TotalExecutions)
	assert.Equal(t, 0, metrics.ReviewMetrics.TotalReviews)
}

func TestTelemetryService_ThreadSafety(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Run concurrent record operations
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				queryID := fmt.Sprintf("query-%d-%d", id, j)
				svc.RecordDecision(ctx, DecisionEvent{
					QueryID:    queryID,
					Complexity: 30 + (j % 50),
					RiskScore:  20 + (j % 30),
					Path:       "fast",
				})
				svc.RecordExecution(ctx, ExecutionEvent{
					QueryID:    queryID,
					Success:    j%2 == 0,
					StepsTotal: 2,
					DurationMs: int64(500 + j*10),
				})
				svc.RecordReview(ctx, ReviewEvent{
					QueryID: queryID,
					Score:   0.5 + float64(j%50)/100.0,
					Verdict: map[bool]string{true: "APPROVED", false: "REVISION_NEEDED"}[j%2 == 0],
				})
			}
		}(i)
	}

	// Wait for all goroutines
	wg.Wait()

	// Verify all events were recorded
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1000, metrics.DecisionMetrics.TotalDecisions)
	assert.Equal(t, 1000, metrics.ExecutionMetrics.TotalExecutions)
	assert.Equal(t, 1000, metrics.ReviewMetrics.TotalReviews)
}

func TestTelemetryService_EmptyMetrics(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)

	// All metrics should be zero/empty
	assert.Equal(t, 0, metrics.DecisionMetrics.TotalDecisions)
	assert.Equal(t, 0, metrics.DecisionMetrics.FastPathCount)
	assert.Equal(t, 0, metrics.DecisionMetrics.DeepPathCount)
	assert.Equal(t, float64(0), metrics.DecisionMetrics.AvgComplexity)
	assert.Equal(t, float64(0), metrics.DecisionMetrics.AvgRiskScore)

	assert.Equal(t, 0, metrics.ExecutionMetrics.TotalExecutions)
	assert.Equal(t, float64(0), metrics.ExecutionMetrics.SuccessRate)

	assert.Equal(t, 0, metrics.ReviewMetrics.TotalReviews)
	assert.Equal(t, float64(0), metrics.ReviewMetrics.ApprovedRate)
	assert.Equal(t, float64(0), metrics.ReviewMetrics.AvgScore)
}

func TestTelemetryService_TriggerBreakdown(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Record decisions with various trigger reasons
	triggers := []string{"high_complexity", "high_risk", "high_complexity", "low_complexity", "high_risk"}
	for i, trigger := range triggers {
		svc.RecordDecision(ctx, DecisionEvent{
			QueryID:       fmt.Sprintf("q%d", i),
			Complexity:    50,
			RiskScore:     30,
			Path:          "deep",
			TriggerReason: trigger,
		})
	}

	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)

	// Verify trigger breakdown
	assert.Equal(t, 2, metrics.DecisionMetrics.TriggerBreakdown["high_complexity"])
	assert.Equal(t, 2, metrics.DecisionMetrics.TriggerBreakdown["high_risk"])
	assert.Equal(t, 1, metrics.DecisionMetrics.TriggerBreakdown["low_complexity"])
}

func TestMetricsValidator_Validate(t *testing.T) {
	t.Parallel()

	validator := NewMetricsValidator()

	// Valid metrics
	validMetrics := Metrics{
		DecisionMetrics: DecisionMetrics{
			TotalDecisions: 10,
			FastPathCount:  6,
			DeepPathCount:  4,
		},
		ExecutionMetrics: ExecutionMetrics{
			TotalExecutions: 10,
			SuccessRate:     0.8,
		},
		ReviewMetrics: ReviewMetrics{
			TotalReviews: 10,
			ApprovedRate: 0.7,
		},
	}

	err := validator.Validate(validMetrics)
	require.NoError(t, err)

	// Invalid metrics - path count mismatch
	invalidMetrics := Metrics{
		DecisionMetrics: DecisionMetrics{
			TotalDecisions: 10,
			FastPathCount:  6,
			DeepPathCount:  5, // Sum is 11, not 10
		},
	}
	err = validator.Validate(invalidMetrics)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "total decisions does not match path counts sum")
}

func TestTelemetryService_TimestampDefaulting(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Record event without timestamp
	svc.RecordDecision(ctx, DecisionEvent{
		QueryID:    "q1",
		Complexity: 30,
		RiskScore:  20,
		Path:       "fast",
		// Timestamp is zero
	})

	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1, metrics.DecisionMetrics.TotalDecisions)
}

func TestTelemetryService_VerdictDistribution(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Record reviews with different verdicts
	reviews := []ReviewEvent{
		{QueryID: "q1", Score: 0.9, Verdict: "APPROVED", ReplanCount: 0},
		{QueryID: "q2", Score: 0.6, Verdict: "REVISION_NEEDED", ReplanCount: 0},
		{QueryID: "q3", Score: 0.3, Verdict: "REPLAN_NEEDED", ReplanCount: 1},
		{QueryID: "q4", Score: 0.85, Verdict: "APPROVED", ReplanCount: 0},
		{QueryID: "q5", Score: 0.45, Verdict: "REPLAN_NEEDED", ReplanCount: 2},
	}

	for _, r := range reviews {
		svc.RecordReview(ctx, r)
	}

	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)

	assert.Equal(t, 5, metrics.ReviewMetrics.TotalReviews)
	assert.InDelta(t, 0.4, metrics.ReviewMetrics.ApprovedRate, 0.01)
	assert.InDelta(t, 0.2, metrics.ReviewMetrics.RevisionRate, 0.01)
	assert.InDelta(t, 0.4, metrics.ReviewMetrics.ReplanRate, 0.01)
	assert.InDelta(t, 0.6, metrics.ReviewMetrics.AvgReplanCount, 0.01)
}

func TestTelemetryService_FallbackAndHandoffRates(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	ctx := context.Background()

	// Record executions with fallbacks and handoffs
	execs := []ExecutionEvent{
		{QueryID: "q1", Success: true, StepsTotal: 3, Handoffs: 1, DurationMs: 1000, TokensUsed: 5000, FallbackUsed: false},
		{QueryID: "q2", Success: true, StepsTotal: 2, Handoffs: 0, DurationMs: 800, TokensUsed: 3000, FallbackUsed: false},
		{QueryID: "q3", Success: false, StepsTotal: 4, Handoffs: 2, DurationMs: 2000, TokensUsed: 10000, FallbackUsed: true},
		{QueryID: "q4", Success: true, StepsTotal: 5, Handoffs: 3, DurationMs: 3000, TokensUsed: 15000, FallbackUsed: true},
	}

	for _, e := range execs {
		svc.RecordExecution(ctx, e)
	}

	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)

	assert.Equal(t, 4, metrics.ExecutionMetrics.TotalExecutions)
	// SuccessRate is 3/4 = 0.75 (q1, q2, q4 are true, q3 is false)
	assert.InDelta(t, 0.75, metrics.ExecutionMetrics.SuccessRate, 0.01)
	// FallbackRate is 2/4 = 0.5 (q3 and q4 have FallbackUsed=true)
	assert.InDelta(t, 0.5, metrics.ExecutionMetrics.FallbackRate, 0.01)
	// HandoffRate is average handoffs per execution: (1+0+2+3)/4 = 1.5
	assert.InDelta(t, 1.5, metrics.ExecutionMetrics.HandoffRate, 0.01)
}
