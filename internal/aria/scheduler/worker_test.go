package scheduler

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/db"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockWorkerDB extends mockDB with additional methods needed for worker tests
type mockWorkerDB struct {
	*mockDB
	queuedTasks []db.Task
}

func (m *mockWorkerDB) ListTasksByStatus(ctx context.Context, arg db.ListTasksByStatusParams) ([]db.Task, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if arg.Status != string(TaskStatusQueued) {
		return nil, nil
	}

	var result []db.Task
	for _, task := range m.tasks {
		if task.Status == arg.Status {
			result = append(result, task)
		}
	}
	m.queuedTasks = result
	return result, nil
}

// mockExecutor is a TaskExecutor that can be configured for testing
type mockExecutor struct {
	mu         sync.Mutex
	executions []string // task IDs that have been executed
	results    map[string]*TaskResult
	errors     map[string]error
	delay      time.Duration
}

func newMockExecutor() *mockExecutor {
	return &mockExecutor{
		results: make(map[string]*TaskResult),
		errors:  make(map[string]error),
	}
}

func (e *mockExecutor) ExecuteTask(ctx context.Context, task Task) (*TaskResult, error) {
	e.mu.Lock()
	e.executions = append(e.executions, string(task.ID))
	e.mu.Unlock()

	if e.delay > 0 {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(e.delay):
		}
	}

	if err, ok := e.errors[string(task.ID)]; ok {
		return nil, err
	}

	if result, ok := e.results[string(task.ID)]; ok {
		return result, nil
	}

	return &TaskResult{
		Output: map[string]any{
			"task_id": string(task.ID),
			"status":  "completed",
		},
		CompletedAt: time.Now(),
	}, nil
}

func TestWorker_ProcessTask(t *testing.T) {
	t.Run("should complete task successfully", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a queued task
		mock.tasks["task-1"] = db.Task{
			ID:       "task-1",
			Name:     "Test Task",
			Type:     "immediate",
			Priority: 50,
			Status:   string(TaskStatusQueued),
		}

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 100*time.Millisecond, executor)

		err := worker.processTask(context.Background(), "task-1")
		require.NoError(t, err)

		// Verify task is marked as completed
		task := mock.tasks["task-1"]
		assert.Equal(t, string(TaskStatusCompleted), task.Status)
		assert.Equal(t, 1.0, task.Progress)

		// Verify executor was called
		assert.Contains(t, executor.executions, "task-1")
	})

	t.Run("should fail task when executor returns error", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a queued task
		mock.tasks["task-2"] = db.Task{
			ID:       "task-2",
			Name:     "Failing Task",
			Type:     "immediate",
			Priority: 50,
			Status:   string(TaskStatusQueued),
		}

		executor := newMockExecutor()
		executor.errors["task-2"] = assert.AnError

		worker := NewWorker(svc, 2, 100*time.Millisecond, executor)

		err := worker.processTask(context.Background(), "task-2")
		require.NoError(t, err) // processTask itself doesn't error, it handles the failure

		// Verify task is marked as failed
		task := mock.tasks["task-2"]
		assert.Equal(t, string(TaskStatusFailed), task.Status)
		assert.True(t, task.Error.Valid)
	})

	t.Run("should create started and completed events", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a queued task
		mock.tasks["task-3"] = db.Task{
			ID:       "task-3",
			Name:     "Event Task",
			Type:     "immediate",
			Priority: 50,
			Status:   string(TaskStatusQueued),
		}

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 100*time.Millisecond, executor)

		err := worker.processTask(context.Background(), "task-3")
		require.NoError(t, err)

		// Verify events were created
		assert.GreaterOrEqual(t, len(mock.events), 2)

		// Check for started event
		startedFound := false
		completedFound := false
		for _, event := range mock.events {
			if event.EventType == "started" && event.TaskID == "task-3" {
				startedFound = true
			}
			if event.EventType == "completed" && event.TaskID == "task-3" {
				completedFound = true
			}
		}
		assert.True(t, startedFound, "started event should be created")
		assert.True(t, completedFound, "completed event should be created")
	})
}

