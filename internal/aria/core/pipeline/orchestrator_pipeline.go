package pipeline

import (
	"context"
	"fmt"

	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/core/plan"
	"github.com/fulvian/aria/internal/aria/routing"
)

// OrchestratorPipeline coordinates phases A-F of the orchestrator.
type OrchestratorPipeline struct {
	DecisionEngine decision.DecisionEngine
	Planner        plan.Planner
	Executor       plan.Executor
	Reviewer       plan.Reviewer
}

// NewOrchestratorPipeline creates a new OrchestratorPipeline.
func NewOrchestratorPipeline(
	decisionEngine decision.DecisionEngine,
	planner plan.Planner,
	executor plan.Executor,
	reviewer plan.Reviewer,
) *OrchestratorPipeline {
	return &OrchestratorPipeline{
		DecisionEngine: decisionEngine,
		Planner:        planner,
		Executor:       executor,
		Reviewer:       reviewer,
	}
}

// Run executes the complete pipeline for a query.
func (p *OrchestratorPipeline) Run(ctx context.Context, query core.Query) (core.Response, error) {
	// Phase A: Intake + Context Recovery (existing memory integration)
	// TODO: Implement with memory service

	// Phase B: Classification (via existing classifier)
	// For now, use a basic classification
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexityMedium,
		Confidence: 0.5,
	}

	// Phase C: Decision Engine
	// For now, return a fast path decision
	decision_ := decision.ExecutionDecision{
		Path:        decision.PathFast,
		Explanation: "Pipeline skeleton - Fast Path",
	}

	// Use class and decision_ to avoid compiler warnings
	_ = class
	_ = decision_

	// Fast Path: return simple response
	return core.Response{
		Text:       fmt.Sprintf("Pipeline skeleton - Fast Path (query: %s)", query.Text),
		Confidence: 0.5,
	}, nil
}

// RunDeepPath executes the deep path: Planner -> Executor -> Reviewer.
func (p *OrchestratorPipeline) RunDeepPath(ctx context.Context, query core.Query, class routing.Classification, decision_ decision.ExecutionDecision) (core.Response, error) {
	// Phase D: Planner
	plan_, err := p.Planner.CreatePlanWithThinking(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
		Metadata:  query.Metadata,
	}, class, decision_)
	if err != nil {
		return core.Response{}, fmt.Errorf("planning failed: %w", err)
	}

	// Phase E: Executor
	result, err := p.Executor.Execute(ctx, plan_)
	if err != nil {
		return core.Response{}, fmt.Errorf("execution failed: %w", err)
	}

	// Phase F: Reviewer
	review, err := p.Reviewer.Review(ctx, plan_, result)
	if err != nil {
		return core.Response{}, fmt.Errorf("review failed: %w", err)
	}

	// Check if replan is needed
	shouldReplan, replanReason := p.Reviewer.ShouldReplan(ctx, *review)
	if shouldReplan && replanReason.Strategy == "REPLAN_FULL" {
		// Retry with new plan
		plan_, err = p.Planner.CreatePlanWithThinking(ctx, routing.Query{
			Text:      query.Text,
			SessionID: query.SessionID,
			UserID:    query.UserID,
			Metadata:  query.Metadata,
		}, class, decision_)
		if err == nil {
			result, err = p.Executor.Execute(ctx, plan_)
			if err == nil {
				review, _ = p.Reviewer.Review(ctx, plan_, result)
			}
		}
	}

	// Build response from review result
	responseText := fmt.Sprintf("Deep path completed. Verdict: %s (score: %.2f). %s",
		review.Verdict, review.Score, review.Feedback)

	return core.Response{
		Text:       responseText,
		Confidence: review.Score,
	}, nil
}
