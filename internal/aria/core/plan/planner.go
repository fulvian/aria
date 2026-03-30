package plan

import (
	"context"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/routing"
)

// Planner builds an execution plan for a query.
type Planner interface {
	// CreatePlan generates a plan for the query (fast path).
	CreatePlan(ctx context.Context, query routing.Query, class routing.Classification, decision_ decision.ExecutionDecision) (*Plan, error)

	// CreatePlanWithThinking generates a plan using sequential-thinking (deep path).
	CreatePlanWithThinking(ctx context.Context, query routing.Query, class routing.Classification, decision_ decision.ExecutionDecision) (*Plan, error)
}

// defaultPlanner is the base implementation of Planner.
type defaultPlanner struct {
	sequentialThinking *SequentialThinkingCaller
}

// NewPlanner creates a new defaultPlanner.
func NewPlanner() *defaultPlanner {
	return &defaultPlanner{}
}

// NewPlannerWithThinking creates a planner with sequential-thinking enabled.
func NewPlannerWithThinking(caller *SequentialThinkingCaller) *defaultPlanner {
	return &defaultPlanner{
		sequentialThinking: caller,
	}
}

// CreatePlan generates a plan using the fast path (no sequential-thinking).
func (p *defaultPlanner) CreatePlan(ctx context.Context, query routing.Query, class routing.Classification, decision_ decision.ExecutionDecision) (*Plan, error) {
	planID := fmt.Sprintf("plan-%d", time.Now().UnixNano())
	objective := extractObjective(query.Text)

	steps := p.buildSteps(query, class, decision_)
	hypotheses := p.buildHypotheses(query, class)
	risks := p.buildRisks(query, class)
	fallbacks := p.buildFallbacks()
	doneCriteria := "response delivered to user"

	return &Plan{
		ID:           planID,
		Query:        query.Text,
		Objective:    objective,
		Steps:        steps,
		Hypotheses:   hypotheses,
		Risks:        risks,
		Fallbacks:    fallbacks,
		DoneCriteria: doneCriteria,
		CreatedAt:    time.Now(),
		Metadata:     map[string]any{},
	}, nil
}

// CreatePlanWithThinking generates a plan using the deep path (with sequential-thinking).
func (p *defaultPlanner) CreatePlanWithThinking(ctx context.Context, query routing.Query, class routing.Classification, decision_ decision.ExecutionDecision) (*Plan, error) {
	// Se sequential-thinking è disponibile, usalo
	if p.sequentialThinking != nil {
		result, err := p.sequentialThinking.Deliberate(ctx, query.Text,
			decision_.Complexity.Value, decision_.Risk.Value)
		if err != nil {
			// Fallback to CreatePlan if sequential-thinking fails
			return p.CreatePlan(ctx, query, class, decision_)
		}

		// Converti DeliberationResult a Plan
		return deliberationResultToPlan(result, query.Text, decision_), nil
	}

	// Altrimenti usa il deep path locale (metodo esistente)
	planID := fmt.Sprintf("plan-deep-%d", time.Now().UnixNano())
	objective := extractObjective(query.Text)

	// Deep path creates more detailed steps
	steps := p.buildDetailedSteps(query, class, decision_)
	hypotheses := p.buildDetailedHypotheses(query, class)
	risks := p.buildDetailedRisks(query, class)
	fallbacks := p.buildDetailedFallbacks()
	doneCriteria := "all acceptance criteria met with score >= 0.75"

	return &Plan{
		ID:           planID,
		Query:        query.Text,
		Objective:    objective,
		Steps:        steps,
		Hypotheses:   hypotheses,
		Risks:        risks,
		Fallbacks:    fallbacks,
		DoneCriteria: doneCriteria,
		CreatedAt:    time.Now(),
		Metadata: map[string]any{
			"path":          "deep",
			"complexity":    decision_.Complexity.Value,
			"risk":          decision_.Risk.Value,
			"used_thinking": true,
		},
	}, nil
}

