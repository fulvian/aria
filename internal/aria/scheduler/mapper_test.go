package scheduler

import (
	"database/sql"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/db"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTaskToDB(t *testing.T) {
	t.Run("basic task conversion", func(t *testing.T) {
		scheduledAt := time.Date(2026, 3, 28, 18, 0, 0, 0, time.UTC)
		deadline := time.Date(2026, 3, 28, 20, 0, 0, 0, time.UTC)

		task := Task{
			ID:          "test-task-123",
			Name:        "Test Task",
			Description: "A test task description",
			Type:        TaskTypeScheduled,
			Priority:    PriorityHigh,
			ScheduledAt: &scheduledAt,
			Deadline:    &deadline,
			Agency:      "test-agency",
			Agent:       "test-agent",
			Skills:      []string{"skill1", "skill2"},
			Params:      map[string]any{"key": "value"},
		}

		params, err := taskToDB(task)
		require.NoError(t, err)

		assert.Equal(t, "test-task-123", params.ID)
		assert.Equal(t, "Test Task", params.Name)
		assert.Equal(t, "A test task description", params.Description.String)
		assert.True(t, params.Description.Valid)
		assert.Equal(t, "scheduled", params.Type)
		assert.Equal(t, int64(100), params.Priority)
		assert.Equal(t, scheduledAt.Unix(), params.ScheduledAt.Int64)
		assert.True(t, params.ScheduledAt.Valid)
		assert.Equal(t, deadline.Unix(), params.Deadline.Int64)
		assert.True(t, params.Deadline.Valid)
		assert.Equal(t, "test-agency", params.Agency.String)
		assert.True(t, params.Agency.Valid)
		assert.Equal(t, "test-agent", params.Agent.String)
		assert.True(t, params.Agent.Valid)
		assert.True(t, params.Skills.Valid)
		assert.True(t, params.Parameters.Valid)
	})

	t.Run("task with empty optional fields", func(t *testing.T) {
		task := Task{
			ID:       "test-task-456",
			Name:     "Minimal Task",
			Type:     TaskTypeImmediate,
			Priority: PriorityNormal,
		}

		params, err := taskToDB(task)
		require.NoError(t, err)

		assert.Equal(t, "test-task-456", params.ID)
		assert.Equal(t, "Minimal Task", params.Name)
		assert.False(t, params.Description.Valid)
		assert.Equal(t, "immediate", params.Type)
		assert.Equal(t, int64(50), params.Priority)
		assert.False(t, params.ScheduledAt.Valid)
		assert.False(t, params.Deadline.Valid)
		assert.False(t, params.Agency.Valid)
		assert.False(t, params.Agent.Valid)
		assert.False(t, params.Skills.Valid)
		assert.False(t, params.Parameters.Valid)
	})

	t.Run("task with schedule", func(t *testing.T) {
		schedule := Schedule{
			Type:       ScheduleCron,
			Expression: "0 * * * *",
			Timezone:   "UTC",
		}
		task := Task{
			ID:       "recurring-task-1",
			Name:     "Recurring Task",
			Type:     TaskTypeRecurring,
			Schedule: &schedule,
		}

		params, err := taskToDB(task)
		require.NoError(t, err)

		assert.True(t, params.ScheduleExpr.Valid)
		assert.Contains(t, params.ScheduleExpr.String, `"Type":"cron"`)
		assert.Contains(t, params.ScheduleExpr.String, `"Expression":"0 * * * *"`)
	})
}

