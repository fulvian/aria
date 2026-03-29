package telemetry

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestFeedbackLoop_RecordOutcome(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	outcome := Outcome{
		QueryID: "q1",
		Decision: DecisionEvent{
			QueryID:       "q1",
			Complexity:    60,
			RiskScore:     45,
			Path:          "deep",
			UseDeepPath:   true,
			TriggerReason: "high_complexity",
		},
		Execution: ExecutionEvent{
			QueryID:     "q1",
			PlanID:      "p1",
			Path:        "deep",
			Success:     true,
			StepsTotal:  3,
			StepsFailed: 0,
			Handoffs:    1,
			DurationMs:  2000,
			TokensUsed:  8000,
		},
		Review: ReviewEvent{
			QueryID:     "q1",
			PlanID:      "p1",
			Score:       0.85,
			Verdict:     "APPROVED",
			ReplanCount: 0,
		},
	}

	err := loop.RecordOutcome(ctx, outcome)
	require.NoError(t, err)

	// Verify events were recorded
	metrics, err := svc.GetMetrics(ctx)
	require.NoError(t, err)
	assert.Equal(t, 1, metrics.DecisionMetrics.TotalDecisions)
	assert.Equal(t, 1, metrics.ExecutionMetrics.TotalExecutions)
	assert.Equal(t, 1, metrics.ReviewMetrics.TotalReviews)
}

func TestFeedbackLoop_RecordOutcome_Validation(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	t.Run("empty QueryID", func(t *testing.T) {
		outcome := Outcome{
			QueryID: "", // Empty
			Decision: DecisionEvent{
				QueryID:    "q1",
				Complexity: 30,
				RiskScore:  20,
				Path:       "fast",
			},
		}

		err := loop.RecordOutcome(ctx, outcome)
		require.Error(t, err)
		assert.Contains(t, err.Error(), "QueryID is required")
	})
}

func TestFeedbackLoop_GetRoutingInsight(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	// Record some outcomes with known characteristics
	outcomes := []Outcome{
		{
			QueryID: "q1",
			Decision: DecisionEvent{
				QueryID:       "q1",
				Complexity:    70,
				RiskScore:     50,
				Path:          "deep",
				TriggerReason: "high_complexity",
			},
			Execution: ExecutionEvent{
				QueryID: "q1",
				Success: true,
				Path:    "deep",
			},
			Review: ReviewEvent{
				QueryID:     "q1",
				Score:       0.9,
				Verdict:     "APPROVED",
				ReplanCount: 0,
			},
		},
		{
			QueryID: "q2",
			Decision: DecisionEvent{
				QueryID:       "q2",
				Complexity:    30,
				RiskScore:     20,
				Path:          "fast",
				TriggerReason: "low_complexity",
			},
			Execution: ExecutionEvent{
				QueryID: "q2",
				Success: true,
				Path:    "fast",
			},
			Review: ReviewEvent{
				QueryID:     "q2",
				Score:       0.85,
				Verdict:     "APPROVED",
				ReplanCount: 0,
			},
		},
		{
			QueryID: "q3",
			Decision: DecisionEvent{
				QueryID:       "q3",
				Complexity:    65,
				RiskScore:     45,
				Path:          "deep",
				TriggerReason: "high_complexity",
			},
			Execution: ExecutionEvent{
				QueryID:      "q3",
				Success:      false,
				Path:         "deep",
				FallbackUsed: true,
			},
			Review: ReviewEvent{
				QueryID:     "q3",
				Score:       0.4,
				Verdict:     "REPLAN_NEEDED",
				ReplanCount: 1,
			},
		},
	}

	for _, o := range outcomes {
		err := loop.RecordOutcome(ctx, o)
		require.NoError(t, err)
	}

	insight, err := loop.GetRoutingInsight(ctx)
	require.NoError(t, err)

	// Verify insight has reasonable values
	assert.NotNil(t, insight.HighValueTriggers)
	assert.NotNil(t, insight.LowValueTriggers)
	// With moderate approval rate (~66%), thresholds should be moderate
	assert.Greater(t, insight.RecommendedComplexityThreshold, 0)
	assert.Greater(t, insight.RecommendedRiskThreshold, 0)
}

