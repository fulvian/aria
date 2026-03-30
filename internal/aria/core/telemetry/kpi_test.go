package telemetry

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestKPICalculator_CalculateKPIs(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	metrics := Metrics{
		DecisionMetrics: DecisionMetrics{
			TotalDecisions: 10,
			FastPathCount:  6,
			DeepPathCount:  4,
		},
		ExecutionMetrics: ExecutionMetrics{
			TotalExecutions: 10,
			SuccessRate:     0.8,
			AvgDurationMs:   1500,
			FallbackRate:    0.1,
		},
		ReviewMetrics: ReviewMetrics{
			TotalReviews: 10,
			ApprovedRate: 0.7,
			RevisionRate: 0.2,
			ReplanRate:   0.1,
			AvgScore:     0.75,
		},
	}

	kpis := calc.CalculateKPIs(metrics)

	assert.InDelta(t, 0.7, kpis.RoutingAccuracy, 0.01)
	assert.InDelta(t, 0.1, kpis.FallbackRate, 0.01)
	assert.InDelta(t, 0.1, kpis.ReplanRate, 0.01)
	assert.InDelta(t, 0.2, kpis.ToolMisuseRate, 0.01)
	assert.InDelta(t, 0.8, kpis.ResponseSuccessRate, 0.01)
}

func TestKPICalculator_RoutingAccuracy(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	t.Run("with reviews", func(t *testing.T) {
		metrics := Metrics{
			ReviewMetrics: ReviewMetrics{
				TotalReviews: 10,
				ApprovedRate: 0.8,
			},
		}

		accuracy := calc.CalculateRoutingAccuracy(metrics)
		assert.InDelta(t, 0.8, accuracy, 0.01)
	})

	t.Run("no reviews", func(t *testing.T) {
		metrics := Metrics{
			ReviewMetrics: ReviewMetrics{
				TotalReviews: 0,
			},
		}

		accuracy := calc.CalculateRoutingAccuracy(metrics)
		assert.Equal(t, 0.0, accuracy)
	})
}

func TestKPICalculator_FallbackRate(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	t.Run("with executions", func(t *testing.T) {
		metrics := Metrics{
			ExecutionMetrics: ExecutionMetrics{
				TotalExecutions: 10,
				FallbackRate:    0.15,
			},
		}

		rate := calc.CalculateFallbackRate(metrics)
		assert.InDelta(t, 0.15, rate, 0.01)
	})

	t.Run("no executions", func(t *testing.T) {
		metrics := Metrics{
			ExecutionMetrics: ExecutionMetrics{
				TotalExecutions: 0,
			},
		}

		rate := calc.CalculateFallbackRate(metrics)
		assert.Equal(t, 0.0, rate)
	})
}

func TestKPICalculator_ReplanRate(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	t.Run("with reviews", func(t *testing.T) {
		metrics := Metrics{
			ReviewMetrics: ReviewMetrics{
				TotalReviews: 10,
				ReplanRate:   0.25,
			},
		}

		rate := calc.CalculateReplanRate(metrics)
		assert.InDelta(t, 0.25, rate, 0.01)
	})

	t.Run("no reviews", func(t *testing.T) {
		metrics := Metrics{
			ReviewMetrics: ReviewMetrics{
				TotalReviews: 0,
			},
		}

		rate := calc.CalculateReplanRate(metrics)
		assert.Equal(t, 0.0, rate)
	})
}

func TestKPICalculator_ToolMisuseRate(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	t.Run("with reviews", func(t *testing.T) {
		metrics := Metrics{
			ReviewMetrics: ReviewMetrics{
				TotalReviews: 10,
				RevisionRate: 0.3,
			},
		}

		rate := calc.CalculateToolMisuseRate(metrics)
		assert.InDelta(t, 0.3, rate, 0.01)
	})

	t.Run("no reviews", func(t *testing.T) {
		metrics := Metrics{
			ReviewMetrics: ReviewMetrics{
				TotalReviews: 0,
			},
		}

		rate := calc.CalculateToolMisuseRate(metrics)
		assert.Equal(t, 0.0, rate)
	})
}

