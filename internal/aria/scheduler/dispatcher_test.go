package scheduler

import (
	"context"
	"database/sql"
	"sync"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/pubsub"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockDB is a minimal mock implementing db.Querier for dispatcher tests
type mockDB struct {
	mu           sync.Mutex
	tasks        map[string]db.Task
	dependencies map[string][]string // taskID -> dependsOn IDs
	events       []db.TaskEvent
}

func newMockDB() *mockDB {
	return &mockDB{
		tasks:        make(map[string]db.Task),
		dependencies: make(map[string][]string),
	}
}

func (m *mockDB) CreateTask(ctx context.Context, arg db.CreateTaskParams) (db.Task, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	task := db.Task{
		ID:       arg.ID,
		Name:     arg.Name,
		Type:     arg.Type,
		Priority: arg.Priority,
		Status:   "created",
	}
	if arg.Description.Valid {
		task.Description = arg.Description
	}
	if arg.ScheduledAt.Valid {
		task.ScheduledAt = arg.ScheduledAt
	}
	m.tasks[arg.ID] = task
	return task, nil
}

func (m *mockDB) GetTaskByID(ctx context.Context, id string) (db.Task, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	task, ok := m.tasks[id]
	if !ok {
		return db.Task{}, sql.ErrNoRows
	}
	return task, nil
}

func (m *mockDB) ListPendingTasks(ctx context.Context, arg db.ListPendingTasksParams) ([]db.Task, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	var result []db.Task
	now := time.Now().Unix()
	for _, task := range m.tasks {
		if task.Status == arg.Status || task.Status == arg.Status_2 {
			if !arg.ScheduledAt.Valid || (task.ScheduledAt.Valid && task.ScheduledAt.Int64 <= now) {
				result = append(result, task)
			}
		}
	}
	return result, nil
}

func (m *mockDB) CountTasksByStatus(ctx context.Context, status string) (int64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	var count int64
	for _, task := range m.tasks {
		if task.Status == status {
			count++
		}
	}
	return count, nil
}

func (m *mockDB) CountEpisodesByOutcome(ctx context.Context, arg db.CountEpisodesByOutcomeParams) (db.CountEpisodesByOutcomeRow, error) {
	return db.CountEpisodesByOutcomeRow{}, nil
}

func (m *mockDB) GetTaskDependencies(ctx context.Context, taskID string) ([]db.Task, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	depIDs, ok := m.dependencies[taskID]
	if !ok {
		return nil, sql.ErrNoRows
	}
	var result []db.Task
	for _, id := range depIDs {
		if task, ok := m.tasks[id]; ok {
			result = append(result, task)
		}
	}
	return result, nil
}

func (m *mockDB) UpdateTaskStatus(ctx context.Context, arg db.UpdateTaskStatusParams) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	task, ok := m.tasks[arg.ID]
	if !ok {
		return sql.ErrNoRows
	}
	task.Status = arg.Status
	if arg.Progress > 0 {
		task.Progress = arg.Progress
	}
	if arg.Error.Valid {
		task.Error = arg.Error
	}
	m.tasks[arg.ID] = task
	return nil
}

func (m *mockDB) CreateTaskEvent(ctx context.Context, arg db.CreateTaskEventParams) (db.TaskEvent, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	event := db.TaskEvent{
		ID:        arg.ID,
		TaskID:    arg.TaskID,
		EventType: arg.EventType,
	}
	m.events = append(m.events, event)
	return event, nil
}

// AddTaskDependency adds a dependency between two tasks
func (m *mockDB) AddTaskDependency(ctx context.Context, arg db.AddTaskDependencyParams) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.dependencies[arg.TaskID] = append(m.dependencies[arg.TaskID], arg.DependsOn)
	return nil
}

// SetTaskStatus directly sets a task status (for test setup)
func (m *mockDB) SetTaskStatus(taskID, status string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if task, ok := m.tasks[taskID]; ok {
		task.Status = status
		m.tasks[taskID] = task
	}
}

