package scheduler

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/pubsub"
)

// ErrTaskNotFound is returned when a task is not found.
var ErrTaskNotFound = errors.New("task not found")

// ErrInvalidTask is returned when task validation fails.
var ErrInvalidTask = errors.New("invalid task")

// SchedulerService implements the Scheduler interface using database persistence.
type SchedulerService struct {
	db            db.Querier
	eventBroker   *pubsub.Broker[TaskEvent]
	maxConcurrent int
	mu            sync.RWMutex
	ctx           context.Context
	cancel        context.CancelFunc
}

// NewSchedulerService creates a new scheduler service.
func NewSchedulerService(dbQuerier db.Querier, maxConcurrent int) *SchedulerService {
	ctx, cancel := context.WithCancel(context.Background())
	return &SchedulerService{
		db:            dbQuerier,
		eventBroker:   pubsub.NewBroker[TaskEvent](),
		maxConcurrent: maxConcurrent,
		ctx:           ctx,
		cancel:        cancel,
	}
}

// Schedule creates a new task and persists it to the database.
func (s *SchedulerService) Schedule(ctx context.Context, task Task) (TaskID, error) {
	// Validate task
	if task.Name == "" {
		return "", fmt.Errorf("%w: name is required", ErrInvalidTask)
	}

	if task.Type == "" {
		task.Type = TaskTypeImmediate
	}

	if task.Priority < 0 {
		task.Priority = PriorityLow
	}
	if task.Priority > PriorityCritical {
		task.Priority = PriorityCritical
	}

	// Set default status
	task.Status = TaskStatusCreated

	// For immediate tasks without scheduled time, set to now
	if task.ScheduledAt == nil && task.Type == TaskTypeImmediate {
		now := time.Now()
		task.ScheduledAt = &now
	}

	// Generate ID if not set
	if task.ID == "" {
		task.ID = TaskID(uuid.New().String())
	}

	// Convert to DB params
	dbParams, err := taskToDB(task)
	if err != nil {
		return "", fmt.Errorf("failed to convert task to db params: %w", err)
	}

	// Insert task
	createdTask, err := s.db.CreateTask(ctx, dbParams)
	if err != nil {
		return "", fmt.Errorf("failed to create task: %w", err)
	}

	// Create created event
	event := TaskEvent{
		TaskID:    task.ID,
		Type:      "created",
		Progress:  0,
		Message:   "Task created",
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("failed to convert task event to db params", "error", err)
	} else {
		if _, err := s.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("failed to create task event", "error", err)
		}
	}

	// Publish event to subscribers
	s.eventBroker.Publish(pubsub.CreatedEvent, event)

	return TaskID(createdTask.ID), nil
}

// Cancel cancels a task.
func (s *SchedulerService) Cancel(ctx context.Context, taskID TaskID) error {
	// Check if task exists
	task, err := s.db.GetTaskByID(ctx, string(taskID))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return fmt.Errorf("cancel task: %w", ErrTaskNotFound)
		}
		return fmt.Errorf("cancel task: %w", err)
	}

	// Only allow cancelling tasks in valid states
	switch TaskStatus(task.Status) {
	case TaskStatusCompleted, TaskStatusFailed, TaskStatusCancelled:
		return fmt.Errorf("cannot cancel task in %s state", task.Status)
	}

	// Cancel the task
	if err := s.db.CancelTask(ctx, string(taskID)); err != nil {
		return fmt.Errorf("failed to cancel task: %w", err)
	}

	// Create cancelled event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "cancelled",
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("failed to convert task event to db params", "error", err)
	} else {
		if _, err := s.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("failed to create task event", "error", err)
		}
	}

	// Publish event
	s.eventBroker.Publish(pubsub.UpdatedEvent, event)

	return nil
}

// Pause pauses a task.
func (s *SchedulerService) Pause(ctx context.Context, taskID TaskID) error {
	// Get current task
	task, err := s.db.GetTaskByID(ctx, string(taskID))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return fmt.Errorf("pause task: %w", ErrTaskNotFound)
		}
		return fmt.Errorf("pause task: %w", err)
	}

	// Only allow pausing running tasks
	if TaskStatus(task.Status) != TaskStatusRunning {
		return fmt.Errorf("cannot pause task in %s state, only running tasks can be paused", task.Status)
	}

	// Update status to paused
	err = s.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusPaused),
		Progress: task.Progress,
		ID:       string(taskID),
	})
	if err != nil {
		return fmt.Errorf("failed to pause task: %w", err)
	}

	// Create paused event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "paused",
		Progress:  task.Progress,
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("failed to convert task event to db params", "error", err)
	} else {
		if _, err := s.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("failed to create task event", "error", err)
		}
	}

	// Publish event
	s.eventBroker.Publish(pubsub.UpdatedEvent, event)

	return nil
}

