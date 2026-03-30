package pipeline

import (
	"context"
	"fmt"

	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/core/plan"
	"github.com/fulvian/aria/internal/aria/memory"
	"github.com/fulvian/aria/internal/aria/routing"
)

// OrchestratorPipeline coordinates phases A-F of the orchestrator.
// This implements the core pipeline defined in WS-A.
type OrchestratorPipeline struct {
	DecisionEngine  decision.DecisionEngine
	Planner         plan.Planner
	Executor        plan.Executor
	Reviewer        plan.Reviewer
	MemoryService   memory.MemoryService
	QueryClassifier routing.QueryClassifier
}

// NewOrchestratorPipeline creates a new OrchestratorPipeline.
func NewOrchestratorPipeline(
	decisionEngine decision.DecisionEngine,
	planner plan.Planner,
	executor plan.Executor,
	reviewer plan.Reviewer,
	memoryService memory.MemoryService,
	classifier routing.QueryClassifier,
) *OrchestratorPipeline {
	return &OrchestratorPipeline{
		DecisionEngine:  decisionEngine,
		Planner:         planner,
		Executor:        executor,
		Reviewer:        reviewer,
		MemoryService:   memoryService,
		QueryClassifier: classifier,
	}
}

// phaseA_IntakeAndContextRecovery implements Phase A: Intake + Context Recovery.
// Loads context from memory service for the session.
func (p *OrchestratorPipeline) phaseA_IntakeAndContextRecovery(ctx context.Context, query core.Query) (*memory.Context, []memory.Episode, error) {
	var workingContext *memory.Context
	var similarEpisodes []memory.Episode

	if p.MemoryService != nil && query.SessionID != "" {
		// Load working memory context
		if ctx_, err := p.MemoryService.GetContext(ctx, query.SessionID); err == nil {
			workingContext = &ctx_
		}

		// Search for similar episodes using memory service
		if episodes, err := p.MemoryService.GetSimilarEpisodes(ctx, memory.Situation{
			Description: query.Text,
			Context:     query.Metadata,
		}); err == nil {
			similarEpisodes = episodes
		}
	}

	return workingContext, similarEpisodes, nil
}

// phaseB_Classification implements Phase B: Classification.
// Uses the real QueryClassifier to determine query characteristics.
func (p *OrchestratorPipeline) phaseB_Classification(ctx context.Context, query routing.Query) (routing.Classification, error) {
	return p.QueryClassifier.Classify(ctx, query)
}

// phaseC_DecisionEngine implements Phase C: Decision Engine.
// Uses the real DecisionEngine to determine execution path.
func (p *OrchestratorPipeline) phaseC_DecisionEngine(ctx context.Context, query routing.Query, class routing.Classification) (decision.ExecutionDecision, error) {
	return p.DecisionEngine.Decide(ctx, query, class)
}

// Run implements the main pipeline entry point (Fast Path).
// This replaces the skeleton implementation with real components:
// - Phase A: Intake + Context Recovery via MemoryService
// - Phase B: Classification via QueryClassifier
// - Phase C: Decision Engine via DecisionEngine
// Returns real responses based on actual routing decisions, not placeholder text.
func (p *OrchestratorPipeline) Run(ctx context.Context, query core.Query) (core.Response, error) {
	// Phase A: Intake + Context Recovery
	workingContext, similarEpisodes, err := p.phaseA_IntakeAndContextRecovery(ctx, query)
	if err != nil {
		// Log but continue - context recovery failure shouldn't block the query
		workingContext = nil
		similarEpisodes = nil
	}

	// Build routing query from core query
	routingQuery := routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
		Metadata:  query.Metadata,
	}

	// Phase B: Classification using real classifier
	class, err := p.phaseB_Classification(ctx, routingQuery)
	if err != nil {
		return core.Response{}, fmt.Errorf("classification failed: %w", err)
	}

	// Phase C: Decision Engine using real decision engine
	decision_, err := p.phaseC_DecisionEngine(ctx, routingQuery, class)
	if err != nil {
		return core.Response{}, fmt.Errorf("decision engine failed: %w", err)
	}

	// Execute based on decision path
	if decision_.Path == decision.PathFast {
		// Fast Path: Return response with real classification and decision info
		// The response Text should indicate fast path execution with real metrics
		responseText := fmt.Sprintf("Fast path (classification: %s %s, confidence: %.2f, complexity: %d, risk: %d)",
			class.Intent, class.Domain, class.Confidence, decision_.Complexity.Value, decision_.Risk.Value)

		// Add context info to response if available
		if workingContext != nil && workingContext.SessionID != "" {
			responseText += " [context loaded]"
		}
		if len(similarEpisodes) > 0 {
			responseText += fmt.Sprintf(" [%d similar episodes]", len(similarEpisodes))
		}

		return core.Response{
			Text:       responseText,
			Confidence: class.Confidence,
		}, nil
	}

	// Deep Path needed - delegate to RunDeepPath
	return p.RunDeepPath(ctx, query, class, decision_)
}

// RunDeepPath implements the deep path: Planner -> Executor -> Reviewer.
// This is called when the DecisionEngine determines Deep Path is needed.
func (p *OrchestratorPipeline) RunDeepPath(ctx context.Context, query core.Query, class routing.Classification, decision_ decision.ExecutionDecision) (core.Response, error) {
	routingQuery := routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
		Metadata:  query.Metadata,
	}

	// Phase D: Planner - Create plan using sequential thinking
	plan_, err := p.Planner.CreatePlanWithThinking(ctx, routingQuery, class, decision_)
	if err != nil {
		return core.Response{}, fmt.Errorf("planning failed: %w", err)
	}

	// Phase E: Executor - Execute the plan
	result, err := p.Executor.Execute(ctx, plan_)
	if err != nil {
		return core.Response{}, fmt.Errorf("execution failed: %w", err)
	}

	// Phase F: Reviewer - Verify the result
	review, err := p.Reviewer.Review(ctx, plan_, result)
	if err != nil {
		return core.Response{}, fmt.Errorf("review failed: %w", err)
	}

	// Check if replan is needed based on review verdict
	shouldReplan, replanReason := p.Reviewer.ShouldReplan(ctx, *review)
	if shouldReplan && replanReason.Strategy == "REPLAN_FULL" {
		// Retry with new plan
		newPlan, err := p.Planner.CreatePlanWithThinking(ctx, routingQuery, class, decision_)
		if err == nil {
			plan_ = newPlan
			result, err = p.Executor.Execute(ctx, plan_)
			if err == nil {
				review, _ = p.Reviewer.Review(ctx, plan_, result)
			}
		}
	}

	// Build response from review result
	responseText := fmt.Sprintf("Deep path completed. Verdict: %s (score: %.2f). %s",
		review.Verdict, review.Score, review.Feedback)

	// Include metadata about execution in the response
	if result.CompletedSteps != nil && len(result.CompletedSteps) > 0 {
		responseText += fmt.Sprintf(" Steps completed: %v", result.CompletedSteps)
	}
	if result.FailedStep != nil {
		responseText += fmt.Sprintf(" Failed at step: %d", *result.FailedStep)
	}

	return core.Response{
		Text:       responseText,
		Confidence: review.Score,
	}, nil
}
