// Package telemetry provides telemetry, metrics, and feedback loop capabilities
// for the orchestrator enhancement (O5).
package telemetry

import (
	"context"
	"fmt"
)

// FeedbackLoop integra telemetria con memoria per apprendimento continuo.
type FeedbackLoop interface {
	// RecordOutcome registra un outcome per il learning
	RecordOutcome(ctx context.Context, outcome Outcome) error

	// GetRoutingInsight restituisce insight per migliorare routing
	GetRoutingInsight(ctx context.Context) (RoutingInsight, error)
}

// Outcome rappresenta un outcome di una query per il learning.
type Outcome struct {
	QueryID      string
	Decision     DecisionEvent
	Execution    ExecutionEvent
	Review       ReviewEvent
	UserFeedback string // eventuale feedback utente
}

// RoutingInsight insight per migliorare routing decisions.
type RoutingInsight struct {
	RecommendedComplexityThreshold int
	RecommendedRiskThreshold       int
	HighValueTriggers              []string
	LowValueTriggers               []string
}

// feedbackLoop implements FeedbackLoop for continuous learning.
type feedbackLoop struct {
	telemetry TelemetryService
}

// NewFeedbackLoop creates a new FeedbackLoop instance.
func NewFeedbackLoop(telemetry TelemetryService) FeedbackLoop {
	return &feedbackLoop{
		telemetry: telemetry,
	}
}

// RecordOutcome registra un outcome per il learning.
func (f *feedbackLoop) RecordOutcome(ctx context.Context, outcome Outcome) error {
	// Validate outcome has required fields
	if outcome.QueryID == "" {
		return fmt.Errorf("outcome QueryID is required")
	}

	// Record all events from the outcome
	f.telemetry.RecordDecision(ctx, outcome.Decision)
	f.telemetry.RecordExecution(ctx, outcome.Execution)
	f.telemetry.RecordReview(ctx, outcome.Review)

	return nil
}

// GetRoutingInsight restituisce insight per migliorare routing decisions
// based on accumulated metrics.
func (f *feedbackLoop) GetRoutingInsight(ctx context.Context) (RoutingInsight, error) {
	metrics, err := f.telemetry.GetMetrics(ctx)
	if err != nil {
		return RoutingInsight{}, fmt.Errorf("failed to get metrics: %w", err)
	}

	// Analyze patterns from accumulated metrics
	insight := RoutingInsight{
		HighValueTriggers: make([]string, 0),
		LowValueTriggers:  make([]string, 0),
	}

	// Calculate recommended thresholds based on successful decisions
	// A decision is considered successful if the review verdict is APPROVED
	if metrics.ReviewMetrics.TotalReviews > 0 {
		// Analyze complexity thresholds
		// If high complexity queries have low approval rates, increase threshold
		approvedRate := metrics.ReviewMetrics.ApprovedRate
		if approvedRate < 0.5 {
			// Low approval rate suggests we may be routing too many to deep path
			// or the deep path isn't working well
			insight.RecommendedComplexityThreshold = 65
			insight.RecommendedRiskThreshold = 50
		} else if approvedRate > 0.8 {
			// High approval rate suggests current thresholds are working well
			insight.RecommendedComplexityThreshold = 55
			insight.RecommendedRiskThreshold = 40
		} else {
			// Moderate approval rate
			insight.RecommendedComplexityThreshold = 60
			insight.RecommendedRiskThreshold = 45
		}
	} else {
		// Default values if no data
		insight.RecommendedComplexityThreshold = 55
		insight.RecommendedRiskThreshold = 40
	}

	// Analyze trigger breakdown to identify high/low value triggers
	if metrics.DecisionMetrics.TriggerBreakdown != nil {
		for trigger, count := range metrics.DecisionMetrics.TriggerBreakdown {
			// Consider triggers with high counts as high value
			if count >= 3 {
				insight.HighValueTriggers = append(insight.HighValueTriggers, trigger)
			} else if count == 1 {
				insight.LowValueTriggers = append(insight.LowValueTriggers, trigger)
			}
		}
	}

	// Analyze fallback patterns
	if metrics.ExecutionMetrics.FallbackRate > 0.2 {
		// High fallback rate suggests more careful routing is needed
		insight.HighValueTriggers = append(insight.HighValueTriggers, "high_fallback_risk")
	}

	// Analyze replan patterns
	if metrics.ReviewMetrics.ReplanRate > 0.15 {
		// High replan rate suggests deep path may need improvement
		insight.HighValueTriggers = append(insight.HighValueTriggers, "high_replan_risk")
	}

	return insight, nil
}

// Ensure feedbackLoop implements FeedbackLoop at compile time.
var _ FeedbackLoop = (*feedbackLoop)(nil)

// ValidateOutcome validates an outcome has required fields.
func ValidateOutcome(o Outcome) error {
	if o.QueryID == "" {
		return fmt.Errorf("QueryID is required")
	}
	return nil
}

// InsightAnalyzer provides methods to analyze routing insights.
type InsightAnalyzer struct{}

// AnalyzePathDistribution analyzes the distribution of fast vs deep path decisions.
func (a *InsightAnalyzer) AnalyzePathDistribution(decisions []DecisionEvent) map[string]int {
	result := map[string]int{
		"fast": 0,
		"deep": 0,
	}

	for _, d := range decisions {
		result[d.Path]++
	}

	return result
}

// AnalyzeSuccessByPath analyzes success rates grouped by path.
func (a *InsightAnalyzer) AnalyzeSuccessByPath(
	decisions []DecisionEvent,
	executions []ExecutionEvent,
	reviews []ReviewEvent,
) map[string]float64 {
	result := map[string]float64{
		"fast": 0.0,
		"deep": 0.0,
	}

	pathSuccess := map[string]int{"fast": 0, "deep": 0}
	pathTotal := map[string]int{"fast": 0, "deep": 0}

	// Build queryID to decision map
	queryToPath := make(map[string]string)
	for _, d := range decisions {
		queryToPath[d.QueryID] = d.Path
	}

	// Build queryID to review verdict map
	queryToVerdict := make(map[string]string)
	for _, r := range reviews {
		queryToVerdict[r.QueryID] = r.Verdict
	}

	// Count successes by path
	for _, d := range decisions {
		path := d.Path
		pathTotal[path]++

		verdict, ok := queryToVerdict[d.QueryID]
		if ok && verdict == "APPROVED" {
			pathSuccess[path]++
		}
	}

	// Calculate rates
	for path, total := range pathTotal {
		if total > 0 {
			result[path] = float64(pathSuccess[path]) / float64(total)
		}
	}

	return result
}

// NewInsightAnalyzer creates a new InsightAnalyzer.
func NewInsightAnalyzer() *InsightAnalyzer {
	return &InsightAnalyzer{}
}
