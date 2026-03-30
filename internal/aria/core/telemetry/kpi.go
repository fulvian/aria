// Package telemetry provides telemetry, metrics, and feedback loop capabilities
// for the orchestrator enhancement (O5).
package telemetry

// KPI Calculator per orchestrator (dal piano)
type KPI struct {
	RoutingAccuracy     float64 // % di routing corretti
	FallbackRate        float64 // % di task che hanno triggerato fallback
	ReplanRate          float64 // % di task che hanno richiesto replan
	ToolMisuseRate      float64 // % di tool usati inappropriatamente
	ResponseSuccessRate float64 // % di risposte di successo
	AvgLatencyFastPath  float64 // ms medi per fast path
	AvgLatencyDeepPath  float64 // ms medi per deep path
}

// KPICalculator calculates KPIs from aggregated metrics.
type KPICalculator struct{}

// NewKPICalculator creates a new KPICalculator.
func NewKPICalculator() *KPICalculator {
	return &KPICalculator{}
}

// CalculateKPIs computes all KPIs from the given metrics.
func (c *KPICalculator) CalculateKPIs(m Metrics) KPI {
	return KPI{
		RoutingAccuracy:     c.CalculateRoutingAccuracy(m),
		FallbackRate:        c.CalculateFallbackRate(m),
		ReplanRate:          c.CalculateReplanRate(m),
		ToolMisuseRate:      c.CalculateToolMisuseRate(m),
		ResponseSuccessRate: c.CalculateResponseSuccessRate(m),
		AvgLatencyFastPath:  c.CalculateAvgLatencyFastPath(m),
		AvgLatencyDeepPath:  c.CalculateAvgLatencyDeepPath(m),
	}
}

// CalculateRoutingAccuracy calculates routing accuracy as the percentage of
// correct routing decisions. A routing decision is considered correct when:
// - The query was routed to the appropriate path (fast/deep)
// based on complexity and risk analysis
// For simplicity, we use approved rate as a proxy for routing accuracy.
func (c *KPICalculator) CalculateRoutingAccuracy(m Metrics) float64 {
	if m.ReviewMetrics.TotalReviews == 0 {
		return 0.0
	}
	// Use approved rate as proxy for routing accuracy
	// In a real implementation, this would be based on user feedback
	// or comparison against expected routing decisions
	return m.ReviewMetrics.ApprovedRate
}

// CalculateFallbackRate calculates the percentage of executions that used fallback.
func (c *KPICalculator) CalculateFallbackRate(m Metrics) float64 {
	if m.ExecutionMetrics.TotalExecutions == 0 {
		return 0.0
	}
	return m.ExecutionMetrics.FallbackRate
}

// CalculateReplanRate calculates the percentage of tasks that required replan.
func (c *KPICalculator) CalculateReplanRate(m Metrics) float64 {
	if m.ReviewMetrics.TotalReviews == 0 {
		return 0.0
	}
	return m.ReviewMetrics.ReplanRate
}

// CalculateToolMisuseRate calculates the percentage of tool usages that were inappropriate.
// This is estimated based on the revision rate - when revisions are needed,
// it often indicates tool misuse or incorrect tool selection.
func (c *KPICalculator) CalculateToolMisuseRate(m Metrics) float64 {
	if m.ReviewMetrics.TotalReviews == 0 {
		return 0.0
	}
	// Use revision rate as a proxy for tool misuse
	// In reality, this would need explicit tracking
	return m.ReviewMetrics.RevisionRate
}

// CalculateResponseSuccessRate calculates the overall success rate of responses.
func (c *KPICalculator) CalculateResponseSuccessRate(m Metrics) float64 {
	if m.ExecutionMetrics.TotalExecutions == 0 {
		return 0.0
	}
	return m.ExecutionMetrics.SuccessRate
}

// CalculateAvgLatencyFastPath calculates average latency for fast path executions.
func (c *KPICalculator) CalculateAvgLatencyFastPath(m Metrics) float64 {
	// Note: Individual execution events don't store path information
	// For a proper implementation, we would need to correlate decisions
	// with executions. For now, we use a simple heuristic based on
	// decision path breakdown.
	if m.DecisionMetrics.TotalDecisions == 0 {
		return 0.0
	}

	// This is a simplified calculation. In production,
	// executions should be tagged with their path.
	fastRatio := float64(m.DecisionMetrics.FastPathCount) / float64(m.DecisionMetrics.TotalDecisions)
	if fastRatio == 0 {
		return 0.0
	}

	// Estimate based on overall average, adjusted for fast path being typically faster
	// Fast path is typically 2-3x faster than deep path
	overallAvg := m.ExecutionMetrics.AvgDurationMs
	if overallAvg == 0 {
		return 0.0
	}

	// Approximate fast path latency
	return overallAvg * (1.0 - (fastRatio * 0.3))
}

// CalculateAvgLatencyDeepPath calculates average latency for deep path executions.
func (c *KPICalculator) CalculateAvgLatencyDeepPath(m Metrics) float64 {
	if m.DecisionMetrics.TotalDecisions == 0 {
		return 0.0
	}

	deepRatio := float64(m.DecisionMetrics.DeepPathCount) / float64(m.DecisionMetrics.TotalDecisions)
	if deepRatio == 0 {
		return 0.0
	}

	overallAvg := m.ExecutionMetrics.AvgDurationMs
	if overallAvg == 0 {
		return 0.0
	}

	// Approximate deep path latency
	return overallAvg * (1.0 + (deepRatio * 0.5))
}

// CalculateLatencyByPath provides a more accurate latency calculation
// when executions are tagged with path information.
func (c *KPICalculator) CalculateLatencyByPath(executions []ExecutionEvent) (fastPath, deepPath float64) {
	var fastCount, deepCount int
	var fastTotal, deepTotal int64

	for _, e := range executions {
		switch e.Path {
		case "fast":
			fastCount++
			fastTotal += e.DurationMs
		case "deep":
			deepCount++
			deepTotal += e.DurationMs
		}
	}

	if fastCount > 0 {
		fastPath = float64(fastTotal) / float64(fastCount)
	}
	if deepCount > 0 {
		deepPath = float64(deepTotal) / float64(deepCount)
	}

	return fastPath, deepPath
}

// Ensure KPICalculator implements the expected interface at compile time.
var _ = KPICalculator{}