func TestKPICalculator_ResponseSuccessRate(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	t.Run("with executions", func(t *testing.T) {
		metrics := Metrics{
			ExecutionMetrics: ExecutionMetrics{
				TotalExecutions: 10,
				SuccessRate:     0.9,
			},
		}

		rate := calc.CalculateResponseSuccessRate(metrics)
		assert.InDelta(t, 0.9, rate, 0.01)
	})

	t.Run("no executions", func(t *testing.T) {
		metrics := Metrics{
			ExecutionMetrics: ExecutionMetrics{
				TotalExecutions: 0,
			},
		}

		rate := calc.CalculateResponseSuccessRate(metrics)
		assert.Equal(t, 0.0, rate)
	})
}

func TestKPICalculator_LatencyByPath(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	executions := []ExecutionEvent{
		{Path: "fast", DurationMs: 500},
		{Path: "fast", DurationMs: 600},
		{Path: "fast", DurationMs: 400},
		{Path: "deep", DurationMs: 2000},
		{Path: "deep", DurationMs: 2500},
	}

	fastPath, deepPath := calc.CalculateLatencyByPath(executions)

	assert.InDelta(t, 500.0, fastPath, 0.1)
	assert.InDelta(t, 2250.0, deepPath, 0.1)
}

func TestKPICalculator_LatencyByPath_Empty(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	executions := []ExecutionEvent{}

	fastPath, deepPath := calc.CalculateLatencyByPath(executions)

	assert.Equal(t, 0.0, fastPath)
	assert.Equal(t, 0.0, deepPath)
}

func TestKPICalculator_LatencyByPath_NoDeepPath(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	executions := []ExecutionEvent{
		{Path: "fast", DurationMs: 500},
		{Path: "fast", DurationMs: 600},
	}

	fastPath, deepPath := calc.CalculateLatencyByPath(executions)

	assert.InDelta(t, 550.0, fastPath, 0.1)
	assert.Equal(t, 0.0, deepPath)
}

func TestKPICalculator_LatencyByPath_NoFastPath(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	executions := []ExecutionEvent{
		{Path: "deep", DurationMs: 2000},
		{Path: "deep", DurationMs: 2500},
	}

	fastPath, deepPath := calc.CalculateLatencyByPath(executions)

	assert.Equal(t, 0.0, fastPath)
	assert.InDelta(t, 2250.0, deepPath, 0.1)
}

func TestKPICalculator_AvgLatencyFastPath(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	metrics := Metrics{
		DecisionMetrics: DecisionMetrics{
			TotalDecisions: 10,
			FastPathCount:  7,
			DeepPathCount:  3,
		},
		ExecutionMetrics: ExecutionMetrics{
			AvgDurationMs: 1500,
		},
	}

	latency := calc.CalculateAvgLatencyFastPath(metrics)
	// Should be less than average due to fast path being faster
	assert.Less(t, latency, metrics.ExecutionMetrics.AvgDurationMs)
}

func TestKPICalculator_AvgLatencyDeepPath(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	metrics := Metrics{
		DecisionMetrics: DecisionMetrics{
			TotalDecisions: 10,
			FastPathCount:  3,
			DeepPathCount:  7,
		},
		ExecutionMetrics: ExecutionMetrics{
			AvgDurationMs: 1500,
		},
	}

	latency := calc.CalculateAvgLatencyDeepPath(metrics)
	// Should be greater than average due to deep path being slower
	assert.Greater(t, latency, metrics.ExecutionMetrics.AvgDurationMs)
}

func TestKPICalculator_CalculateKPIs_ZeroMetrics(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()

	metrics := Metrics{}

	kpis := calc.CalculateKPIs(metrics)

	assert.Equal(t, 0.0, kpis.RoutingAccuracy)
	assert.Equal(t, 0.0, kpis.FallbackRate)
	assert.Equal(t, 0.0, kpis.ReplanRate)
	assert.Equal(t, 0.0, kpis.ToolMisuseRate)
	assert.Equal(t, 0.0, kpis.ResponseSuccessRate)
	assert.Equal(t, 0.0, kpis.AvgLatencyFastPath)
	assert.Equal(t, 0.0, kpis.AvgLatencyDeepPath)
}

func TestKPICalculator_NewKPICalculator(t *testing.T) {
	t.Parallel()

	calc := NewKPICalculator()
	require.NotNil(t, calc)
}
