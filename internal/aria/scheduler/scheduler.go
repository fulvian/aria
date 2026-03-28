// Package scheduler provides the task scheduling system for ARIA,
// supporting immediate, scheduled, recurring, and dependent tasks.
//
// This package implements the scheduler interfaces defined in Blueprint Section 4.2.
package scheduler

import (
	"context"
	"time"
)

// TaskID is a unique identifier for a task.
type TaskID string

// TaskStatus represents the current status of a task.
type TaskStatus string

// Task status constants
const (
	TaskStatusCreated   TaskStatus = "created"
	TaskStatusQueued    TaskStatus = "queued"
	TaskStatusRunning   TaskStatus = "running"
	TaskStatusPaused    TaskStatus = "paused"
	TaskStatusCompleted TaskStatus = "completed"
	TaskStatusFailed    TaskStatus = "failed"
	TaskStatusCancelled TaskStatus = "cancelled"
	TaskStatusDeferred  TaskStatus = "deferred"
)

// TaskType represents the type of task.
type TaskType string

// Task type constants
const (
	TaskTypeImmediate  TaskType = "immediate"  // Execute now
	TaskTypeScheduled  TaskType = "scheduled"  // Execute at specific time
	TaskTypeRecurring  TaskType = "recurring"  // Repeat on schedule
	TaskTypeBackground TaskType = "background" // Low-priority background work
	TaskTypeDependent  TaskType = "dependent"  // Wait for dependencies
)

// Priority represents task priority.
type Priority int

// Priority constants
const (
	PriorityLow      Priority = 0
	PriorityNormal   Priority = 50
	PriorityHigh     Priority = 100
	PriorityCritical Priority = 200
)

// Task represents a unit of work to be scheduled and executed.
type Task struct {
	ID          TaskID
	Name        string
	Description string
	Type        TaskType
	Priority    Priority

	// Scheduling
	ScheduledAt *time.Time
	Deadline    *time.Time
	Schedule    *Schedule // For recurring tasks

	// Execution
	Agency string
	Agent  string
	Skills []string
	Params map[string]any

	// State
	Status    TaskStatus
	Progress  float64 // 0.0 - 1.0
	CreatedAt time.Time
	StartedAt *time.Time
	EndedAt   *time.Time

	// Dependencies
	DependsOn []TaskID
	Blocks    []TaskID

	// Results
	Result *TaskResult
	Error  *TaskError
}

// Schedule defines when a recurring task should run.
type Schedule struct {
	Type       ScheduleType
	Expression string // Cron expression or interval
	Timezone   string
	StartDate  *time.Time
	EndDate    *time.Time
}

// ScheduleType represents the type of schedule.
type ScheduleType string

// Schedule type constants
const (
	ScheduleCron     ScheduleType = "cron"
	ScheduleInterval ScheduleType = "interval"
	ScheduleSpecific ScheduleType = "specific_times"
)

// RecurringTask extends Task with recurring configuration.
type RecurringTask struct {
	Task
	Schedule Schedule
}

// TaskResult represents the result of a completed task.
type TaskResult struct {
	Output      map[string]any
	CompletedAt time.Time
}

// TaskError represents an error from a failed task.
type TaskError struct {
	Message   string
	Code      string
	Retriable bool
	FailedAt  time.Time
}

// TaskEvent represents events from task lifecycle.
type TaskEvent struct {
	TaskID    TaskID
	Type      string // created, started, progress, completed, failed, cancelled
	Progress  float64
	Message   string
	Timestamp time.Time
}

// TaskFilter represents filters for querying tasks.
type TaskFilter struct {
	Status          []TaskStatus
	Agency          string
	Agent           string
	Skill           string
	ScheduledBefore *time.Time
	ScheduledAfter  *time.Time
	Limit           int
	Offset          int
}

// Progress represents task progress information.
type Progress struct {
	TaskID      TaskID
	Status      TaskStatus
	Progress    float64
	CurrentStep string
	StepsTotal  int
	StepsDone   int
	EstimatedMs int64
}

// Scheduler manages task scheduling and execution.
//
// Reference: Blueprint Section 4.2
type Scheduler interface {
	// Task management
	Schedule(ctx context.Context, task Task) (TaskID, error)
	Cancel(ctx context.Context, taskID TaskID) error
	Pause(ctx context.Context, taskID TaskID) error
	Resume(ctx context.Context, taskID TaskID) error

	// Queries
	GetTask(ctx context.Context, taskID TaskID) (Task, error)
	ListTasks(ctx context.Context, filter TaskFilter) ([]Task, error)

	// Monitoring
	Subscribe(ctx context.Context) <-chan TaskEvent
	GetProgress(ctx context.Context, taskID TaskID) (Progress, error)

	// Recurring tasks
	ScheduleRecurring(ctx context.Context, task RecurringTask) (TaskID, error)
	UpdateSchedule(ctx context.Context, taskID TaskID, schedule Schedule) error
}
