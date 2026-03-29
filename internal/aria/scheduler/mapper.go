package scheduler

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/db"
)

// taskToDB converts a scheduler Task to database CreateTaskParams.
func taskToDB(task Task) (db.CreateTaskParams, error) {
	params := db.CreateTaskParams{
		ID:       string(task.ID),
		Name:     task.Name,
		Type:     string(task.Type),
		Priority: int64(task.Priority),
	}

	if task.Description != "" {
		params.Description = sql.NullString{String: task.Description, Valid: true}
	}

	if task.ScheduledAt != nil {
		params.ScheduledAt = sql.NullInt64{Int64: task.ScheduledAt.Unix(), Valid: true}
	}

	if task.Deadline != nil {
		params.Deadline = sql.NullInt64{Int64: task.Deadline.Unix(), Valid: true}
	}

	if task.Schedule != nil {
		scheduleJSON, err := json.Marshal(task.Schedule)
		if err != nil {
			return db.CreateTaskParams{}, fmt.Errorf("failed to marshal schedule: %w", err)
		}
		params.ScheduleExpr = sql.NullString{String: string(scheduleJSON), Valid: true}
	}

	if task.Agency != "" {
		params.Agency = sql.NullString{String: task.Agency, Valid: true}
	}

	if task.Agent != "" {
		params.Agent = sql.NullString{String: task.Agent, Valid: true}
	}

	if len(task.Skills) > 0 {
		skillsJSON, err := json.Marshal(task.Skills)
		if err != nil {
			return db.CreateTaskParams{}, fmt.Errorf("failed to marshal skills: %w", err)
		}
		params.Skills = sql.NullString{String: string(skillsJSON), Valid: true}
	}

	if len(task.Params) > 0 {
		paramsJSON, err := json.Marshal(task.Params)
		if err != nil {
			return db.CreateTaskParams{}, fmt.Errorf("failed to marshal parameters: %w", err)
		}
		params.Parameters = sql.NullString{String: string(paramsJSON), Valid: true}
	}

	return params, nil
}

// dbToTask converts a database Task to scheduler Task.
func dbToTask(dbTask db.Task) (Task, error) {
	task := Task{
		ID:       TaskID(dbTask.ID),
		Name:     dbTask.Name,
		Type:     TaskType(dbTask.Type),
		Priority: Priority(dbTask.Priority),
		Status:   TaskStatus(dbTask.Status),
		Progress: dbTask.Progress,
	}

	if dbTask.Description.Valid {
		task.Description = dbTask.Description.String
	}

	if dbTask.ScheduledAt.Valid {
		scheduledAt := time.Unix(dbTask.ScheduledAt.Int64, 0)
		task.ScheduledAt = &scheduledAt
	}

	if dbTask.Deadline.Valid {
		deadline := time.Unix(dbTask.Deadline.Int64, 0)
		task.Deadline = &deadline
	}

	if dbTask.ScheduleExpr.Valid && dbTask.ScheduleExpr.String != "" {
		var schedule Schedule
		if err := json.Unmarshal([]byte(dbTask.ScheduleExpr.String), &schedule); err != nil {
			// Fallback to zero value on corrupted JSON
			task.Schedule = nil
		} else {
			task.Schedule = &schedule
		}
	}

	if dbTask.Agency.Valid {
		task.Agency = dbTask.Agency.String
	}

	if dbTask.Agent.Valid {
		task.Agent = dbTask.Agent.String
	}

	if dbTask.Skills.Valid && dbTask.Skills.String != "" {
		if err := json.Unmarshal([]byte(dbTask.Skills.String), &task.Skills); err != nil {
			// Fallback to empty slice on corrupted JSON
			task.Skills = []string{}
		}
	} else {
		task.Skills = []string{}
	}

	if dbTask.Parameters.Valid && dbTask.Parameters.String != "" {
		if err := json.Unmarshal([]byte(dbTask.Parameters.String), &task.Params); err != nil {
			// Fallback to nil map on corrupted JSON
			task.Params = nil
		}
	} else {
		task.Params = nil
	}

	task.CreatedAt = time.Unix(dbTask.CreatedAt, 0)

	if dbTask.StartedAt.Valid {
		startedAt := time.Unix(dbTask.StartedAt.Int64, 0)
		task.StartedAt = &startedAt
	}

	if dbTask.CompletedAt.Valid {
		completedAt := time.Unix(dbTask.CompletedAt.Int64, 0)
		task.EndedAt = &completedAt
	}

	if dbTask.Result.Valid && dbTask.Result.String != "" {
		var result TaskResult
		if err := json.Unmarshal([]byte(dbTask.Result.String), &result); err != nil {
			// Fallback to nil on corrupted JSON
			task.Result = nil
		} else {
			task.Result = &result
		}
	}

	if dbTask.Error.Valid && dbTask.Error.String != "" {
		var taskErr TaskError
		if err := json.Unmarshal([]byte(dbTask.Error.String), &taskErr); err != nil {
			// Fallback to nil on corrupted JSON
			task.Error = nil
		} else {
			task.Error = &taskErr
		}
	}

	return task, nil
}

// taskEventToDB converts a scheduler TaskEvent to database CreateTaskEventParams.
func taskEventToDB(event TaskEvent) (db.CreateTaskEventParams, error) {
	params := db.CreateTaskEventParams{
		ID:        uuid.New().String(),
		TaskID:    string(event.TaskID),
		EventType: event.Type,
	}

	if event.Progress > 0 || event.Message != "" {
		eventData := struct {
			Progress float64 `json:"progress,omitempty"`
			Message  string  `json:"message,omitempty"`
		}{
			Progress: event.Progress,
			Message:  event.Message,
		}
		dataJSON, err := json.Marshal(eventData)
		if err != nil {
			return db.CreateTaskEventParams{}, fmt.Errorf("failed to marshal event data: %w", err)
		}
		params.EventData = sql.NullString{String: string(dataJSON), Valid: true}
	}

	return params, nil
}
