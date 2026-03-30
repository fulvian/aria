// Package telemetry provides telemetry, metrics, and feedback loop capabilities
// for the orchestrator enhancement (O5).
package telemetry

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// TelemetryService raccoglie e aggrega metriche dell'orchestrator.
type TelemetryService interface {
	// RecordDecision registra una decisione del decision engine
	RecordDecision(ctx context.Context, event DecisionEvent)

	// RecordExecution registra un'esecuzione
	RecordExecution(ctx context.Context, event ExecutionEvent)

	// RecordReview registra un risultato della review
	RecordReview(ctx context.Context, event ReviewEvent)

	// GetMetrics restituisce metriche aggregate
	GetMetrics(ctx context.Context) (Metrics, error)

	// Reset pulisce tutte le metriche
	Reset(ctx context.Context) error
}

// DecisionEvent evento di decisione.
type DecisionEvent struct {
	Timestamp     time.Time
	QueryID       string
	Complexity    int
	RiskScore     int
	Path          string // "fast" or "deep"
	UseDeepPath   bool
	TriggerReason string
}

// ExecutionEvent evento di esecuzione.
type ExecutionEvent struct {
	Timestamp    time.Time
	QueryID      string
	PlanID       string
	Path         string
	Success      bool
	StepsTotal   int
	StepsFailed  int
	Handoffs     int
	DurationMs   int64
	TokensUsed   int
	FallbackUsed bool
}

// ReviewEvent evento di review.
type ReviewEvent struct {
	Timestamp       time.Time
	QueryID         string
	PlanID          string
	Score           float64
	Verdict         string // "APPROVED", "REVISION_NEEDED", "REPLAN_NEEDED"
	CriteriaResults []bool // one per criterion
	ReplanCount     int
}

// Metrics metriche aggregate.
type Metrics struct {
	DecisionMetrics  DecisionMetrics
	ExecutionMetrics ExecutionMetrics
	ReviewMetrics    ReviewMetrics
}

// DecisionMetrics metriche relative a decisioni.
type DecisionMetrics struct {
	TotalDecisions   int
	FastPathCount    int
	DeepPathCount    int
	AvgComplexity    float64
	AvgRiskScore     float64
	TriggerBreakdown map[string]int // reason -> count
}

// ExecutionMetrics metriche relative a esecuzioni.
type ExecutionMetrics struct {
	TotalExecutions int
	SuccessRate     float64
	AvgStepsPerPlan float64
	AvgDurationMs   float64
	AvgTokensUsed   float64
	FallbackRate    float64
	HandoffRate     float64
}

// ReviewMetrics metriche relative a review.
type ReviewMetrics struct {
	TotalReviews   int
	ApprovedRate   float64
	RevisionRate   float64
	ReplanRate     float64
	AvgScore       float64
	AvgReplanCount float64
}

// telemetryService implements TelemetryService using sync.Map for thread-safety.
type telemetryService struct {
	mu sync.RWMutex

	decisions  []DecisionEvent
	executions []ExecutionEvent
	reviews    []ReviewEvent
}

// NewTelemetryService creates a new TelemetryService instance.
func NewTelemetryService() TelemetryService {
	return &telemetryService{
		decisions:  make([]DecisionEvent, 0),
		executions: make([]ExecutionEvent, 0),
		reviews:    make([]ReviewEvent, 0),
	}
}