// Unused methods to satisfy interface - these won't be called in our tests
func (m *mockDB) CancelTask(ctx context.Context, id string) error { return nil }
func (m *mockDB) CreateAgency(ctx context.Context, arg db.CreateAgencyParams) (db.Agency, error) {
	return db.Agency{}, nil
}
func (m *mockDB) CreateEpisode(ctx context.Context, arg db.CreateEpisodeParams) (db.Episode, error) {
	return db.Episode{}, nil
}
func (m *mockDB) CreateFact(ctx context.Context, arg db.CreateFactParams) (db.Fact, error) {
	return db.Fact{}, nil
}
func (m *mockDB) CreateFile(ctx context.Context, arg db.CreateFileParams) (db.File, error) {
	return db.File{}, nil
}
func (m *mockDB) CreateMessage(ctx context.Context, arg db.CreateMessageParams) (db.Message, error) {
	return db.Message{}, nil
}
func (m *mockDB) CreateProcedure(ctx context.Context, arg db.CreateProcedureParams) (db.Procedure, error) {
	return db.Procedure{}, nil
}
func (m *mockDB) CreateSession(ctx context.Context, arg db.CreateSessionParams) (db.Session, error) {
	return db.Session{}, nil
}
func (m *mockDB) DeleteAgency(ctx context.Context, id string) error                 { return nil }
func (m *mockDB) DeleteEpisode(ctx context.Context, id string) error                { return nil }
func (m *mockDB) DeleteFact(ctx context.Context, id string) error                   { return nil }
func (m *mockDB) DeleteFile(ctx context.Context, id string) error                   { return nil }
func (m *mockDB) DeleteMessage(ctx context.Context, id string) error                { return nil }
func (m *mockDB) DeleteOldEpisodes(ctx context.Context, createdAt int64) error      { return nil }
func (m *mockDB) DeleteProcedure(ctx context.Context, id string) error              { return nil }
func (m *mockDB) DeleteSession(ctx context.Context, id string) error                { return nil }
func (m *mockDB) DeleteSessionFiles(ctx context.Context, sessionID string) error    { return nil }
func (m *mockDB) DeleteSessionMessages(ctx context.Context, sessionID string) error { return nil }
func (m *mockDB) DeleteTask(ctx context.Context, id string) error                   { return nil }
func (m *mockDB) DeleteExpiredContexts(ctx context.Context) error                   { return nil }
func (m *mockDB) DeleteWorkingContext(ctx context.Context, sessionID string) error  { return nil }
func (m *mockDB) GetWorkingContext(ctx context.Context, sessionID string) (db.WorkingMemoryContext, error) {
	return db.WorkingMemoryContext{}, sql.ErrNoRows
}
func (m *mockDB) SaveWorkingContext(ctx context.Context, arg db.SaveWorkingContextParams) (db.WorkingMemoryContext, error) {
	return db.WorkingMemoryContext{}, nil
}
func (m *mockDB) GetAgencyByID(ctx context.Context, id string) (db.Agency, error) {
	return db.Agency{}, nil
}
func (m *mockDB) GetAgencyByName(ctx context.Context, name string) (db.Agency, error) {
	return db.Agency{}, nil
}
func (m *mockDB) GetDependentTasks(ctx context.Context, dependsOn string) ([]db.Task, error) {
	return nil, nil
}
func (m *mockDB) GetEpisodeByID(ctx context.Context, id string) (db.Episode, error) {
	return db.Episode{}, nil
}
func (m *mockDB) GetFactByID(ctx context.Context, id string) (db.Fact, error) { return db.Fact{}, nil }
func (m *mockDB) GetFile(ctx context.Context, id string) (db.File, error)     { return db.File{}, nil }
func (m *mockDB) GetFileByPathAndSession(ctx context.Context, arg db.GetFileByPathAndSessionParams) (db.File, error) {
	return db.File{}, nil
}
func (m *mockDB) GetMessage(ctx context.Context, id string) (db.Message, error) {
	return db.Message{}, nil
}
func (m *mockDB) GetProcedureByID(ctx context.Context, id string) (db.Procedure, error) {
	return db.Procedure{}, nil
}
func (m *mockDB) GetProcedureByName(ctx context.Context, name string) (db.Procedure, error) {
	return db.Procedure{}, nil
}
func (m *mockDB) GetRecentTaskEvents(ctx context.Context, limit int64) ([]db.TaskEvent, error) {
	return nil, nil
}
func (m *mockDB) GetSessionByID(ctx context.Context, id string) (db.Session, error) {
	return db.Session{}, nil
}
func (m *mockDB) GetTaskEvents(ctx context.Context, taskID string) ([]db.TaskEvent, error) {
	return nil, nil
}
func (m *mockDB) IncrementFactUsage(ctx context.Context, id string) error { return nil }
func (m *mockDB) ListAgencies(ctx context.Context) ([]db.Agency, error)   { return nil, nil }
func (m *mockDB) ListAgenciesByStatus(ctx context.Context, status string) ([]db.Agency, error) {
	return nil, nil
}
func (m *mockDB) ListEpisodes(ctx context.Context, arg db.ListEpisodesParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) ListEpisodesByAgency(ctx context.Context, arg db.ListEpisodesByAgencyParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) ListEpisodesBySession(ctx context.Context, arg db.ListEpisodesBySessionParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) ListFactsByCategory(ctx context.Context, category sql.NullString) ([]db.Fact, error) {
	return nil, nil
}
func (m *mockDB) ListFactsByDomain(ctx context.Context, domain string) ([]db.Fact, error) {
	return nil, nil
}
func (m *mockDB) ListFilesByPath(ctx context.Context, path string) ([]db.File, error) {
	return nil, nil
}
func (m *mockDB) ListFilesBySession(ctx context.Context, sessionID string) ([]db.File, error) {
	return nil, nil
}
func (m *mockDB) ListLatestSessionFiles(ctx context.Context, sessionID string) ([]db.File, error) {
	return nil, nil
}
func (m *mockDB) ListMessagesBySession(ctx context.Context, sessionID string) ([]db.Message, error) {
	return nil, nil
}
func (m *mockDB) ListNewFiles(ctx context.Context) ([]db.File, error)        { return nil, nil }
func (m *mockDB) ListProcedures(ctx context.Context) ([]db.Procedure, error) { return nil, nil }
func (m *mockDB) ListProceduresByTrigger(ctx context.Context, triggerType string) ([]db.Procedure, error) {
	return nil, nil
}
func (m *mockDB) ListTasks(ctx context.Context, arg db.ListTasksParams) ([]db.Task, error) {
	return nil, nil
}
func (m *mockDB) ListTasksByAgency(ctx context.Context, arg db.ListTasksByAgencyParams) ([]db.Task, error) {
	return nil, nil
}
func (m *mockDB) ListTasksByStatus(ctx context.Context, arg db.ListTasksByStatusParams) ([]db.Task, error) {
	return nil, nil
}
func (m *mockDB) ListSessions(ctx context.Context) ([]db.Session, error) {
	return nil, nil
}
func (m *mockDB) RemoveTaskDependency(ctx context.Context, arg db.RemoveTaskDependencyParams) error {
	return nil
}
func (m *mockDB) SearchEpisodes(ctx context.Context, arg db.SearchEpisodesParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) SearchEpisodesByAgent(ctx context.Context, arg db.SearchEpisodesByAgentParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) SearchEpisodesByTimeRange(ctx context.Context, arg db.SearchEpisodesByTimeRangeParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) SearchEpisodesFull(ctx context.Context, arg db.SearchEpisodesFullParams) ([]db.Episode, error) {
	return nil, nil
}
func (m *mockDB) SearchFacts(ctx context.Context, arg db.SearchFactsParams) ([]db.Fact, error) {
	return nil, nil
}
func (m *mockDB) SearchProcedures(ctx context.Context, arg db.SearchProceduresParams) ([]db.Procedure, error) {
	return nil, nil
}
func (m *mockDB) UpdateAgencyStatus(ctx context.Context, arg db.UpdateAgencyStatusParams) error {
	return nil
}
func (m *mockDB) UpdateFactConfidence(ctx context.Context, arg db.UpdateFactConfidenceParams) error {
	return nil
}
func (m *mockDB) UpdateFile(ctx context.Context, arg db.UpdateFileParams) (db.File, error) {
	return db.File{}, nil
}
func (m *mockDB) UpdateMessage(ctx context.Context, arg db.UpdateMessageParams) error { return nil }
func (m *mockDB) UpdateProcedureStats(ctx context.Context, arg db.UpdateProcedureStatsParams) error {
	return nil
}
func (m *mockDB) UpdateSession(ctx context.Context, arg db.UpdateSessionParams) (db.Session, error) {
	return db.Session{}, nil
}
func (m *mockDB) UpdateTaskProgress(ctx context.Context, arg db.UpdateTaskProgressParams) error {
	return nil
}
func (m *mockDB) UpdateTaskScheduleExpr(ctx context.Context, arg db.UpdateTaskScheduleExprParams) error {
	return nil
}
func (m *mockDB) DeleteAgencyState(ctx context.Context, agencyID string) error {
	return nil
}
func (m *mockDB) GetAgencyState(ctx context.Context, agencyID string) (db.AgencyState, error) {
	return db.AgencyState{}, nil
}
func (m *mockDB) UpsertAgencyState(ctx context.Context, arg db.UpsertAgencyStateParams) (db.AgencyState, error) {
	return db.AgencyState{}, nil
}

