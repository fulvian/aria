package plan

import (
	"context"
	"fmt"
)

// Reviewer verifies output against objectives.
type Reviewer interface {
	Review(ctx context.Context, plan *Plan, result *ExecutionResult) (*ReviewResult, error)
	ShouldReplan(ctx context.Context, review ReviewResult) (bool, ReplanReason)
}

// ReviewResult is the result of a review.
type ReviewResult struct {
	Score    float64
	Passed   bool
	Criteria []AcceptanceCriterion
	Verdict  string
	Feedback string
}

// AcceptanceCriterion is a single acceptance criterion.
type AcceptanceCriterion struct {
	Name     string
	Passed   bool
	Evidence string
	Weight   float64
}

// ReplanReason is the reason for replanning.
type ReplanReason struct {
	Reason   string
	Strategy string // "RETRY", "FALLBACK", "REPLAN_FULL"
}

// ReviewerConfig is the configuration for the reviewer.
type ReviewerConfig struct {
	MinAcceptanceScore float64
	MaxReplan          int
	MaxRetries         int
}

// defaultReviewer is the base implementation of Reviewer.
type defaultReviewer struct {
	config ReviewerConfig
}

// NewReviewer creates a new defaultReviewer with default config.
func NewReviewer() *defaultReviewer {
	return &defaultReviewer{
		config: ReviewerConfig{
			MinAcceptanceScore: 0.75,
			MaxReplan:          2,
			MaxRetries:         1,
		},
	}
}

// NewReviewerWithConfig creates a new defaultReviewer with custom config.
func NewReviewerWithConfig(config ReviewerConfig) *defaultReviewer {
	return &defaultReviewer{config: config}
}

// Review evaluates whether the result satisfies the acceptance criteria.
func (r *defaultReviewer) Review(ctx context.Context, plan *Plan, result *ExecutionResult) (*ReviewResult, error) {
	criteria := r.evaluateCriteria(plan, result)

	// Calculate weighted score
	var totalScore float64
	var criticalPassed bool = true
	for _, c := range criteria {
		if c.Passed {
			totalScore += c.Weight
		}
		// Check critical criteria
		if c.Name == "Objective satisfied" && !c.Passed {
			criticalPassed = false
		}
	}

	// Determine verdict
	verdict := r.determineVerdict(totalScore, criteria, criticalPassed)

	feedback := r.buildFeedback(criteria, verdict)

	return &ReviewResult{
		Score:    totalScore,
		Passed:   totalScore >= r.config.MinAcceptanceScore,
		Criteria: criteria,
		Verdict:  verdict,
		Feedback: feedback,
	}, nil
}

// ShouldReplan determines if replanning is needed.
func (r *defaultReviewer) ShouldReplan(ctx context.Context, review ReviewResult) (bool, ReplanReason) {
	switch review.Verdict {
	case "REPLAN_NEEDED":
		return true, ReplanReason{
			Reason:   "low_score",
			Strategy: "REPLAN_FULL",
		}
	case "REVISION_NEEDED":
		return true, ReplanReason{
			Reason:   "needs_revision",
			Strategy: "RETRY",
		}
	default:
		return false, ReplanReason{}
	}
}

// evaluateCriteria evaluates all acceptance criteria.
func (r *defaultReviewer) evaluateCriteria(plan *Plan, result *ExecutionResult) []AcceptanceCriterion {
	criteria := []AcceptanceCriterion{}

	// Objective satisfied (weight 0.30)
	objectivePassed := result.Success && len(result.CompletedSteps) >= len(plan.Steps)
	criteria = append(criteria, AcceptanceCriterion{
		Name:     "Objective satisfied",
		Passed:   objectivePassed,
		Evidence: fmt.Sprintf("completed %d/%d steps, success=%v", len(result.CompletedSteps), len(plan.Steps), result.Success),
		Weight:   0.30,
	})

	// Constraints respected (weight 0.25)
	constraintsPassed := true
	evidence := "all constraints checked"
	for _, step := range plan.Steps {
		if len(step.Constraints) > 0 {
			// Check if step was completed (if not, constraints weren't respected)
			stepCompleted := false
			for _, completedIdx := range result.CompletedSteps {
				if completedIdx == step.Index {
					stepCompleted = true
					break
				}
			}
			if !stepCompleted && step.Index != 0 {
				constraintsPassed = false
				evidence = fmt.Sprintf("step %d not completed", step.Index)
				break
			}
		}
	}
	criteria = append(criteria, AcceptanceCriterion{
		Name:     "Constraints respected",
		Passed:   constraintsPassed,
		Evidence: evidence,
		Weight:   0.25,
	})

	// Risk within threshold (weight 0.20) - placeholder
	riskPassed := true
	if result.FailedStep != nil {
		riskPassed = false
	}
	criteria = append(criteria, AcceptanceCriterion{
		Name:     "Risk within threshold",
		Passed:   riskPassed,
		Evidence: "risk assessment placeholder - no high-risk failures detected",
		Weight:   0.20,
	})

	// Evidence available (weight 0.15)
	evidencePassed := len(result.Outputs) > 0
	evidenceStr := fmt.Sprintf("outputs count: %d", len(result.Outputs))
	criteria = append(criteria, AcceptanceCriterion{
		Name:     "Evidence available",
		Passed:   evidencePassed,
		Evidence: evidenceStr,
		Weight:   0.15,
	})

	// Fallback not triggered excessively (weight 0.10)
	fallbackNotExcessive := !result.Metrics.FallbackUsed
	fallbackEvidence := "no fallback used"
	if result.Metrics.FallbackUsed {
		fallbackEvidence = "fallback was used"
	}
	criteria = append(criteria, AcceptanceCriterion{
		Name:     "Fallback not triggered excessively",
		Passed:   fallbackNotExcessive,
		Evidence: fallbackEvidence,
		Weight:   0.10,
	})

	return criteria
}

// determineVerdict determines the verdict based on score and criteria.
func (r *defaultReviewer) determineVerdict(score float64, criteria []AcceptanceCriterion, criticalPassed bool) string {
	// Check if all critical criteria passed
	allCriticalPassed := true
	for _, c := range criteria {
		if c.Name == "Objective satisfied" && !c.Passed {
			allCriticalPassed = false
			break
		}
	}

	if score >= 0.75 && allCriticalPassed {
		return "APPROVED"
	}

	if score >= 0.50 && !criticalPassed {
		return "REVISION_NEEDED"
	}

	return "REPLAN_NEEDED"
}

// buildFeedback builds feedback string from criteria.
func (r *defaultReviewer) buildFeedback(criteria []AcceptanceCriterion, verdict string) string {
	var failed []string
	for _, c := range criteria {
		if !c.Passed {
			failed = append(failed, c.Name)
		}
	}

	if len(failed) == 0 {
		return fmt.Sprintf("All criteria passed. Verdict: %s", verdict)
	}

	return fmt.Sprintf("Failed criteria: %v. Verdict: %s", failed, verdict)
}