// deliberationResultToPlan converts a DeliberationResult to a Plan.
func deliberationResultToPlan(result *DeliberationResult, queryText string, decision_ decision.ExecutionDecision) *Plan {
	planID := fmt.Sprintf("plan-deep-%d", time.Now().UnixNano())

	// Convert deliberation steps to PlanSteps
	steps := make([]PlanStep, len(result.Steps))
	for i, step := range result.Steps {
		steps[i] = PlanStep{
			Index:       i,
			Action:      "deliberated",
			Target:      "sequential-thinking",
			Inputs:      map[string]any{"thought": step},
			ExpectedOut: map[string]any{"completed": true},
			Constraints: []string{},
			Timeout:     30 * time.Second,
		}
	}

	// Convert deliberation hypotheses
	hypotheses := make([]Hypothesis, len(result.Hypotheses))
	for i, h := range result.Hypotheses {
		hypotheses[i] = Hypothesis{
			Description: h,
			Confidence:  0.8,
			Conditions:  []string{"reasoning valid"},
		}
	}

	// Convert deliberation risks
	risks := make([]PlanRisk, len(result.Risks))
	for i, r := range result.Risks {
		risks[i] = PlanRisk{
			Description: r,
			Probability: 0.2,
			Impact:      "medium",
			Mitigation:  "monitor and adjust",
		}
	}

	// Convert deliberation fallbacks
	fallbacks := make([]FallbackStrategy, len(result.Fallbacks))
	for i, f := range result.Fallbacks {
		fallbacks[i] = FallbackStrategy{
			Condition: "execution failed",
			Action:    f,
			Target:    "fallback",
		}
	}

	doneCriteria := result.DoneCriteria
	if doneCriteria == "" {
		doneCriteria = "all acceptance criteria met with score >= 0.75"
	}

	return &Plan{
		ID:           planID,
		Query:        queryText,
		Objective:    result.Objective,
		Steps:        steps,
		Hypotheses:   hypotheses,
		Risks:        risks,
		Fallbacks:    fallbacks,
		DoneCriteria: doneCriteria,
		CreatedAt:    time.Now(),
		Metadata: map[string]any{
			"path":                "deep",
			"complexity":          decision_.Complexity.Value,
			"risk":                decision_.Risk.Value,
			"used_thinking":       true,
			"sequential_thinking": true,
			"confidence":          result.Confidence,
		},
	}
}

// extractObjective extracts and normalizes the objective from the query.
func extractObjective(queryText string) string {
	// Simple normalization - remove trailing whitespace and newlines
	objective := queryText
	for len(objective) > 0 && (objective[len(objective)-1] == '\n' || objective[len(objective)-1] == ' ') {
		objective = objective[:len(objective)-1]
	}
	return objective
}

// buildSteps builds steps for the fast path.
func (p *defaultPlanner) buildSteps(query routing.Query, class routing.Classification, decision_ decision.ExecutionDecision) []PlanStep {
	// Simple query = single step
	if class.Complexity == routing.ComplexitySimple || decision_.Complexity.Value < 36 {
		return []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": query.Text},
				ExpectedOut: map[string]any{"response": "text"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
		}
	}

	// Medium complexity = two steps
	if decision_.Complexity.Value < 71 {
		return []PlanStep{
			{
				Index:       0,
				Action:      "analyze",
				Target:      "context",
				Inputs:      map[string]any{"query": query.Text},
				ExpectedOut: map[string]any{"analysis": "completed"},
				Constraints: []string{},
				Timeout:     15 * time.Second,
			},
			{
				Index:       1,
				Action:      "execute",
				Target:      "direct",
				Inputs:      map[string]any{"query": query.Text},
				ExpectedOut: map[string]any{"response": "text"},
				Constraints: []string{},
				Timeout:     30 * time.Second,
			},
		}
	}

	// Complex = multiple steps
	return p.buildDetailedSteps(query, class, decision_)
}

// buildDetailedSteps builds detailed steps for the deep path.
func (p *defaultPlanner) buildDetailedSteps(query routing.Query, class routing.Classification, decision_ decision.ExecutionDecision) []PlanStep {
	steps := []PlanStep{}

	// Step 1: Context analysis
	steps = append(steps, PlanStep{
		Index:       0,
		Action:      "analyze_context",
		Target:      "memory",
		Inputs:      map[string]any{"query": query.Text, "history": query.History},
		ExpectedOut: map[string]any{"context": "loaded"},
		Constraints: []string{"preserve context"},
		Timeout:     10 * time.Second,
	})

	// Step 2: Planning
	steps = append(steps, PlanStep{
		Index:       1,
		Action:      "plan",
		Target:      "orchestrator",
		Inputs:      map[string]any{"query": query.Text, "class": class},
		ExpectedOut: map[string]any{"plan": "created"},
		Constraints: []string{"efficient execution"},
		Timeout:     15 * time.Second,
	})

	// Step 3: Execution
	steps = append(steps, PlanStep{
		Index:       2,
		Action:      "execute",
		Target:      "agency",
		Inputs:      map[string]any{"query": query.Text, "plan": steps},
		ExpectedOut: map[string]any{"result": "completed"},
		Constraints: []string{"within budget"},
		Timeout:     60 * time.Second,
	})

	// Step 4: Verification
	steps = append(steps, PlanStep{
		Index:       3,
		Action:      "verify",
		Target:      "reviewer",
		Inputs:      map[string]any{"result": "output"},
		ExpectedOut: map[string]any{"verified": true},
		Constraints: []string{"acceptance criteria met"},
		Timeout:     10 * time.Second,
	})

	return steps
}

