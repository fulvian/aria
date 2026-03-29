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

// Dispatcher manages the queue of tasks ready to be executed.
// It periodically checks for tasks that are eligible (time + dependencies met)
// and promotes them to the queued state.
type Dispatcher struct {
	scheduler    *SchedulerService
	interval     time.Duration
	mu           sync.Mutex
	running      bool
	stopCh       chan struct{}
	failOnBadDep bool // If true, fail tasks with failed/cancelled dependencies
}

// NewDispatcher creates a new Dispatcher.
func NewDispatcher(scheduler *SchedulerService, interval time.Duration, failOnBadDep bool) *Dispatcher {
	return &Dispatcher{
		scheduler:    scheduler,
		interval:     interval,
		failOnBadDep: failOnBadDep,
		stopCh:       make(chan struct{}),
	}
}

// Run starts the dispatcher loop. It runs until Stop is called or the context is cancelled.
func (d *Dispatcher) Run(ctx context.Context) {
	d.mu.Lock()
	if d.running {
		d.mu.Unlock()
		return
	}
	d.running = true
	d.mu.Unlock()

	logging.Info("dispatcher started", "interval", d.interval.String())

	defer func() {
		d.mu.Lock()
		d.running = false
		d.mu.Unlock()
	}()

	ticker := time.NewTicker(d.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			logging.Info("dispatcher stopped: context cancelled")
			return
		case <-d.stopCh:
			logging.Info("dispatcher stopped: stop signal received")
			return
		case <-ticker.C:
			if err := d.promoteEligibleTasks(ctx); err != nil {
				logging.Error("dispatcher: error promoting eligible tasks", "error", err)
			}
		}
	}
}

// Stop stops the dispatcher loop gracefully.
func (d *Dispatcher) Stop() {
	d.mu.Lock()
	if !d.running {
		d.mu.Unlock()
		return
	}
	d.mu.Unlock()

	select {
	case <-d.stopCh:
		// Already stopped
	default:
		close(d.stopCh)
	}
}

// promoteEligibleTasks finds tasks that are ready (time + dependencies met)
// and promotes them to the queued state.
func (d *Dispatcher) promoteEligibleTasks(ctx context.Context) error {
	now := time.Now().Unix()

	// Query tasks with status 'created' or 'deferred' that are ready (scheduled_at <= now)
	dbTasks, err := d.scheduler.db.ListPendingTasks(ctx, db.ListPendingTasksParams{
		Status:      string(TaskStatusCreated),
		Status_2:    string(TaskStatusDeferred),
		ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
	})
	if err != nil {
		return fmt.Errorf("failed to list pending tasks: %w", err)
	}

	if len(dbTasks) == 0 {
		return nil
	}

	// Count currently running tasks for backpressure
	runningCount, err := d.scheduler.db.CountTasksByStatus(ctx, string(TaskStatusRunning))
	if err != nil {
		return fmt.Errorf("failed to count running tasks: %w", err)
	}

	slotsAvailable := d.scheduler.maxConcurrent - int(runningCount)
	if slotsAvailable <= 0 {
		logging.Debug("dispatcher: backpressure active, no slots available",
			"running", runningCount, "max", d.scheduler.maxConcurrent)
		return nil
	}

	// Process tasks and promote up to slotsAvailable
	promoted := 0
	for _, dbTask := range dbTasks {
		if promoted >= slotsAvailable {
			break
		}

		taskID := TaskID(dbTask.ID)

		// Check dependencies
		ready, depStatus, err := d.checkDependencies(ctx, taskID)
		if err != nil {
			logging.Error("dispatcher: error checking dependencies",
				"task_id", taskID, "error", err)
			continue
		}

		if !ready {
			if depStatus == "bad_dep" {
				// A dependency is failed/cancelled
				if d.failOnBadDep {
					// Mark dependent task as failed
					if err := d.failTask(ctx, taskID, "dependency failed or cancelled"); err != nil {
						logging.Error("dispatcher: failed to mark task as failed",
							"task_id", taskID, "error", err)
					}
				}
				continue
			}
			// Still waiting on dependencies
			continue
		}

		// Promote task to queued
		if err := d.promoteTask(ctx, taskID); err != nil {
			logging.Error("dispatcher: failed to promote task",
				"task_id", taskID, "error", err)
			continue
		}

		promoted++
	}

	if promoted > 0 {
		logging.Debug("dispatcher: promoted tasks", "count", promoted)
	}

	return nil
}