// testSchedulerService creates a scheduler service with a mock DB for testing
func newTestSchedulerService(mock db.Querier, maxConcurrent int) *SchedulerService {
	ctx, cancel := context.WithCancel(context.Background())
	return &SchedulerService{
		db:            mock,
		eventBroker:   pubsub.NewBroker[TaskEvent](),
		maxConcurrent: maxConcurrent,
		ctx:           ctx,
		cancel:        cancel,
	}
}

func TestDispatcher_PromoteEligibleTasks(t *testing.T) {
	t.Run("should promote task with no dependencies", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a task
		now := time.Now().Unix()
		mock.tasks["task-1"] = db.Task{
			ID:          "task-1",
			Name:        "Test Task",
			Type:        "immediate",
			Priority:    50,
			Status:      "created",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		err := d.promoteEligibleTasks(context.Background())
		require.NoError(t, err)

		// Verify task was promoted to queued
		task := mock.tasks["task-1"]
		assert.Equal(t, "queued", task.Status)
	})

	t.Run("should not promote task with unmet dependencies", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		now := time.Now().Unix()
		// Create two tasks - task-2 depends on task-1
		mock.tasks["task-1"] = db.Task{
			ID:          "task-1",
			Name:        "Dependency Task",
			Type:        "immediate",
			Priority:    50,
			Status:      "created",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		mock.tasks["task-2"] = db.Task{
			ID:          "task-2",
			Name:        "Dependent Task",
			Type:        "dependent",
			Priority:    50,
			Status:      "created",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		mock.AddTaskDependency(context.Background(), db.AddTaskDependencyParams{
			TaskID:    "task-2",
			DependsOn: "task-1",
		})

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		err := d.promoteEligibleTasks(context.Background())
		require.NoError(t, err)

		// task-2 should NOT be promoted because task-1 is not completed
		task2 := mock.tasks["task-2"]
		assert.Equal(t, "created", task2.Status)
	})

	t.Run("should promote task when dependency is completed", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		now := time.Now().Unix()
		// Create two tasks - task-2 depends on task-1, task-1 is completed
		mock.tasks["task-1"] = db.Task{
			ID:          "task-1",
			Name:        "Completed Dependency",
			Type:        "immediate",
			Priority:    50,
			Status:      "completed",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		mock.tasks["task-2"] = db.Task{
			ID:          "task-2",
			Name:        "Dependent Task",
			Type:        "dependent",
			Priority:    50,
			Status:      "created",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		mock.AddTaskDependency(context.Background(), db.AddTaskDependencyParams{
			TaskID:    "task-2",
			DependsOn: "task-1",
		})

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		err := d.promoteEligibleTasks(context.Background())
		require.NoError(t, err)

		// task-2 SHOULD be promoted because task-1 is completed
		task2 := mock.tasks["task-2"]
		assert.Equal(t, "queued", task2.Status)
	})

	t.Run("should respect backpressure when at max concurrent", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 1) // max 1 concurrent

		now := time.Now().Unix()
		// Create a running task (at capacity)
		mock.tasks["running-task"] = db.Task{
			ID:          "running-task",
			Name:        "Running Task",
			Type:        "immediate",
			Priority:    50,
			Status:      "running",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		// Create a ready task
		mock.tasks["ready-task"] = db.Task{
			ID:          "ready-task",
			Name:        "Ready Task",
			Type:        "immediate",
			Priority:    50,
			Status:      "created",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		err := d.promoteEligibleTasks(context.Background())
		require.NoError(t, err)

		// ready-task should NOT be promoted due to backpressure
		task := mock.tasks["ready-task"]
		assert.Equal(t, "created", task.Status)
	})

	t.Run("should promote multiple tasks up to capacity", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		now := time.Now().Unix()
		// Create three tasks with same priority
		for i := 1; i <= 3; i++ {
			taskID := "task-" + string(rune('0'+i))
			mock.tasks[taskID] = db.Task{
				ID:          taskID,
				Name:        "Task " + taskID,
				Type:        "immediate",
				Priority:    50,
				Status:      "created",
				ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
			}
		}

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		err := d.promoteEligibleTasks(context.Background())
		require.NoError(t, err)

		// All should be promoted (we have capacity of 3)
		for i := 1; i <= 3; i++ {
			taskID := "task-" + string(rune('0'+i))
			assert.Equal(t, "queued", mock.tasks[taskID].Status)
		}
	})

	t.Run("should fail task when dependency fails and failOnBadDep is true", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		now := time.Now().Unix()
		// Create two tasks - task-2 depends on task-1, task-1 failed
		mock.tasks["task-1"] = db.Task{
			ID:          "task-1",
			Name:        "Failed Dependency",
			Type:        "immediate",
			Priority:    50,
			Status:      "failed",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		mock.tasks["task-2"] = db.Task{
			ID:          "task-2",
			Name:        "Dependent Task",
			Type:        "dependent",
			Priority:    50,
			Status:      "created",
			ScheduledAt: sql.NullInt64{Int64: now, Valid: true},
		}
		mock.AddTaskDependency(context.Background(), db.AddTaskDependencyParams{
			TaskID:    "task-2",
			DependsOn: "task-1",
		})

		d := NewDispatcher(svc, 100*time.Millisecond, true) // failOnBadDep = true

		err := d.promoteEligibleTasks(context.Background())
		require.NoError(t, err)

		// task-2 SHOULD be marked as failed because task-1 failed
		task2 := mock.tasks["task-2"]
		assert.Equal(t, "failed", task2.Status)
	})
}

func TestDispatcher_RunStop(t *testing.T) {
	t.Run("should start and stop dispatcher", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		d := NewDispatcher(svc, 50*time.Millisecond, false)

		ctx, cancel := context.WithCancel(context.Background())
		go d.Run(ctx)

		// Let it run for a bit
		time.Sleep(100 * time.Millisecond)

		// Cancel context and stop dispatcher
		cancel()
		d.Stop()

		// Verify it's stopped by checking the mutex/running state
		// We can verify by stopping again - should be a no-op
		d.Stop()
	})

	t.Run("should stop when context is cancelled", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		d := NewDispatcher(svc, 50*time.Millisecond, false)

		ctx, cancel := context.WithCancel(context.Background())
		go d.Run(ctx)

		// Let it run for a bit
		time.Sleep(100 * time.Millisecond)

		// Cancel the context
		cancel()

		// Give it time to stop
		time.Sleep(50 * time.Millisecond)

		// The dispatcher should have stopped
		d.mu.Lock()
		running := d.running
		d.mu.Unlock()

		assert.False(t, running)
	})
}