func TestDBToTask(t *testing.T) {
	t.Run("basic db task conversion", func(t *testing.T) {
		now := time.Now().Unix()
		dbTask := db.Task{
			ID:          "db-task-123",
			Name:        "DB Task",
			Description: sql.NullString{String: "A DB task", Valid: true},
			Type:        "scheduled",
			Priority:    int64(100),
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
			Deadline:    sql.NullInt64{Int64: now + 3600, Valid: true},
			Agency:      sql.NullString{String: "agency1", Valid: true},
			Agent:       sql.NullString{String: "agent1", Valid: true},
			Skills:      sql.NullString{String: `["skill1","skill2"]`, Valid: true},
			Parameters:  sql.NullString{String: `{"key":"value"}`, Valid: true},
			Status:      "running",
			Progress:    0.5,
			CreatedAt:   now,
			StartedAt:   sql.NullInt64{Int64: now + 60, Valid: true},
			CompletedAt: sql.NullInt64{Int64: 0, Valid: false},
		}

		task, err := dbToTask(dbTask)
		require.NoError(t, err)

		assert.Equal(t, TaskID("db-task-123"), task.ID)
		assert.Equal(t, "DB Task", task.Name)
		assert.Equal(t, "A DB task", task.Description)
		assert.Equal(t, TaskTypeScheduled, task.Type)
		assert.Equal(t, Priority(100), task.Priority)
		assert.NotNil(t, task.ScheduledAt)
		assert.Equal(t, now, task.ScheduledAt.Unix())
		assert.NotNil(t, task.Deadline)
		assert.Equal(t, "agency1", task.Agency)
		assert.Equal(t, "agent1", task.Agent)
		assert.Equal(t, []string{"skill1", "skill2"}, task.Skills)
		assert.Equal(t, map[string]any{"key": "value"}, task.Params)
		assert.Equal(t, TaskStatusRunning, task.Status)
		assert.Equal(t, 0.5, task.Progress)
		assert.NotNil(t, task.StartedAt)
		assert.Nil(t, task.EndedAt)
	})

	t.Run("db task with null optional fields", func(t *testing.T) {
		dbTask := db.Task{
			ID:        "db-task-minimal",
			Name:      "Minimal DB Task",
			Type:      "immediate",
			Priority:  int64(50),
			Status:    "created",
			Progress:  0,
			CreatedAt: time.Now().Unix(),
		}

		task, err := dbToTask(dbTask)
		require.NoError(t, err)

		assert.Equal(t, TaskID("db-task-minimal"), task.ID)
		assert.Equal(t, "Minimal DB Task", task.Name)
		assert.Equal(t, "", task.Description)
		assert.Equal(t, TaskTypeImmediate, task.Type)
		assert.Equal(t, PriorityNormal, task.Priority)
		assert.Nil(t, task.ScheduledAt)
		assert.Nil(t, task.Deadline)
		assert.Equal(t, "", task.Agency)
		assert.Equal(t, "", task.Agent)
		assert.Equal(t, []string{}, task.Skills)
		assert.Nil(t, task.Params)
		assert.Equal(t, TaskStatusCreated, task.Status)
		assert.Nil(t, task.StartedAt)
		assert.Nil(t, task.EndedAt)
	})

	t.Run("db task with corrupted JSON falls back gracefully", func(t *testing.T) {
		dbTask := db.Task{
			ID:         "db-task-corrupted",
			Name:       "Corrupted JSON Task",
			Type:       "immediate",
			Priority:   int64(50),
			Status:     "created",
			Progress:   0,
			CreatedAt:  time.Now().Unix(),
			Skills:     sql.NullString{String: "not valid json", Valid: true},
			Parameters: sql.NullString{String: `{bad json`, Valid: true},
			Result:     sql.NullString{String: "also bad", Valid: true},
			Error:      sql.NullString{String: "also bad", Valid: true},
		}

		task, err := dbToTask(dbTask)
		require.NoError(t, err)

		// Should fall back to zero values
		assert.Equal(t, []string{}, task.Skills)
		assert.Nil(t, task.Params)
		assert.Nil(t, task.Result)
		assert.Nil(t, task.Error)
	})

	t.Run("db task with empty JSON strings", func(t *testing.T) {
		dbTask := db.Task{
			ID:         "db-task-empty",
			Name:       "Empty JSON Task",
			Type:       "immediate",
			Priority:   int64(50),
			Status:     "created",
			Progress:   0,
			CreatedAt:  time.Now().Unix(),
			Skills:     sql.NullString{String: "", Valid: true},
			Parameters: sql.NullString{String: "", Valid: true},
			Result:     sql.NullString{String: "", Valid: true},
			Error:      sql.NullString{String: "", Valid: true},
		}

		task, err := dbToTask(dbTask)
		require.NoError(t, err)

		assert.Equal(t, []string{}, task.Skills)
		assert.Nil(t, task.Params)
		assert.Nil(t, task.Result)
		assert.Nil(t, task.Error)
	})

	t.Run("db task with result and error", func(t *testing.T) {
		completedAt := time.Now().Unix()
		dbTask := db.Task{
			ID:          "db-task-result",
			Name:        "Task with Result",
			Type:        "immediate",
			Priority:    int64(50),
			Status:      "completed",
			Progress:    1.0,
			CreatedAt:   time.Now().Unix() - 3600,
			CompletedAt: sql.NullInt64{Int64: completedAt, Valid: true},
			Result:      sql.NullString{String: `{"output":{"value":42},"completedAt":"2026-03-28T17:00:00Z"}`, Valid: true},
		}

		task, err := dbToTask(dbTask)
		require.NoError(t, err)

		assert.NotNil(t, task.Result)
		assert.NotNil(t, task.EndedAt) // EndedAt is derived from CompletedAt
		assert.Equal(t, 1.0, task.Progress)
	})

	t.Run("db task with task error", func(t *testing.T) {
		dbTask := db.Task{
			ID:        "db-task-error",
			Name:      "Failed Task",
			Type:      "immediate",
			Priority:  int64(50),
			Status:    "failed",
			Progress:  0.3,
			CreatedAt: time.Now().Unix() - 3600,
			Error:     sql.NullString{String: `{"message":"something went wrong","code":"ERR_001","retriable":true,"failedAt":"2026-03-28T17:00:00Z"}`, Valid: true},
		}

		task, err := dbToTask(dbTask)
		require.NoError(t, err)

		assert.NotNil(t, task.Error)
		assert.Equal(t, "something went wrong", task.Error.Message)
		assert.Equal(t, "ERR_001", task.Error.Code)
		assert.True(t, task.Error.Retriable)
	})
}

