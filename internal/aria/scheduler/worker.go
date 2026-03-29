package scheduler

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/pubsub"
)

// TaskExecutor executes tasks.
type TaskExecutor interface {
	ExecuteTask(ctx context.Context, task Task) (*TaskResult, error)
}

// Worker runs tasks from the queue.
type Worker struct {
	scheduler     *SchedulerService
	maxConcurrent int
	pollInterval  time.Duration
	executor      TaskExecutor
	mu            sync.Mutex
	running       bool
	stopCh        chan struct{}
	waitGroup     sync.WaitGroup
}

// NewWorker creates a new Worker.
func NewWorker(scheduler *SchedulerService, maxConcurrent int, pollInterval time.Duration, executor TaskExecutor) *Worker {
	return &Worker{
		scheduler:     scheduler,
		maxConcurrent: maxConcurrent,
		pollInterval:  pollInterval,
		executor:      executor,
		stopCh:        make(chan struct{}),
	}
}

// Run starts the worker pool. It polls for queued tasks and executes them.
func (w *Worker) Run(ctx context.Context) {
	w.mu.Lock()
	if w.running {
		w.mu.Unlock()
		return
	}
	w.running = true
	w.mu.Unlock()

	logging.Info("worker started",
		"max_concurrent", w.maxConcurrent,
		"poll_interval", w.pollInterval.String())

	defer func() {
		w.mu.Lock()
		w.running = false
		w.mu.Unlock()
	}()

	// Semaphore to limit concurrent executions
	sem := make(chan struct{}, w.maxConcurrent)

	ticker := time.NewTicker(w.pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			logging.Info("worker stopped: context cancelled")
			w.waitGroup.Wait()
			return
		case <-w.stopCh:
			logging.Info("worker stopped: stop signal received")
			w.waitGroup.Wait()
			return
		case <-ticker.C:
			w.processQueuedTasks(ctx, sem)
		}
	}
}

// Stop stops the worker pool gracefully.
func (w *Worker) Stop() {
	w.mu.Lock()
	if !w.running {
		w.mu.Unlock()
		return
	}
	w.mu.Unlock()

	select {
	case <-w.stopCh:
		// Already stopped
	default:
		close(w.stopCh)
	}

	// Wait for in-flight tasks to complete
	w.waitGroup.Wait()
}

// processQueuedTasks polls for queued tasks and starts execution for each.
func (w *Worker) processQueuedTasks(ctx context.Context, sem chan struct{}) {
	// Fetch queued tasks ordered by priority
	dbTasks, err := w.scheduler.db.ListTasksByStatus(ctx, db.ListTasksByStatusParams{
		Status: string(TaskStatusQueued),
		Limit:  int64(w.maxConcurrent * 2), // Fetch a batch to keep workers busy
		Offset: 0,
	})
	if err != nil {
		logging.Error("worker: failed to list queued tasks", "error", err)
		return
	}

	if len(dbTasks) == 0 {
		return
	}

	logging.Debug("worker: found queued tasks", "count", len(dbTasks))

	for _, dbTask := range dbTasks {
		select {
		case <-ctx.Done():
			return
		case <-w.stopCh:
			return
		case sem <- struct{}{}:
			// Acquired slot
		}

		w.waitGroup.Add(1)
		go func(task db.Task) {
			defer w.waitGroup.Done()
			defer func() { <-sem }() // Release slot

			taskID := TaskID(task.ID)
			if err := w.processTask(ctx, taskID); err != nil {
				logging.Error("worker: failed to process task",
					"task_id", taskID, "error", err)
			}
		}(dbTask)
	}
}

