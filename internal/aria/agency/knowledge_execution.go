// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/logging"
)

// ExecutionMode defines how a workflow should be executed.
type ExecutionMode string

const (
	// ModeSequential - Execute agents one after another
	ModeSequential ExecutionMode = "sequential"
	// ModeParallel - Execute agents concurrently
	ModeParallel ExecutionMode = "parallel"
	// ModeFallback - Execute agents in order until one succeeds
	ModeFallback ExecutionMode = "fallback"
	// ModeFanOut - Execute all agents and synthesize results
	ModeFanOut ExecutionMode = "fan_out"
)

// WorkflowStep represents a single step in a workflow.
type WorkflowStep struct {
	Name        string
	AgentName   contracts.AgentName
	Skill       string
	Mode        ExecutionMode
	RetryPolicy *RetryPolicy
	Timeout     time.Duration
}

// RetryPolicy defines how to retry failed steps.
type RetryPolicy struct {
	MaxAttempts int
	BaseDelay   time.Duration
	MaxDelay    time.Duration
}

// DefaultRetryPolicy is the default retry policy.
var DefaultRetryPolicy = &RetryPolicy{
	MaxAttempts: 3,
	BaseDelay:   1 * time.Second,
	MaxDelay:    30 * time.Second,
}

// WorkflowEngine executes tasks following defined procedures.
type WorkflowEngine struct {
	supervisor   *TaskRouter
	agentTimeout time.Duration
}

// NewWorkflowEngine creates a new workflow engine.
func NewWorkflowEngine(supervisor *TaskRouter, agentTimeout time.Duration) *WorkflowEngine {
	if agentTimeout == 0 {
		agentTimeout = 60 * time.Second
	}
	return &WorkflowEngine{
		supervisor:   supervisor,
		agentTimeout: agentTimeout,
	}
}

// ExecuteWorkflow executes a workflow with the given steps.
func (e *WorkflowEngine) ExecuteWorkflow(ctx context.Context, task contracts.Task, steps []WorkflowStep) (map[string]any, error) {
	if len(steps) == 0 {
		return nil, fmt.Errorf("no workflow steps defined")
	}

	// Execute based on mode of first step
	switch steps[0].Mode {
	case ModeSequential:
		return e.executeSequential(ctx, task, steps)
	case ModeParallel:
		return e.executeParallel(ctx, task, steps)
	case ModeFallback:
		return e.executeFallback(ctx, task, steps)
	case ModeFanOut:
		return e.executeFanOut(ctx, task, steps)
	default:
		return e.executeSequential(ctx, task, steps)
	}
}

// executeSequential executes steps one after another.
func (e *WorkflowEngine) executeSequential(ctx context.Context, task contracts.Task, steps []WorkflowStep) (map[string]any, error) {
	results := make([]map[string]any, len(steps))
	var lastErr error

	for i, step := range steps {
		stepCtx, cancel := context.WithTimeout(ctx, step.Timeout)
		if step.Timeout == 0 {
			stepCtx, cancel = context.WithTimeout(ctx, e.agentTimeout)
		}

		result, err := e.executeStep(stepCtx, task, step)
		cancel()

		if err != nil {
			logging.Warn("workflow step failed", "step", step.Name, "error", err)
			// Check if we should retry
			if step.RetryPolicy != nil && step.RetryPolicy.MaxAttempts > 1 {
				result, err = e.retryStep(stepCtx, task, step)
			}
			if err != nil {
				lastErr = err
				// Continue to next step or return based on policy
				continue
			}
		}

		results[i] = result
	}

	// If all steps failed, return the last error
	if lastErr != nil && results[0] == nil {
		return nil, lastErr
	}

	// Synthesize results
	return e.synthesizeResults(task.ID, steps, results)
}

// executeParallel executes steps concurrently.
func (e *WorkflowEngine) executeParallel(ctx context.Context, task contracts.Task, steps []WorkflowStep) (map[string]any, error) {
	var wg sync.WaitGroup
	mu := sync.Mutex{}
	results := make([]map[string]any, len(steps))
	errors := make([]error, len(steps))

	for i, step := range steps {
		wg.Add(1)
		go func(idx int, s WorkflowStep) {
			defer wg.Done()

			stepCtx, cancel := context.WithTimeout(ctx, e.agentTimeout)
			defer cancel()

			result, err := e.executeStep(stepCtx, task, s)
			mu.Lock()
			results[idx] = result
			errors[idx] = err
			mu.Unlock()
		}(i, step)
	}

	wg.Wait()

	// Check for errors
	var hasErrors bool
	for i, err := range errors {
		if err != nil {
			logging.Warn("parallel step failed", "step", steps[i].Name, "error", err)
			hasErrors = true
		}
	}

	// If all failed, return error
	if hasErrors && results[0] == nil {
		return nil, fmt.Errorf("all parallel steps failed")
	}

	return e.synthesizeResults(task.ID, steps, results)
}

// executeFallback tries each step until one succeeds.
func (e *WorkflowEngine) executeFallback(ctx context.Context, task contracts.Task, steps []WorkflowStep) (map[string]any, error) {
	var lastErr error

	for _, step := range steps {
		stepCtx, cancel := context.WithTimeout(ctx, e.agentTimeout)
		defer cancel()

		result, err := e.executeStep(stepCtx, task, step)
		if err == nil {
			return result, nil
		}

		logging.Warn("fallback step failed, trying next", "step", step.Name, "error", err)
		lastErr = err
	}

	return nil, fmt.Errorf("all fallback steps failed: %w", lastErr)
}