func TestFeedbackLoop_GetRoutingInsight_NoData(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	insight, err := loop.GetRoutingInsight(ctx)
	require.NoError(t, err)

	// With no data, should return default values
	assert.Equal(t, 55, insight.RecommendedComplexityThreshold)
	assert.Equal(t, 40, insight.RecommendedRiskThreshold)
	assert.NotNil(t, insight.HighValueTriggers)
	assert.NotNil(t, insight.LowValueTriggers)
}

func TestFeedbackLoop_GetRoutingInsight_HighFallbackRate(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	// Record many outcomes with high fallback rate (> 0.2)
	for i := 0; i < 5; i++ {
		outcome := Outcome{
			QueryID: "q" + string(rune('0'+i)),
			Decision: DecisionEvent{
				QueryID:       "q" + string(rune('0'+i)),
				Complexity:    50,
				RiskScore:     30,
				Path:          "deep",
				TriggerReason: "high_risk",
			},
			Execution: ExecutionEvent{
				QueryID:      "q" + string(rune('0'+i)),
				Success:      false,
				Path:         "deep",
				FallbackUsed: true,
			},
			Review: ReviewEvent{
				QueryID:     "q" + string(rune('0'+i)),
				Score:       0.3,
				Verdict:     "REPLAN_NEEDED",
				ReplanCount: 1,
			},
		}
		err := loop.RecordOutcome(ctx, outcome)
		require.NoError(t, err)
	}

	insight, err := loop.GetRoutingInsight(ctx)
	require.NoError(t, err)

	// High fallback rate should be identified as high value trigger
	assert.Contains(t, insight.HighValueTriggers, "high_fallback_risk")
}

func TestFeedbackLoop_GetRoutingInsight_HighReplanRate(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	// Record many outcomes with high replan rate (> 0.15)
	for i := 0; i < 5; i++ {
		outcome := Outcome{
			QueryID: "q" + string(rune('0'+i)),
			Decision: DecisionEvent{
				QueryID:       "q" + string(rune('0'+i)),
				Complexity:    60,
				RiskScore:     40,
				Path:          "deep",
				TriggerReason: "high_complexity",
			},
			Execution: ExecutionEvent{
				QueryID: "q" + string(rune('0'+i)),
				Success: false,
				Path:    "deep",
			},
			Review: ReviewEvent{
				QueryID:     "q" + string(rune('0'+i)),
				Score:       0.4,
				Verdict:     "REPLAN_NEEDED",
				ReplanCount: 1,
			},
		}
		err := loop.RecordOutcome(ctx, outcome)
		require.NoError(t, err)
	}

	insight, err := loop.GetRoutingInsight(ctx)
	require.NoError(t, err)

	// High replan rate should be identified as high value trigger
	assert.Contains(t, insight.HighValueTriggers, "high_replan_risk")
}

func TestFeedbackLoop_GetRoutingInsight_LowApprovalRate(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	// Record many outcomes with low approval rate (< 0.5)
	for i := 0; i < 4; i++ {
		outcome := Outcome{
			QueryID: "q" + string(rune('0'+i)),
			Decision: DecisionEvent{
				QueryID:    "q" + string(rune('0'+i)),
				Complexity: 60,
				RiskScore:  40,
				Path:       "deep",
			},
			Execution: ExecutionEvent{
				QueryID: "q" + string(rune('0'+i)),
				Success: false,
				Path:    "deep",
			},
			Review: ReviewEvent{
				QueryID:     "q" + string(rune('0'+i)),
				Score:       0.3,
				Verdict:     "REPLAN_NEEDED",
				ReplanCount: 1,
			},
		}
		err := loop.RecordOutcome(ctx, outcome)
		require.NoError(t, err)
	}

	insight, err := loop.GetRoutingInsight(ctx)
	require.NoError(t, err)

	// Low approval rate should suggest higher thresholds
	assert.Equal(t, 65, insight.RecommendedComplexityThreshold)
	assert.Equal(t, 50, insight.RecommendedRiskThreshold)
}