// processTask processes a single task from queued to completion or failure.
func (w *Worker) processTask(ctx context.Context, taskID TaskID) error {
	// 1. Update status to 'running', started_at = now, create 'started' event
	now := time.Now()
	if err := w.scheduler.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusRunning),
		Column2:  string(TaskStatusRunning), // For started_at CASE
		Column3:  string(TaskStatusCompleted),
		Column4:  string(TaskStatusFailed),
		Column5:  string(TaskStatusCancelled),
		Progress: 0,
		Result:   sql.NullString{Valid: false},
		Error:    sql.NullString{Valid: false},
		ID:       string(taskID),
	}); err != nil {
		return fmt.Errorf("failed to update task status to running: %w", err)
	}

	// Create started event
	startedEvent := TaskEvent{
		TaskID:    taskID,
		Type:      "started",
		Progress:  0,
		Message:   "Task execution started",
		Timestamp: now,
	}

	dbEventParams, err := taskEventToDB(startedEvent)
	if err != nil {
		logging.Error("worker: failed to convert started event to db params", "error", err)
	} else {
		if _, err := w.scheduler.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("worker: failed to create started event", "error", err)
		}
	}

	// Publish event
	w.scheduler.eventBroker.Publish(pubsub.UpdatedEvent, startedEvent)

	// Get full task details for executor
	task, err := w.scheduler.GetTask(ctx, taskID)
	if err != nil {
		return w.failTask(ctx, taskID, fmt.Sprintf("failed to get task: %v", err))
	}

	// 2. Execute the task
	result, err := w.executor.ExecuteTask(ctx, task)

	// 3. Handle outcome
	if err != nil {
		return w.failTask(ctx, taskID, fmt.Sprintf("task execution failed: %v", err))
	}

	return w.completeTask(ctx, taskID, result)
}

// completeTask marks a task as completed with the result.
func (w *Worker) completeTask(ctx context.Context, taskID TaskID, result *TaskResult) error {
	completedAt := time.Now()

	// Serialize result
	var resultJSON []byte
	if result != nil {
		resultJSON, _ = json.Marshal(result)
	}

	// Update task status to completed
	err := w.scheduler.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusCompleted),
		Column2:  string(TaskStatusRunning),
		Column3:  string(TaskStatusCompleted),
		Column4:  string(TaskStatusFailed),
		Column5:  string(TaskStatusCancelled),
		Progress: 1.0,
		Result:   sql.NullString{String: string(resultJSON), Valid: len(resultJSON) > 0},
		Error:    sql.NullString{Valid: false},
		ID:       string(taskID),
	})
	if err != nil {
		return fmt.Errorf("failed to update task status to completed: %w", err)
	}

	// Create completed event
	completedEvent := TaskEvent{
		TaskID:    taskID,
		Type:      "completed",
		Progress:  1.0,
		Message:   "Task completed successfully",
		Timestamp: completedAt,
	}

	dbEventParams, err := taskEventToDB(completedEvent)
	if err != nil {
		logging.Error("worker: failed to convert completed event to db params", "error", err)
	} else {
		if _, err := w.scheduler.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("worker: failed to create completed event", "error", err)
		}
	}

	// Publish event
	w.scheduler.eventBroker.Publish(pubsub.UpdatedEvent, completedEvent)

	logging.Debug("worker: task completed", "task_id", taskID)

	return nil
}

// failTask marks a task as failed with an error message.
func (w *Worker) failTask(ctx context.Context, taskID TaskID, reason string) error {
	failedAt := time.Now()

	// Create error JSON
	taskErr := TaskError{
		Message:   reason,
		Code:      "EXECUTION_FAILED",
		Retriable: false,
		FailedAt:  failedAt,
	}
	errJSON, err := json.Marshal(taskErr)
	if err != nil {
		errJSON = []byte(fmt.Sprintf(`{"message":"%s"}`, reason))
	}

	// Update task status to failed
	err = w.scheduler.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusFailed),
		Column2:  string(TaskStatusRunning),
		Column3:  string(TaskStatusCompleted),
		Column4:  string(TaskStatusFailed),
		Column5:  string(TaskStatusCancelled),
		Progress: 0,
		Result:   sql.NullString{Valid: false},
		Error:    sql.NullString{String: string(errJSON), Valid: true},
		ID:       string(taskID),
	})
	if err != nil {
		return fmt.Errorf("failed to update task status to failed: %w", err)
	}

	// Create failed event
	failedEvent := TaskEvent{
		TaskID:    taskID,
		Type:      "failed",
		Progress:  0,
		Message:   reason,
		Timestamp: failedAt,
	}

	dbEventParams, err := taskEventToDB(failedEvent)
	if err != nil {
		logging.Error("worker: failed to convert failed event to db params", "error", err)
	} else {
		if _, err := w.scheduler.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("worker: failed to create failed event", "error", err)
		}
	}

	// Publish event
	w.scheduler.eventBroker.Publish(pubsub.UpdatedEvent, failedEvent)

	logging.Debug("worker: task failed", "task_id", taskID, "reason", reason)

	return nil
}