// executeFanOut executes all steps and synthesizes results.
func (e *WorkflowEngine) executeFanOut(ctx context.Context, task contracts.Task, steps []WorkflowStep) (map[string]any, error) {
	// Execute all steps in parallel
	var wg sync.WaitGroup
	mu := sync.Mutex{}
	results := make([]map[string]any, len(steps))
	errors := make([]error, len(steps))

	for i, step := range steps {
		wg.Add(1)
		go func(idx int, s WorkflowStep) {
			defer wg.Done()

			stepCtx, cancel := context.WithTimeout(ctx, e.agentTimeout)
			defer cancel()

			result, err := e.executeStep(stepCtx, task, s)
			mu.Lock()
			results[idx] = result
			errors[idx] = err
			mu.Unlock()
		}(i, step)
	}

	wg.Wait()

	// Aggregate errors
	var aggregatedErrs []string
	for i, err := range errors {
		if err != nil {
			aggregatedErrs = append(aggregatedErrs, fmt.Sprintf("%s: %v", steps[i].Name, err))
		}
	}

	// Synthesize all results
	synthesized, err := e.synthesizeResults(task.ID, steps, results)
	if err != nil {
		return nil, err
	}

	// Add error info if any
	if len(aggregatedErrs) > 0 {
		synthesized["partial_errors"] = aggregatedErrs
		synthesized["partial_failure"] = true
	}

	return synthesized, nil
}

// executeStep executes a single workflow step.
func (e *WorkflowEngine) executeStep(ctx context.Context, task contracts.Task, step WorkflowStep) (map[string]any, error) {
	// Get agent from supervisor
	agent, err := e.supervisor.RouteToAgent(task, step.AgentName)
	if err != nil {
		return nil, fmt.Errorf("failed to route to agent: %w", err)
	}

	// Create task with skill context
	execTask := task
	if step.Skill != "" {
		execTask.Skills = []string{step.Skill}
	}

	// Execute via executor
	if executor, ok := agent.Executor.(TaskExecutor); ok {
		return executor.Execute(ctx, execTask)
	}

	return nil, fmt.Errorf("agent %s does not implement TaskExecutor", step.AgentName)
}

// retryStep retries a step with exponential backoff.
func (e *WorkflowEngine) retryStep(ctx context.Context, task contracts.Task, step WorkflowStep) (map[string]any, error) {
	policy := step.RetryPolicy
	if policy == nil {
		policy = DefaultRetryPolicy
	}

	var lastErr error
	delay := policy.BaseDelay

	for attempt := 1; attempt <= policy.MaxAttempts; attempt++ {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(delay):
		}

		result, err := e.executeStep(ctx, task, step)
		if err == nil {
			return result, nil
		}

		lastErr = err
		delay *= 2
		if delay > policy.MaxDelay {
			delay = policy.MaxDelay
		}

		logging.Warn("retry attempt failed", "step", step.Name, "attempt", attempt, "error", err)
	}

	return nil, fmt.Errorf("step %s failed after %d attempts: %w", step.Name, policy.MaxAttempts, lastErr)
}

// synthesizeResults combines results from multiple steps.
func (e *WorkflowEngine) synthesizeResults(taskID string, steps []WorkflowStep, results []map[string]any) (map[string]any, error) {
	if len(results) == 0 {
		return nil, fmt.Errorf("no results to synthesize")
	}

	// For single result, just return it
	if len(results) == 1 {
		return results[0], nil
	}

	// Aggregate multiple results
	aggregated := map[string]any{
		"task_id":       taskID,
		"steps_total":   len(steps),
		"steps_results": make([]map[string]any, 0),
	}

	// Count successful steps
	successCount := 0
	for i, r := range results {
		if r != nil {
			successCount++
			stepInfo := map[string]any{
				"step_name": steps[i].Name,
				"success":   true,
				"result":    r,
			}
			aggregated["steps_results"] = append(aggregated["steps_results"].([]map[string]any), stepInfo)

			// Merge top-level fields
			for k, v := range r {
				if k != "task_id" {
					aggregated[k] = v
				}
			}
		}
	}

	aggregated["steps_successful"] = successCount
	aggregated["steps_failed"] = len(results) - successCount

	return aggregated, nil
}

// CreateSimpleWorkflow creates a single-step workflow for a task.
func (e *WorkflowEngine) CreateSimpleWorkflow(task contracts.Task, agentName contracts.AgentName, skill string) []WorkflowStep {
	return []WorkflowStep{
		{
			Name:      fmt.Sprintf("execute_%s", agentName),
			AgentName: agentName,
			Skill:     skill,
			Mode:      ModeSequential,
		},
	}
}

// CreateResearchWorkflow creates a research workflow with validation and synthesis.
func (e *WorkflowEngine) CreateResearchWorkflow(task contracts.Task, primaryAgent, fallbackAgent contracts.AgentName) []WorkflowStep {
	return []WorkflowStep{
		{
			Name:      "validate_task",
			AgentName: primaryAgent,
			Skill:     "validation",
			Mode:      ModeSequential,
			Timeout:   10 * time.Second,
		},
		{
			Name:      "primary_research",
			AgentName: primaryAgent,
			Skill:     "web-research",
			Mode:      ModeSequential,
			Timeout:   60 * time.Second,
		},
		{
			Name:        "fallback_research",
			AgentName:   fallbackAgent,
			Skill:       "web-research",
			Mode:        ModeFallback,
			RetryPolicy: DefaultRetryPolicy,
			Timeout:     60 * time.Second,
		},
	}
}