func TestFeedbackLoop_GetRoutingInsight_HighApprovalRate(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	ctx := context.Background()

	// Record many outcomes with high approval rate (> 0.8)
	for i := 0; i < 5; i++ {
		outcome := Outcome{
			QueryID: "q" + string(rune('0'+i)),
			Decision: DecisionEvent{
				QueryID:    "q" + string(rune('0'+i)),
				Complexity: 40,
				RiskScore:  25,
				Path:       "fast",
			},
			Execution: ExecutionEvent{
				QueryID: "q" + string(rune('0'+i)),
				Success: true,
				Path:    "fast",
			},
			Review: ReviewEvent{
				QueryID:     "q" + string(rune('0'+i)),
				Score:       0.9,
				Verdict:     "APPROVED",
				ReplanCount: 0,
			},
		}
		err := loop.RecordOutcome(ctx, outcome)
		require.NoError(t, err)
	}

	insight, err := loop.GetRoutingInsight(ctx)
	require.NoError(t, err)

	// High approval rate should suggest default/lower thresholds
	assert.Equal(t, 55, insight.RecommendedComplexityThreshold)
	assert.Equal(t, 40, insight.RecommendedRiskThreshold)
}

func TestNewFeedbackLoop(t *testing.T) {
	t.Parallel()

	svc := NewTelemetryService()
	loop := NewFeedbackLoop(svc)
	require.NotNil(t, loop)
}

func TestValidateOutcome(t *testing.T) {
	t.Parallel()

	t.Run("valid outcome", func(t *testing.T) {
		outcome := Outcome{
			QueryID: "q1",
		}
		err := ValidateOutcome(outcome)
		require.NoError(t, err)
	})

	t.Run("empty QueryID", func(t *testing.T) {
		outcome := Outcome{
			QueryID: "",
		}
		err := ValidateOutcome(outcome)
		require.Error(t, err)
		assert.Contains(t, err.Error(), "QueryID is required")
	})
}

func TestInsightAnalyzer_AnalyzePathDistribution(t *testing.T) {
	t.Parallel()

	analyzer := NewInsightAnalyzer()

	decisions := []DecisionEvent{
		{QueryID: "q1", Path: "fast"},
		{QueryID: "q2", Path: "fast"},
		{QueryID: "q3", Path: "deep"},
		{QueryID: "q4", Path: "deep"},
		{QueryID: "q5", Path: "deep"},
	}

	distribution := analyzer.AnalyzePathDistribution(decisions)

	assert.Equal(t, 2, distribution["fast"])
	assert.Equal(t, 3, distribution["deep"])
}

func TestInsightAnalyzer_AnalyzeSuccessByPath(t *testing.T) {
	t.Parallel()

	analyzer := NewInsightAnalyzer()

	decisions := []DecisionEvent{
		{QueryID: "q1", Path: "fast"},
		{QueryID: "q2", Path: "fast"},
		{QueryID: "q3", Path: "deep"},
	}
	executions := []ExecutionEvent{
		{QueryID: "q1"},
		{QueryID: "q2"},
		{QueryID: "q3"},
	}
	reviews := []ReviewEvent{
		{QueryID: "q1", Verdict: "APPROVED"},
		{QueryID: "q2", Verdict: "APPROVED"},
		{QueryID: "q3", Verdict: "REPLAN_NEEDED"},
	}

	successByPath := analyzer.AnalyzeSuccessByPath(decisions, executions, reviews)

	assert.Equal(t, 1.0, successByPath["fast"]) // 2 approved out of 2
	assert.Equal(t, 0.0, successByPath["deep"]) // 0 approved out of 1
}

func TestInsightAnalyzer_AnalyzeSuccessByPath_Empty(t *testing.T) {
	t.Parallel()

	analyzer := NewInsightAnalyzer()

	successByPath := analyzer.AnalyzeSuccessByPath(nil, nil, nil)

	assert.Equal(t, 0.0, successByPath["fast"])
	assert.Equal(t, 0.0, successByPath["deep"])
}

func TestOutcome_WithTimestamp(t *testing.T) {
	t.Parallel()

	outcome := Outcome{
		QueryID: "q1",
		Decision: DecisionEvent{
			QueryID:   "q1",
			Timestamp: time.Now(),
		},
	}

	assert.NotZero(t, outcome.Decision.Timestamp)
}