// Resume resumes a paused task.
func (s *SchedulerService) Resume(ctx context.Context, taskID TaskID) error {
	// Get current task
	task, err := s.db.GetTaskByID(ctx, string(taskID))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return fmt.Errorf("resume task: %w", ErrTaskNotFound)
		}
		return fmt.Errorf("resume task: %w", err)
	}

	// Only allow resuming paused tasks
	if TaskStatus(task.Status) != TaskStatusPaused {
		return fmt.Errorf("cannot resume task in %s state, only paused tasks can be resumed", task.Status)
	}

	// Update status back to queued
	err = s.db.UpdateTaskStatus(ctx, db.UpdateTaskStatusParams{
		Status:   string(TaskStatusQueued),
		Progress: task.Progress,
		ID:       string(taskID),
	})
	if err != nil {
		return fmt.Errorf("failed to resume task: %w", err)
	}

	// Create resumed event
	event := TaskEvent{
		TaskID:    taskID,
		Type:      "resumed",
		Progress:  task.Progress,
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("failed to convert task event to db params", "error", err)
	} else {
		if _, err := s.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("failed to create task event", "error", err)
		}
	}

	// Publish event
	s.eventBroker.Publish(pubsub.UpdatedEvent, event)

	return nil
}

// GetTask retrieves a task by ID.
func (s *SchedulerService) GetTask(ctx context.Context, taskID TaskID) (Task, error) {
	dbTask, err := s.db.GetTaskByID(ctx, string(taskID))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return Task{}, fmt.Errorf("get task: %w", ErrTaskNotFound)
		}
		return Task{}, fmt.Errorf("failed to get task: %w", err)
	}

	task, err := dbToTask(dbTask)
	if err != nil {
		return Task{}, fmt.Errorf("failed to convert db task: %w", err)
	}

	// Load dependencies
	dependencies, err := s.db.GetTaskDependencies(ctx, string(taskID))
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		logging.Error("failed to get task dependencies", "error", err)
	}
	task.DependsOn = make([]TaskID, 0, len(dependencies))
	for _, dep := range dependencies {
		task.DependsOn = append(task.DependsOn, TaskID(dep.ID))
	}

	return task, nil
}

// ListTasks retrieves tasks based on filters.
func (s *SchedulerService) ListTasks(ctx context.Context, filter TaskFilter) ([]Task, error) {
	// Set defaults
	limit := int64(filter.Limit)
	if limit <= 0 {
		limit = 50
	}
	if limit > 100 {
		limit = 100
	}

	offset := int64(filter.Offset)
	if offset < 0 {
		offset = 0
	}

	var dbTasks []db.Task
	var err error

	// Apply filters
	if len(filter.Status) == 1 {
		dbTasks, err = s.db.ListTasksByStatus(ctx, db.ListTasksByStatusParams{
			Status: string(filter.Status[0]),
			Limit:  limit,
			Offset: offset,
		})
	} else if filter.Agency != "" {
		dbTasks, err = s.db.ListTasksByAgency(ctx, db.ListTasksByAgencyParams{
			Agency: sql.NullString{String: filter.Agency, Valid: true},
			Limit:  limit,
			Offset: offset,
		})
	} else {
		dbTasks, err = s.db.ListTasks(ctx, db.ListTasksParams{
			Limit:  limit,
			Offset: offset,
		})
	}

	if err != nil {
		return nil, fmt.Errorf("failed to list tasks: %w", err)
	}

	tasks := make([]Task, 0, len(dbTasks))
	for _, dbTask := range dbTasks {
		task, err := dbToTask(dbTask)
		if err != nil {
			logging.Error("failed to convert db task", "error", err)
			continue
		}

		// Apply additional filters
		if filter.Skill != "" && !containsSkill(task.Skills, filter.Skill) {
			continue
		}
		if filter.ScheduledBefore != nil {
			if task.ScheduledAt == nil || task.ScheduledAt.After(*filter.ScheduledBefore) {
				continue
			}
		}
		if filter.ScheduledAfter != nil {
			if task.ScheduledAt == nil || task.ScheduledAt.Before(*filter.ScheduledAfter) {
				continue
			}
		}
		if len(filter.Status) > 1 {
			if !containsStatus(filter.Status, task.Status) {
				continue
			}
		}

		tasks = append(tasks, task)
	}

	return tasks, nil
}

// Subscribe returns a channel that receives task events.
func (s *SchedulerService) Subscribe(ctx context.Context) <-chan TaskEvent {
	// Create adapter to convert from pubsub.Event[TaskEvent] to TaskEvent
	out := make(chan TaskEvent, 64)
	go func() {
		defer close(out)
		for {
			select {
			case <-ctx.Done():
				return
			case event, ok := <-s.eventBroker.Subscribe(ctx):
				if !ok {
					return
				}
				select {
				case out <- event.Payload:
				case <-ctx.Done():
					return
				}
			}
		}
	}()
	return out
}

