// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
)

// TaskState represents the state of a task in the execution pipeline.
type TaskState string

const (
	// TaskStatePending - Task received, not yet started
	TaskStatePending TaskState = "pending"
	// TaskStateValidating - Task parameters being validated
	TaskStateValidating TaskState = "validating"
	// TaskStateRunning - Task is being executed
	TaskStateRunning TaskState = "running"
	// TaskStateWaitingFallback - Primary agent failed, trying fallback
	TaskStateWaitingFallback TaskState = "waiting_fallback"
	// TaskStateSynthesizing - Results being synthesized from multiple agents
	TaskStateSynthesizing TaskState = "synthesizing"
	// TaskStateCompleted - Task completed successfully
	TaskStateCompleted TaskState = "completed"
	// TaskStateFailed - Task failed
	TaskStateFailed TaskState = "failed"
	// TaskStateCancelled - Task was cancelled
	TaskStateCancelled TaskState = "cancelled"
)

// TaskStatus tracks the status of a single task.
type TaskStatus struct {
	TaskID      string
	State       TaskState
	StartedAt   time.Time
	CompletedAt time.Time
	AgentName   string
	Error       string
	Attempts    int
	MaxAttempts int
	Result      map[string]any
	Steps       []TaskStep
}

// TaskStep represents a single step within a task execution.
type TaskStep struct {
	Name        string
	Description string
	Status      string // pending, running, completed, failed, skipped
	StartedAt   time.Time
	CompletedAt time.Time
	Error       string
	Result      map[string]any
}

// TaskStateMachine manages task state transitions.
type TaskStateMachine struct {
	mu      sync.RWMutex
	tasks   map[string]*TaskStatus
	history map[string][]TaskState // Task history for debugging
}

// NewTaskStateMachine creates a new task state machine.
func NewTaskStateMachine() *TaskStateMachine {
	return &TaskStateMachine{
		tasks:   make(map[string]*TaskStatus),
		history: make(map[string][]TaskState),
	}
}

// CreateTask creates a new task status entry.
func (sm *TaskStateMachine) CreateTask(taskID string, maxAttempts int) *TaskStatus {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status := &TaskStatus{
		TaskID:      taskID,
		State:       TaskStatePending,
		StartedAt:   time.Now(),
		MaxAttempts: maxAttempts,
		Attempts:    0,
		Steps:       []TaskStep{},
	}
	sm.tasks[taskID] = status
	sm.history[taskID] = []TaskState{TaskStatePending}
	return status
}

// GetTask returns the status of a task.
func (sm *TaskStateMachine) GetTask(taskID string) (*TaskStatus, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return nil, fmt.Errorf("task not found: %s", taskID)
	}
	return status, nil
}

// Transition moves a task to a new state.
func (sm *TaskStateMachine) Transition(taskID string, newState TaskState) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	// Validate transition
	if !sm.isValidTransition(status.State, newState) {
		return fmt.Errorf("invalid transition from %s to %s", status.State, newState)
	}

	status.State = newState
	sm.history[taskID] = append(sm.history[taskID], newState)

	// Update timestamps
	switch newState {
	case TaskStateRunning, TaskStateValidating:
		if status.StartedAt.IsZero() {
			status.StartedAt = time.Now()
		}
	case TaskStateCompleted, TaskStateFailed, TaskStateCancelled:
		status.CompletedAt = time.Now()
	}

	return nil
}

// isValidTransition checks if a state transition is valid.
func (sm *TaskStateMachine) isValidTransition(from, to TaskState) bool {
	validTransitions := map[TaskState][]TaskState{
		TaskStatePending:         {TaskStateValidating, TaskStateRunning, TaskStateFailed, TaskStateCancelled},
		TaskStateValidating:      {TaskStateRunning, TaskStateFailed, TaskStateCancelled},
		TaskStateRunning:         {TaskStateSynthesizing, TaskStateWaitingFallback, TaskStateCompleted, TaskStateFailed, TaskStateCancelled},
		TaskStateWaitingFallback: {TaskStateRunning, TaskStateFailed, TaskStateCancelled},
		TaskStateSynthesizing:    {TaskStateCompleted, TaskStateFailed},
	}

	allowed, ok := validTransitions[from]
	if !ok {
		return false
	}

	for _, s := range allowed {
		if s == to {
			return true
		}
	}
	return false
}

// SetAgent records which agent is handling the task.
func (sm *TaskStateMachine) SetAgent(taskID string, agentName string) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	status.AgentName = agentName
	return nil
}

// IncrementAttempts increments the attempt counter.
func (sm *TaskStateMachine) IncrementAttempts(taskID string) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	status.Attempts++
	return nil
}

// SetResult sets the final result of a task.
func (sm *TaskStateMachine) SetResult(taskID string, result map[string]any) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	status.Result = result
	return nil
}

// SetError sets the error message for a failed task.
func (sm *TaskStateMachine) SetError(taskID string, err string) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	status.Error = err
	return nil
}

// AddStep adds a step to the task execution.
func (sm *TaskStateMachine) AddStep(taskID string, step TaskStep) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	status.Steps = append(status.Steps, step)
	return nil
}

// UpdateStep updates a step in the task execution.
func (sm *TaskStateMachine) UpdateStep(taskID string, stepName string, updates func(*TaskStep)) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	status, ok := sm.tasks[taskID]
	if !ok {
		return fmt.Errorf("task not found: %s", taskID)
	}

	for i := range status.Steps {
		if status.Steps[i].Name == stepName {
			updates(&status.Steps[i])
			return nil
		}
	}

	return fmt.Errorf("step not found: %s", stepName)
}

// GetHistory returns the state history of a task.
func (sm *TaskStateMachine) GetHistory(taskID string) ([]TaskState, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	history, ok := sm.history[taskID]
	if !ok {
		return nil, fmt.Errorf("task not found: %s", taskID)
	}

	return history, nil
}

// ListTasks returns all tasks in a specific state.
func (sm *TaskStateMachine) ListTasks(state TaskState) []*TaskStatus {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	var result []*TaskStatus
	for _, status := range sm.tasks {
		if status.State == state {
			result = append(result, status)
		}
	}
	return result
}

// CleanupOldTasks removes completed/failed tasks older than the specified duration.
func (sm *TaskStateMachine) CleanupOldTasks(olderThan time.Duration) int {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	cutoff := time.Now().Add(-olderThan)
	var removed int

	for taskID, status := range sm.tasks {
		if !status.CompletedAt.IsZero() && status.CompletedAt.Before(cutoff) {
			delete(sm.tasks, taskID)
			delete(sm.history, taskID)
			removed++
		}
	}

	return removed
}

// TaskExecutionCtx holds context for a task being executed.
type TaskExecutionCtx struct {
	Task         contracts.Task
	Status       *TaskStatus
	StateMachine *TaskStateMachine
	CancelFunc   context.CancelFunc
}

// NewTaskExecutionCtx creates a new task execution context.
func NewTaskExecutionCtx(task contracts.Task, maxAttempts int) (*TaskExecutionCtx, context.Context, context.CancelFunc) {
	sm := NewTaskStateMachine()
	status := sm.CreateTask(task.ID, maxAttempts)

	ctx, cancel := context.WithCancel(context.Background())

	return &TaskExecutionCtx{
		Task:         task,
		Status:       status,
		StateMachine: sm,
		CancelFunc:   cancel,
	}, ctx, cancel
}