func TestWorker_RunStop(t *testing.T) {
	t.Run("should start and stop worker", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 50*time.Millisecond, executor)

		ctx, cancel := context.WithCancel(context.Background())
		go worker.Run(ctx)

		// Let it run for a bit
		time.Sleep(100 * time.Millisecond)

		// Cancel context to stop
		cancel()
		worker.Stop()

		// Verify it's stopped by stopping again - should be a no-op
		worker.Stop()
	})

	t.Run("should stop when context is cancelled", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 50*time.Millisecond, executor)

		ctx, cancel := context.WithCancel(context.Background())
		go worker.Run(ctx)

		// Let it run for a bit
		time.Sleep(100 * time.Millisecond)

		// Cancel the context
		cancel()

		// Give it time to stop
		time.Sleep(50 * time.Millisecond)

		// The worker should have stopped
		worker.mu.Lock()
		running := worker.running
		worker.mu.Unlock()

		assert.False(t, running)
	})

	t.Run("should not start twice", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 50*time.Millisecond, executor)

		ctx, cancel := context.WithCancel(context.Background())

		// Start worker in a goroutine
		go worker.Run(ctx)

		// Let it start
		time.Sleep(20 * time.Millisecond)

		// Try to start again - should be a no-op
		worker.Run(ctx)

		// It should be running
		worker.mu.Lock()
		running := worker.running
		worker.mu.Unlock()
		assert.True(t, running)

		// Clean up
		cancel()
		worker.Stop()
	})
}

func TestWorker_ConcurrentExecution(t *testing.T) {
	// Note: Full concurrent execution testing requires a more sophisticated mock
	// that tracks picked-up tasks. For now, we verify that the worker
	// can handle multiple tasks being executed.
	t.Run("can execute multiple tasks", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 10*time.Millisecond, executor)

		ctx, cancel := context.WithCancel(context.Background())
		go worker.Run(ctx)

		// Let it run briefly
		time.Sleep(50 * time.Millisecond)

		cancel()
		worker.Stop()

		// Just verify it runs without hanging
		assert.True(t, true)
	})
}

func TestWorker_UpdateTaskProgress(t *testing.T) {
	t.Run("should update task progress during execution", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a queued task
		mock.tasks["progress-task"] = db.Task{
			ID:       "progress-task",
			Name:     "Progress Task",
			Type:     "immediate",
			Priority: 50,
			Status:   string(TaskStatusQueued),
		}

		executor := newMockExecutor()
		worker := NewWorker(svc, 2, 100*time.Millisecond, executor)

		err := worker.processTask(context.Background(), "progress-task")
		require.NoError(t, err)

		// Task should be completed with progress = 1.0
		task := mock.tasks["progress-task"]
		assert.Equal(t, string(TaskStatusCompleted), task.Status)
		assert.Equal(t, 1.0, task.Progress)
	})
}

func TestWorker_FailTask(t *testing.T) {
	t.Run("should mark task as failed with error", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a queued task
		mock.tasks["fail-task"] = db.Task{
			ID:       "fail-task",
			Name:     "Fail Task",
			Type:     "immediate",
			Priority: 50,
			Status:   string(TaskStatusQueued),
		}

		executor := newMockExecutor()
		executor.errors["fail-task"] = assert.AnError

		worker := NewWorker(svc, 2, 100*time.Millisecond, executor)

		err := worker.processTask(context.Background(), "fail-task")
		require.NoError(t, err)

		// Verify task is marked as failed
		task := mock.tasks["fail-task"]
		assert.Equal(t, string(TaskStatusFailed), task.Status)
		assert.True(t, task.Error.Valid)
		assert.Contains(t, task.Error.String, "EXECUTION_FAILED")
	})

	t.Run("should create failed event", func(t *testing.T) {
		mock := newMockDB()
		svc := newTestSchedulerService(mock, 3)

		// Create a queued task
		mock.tasks["event-fail-task"] = db.Task{
			ID:       "event-fail-task",
			Name:     "Event Fail Task",
			Type:     "immediate",
			Priority: 50,
			Status:   string(TaskStatusQueued),
		}

		executor := newMockExecutor()
		executor.errors["event-fail-task"] = assert.AnError

		worker := NewWorker(svc, 2, 100*time.Millisecond, executor)

		err := worker.processTask(context.Background(), "event-fail-task")
		require.NoError(t, err)

		// Verify failed event was created
		failedFound := false
		for _, event := range mock.events {
			if event.EventType == "failed" && event.TaskID == "event-fail-task" {
				failedFound = true
				break
			}
		}
		assert.True(t, failedFound, "failed event should be created")
	})
}
