package plan

import (
	"context"
	"fmt"
	"time"
)

// Executor executes a plan.
type Executor interface {
	Execute(ctx context.Context, plan *Plan) (*ExecutionResult, error)
	ExecuteStep(ctx context.Context, step PlanStep) (*StepResult, error)
}

// ExecutionResult is the result of executing a complete plan.
type ExecutionResult struct {
	PlanID         string
	Success        bool
	CompletedSteps []int
	FailedStep     *int
	Outputs        map[string]any
	Handoffs       []HandoffRecord
	Metrics        ExecutionMetrics
	Error          error
}

// StepResult is the result of executing a single step.
type StepResult struct {
	StepIndex int
	Success   bool
	Output    map[string]any
	Error     error
}

// HandoffRecord is a record of an executed handover.
type HandoffRecord struct {
	Handoff    Handoff
	FromOutput map[string]any
	ToInput    map[string]any
	Completed  bool
	Duration   time.Duration
}

// ExecutionMetrics are execution metrics.
type ExecutionMetrics struct {
	TotalTokens  int
	TotalTime    time.Duration
	StepsTime    []time.Duration
	FallbackUsed bool
}

// defaultExecutor is the base implementation of Executor.
type defaultExecutor struct {
	// agency registry for execution (placeholder for future integration)
}

// NewExecutor creates a new defaultExecutor.
func NewExecutor() *defaultExecutor {
	return &defaultExecutor{}
}

// Execute executes the plan.
func (e *defaultExecutor) Execute(ctx context.Context, plan *Plan) (*ExecutionResult, error) {
	result := &ExecutionResult{
		PlanID:         plan.ID,
		Success:        true,
		CompletedSteps: []int{},
		Outputs:        map[string]any{},
		Handoffs:       []HandoffRecord{},
		Metrics:        ExecutionMetrics{},
	}

	startTime := time.Now()
	stepTimes := []time.Duration{}

	for _, step := range plan.Steps {
		stepStart := time.Now()

		// Check context cancellation
		select {
		case <-ctx.Done():
			result.Success = false
			result.Error = ctx.Err()
			idx := step.Index
			result.FailedStep = &idx
			break
		default:
		}

		// Execute step
		stepResult, err := e.ExecuteStep(ctx, step)
		stepDuration := time.Since(stepStart)
		stepTimes = append(stepTimes, stepDuration)

		if err != nil {
			// Check for fallback
			fallback := e.findFallback(plan.Fallbacks, step)
			if fallback != nil {
				result.Metrics.FallbackUsed = true
				fbResult := e.executeFallback(ctx, step, fallback)
				if fbResult.Success {
					result.CompletedSteps = append(result.CompletedSteps, step.Index)
					result.Outputs[fmt.Sprintf("step_%d", step.Index)] = fbResult.Output
					continue
				}
			}

			result.Success = false
			result.Error = err
			idx := step.Index
			result.FailedStep = &idx
			break
		}

		if !stepResult.Success {
			// Check for fallback
			fallback := e.findFallback(plan.Fallbacks, step)
			if fallback != nil {
				result.Metrics.FallbackUsed = true
				fbResult := e.executeFallback(ctx, step, fallback)
				if fbResult.Success {
					result.CompletedSteps = append(result.CompletedSteps, step.Index)
					result.Outputs[fmt.Sprintf("step_%d", step.Index)] = fbResult.Output
					continue
				}
			}

			result.Success = false
			idx := step.Index
			result.FailedStep = &idx
			break
		}

		result.CompletedSteps = append(result.CompletedSteps, step.Index)
		result.Outputs[fmt.Sprintf("step_%d", step.Index)] = stepResult.Output
	}

	result.Metrics.TotalTime = time.Since(startTime)
	result.Metrics.StepsTime = stepTimes

	// Estimate tokens based on steps
	result.Metrics.TotalTokens = len(plan.Steps) * 100

	return result, nil
}

// ExecuteStep executes a single step.
func (e *defaultExecutor) ExecuteStep(ctx context.Context, step PlanStep) (*StepResult, error) {
	// Check preconditions
	for _, constraint := range step.Constraints {
		if !e.checkConstraint(constraint) {
			return &StepResult{
				StepIndex: step.Index,
				Success:   false,
				Output:    nil,
				Error:     fmt.Errorf("constraint not met: %s", constraint),
			}, nil
		}
	}

	// Simulate execution
	// In a real implementation, this would call agency/agent
	// For now, we simulate a successful execution
	output := map[string]any{
		"executed":  true,
		"action":    step.Action,
		"target":    step.Target,
		"simulated": true,
	}

	return &StepResult{
		StepIndex: step.Index,
		Success:   true,
		Output:    output,
		Error:     nil,
	}, nil
}

// findFallback finds a fallback strategy for a step.
func (e *defaultExecutor) findFallback(fallbacks []FallbackStrategy, step PlanStep) *FallbackStrategy {
	for i := range fallbacks {
		fb := &fallbacks[i]
		if fb.Condition == "execution failed" || fb.Condition == "constraint not met" {
			return fb
		}
	}
	return nil
}

// executeFallback executes a fallback strategy.
func (e *defaultExecutor) executeFallback(ctx context.Context, step PlanStep, fallback *FallbackStrategy) *StepResult {
	// Simulate fallback execution
	output := map[string]any{
		"executed":  true,
		"action":    fallback.Action,
		"target":    fallback.Target,
		"fallback":  true,
		"simulated": true,
	}

	return &StepResult{
		StepIndex: step.Index,
		Success:   true,
		Output:    output,
		Error:     nil,
	}
}

// checkConstraint checks if a constraint is met.
func (e *defaultExecutor) checkConstraint(constraint string) bool {
	// Placeholder implementation
	// In a real implementation, this would check actual constraints
	switch constraint {
	case "preserve context":
		return true
	case "efficient execution":
		return true
	case "within budget":
		return true
	case "acceptance criteria met":
		return true
	default:
		return true
	}
}