func TestDispatcher_CheckDependencies(t *testing.T) {
	t.Run("should return ready for task with no dependencies", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		mock.tasks["task-1"] = db.Task{
			ID:     "task-1",
			Name:   "Task",
			Status: "created",
		}

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		ready, reason, err := d.checkDependencies(context.Background(), "task-1")
		require.NoError(t, err)
		assert.True(t, ready)
		assert.Empty(t, reason)
	})

	t.Run("should return waiting when dependency not completed", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		mock.tasks["task-1"] = db.Task{
			ID:     "task-1",
			Name:   "Dependency",
			Status: "created", // Not completed
		}
		mock.tasks["task-2"] = db.Task{
			ID:     "task-2",
			Name:   "Dependent",
			Status: "created",
		}
		mock.AddTaskDependency(context.Background(), db.AddTaskDependencyParams{
			TaskID:    "task-2",
			DependsOn: "task-1",
		})

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		ready, reason, err := d.checkDependencies(context.Background(), "task-2")
		require.NoError(t, err)
		assert.False(t, ready)
		assert.Equal(t, "waiting", reason)
	})

	t.Run("should return bad_dep when dependency failed", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		mock.tasks["task-1"] = db.Task{
			ID:     "task-1",
			Name:   "Failed Dependency",
			Status: "failed",
		}
		mock.tasks["task-2"] = db.Task{
			ID:     "task-2",
			Name:   "Dependent",
			Status: "created",
		}
		mock.AddTaskDependency(context.Background(), db.AddTaskDependencyParams{
			TaskID:    "task-2",
			DependsOn: "task-1",
		})

		d := NewDispatcher(svc, 100*time.Millisecond, true)

		ready, reason, err := d.checkDependencies(context.Background(), "task-2")
		require.NoError(t, err)
		assert.False(t, ready)
		assert.Equal(t, "bad_dep", reason)
	})

	t.Run("should return ready when all dependencies completed", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		mock.tasks["task-1"] = db.Task{
			ID:     "task-1",
			Name:   "Completed Dependency",
			Status: "completed",
		}
		mock.tasks["task-2"] = db.Task{
			ID:     "task-2",
			Name:   "Dependent",
			Status: "created",
		}
		mock.AddTaskDependency(context.Background(), db.AddTaskDependencyParams{
			TaskID:    "task-2",
			DependsOn: "task-1",
		})

		d := NewDispatcher(svc, 100*time.Millisecond, false)

		ready, reason, err := d.checkDependencies(context.Background(), "task-2")
		require.NoError(t, err)
		assert.True(t, ready)
		assert.Empty(t, reason)
	})
}
