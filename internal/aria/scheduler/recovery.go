package scheduler

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/pubsub"
)

// RecoveryPolicy defines how orphaned running tasks are handled on startup.
type RecoveryPolicy string

const (
	// PolicyRequeue puts orphaned running tasks back to queued state.
	PolicyRequeue RecoveryPolicy = "requeue_running"
	// PolicyFail marks orphaned running tasks as failed.
	PolicyFail RecoveryPolicy = "fail_running"
)

// RecoveryManager handles startup recovery of orphaned tasks.
type RecoveryManager struct {
	db          db.Querier
	eventBroker *pubsub.Broker[TaskEvent]
	policy      RecoveryPolicy
}

// NewRecoveryManager creates a new RecoveryManager.
func NewRecoveryManager(dbQuerier db.Querier, eventBroker *pubsub.Broker[TaskEvent], policy RecoveryPolicy) *RecoveryManager {
	return &RecoveryManager{
		db:          dbQuerier,
		eventBroker: eventBroker,
		policy:      policy,
	}
}

// Recover performs startup recovery of orphaned tasks.
// It handles:
// 1. Running tasks that were orphaned from a previous crash
// 2. Queued tasks that might have been picked but not completed
func (r *RecoveryManager) Recover(ctx context.Context) error {
	logging.Info("starting scheduler recovery", "policy", r.policy)

	// Recover orphaned running tasks first
	if err := r.recoverRunningTasks(ctx); err != nil {
		return fmt.Errorf("failed to recover running tasks: %w", err)
	}

	// Handle orphaned queued tasks ( dispatcher will pick them up)
	if err := r.recoverQueuedTasks(ctx); err != nil {
		return fmt.Errorf("failed to recover queued tasks: %w", err)
	}

	logging.Info("scheduler recovery completed")
	return nil
}

// recoverRunningTasks handles orphaned running tasks from a previous crash.
func (r *RecoveryManager) recoverRunningTasks(ctx context.Context) error {
	// Find all tasks with status = 'running' (orphaned from previous crash)
	dbTasks, err := r.db.ListTasksByStatus(ctx, db.ListTasksByStatusParams{
		Status: string(TaskStatusRunning),
		Limit:  1000, // Reasonable limit for startup recovery
		Offset: 0,
	})
	if err != nil {
		return fmt.Errorf("failed to list running tasks: %w", err)
	}

	if len(dbTasks) == 0 {
		logging.Debug("no orphaned running tasks found")
		return nil
	}

	logging.Info("found orphaned running tasks", "count", len(dbTasks), "policy", r.policy)

	for _, dbTask := range dbTasks {
		taskID := TaskID(dbTask.ID)

		switch r.policy {
		case PolicyRequeue:
			if err := r.requeueTask(ctx, taskID); err != nil {
				logging.Error("recovery: failed to requeue task",
					"task_id", taskID, "error", err)
				continue
			}
			logging.Info("recovery: task requeued", "task_id", taskID)

		case PolicyFail:
			if err := r.failTask(ctx, taskID, "orphaned task recovered on startup"); err != nil {
				logging.Error("recovery: failed to mark task as failed",
					"task_id", taskID, "error", err)
				continue
			}
			logging.Info("recovery: task marked as failed", "task_id", taskID)
		}
	}

	return nil
}

// recoverQueuedTasks handles orphaned queued tasks.
// These tasks are left in queued state - the dispatcher will pick them up.
func (r *RecoveryManager) recoverQueuedTasks(ctx context.Context) error {
	// Find all tasks with status = 'queued' (might have been picked but not completed)
	dbTasks, err := r.db.ListTasksByStatus(ctx, db.ListTasksByStatusParams{
		Status: string(TaskStatusQueued),
		Limit:  1000,
		Offset: 0,
	})
	if err != nil {
		return fmt.Errorf("failed to list queued tasks: %w", err)
	}

	if len(dbTasks) == 0 {
		logging.Debug("no orphaned queued tasks found")
		return nil
	}

	logging.Info("found orphaned queued tasks", "count", len(dbTasks))
	// Tasks remain in queued state, dispatcher will process them
	// No action needed - just log for visibility

	return nil
}

// requeueTask puts a task back to queued state with a recovery event.
func (r *RecoveryManager) requeueTask(ctx context.Context, taskID TaskID) error {
	// Update task status to queued
	err := r.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
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
		return fmt.Errorf("failed to update task status: %w", err)
	}

	// Create recovery_requeue event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "recovery_requeue",
		Progress:  0,
		Message:   "Task requeued after startup recovery",
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("recovery: failed to convert event to db params", "error", err)
	} else {
		if _, err := r.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("recovery: failed to create recovery event", "error", err)
		}
	}

	// Publish event to subscribers
	r.eventBroker.Publish(pubsub.UpdatedEvent, event)

	return nil
}

// failTask marks a task as failed with a given reason.
func (r *RecoveryManager) failTask(ctx context.Context, taskID TaskID, reason string) error {
	// Create error JSON
	taskErr := TaskError{
		Message:   reason,
		Code:      "RECOVERY_FAILED",
		Retriable: false,
		FailedAt:  time.Now(),
	}
	errJSON, err := json.Marshal(taskErr)
	if err != nil {
		errJSON = []byte(fmt.Sprintf(`{"message":"%s"}`, reason))
	}

	// Update task status to failed
	err = r.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
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

	// Create recovery_failed event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "recovery_failed",
		Progress:  0,
		Message:   reason,
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("recovery: failed to convert event to db params", "error", err)
	} else {
		if _, err := r.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("recovery: failed to create recovery event", "error", err)
		}
	}

	// Publish event to subscribers
	r.eventBroker.Publish(pubsub.UpdatedEvent, event)

	return nil
}