// GetProgress returns progress information for a task.
func (s *SchedulerService) GetProgress(ctx context.Context, taskID TaskID) (Progress, error) {
	task, err := s.GetTask(ctx, taskID)
	if err != nil {
		return Progress{}, err
	}

	progress := Progress{
		TaskID:      taskID,
		Status:      task.Status,
		Progress:    task.Progress,
		CurrentStep: "",
		StepsTotal:  0,
		StepsDone:   0,
	}

	// Estimate remaining time based on progress
	if task.Progress > 0 && task.Progress < 1 {
		if task.StartedAt != nil {
			elapsed := time.Since(*task.StartedAt)
			totalEstimate := time.Duration(float64(elapsed) / task.Progress)
			remaining := totalEstimate - elapsed
			progress.EstimatedMs = remaining.Milliseconds()
		}
	}

	// Set current step based on status
	switch task.Status {
	case TaskStatusCreated:
		progress.CurrentStep = "Waiting to be queued"
	case TaskStatusQueued:
		progress.CurrentStep = "Queued for execution"
	case TaskStatusRunning:
		progress.CurrentStep = "Executing"
		progress.StepsTotal = 10
		progress.StepsDone = int(task.Progress * 10)
	case TaskStatusPaused:
		progress.CurrentStep = "Paused"
	case TaskStatusCompleted:
		progress.CurrentStep = "Completed"
		progress.StepsTotal = 10
		progress.StepsDone = 10
	case TaskStatusFailed:
		progress.CurrentStep = "Failed"
	case TaskStatusCancelled:
		progress.CurrentStep = "Cancelled"
	}

	return progress, nil
}

// ScheduleRecurring creates a recurring task.
func (s *SchedulerService) ScheduleRecurring(ctx context.Context, task RecurringTask) (TaskID, error) {
	// Validate schedule
	if task.Schedule.Type == "" {
		return "", fmt.Errorf("%w: schedule type is required", ErrInvalidTask)
	}
	if task.Schedule.Expression == "" {
		return "", fmt.Errorf("%w: schedule expression is required", ErrInvalidTask)
	}

	// Set type to recurring
	task.Task.Type = TaskTypeRecurring

	// Store schedule expression
	scheduleJSON, err := json.Marshal(task.Schedule)
	if err != nil {
		return "", fmt.Errorf("failed to marshal schedule: %w", err)
	}
	task.Task.Schedule = &Schedule{
		Type:       task.Schedule.Type,
		Expression: task.Schedule.Expression,
		Timezone:   task.Schedule.Timezone,
		StartDate:  task.Schedule.StartDate,
		EndDate:    task.Schedule.EndDate,
	}

	// Use the embedded task's Schedule field to store serialized schedule
	// This is a bit of a hack since taskToDB expects a *Schedule
	task.Task.ID = TaskID(uuid.New().String())

	dbParams, err := taskToDB(task.Task)
	if err != nil {
		return "", fmt.Errorf("failed to convert recurring task to db params: %w", err)
	}

	// Override the schedule_expr with our JSON
	dbParams.ScheduleExpr = sql.NullString{String: string(scheduleJSON), Valid: true}

	createdTask, err := s.db.CreateTask(ctx, dbParams)
	if err != nil {
		return "", fmt.Errorf("failed to create recurring task: %w", err)
	}

	// Create created event
	event := TaskEvent{
		TaskID:    TaskID(createdTask.ID),
		Type:      "created",
		Progress:  0,
		Message:   "Recurring task created",
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("failed to convert task event to db params", "error", err)
	} else {
		if _, err := s.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("failed to create task event", "error", err)
		}
	}

	// Publish event
	s.eventBroker.Publish(pubsub.CreatedEvent, event)

	return TaskID(createdTask.ID), nil
}

// UpdateSchedule updates the schedule for a recurring task.
func (s *SchedulerService) UpdateSchedule(ctx context.Context, taskID TaskID, schedule Schedule) error {
	// Get existing task
	task, err := s.GetTask(ctx, taskID)
	if err != nil {
		return err
	}

	if task.Type != TaskTypeRecurring {
		return fmt.Errorf("%w: task is not recurring", ErrInvalidTask)
	}

	// Validate schedule
	if schedule.Type == "" {
		return fmt.Errorf("%w: schedule type is required", ErrInvalidTask)
	}
	if schedule.Expression == "" {
		return fmt.Errorf("%w: schedule expression is required", ErrInvalidTask)
	}

	// Note: Full schedule_expr update requires a DB migration and additional query.
	// The current implementation validates the input but cannot persist the changes
	// until FASE 3.4 or a follow-up migration.
	// For now, we log the intended update.
	logging.Info("schedule update validated",
		"task_id", taskID,
		"schedule_type", schedule.Type,
		"schedule_expr", schedule.Expression)

	return nil
}

// GetEventBroker returns the event broker for the scheduler.
func (s *SchedulerService) GetEventBroker() *pubsub.Broker[TaskEvent] {
	return s.eventBroker
}

// Shutdown gracefully shuts down the scheduler.
func (s *SchedulerService) Shutdown() {
	s.cancel()
	s.eventBroker.Shutdown()
}

// Helper functions

func containsSkill(skills []string, skill string) bool {
	for _, s := range skills {
		if s == skill {
			return true
		}
	}
	return false
}

func containsStatus(statuses []TaskStatus, status TaskStatus) bool {
	for _, s := range statuses {
		if s == status {
			return true
		}
	}
	return false
}