// buildHypotheses builds basic hypotheses for the fast path.
func (p *defaultPlanner) buildHypotheses(query routing.Query, class routing.Classification) []Hypothesis {
	return []Hypothesis{
		{
			Description: "The query can be answered directly",
			Confidence:  0.7,
			Conditions:  []string{"intent is question or task"},
		},
	}
}

// buildDetailedHypotheses builds detailed hypotheses for the deep path.
func (p *defaultPlanner) buildDetailedHypotheses(query routing.Query, class routing.Classification) []Hypothesis {
	return []Hypothesis{
		{
			Description: "The query requires multi-step reasoning",
			Confidence:  0.8,
			Conditions:  []string{"complexity >= 70", "intent requires planning"},
		},
		{
			Description: "Context from history is relevant",
			Confidence:  0.75,
			Conditions:  []string{"history exists", "related topics"},
		},
		{
			Description: "Standard execution path will succeed",
			Confidence:  0.85,
			Conditions:  []string{"no irreversible actions", "within budget"},
		},
	}
}

// buildRisks builds basic risks for the fast path.
func (p *defaultPlanner) buildRisks(query routing.Query, class routing.Classification) []PlanRisk {
	risks := []PlanRisk{}

	// Add risk based on query content
	risks = append(risks, PlanRisk{
		Description: "Standard execution risk",
		Probability: 0.1,
		Impact:      "low",
		Mitigation:  "Direct execution with error handling",
	})

	return risks
}

// buildDetailedRisks builds detailed risks for the deep path.
func (p *defaultPlanner) buildDetailedRisks(query routing.Query, class routing.Classification) []PlanRisk {
	risks := []PlanRisk{}

	// Context loading risk
	risks = append(risks, PlanRisk{
		Description: "Context recovery may fail",
		Probability: 0.15,
		Impact:      "medium",
		Mitigation:  "Use default context if memory unavailable",
	})

	// Planning risk
	risks = append(risks, PlanRisk{
		Description: "Planning may timeout",
		Probability: 0.1,
		Impact:      "low",
		Mitigation:  "Fall back to direct execution",
	})

	// Execution risk
	risks = append(risks, PlanRisk{
		Description: "Execution may fail",
		Probability: 0.2,
		Impact:      "high",
		Mitigation:  "Use fallback strategy",
	})

	// Handoff risk
	if len(query.History) > 3 {
		risks = append(risks, PlanRisk{
			Description: "Handoff between agents may lose context",
			Probability: 0.25,
			Impact:      "medium",
			Mitigation:  "Include full context in handoff",
		})
	}

	return risks
}

// buildFallbacks builds basic fallbacks for the fast path.
func (p *defaultPlanner) buildFallbacks() []FallbackStrategy {
	return []FallbackStrategy{
		{
			Condition: "execution failed",
			Action:    "retry",
			Target:    "simpler approach",
		},
	}
}

// buildDetailedFallbacks builds detailed fallbacks for the deep path.
func (p *defaultPlanner) buildDetailedFallbacks() []FallbackStrategy {
	return []FallbackStrategy{
		{
			Condition: "context unavailable",
			Action:    "skip_context",
			Target:    "direct execution",
		},
		{
			Condition: "planning timeout",
			Action:    "use_cached_plan",
			Target:    "previous plan if available",
		},
		{
			Condition: "execution failed",
			Action:    "retry_with_simpler",
			Target:    "reduced scope",
		},
		{
			Condition: "fallback failed",
			Action:    "abort",
			Target:    "return error",
		},
	}
}
