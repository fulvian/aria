package scheduler

import (
	"context"
	"time"
)

// defaultTaskExecutor is a simple TaskExecutor implementation that logs tasks.
// For MVP, this is a stub. Real implementation will delegate to agency/agent.
type defaultTaskExecutor struct {
}

// NewDefaultTaskExecutor creates a new defaultTaskExecutor.
func NewDefaultTaskExecutor() *defaultTaskExecutor {
	return &defaultTaskExecutor{}
}

// ExecuteTask executes a task (stub implementation for MVP).
func (e *defaultTaskExecutor) ExecuteTask(ctx context.Context, task Task) (*TaskResult, error) {
	// For MVP, just log and return success
	// Real implementation will delegate to agency/agent bridge
	return &TaskResult{
		Output: map[string]any{
			"status":    "executed",
			"task_id":   string(task.ID),
			"task_name": task.Name,
		},
		CompletedAt: time.Now(),
	}, nil
}