// checkDependencies checks if all dependencies of a task are satisfied.
// Returns (true, "", nil) if all dependencies are completed.
// Returns (false, "waiting", nil) if still waiting on dependencies.
// Returns (false, "bad_dep", nil) if a dependency is failed/cancelled.
// Returns (false, "", error) on database error.
func (d *Dispatcher) checkDependencies(ctx context.Context, taskID TaskID) (bool, string, error) {
	deps, err := d.scheduler.db.GetTaskDependencies(ctx, string(taskID))
	if err != nil {
		if err == sql.ErrNoRows {
			// No dependencies, task is ready
			return true, "", nil
		}
		return false, "", fmt.Errorf("failed to get task dependencies: %w", err)
	}

	if len(deps) == 0 {
		return true, "", nil
	}

	for _, dep := range deps {
		status := TaskStatus(dep.Status)
		switch status {
		case TaskStatusCompleted:
			// Dependency satisfied
			continue
		case TaskStatusFailed, TaskStatusCancelled:
			// A dependency failed/cancelled - this is a bad dependency state
			return false, "bad_dep", nil
		default:
			// Still waiting on this dependency
			return false, "waiting", nil
		}
	}

	return true, "", nil
}

// promoteTask marks a task as queued and publishes a queued event.
func (d *Dispatcher) promoteTask(ctx context.Context, taskID TaskID) error {
	// Update task status to queued
	err := d.scheduler.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusQueued),
		Column2:  "",
		Column3:  "",
		Column4:  "",
		Column5:  "",
		Progress: 0,
		Result:   sql.NullString{Valid: false},
		Error:    sql.NullString{Valid: false},
		ID:       string(taskID),
	})
	if err != nil {
		return fmt.Errorf("failed to update task status to queued: %w", err)
	}

	// Create queued event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "queued",
		Progress:  0,
		Message:   "Task queued for execution",
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("dispatcher: failed to convert queued event to db params", "error", err)
	} else {
		if _, err := d.scheduler.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("dispatcher: failed to create queued event", "error", err)
		}
	}

	// Publish event to subscribers
	d.scheduler.eventBroker.Publish(pubsub.UpdatedEvent, event)

	logging.Debug("dispatcher: task promoted to queued", "task_id", taskID)

	return nil
}

// failTask marks a task as failed with a given reason.
func (d *Dispatcher) failTask(ctx context.Context, taskID TaskID, reason string) error {
	// Create error JSON
	taskErr := TaskError{
		Message:   reason,
		Code:      "DEPENDENCY_FAILED",
		Retriable: false,
		FailedAt:  time.Now(),
	}
	errJSON, err := json.Marshal(taskErr)
	if err != nil {
		errJSON = []byte(fmt.Sprintf(`{"message":"%s"}`, reason))
	}

	// Update task status to failed
	err = d.scheduler.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusFailed),
		Column2:  "",
		Column3:  "",
		Column4:  "",
		Column5:  "",
		Progress: 0,
		Result:   sql.NullString{Valid: false},
		Error:    sql.NullString{String: string(errJSON), Valid: true},
		ID:       string(taskID),
	})
	if err != nil {
		return fmt.Errorf("failed to update task status to failed: %w", err)
	}

	// Create failed event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "failed",
		Progress:  0,
		Message:   reason,
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("dispatcher: failed to convert failed event to db params", "error", err)
	} else {
		if _, err := d.scheduler.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("dispatcher: failed to create failed event", "error", err)
		}
	}

	// Publish event to subscribers
	d.scheduler.eventBroker.Publish(pubsub.UpdatedEvent, event)

	logging.Debug("dispatcher: task marked as failed", "task_id", taskID, "reason", reason)

	return nil
}