// RecordDecision registra una decisione del decision engine.
func (s *telemetryService) RecordDecision(ctx context.Context, event DecisionEvent) {
	if event.Timestamp.IsZero() {
		event.Timestamp = time.Now()
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	s.decisions = append(s.decisions, event)
}

// RecordExecution registra un'esecuzione.
func (s *telemetryService) RecordExecution(ctx context.Context, event ExecutionEvent) {
	if event.Timestamp.IsZero() {
		event.Timestamp = time.Now()
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	s.executions = append(s.executions, event)
}

// RecordReview registra un risultato della review.
func (s *telemetryService) RecordReview(ctx context.Context, event ReviewEvent) {
	if event.Timestamp.IsZero() {
		event.Timestamp = time.Now()
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	s.reviews = append(s.reviews, event)
}

// GetMetrics restituisce metriche aggregate.
func (s *telemetryService) GetMetrics(ctx context.Context) (Metrics, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	decisionMetrics := s.aggregateDecisionMetrics()
	executionMetrics := s.aggregateExecutionMetrics()
	reviewMetrics := s.aggregateReviewMetrics()

	return Metrics{
		DecisionMetrics:  decisionMetrics,
		ExecutionMetrics: executionMetrics,
		ReviewMetrics:    reviewMetrics,
	}, nil
}

// aggregateDecisionMetrics aggregates decision metrics.
func (s *telemetryService) aggregateDecisionMetrics() DecisionMetrics {
	n := len(s.decisions)
	if n == 0 {
		return DecisionMetrics{
			TriggerBreakdown: make(map[string]int),
		}
	}

	var totalComplexity, totalRiskScore int
	fastPathCount := 0
	deepPathCount := 0
	triggerBreakdown := make(map[string]int)

	for _, d := range s.decisions {
		totalComplexity += d.Complexity
		totalRiskScore += d.RiskScore

		if d.Path == "fast" {
			fastPathCount++
		} else {
			deepPathCount++
		}

		if d.TriggerReason != "" {
			triggerBreakdown[d.TriggerReason]++
		}
	}

	return DecisionMetrics{
		TotalDecisions:   n,
		FastPathCount:    fastPathCount,
		DeepPathCount:    deepPathCount,
		AvgComplexity:    float64(totalComplexity) / float64(n),
		AvgRiskScore:     float64(totalRiskScore) / float64(n),
		TriggerBreakdown: triggerBreakdown,
	}
}

// aggregateExecutionMetrics aggregates execution metrics.
func (s *telemetryService) aggregateExecutionMetrics() ExecutionMetrics {
	n := len(s.executions)
	if n == 0 {
		return ExecutionMetrics{}
	}

	var successCount, totalSteps, totalFailed, totalHandoffs, totalTokens int64
	var totalDurationMs int64
	fallbackCount := 0

	for _, e := range s.executions {
		if e.Success {
			successCount++
		}
		totalSteps += int64(e.StepsTotal)
		totalFailed += int64(e.StepsFailed)
		totalHandoffs += int64(e.Handoffs)
		totalTokens += int64(e.TokensUsed)
		totalDurationMs += e.DurationMs
		if e.FallbackUsed {
			fallbackCount++
		}
	}

	return ExecutionMetrics{
		TotalExecutions: n,
		SuccessRate:     float64(successCount) / float64(n),
		AvgStepsPerPlan: float64(totalSteps) / float64(n),
		AvgDurationMs:   float64(totalDurationMs) / float64(n),
		AvgTokensUsed:   float64(totalTokens) / float64(n),
		FallbackRate:    float64(fallbackCount) / float64(n),
		HandoffRate:     float64(totalHandoffs) / float64(n),
	}
}

// aggregateReviewMetrics aggregates review metrics.
func (s *telemetryService) aggregateReviewMetrics() ReviewMetrics {
	n := len(s.reviews)
	if n == 0 {
		return ReviewMetrics{}
	}

	var approvedCount, revisionCount, replanCount int
	var totalScore float64
	var totalReplanCount int

	for _, r := range s.reviews {
		totalScore += r.Score
		totalReplanCount += r.ReplanCount

		switch r.Verdict {
		case "APPROVED":
			approvedCount++
		case "REVISION_NEEDED":
			revisionCount++
		case "REPLAN_NEEDED":
			replanCount++
		}
	}

	return ReviewMetrics{
		TotalReviews:   n,
		ApprovedRate:   float64(approvedCount) / float64(n),
		RevisionRate:   float64(revisionCount) / float64(n),
		ReplanRate:     float64(replanCount) / float64(n),
		AvgScore:       totalScore / float64(n),
		AvgReplanCount: float64(totalReplanCount) / float64(n),
	}
}

// Reset pulisce tutte le metriche.
func (s *telemetryService) Reset(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.decisions = make([]DecisionEvent, 0)
	s.executions = make([]ExecutionEvent, 0)
	s.reviews = make([]ReviewEvent, 0)

	return nil
}

// Ensure telemetryService implements TelemetryService at compile time.
var _ TelemetryService = (*telemetryService)(nil)

// MetricsValidator provides validation helpers for testing.
type MetricsValidator struct{}

// Validate runs validation checks on metrics.
func (v *MetricsValidator) Validate(m Metrics) error {
	if m.DecisionMetrics.TotalDecisions < 0 {
		return fmt.Errorf("invalid DecisionMetrics.TotalDecisions: %d", m.DecisionMetrics.TotalDecisions)
	}
	if m.DecisionMetrics.FastPathCount < 0 || m.DecisionMetrics.DeepPathCount < 0 {
		return fmt.Errorf("invalid path counts")
	}
	if m.DecisionMetrics.TotalDecisions != m.DecisionMetrics.FastPathCount+m.DecisionMetrics.DeepPathCount {
		return fmt.Errorf("total decisions does not match path counts sum")
	}
	if m.ExecutionMetrics.TotalExecutions < 0 {
		return fmt.Errorf("invalid ExecutionMetrics.TotalExecutions")
	}
	if m.ReviewMetrics.TotalReviews < 0 {
		return fmt.Errorf("invalid ReviewMetrics.TotalReviews")
	}
	if m.ReviewMetrics.ApprovedRate < 0 || m.ReviewMetrics.ApprovedRate > 1 {
		return fmt.Errorf("invalid ReviewMetrics.ApprovedRate: %f", m.ReviewMetrics.ApprovedRate)
	}
	return nil
}

// NewMetricsValidator creates a new MetricsValidator.
func NewMetricsValidator() *MetricsValidator {
	return &MetricsValidator{}
}