func TestTaskEventToDB(t *testing.T) {
	t.Run("basic event conversion", func(t *testing.T) {
		event := TaskEvent{
			TaskID:    "task-event-123",
			Type:      "started",
			Progress:  0.5,
			Message:   "Task started",
			Timestamp: time.Now(),
		}

		params, err := taskEventToDB(event)
		require.NoError(t, err)

		assert.NotEmpty(t, params.ID)
		assert.Equal(t, "task-event-123", params.TaskID)
		assert.Equal(t, "started", params.EventType)
		assert.True(t, params.EventData.Valid)
		assert.Contains(t, params.EventData.String, `"progress":0.5`)
		assert.Contains(t, params.EventData.String, `"message":"Task started"`)
	})

	t.Run("event without optional fields", func(t *testing.T) {
		event := TaskEvent{
			TaskID:    "task-event-456",
			Type:      "created",
			Timestamp: time.Now(),
		}

		params, err := taskEventToDB(event)
		require.NoError(t, err)

		assert.NotEmpty(t, params.ID)
		assert.Equal(t, "task-event-456", params.TaskID)
		assert.Equal(t, "created", params.EventType)
		assert.False(t, params.EventData.Valid)
	})

	t.Run("event with only progress", func(t *testing.T) {
		event := TaskEvent{
			TaskID:    "task-event-789",
			Type:      "progress",
			Progress:  0.75,
			Timestamp: time.Now(),
		}

		params, err := taskEventToDB(event)
		require.NoError(t, err)

		assert.True(t, params.EventData.Valid)
		assert.Contains(t, params.EventData.String, `"progress":0.75`)
	})
}
