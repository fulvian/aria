package analysis

import (
	"context"
	"database/sql"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/db"
)

// mockAnalysisQuerier implements db.Querier for testing analysis service.
type mockAnalysisQuerier struct {
	episodes    []db.Episode
	facts       []db.Fact
	procedures  []db.Procedure
	tasks       []db.Task
	taskEvents  []db.TaskEvent
	createError error
	listError   error
}

func (m *mockAnalysisQuerier) ListEpisodes(ctx context.Context, arg db.ListEpisodesParams) ([]db.Episode, error) {
	if m.listError != nil {
		return nil, m.listError
	}
	offset := int(arg.Offset)
	limit := int(arg.Limit)
	if offset >= len(m.episodes) {
		return []db.Episode{}, nil
	}
	end := offset + limit
	if end > len(m.episodes) {
		end = len(m.episodes)
	}
	return m.episodes[offset:end], nil
}

func (m *mockAnalysisQuerier) ListTasks(ctx context.Context, arg db.ListTasksParams) ([]db.Task, error) {
	if m.listError != nil {
		return nil, m.listError
	}
	return m.tasks, nil
}

func (m *mockAnalysisQuerier) ListTasksByStatus(ctx context.Context, arg db.ListTasksByStatusParams) ([]db.Task, error) {
	var result []db.Task
	for _, task := range m.tasks {
		if task.Status == arg.Status {
			result = append(result, task)
		}
	}
	return result, nil
}

func (m *mockAnalysisQuerier) GetRecentTaskEvents(ctx context.Context, limit int64) ([]db.TaskEvent, error) {
	return m.taskEvents, nil
}

func (m *mockAnalysisQuerier) ListProcedures(ctx context.Context) ([]db.Procedure, error) {
	return m.procedures, nil
}

func (m *mockAnalysisQuerier) ListFactsByDomain(ctx context.Context, domain string) ([]db.Fact, error) {
	var result []db.Fact
	for _, f := range m.facts {
		if f.Domain == domain {
			result = append(result, f)
		}
	}
	return result, nil
}

func (m *mockAnalysisQuerier) ListTasksByAgency(ctx context.Context, arg db.ListTasksByAgencyParams) ([]db.Task, error) {
	var result []db.Task
	for _, task := range m.tasks {
		if task.Agency.Valid && task.Agency.String == arg.Agency.String {
			result = append(result, task)
		}
	}
	return result, nil
}

func (m *mockAnalysisQuerier) SearchEpisodes(ctx context.Context, arg db.SearchEpisodesParams) ([]db.Episode, error) {
	return m.episodes, nil
}

func (m *mockAnalysisQuerier) ListEpisodesBySession(ctx context.Context, arg db.ListEpisodesBySessionParams) ([]db.Episode, error) {
	return m.episodes, nil
}

func (m *mockAnalysisQuerier) ListEpisodesByAgency(ctx context.Context, arg db.ListEpisodesByAgencyParams) ([]db.Episode, error) {
	return m.episodes, nil
}

// Unused methods - return empty/default values
func (m *mockAnalysisQuerier) CreateEpisode(ctx context.Context, arg db.CreateEpisodeParams) (db.Episode, error) {
	return db.Episode{}, nil
}
func (m *mockAnalysisQuerier) GetEpisodeByID(ctx context.Context, id string) (db.Episode, error) {
	return db.Episode{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) DeleteEpisode(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteOldEpisodes(ctx context.Context, createdAt int64) error {
	return nil
}
func (m *mockAnalysisQuerier) CreateFact(ctx context.Context, arg db.CreateFactParams) (db.Fact, error) {
	return db.Fact{}, nil
}
func (m *mockAnalysisQuerier) GetFactByID(ctx context.Context, id string) (db.Fact, error) {
	return db.Fact{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) ListFactsByCategory(ctx context.Context, category sql.NullString) ([]db.Fact, error) {
	return []db.Fact{}, nil
}
func (m *mockAnalysisQuerier) IncrementFactUsage(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) UpdateFactConfidence(ctx context.Context, arg db.UpdateFactConfidenceParams) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteFact(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) SearchFacts(ctx context.Context, arg db.SearchFactsParams) ([]db.Fact, error) {
	return []db.Fact{}, nil
}
func (m *mockAnalysisQuerier) CreateProcedure(ctx context.Context, arg db.CreateProcedureParams) (db.Procedure, error) {
	return db.Procedure{}, nil
}
func (m *mockAnalysisQuerier) GetProcedureByID(ctx context.Context, id string) (db.Procedure, error) {
	return db.Procedure{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetProcedureByName(ctx context.Context, name string) (db.Procedure, error) {
	return db.Procedure{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) ListProceduresByTrigger(ctx context.Context, triggerType string) ([]db.Procedure, error) {
	return []db.Procedure{}, nil
}
func (m *mockAnalysisQuerier) UpdateProcedureStats(ctx context.Context, arg db.UpdateProcedureStatsParams) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteProcedure(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) SearchProcedures(ctx context.Context, arg db.SearchProceduresParams) ([]db.Procedure, error) {
	return []db.Procedure{}, nil
}
func (m *mockAnalysisQuerier) AddTaskDependency(ctx context.Context, arg db.AddTaskDependencyParams) error {
	return nil
}
func (m *mockAnalysisQuerier) CancelTask(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) CreateAgency(ctx context.Context, arg db.CreateAgencyParams) (db.Agency, error) {
	return db.Agency{}, nil
}
func (m *mockAnalysisQuerier) CreateFile(ctx context.Context, arg db.CreateFileParams) (db.File, error) {
	return db.File{}, nil
}
func (m *mockAnalysisQuerier) CreateMessage(ctx context.Context, arg db.CreateMessageParams) (db.Message, error) {
	return db.Message{}, nil
}
func (m *mockAnalysisQuerier) CreateSession(ctx context.Context, arg db.CreateSessionParams) (db.Session, error) {
	return db.Session{}, nil
}
func (m *mockAnalysisQuerier) CreateTask(ctx context.Context, arg db.CreateTaskParams) (db.Task, error) {
	return db.Task{}, nil
}
func (m *mockAnalysisQuerier) CreateTaskEvent(ctx context.Context, arg db.CreateTaskEventParams) (db.TaskEvent, error) {
	return db.TaskEvent{}, nil
}
func (m *mockAnalysisQuerier) DeleteAgency(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteFile(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteMessage(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteSession(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteSessionFiles(ctx context.Context, sessionID string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteSessionMessages(ctx context.Context, sessionID string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteTask(ctx context.Context, id string) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteExpiredContexts(ctx context.Context) error {
	return nil
}
func (m *mockAnalysisQuerier) DeleteWorkingContext(ctx context.Context, sessionID string) error {
	return nil
}
func (m *mockAnalysisQuerier) GetWorkingContext(ctx context.Context, sessionID string) (db.WorkingMemoryContext, error) {
	return db.WorkingMemoryContext{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) SaveWorkingContext(ctx context.Context, arg db.SaveWorkingContextParams) (db.WorkingMemoryContext, error) {
	return db.WorkingMemoryContext{}, nil
}
func (m *mockAnalysisQuerier) GetAgencyByID(ctx context.Context, id string) (db.Agency, error) {
	return db.Agency{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetAgencyByName(ctx context.Context, name string) (db.Agency, error) {
	return db.Agency{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetDependentTasks(ctx context.Context, dependsOn string) ([]db.Task, error) {
	return []db.Task{}, nil
}
func (m *mockAnalysisQuerier) GetFile(ctx context.Context, id string) (db.File, error) {
	return db.File{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetFileByPathAndSession(ctx context.Context, arg db.GetFileByPathAndSessionParams) (db.File, error) {
	return db.File{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetMessage(ctx context.Context, id string) (db.Message, error) {
	return db.Message{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetSessionByID(ctx context.Context, id string) (db.Session, error) {
	return db.Session{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetTaskByID(ctx context.Context, id string) (db.Task, error) {
	return db.Task{}, sql.ErrNoRows
}
func (m *mockAnalysisQuerier) GetTaskDependencies(ctx context.Context, taskID string) ([]db.Task, error) {
	return []db.Task{}, nil
}
func (m *mockAnalysisQuerier) GetTaskEvents(ctx context.Context, taskID string) ([]db.TaskEvent, error) {
	return []db.TaskEvent{}, nil
}
func (m *mockAnalysisQuerier) ListAgencies(ctx context.Context) ([]db.Agency, error) {
	return []db.Agency{}, nil
}
func (m *mockAnalysisQuerier) ListAgenciesByStatus(ctx context.Context, status string) ([]db.Agency, error) {
	return []db.Agency{}, nil
}
func (m *mockAnalysisQuerier) ListFilesByPath(ctx context.Context, path string) ([]db.File, error) {
	return []db.File{}, nil
}
func (m *mockAnalysisQuerier) ListFilesBySession(ctx context.Context, sessionID string) ([]db.File, error) {
	return []db.File{}, nil
}
func (m *mockAnalysisQuerier) ListLatestSessionFiles(ctx context.Context, sessionID string) ([]db.File, error) {
	return []db.File{}, nil
}
func (m *mockAnalysisQuerier) ListMessagesBySession(ctx context.Context, sessionID string) ([]db.Message, error) {
	return []db.Message{}, nil
}
func (m *mockAnalysisQuerier) ListNewFiles(ctx context.Context) ([]db.File, error) {
	return []db.File{}, nil
}
func (m *mockAnalysisQuerier) ListSessions(ctx context.Context) ([]db.Session, error) {
	return []db.Session{}, nil
}
func (m *mockAnalysisQuerier) RemoveTaskDependency(ctx context.Context, arg db.RemoveTaskDependencyParams) error {
	return nil
}
func (m *mockAnalysisQuerier) UpdateAgencyStatus(ctx context.Context, arg db.UpdateAgencyStatusParams) error {
	return nil
}
func (m *mockAnalysisQuerier) UpdateFile(ctx context.Context, arg db.UpdateFileParams) (db.File, error) {
	return db.File{}, nil
}
func (m *mockAnalysisQuerier) UpdateMessage(ctx context.Context, arg db.UpdateMessageParams) error {
	return nil
}
func (m *mockAnalysisQuerier) UpdateSession(ctx context.Context, arg db.UpdateSessionParams) (db.Session, error) {
	return db.Session{}, nil
}
func (m *mockAnalysisQuerier) UpdateTaskProgress(ctx context.Context, arg db.UpdateTaskProgressParams) error {
	return nil
}
func (m *mockAnalysisQuerier) UpdateTaskStatus(ctx context.Context, arg db.UpdateTaskStatusParams) error {
	return nil
}
func (m *mockAnalysisQuerier) CountTasksByStatus(ctx context.Context, status string) (int64, error) {
	return 0, nil
}
func (m *mockAnalysisQuerier) ListPendingTasks(ctx context.Context, arg db.ListPendingTasksParams) ([]db.Task, error) {
	return []db.Task{}, nil
}

func TestSelfAnalysisService_AnalyzePerformance_NoTasks(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockAnalysisQuerier{}).(*selfAnalysisService)
	ctx := context.Background()

	report, err := svc.AnalyzePerformance(ctx, TimeRange{
		Start: time.Now().Add(-1 * time.Hour),
		End:   time.Now(),
	})
	require.NoError(t, err)

	// With no tasks, metrics should be zero
	assert.Equal(t, int64(0), report.TotalTasks)
	assert.Equal(t, 0.0, report.SuccessRate)
	assert.Equal(t, int64(0), report.AverageTimeMs)
}

func TestSelfAnalysisService_AnalyzePerformance_WithTasks(t *testing.T) {
	t.Parallel()

	now := time.Now()
	mock := &mockAnalysisQuerier{
		tasks: []db.Task{
			{
				ID:          "task-1",
				Name:        "Task 1",
				Status:      "completed",
				StartedAt:   sql.NullInt64{Int64: now.Add(-5 * time.Minute).Unix(), Valid: true},
				CompletedAt: sql.NullInt64{Int64: now.Unix(), Valid: true},
				Agency:      sql.NullString{String: "agency-1", Valid: true},
			},
			{
				ID:          "task-2",
				Name:        "Task 2",
				Status:      "completed",
				StartedAt:   sql.NullInt64{Int64: now.Add(-3 * time.Minute).Unix(), Valid: true},
				CompletedAt: sql.NullInt64{Int64: now.Unix(), Valid: true},
				Agency:      sql.NullString{String: "agency-1", Valid: true},
			},
			{
				ID:          "task-3",
				Name:        "Task 3",
				Status:      "failed",
				StartedAt:   sql.NullInt64{Int64: now.Add(-1 * time.Minute).Unix(), Valid: true},
				CompletedAt: sql.NullInt64{Int64: now.Unix(), Valid: true},
				Agency:      sql.NullString{String: "agency-1", Valid: true},
			},
		},
	}

	svc := NewService(mock).(*selfAnalysisService)
	ctx := context.Background()

	report, err := svc.AnalyzePerformance(ctx, TimeRange{
		Start: time.Now().Add(-1 * time.Hour),
		End:   time.Now(),
	})
	require.NoError(t, err)

	// 3 tasks total, 2 completed, 1 failed
	assert.Equal(t, int64(3), report.TotalTasks)
	assert.InDelta(t, 0.667, report.SuccessRate, 0.01) // 2/3 = ~67%
	assert.Greater(t, report.AverageTimeMs, int64(0))

	// Check agency metrics
	assert.Contains(t, report.ByAgency, agency.AgencyName("agency-1"))
	agencyMetrics := report.ByAgency[agency.AgencyName("agency-1")]
	assert.Equal(t, int64(3), agencyMetrics.TotalTasks)
	assert.InDelta(t, 0.667, agencyMetrics.SuccessRate, 0.01)
}

func TestSelfAnalysisService_AnalyzePatterns_NoData(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockAnalysisQuerier{}).(*selfAnalysisService)
	ctx := context.Background()

	report, err := svc.AnalyzePatterns(ctx)
	require.NoError(t, err)

	// With no data, patterns should be empty
	assert.Empty(t, report.RecurringTasks)
	assert.Empty(t, report.CommonWorkflows)
	assert.Empty(t, report.OptimizationOpps)
}

func TestSelfAnalysisService_AnalyzePatterns_WithData(t *testing.T) {
	t.Parallel()

	mock := &mockAnalysisQuerier{
		episodes: []db.Episode{
			{
				ID:      "ep-1",
				Task:    sql.NullString{String: `{"type": "bash", "description": "run command"}`, Valid: true},
				Outcome: sql.NullString{String: "success", Valid: true},
			},
			{
				ID:      "ep-2",
				Task:    sql.NullString{String: `{"type": "bash", "description": "run another"}`, Valid: true},
				Outcome: sql.NullString{String: "success", Valid: true},
			},
			{
				ID:      "ep-3",
				Task:    sql.NullString{String: `{"type": "code_review", "description": "review code"}`, Valid: true},
				Outcome: sql.NullString{String: "failure: syntax error", Valid: true},
			},
		},
	}

	svc := NewService(mock).(*selfAnalysisService)
	ctx := context.Background()

	report, err := svc.AnalyzePatterns(ctx)
	require.NoError(t, err)

	// Should identify patterns from episodes
	assert.NotEmpty(t, report.RecurringTasks)
	// First task type should be bash (appears 2 times)
	assert.Equal(t, "bash", report.RecurringTasks[0].TaskType)
}

func TestSelfAnalysisService_AnalyzeFailures_NoData(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockAnalysisQuerier{}).(*selfAnalysisService)
	ctx := context.Background()

	report, err := svc.AnalyzeFailures(ctx)
	require.NoError(t, err)

	// With no failed tasks
	assert.Equal(t, int64(0), report.TotalFailures)
	assert.Empty(t, report.FailedTasks)
	assert.Empty(t, report.RootCauses)
}

func TestSelfAnalysisService_AnalyzeFailures_WithData(t *testing.T) {
	t.Parallel()

	now := time.Now()
	mock := &mockAnalysisQuerier{
		tasks: []db.Task{
			{
				ID:          "task-1",
				Name:        "Failed Task 1",
				Status:      "failed",
				Error:       sql.NullString{String: "connection timeout", Valid: true},
				CompletedAt: sql.NullInt64{Int64: now.Unix(), Valid: true},
			},
			{
				ID:          "task-2",
				Name:        "Failed Task 2",
				Status:      "failed",
				Error:       sql.NullString{String: "connection timeout", Valid: true},
				CompletedAt: sql.NullInt64{Int64: now.Unix(), Valid: true},
			},
			{
				ID:          "task-3",
				Name:        "Failed Task 3",
				Status:      "failed",
				Error:       sql.NullString{String: "syntax error", Valid: true},
				CompletedAt: sql.NullInt64{Int64: now.Unix(), Valid: true},
			},
		},
		taskEvents: []db.TaskEvent{
			{ID: "event-1", TaskID: "task-1", EventType: "failed"},
			{ID: "event-2", TaskID: "task-2", EventType: "failed"},
			{ID: "event-3", TaskID: "task-3", EventType: "failed"},
		},
	}

	svc := NewService(mock).(*selfAnalysisService)
	ctx := context.Background()

	report, err := svc.AnalyzeFailures(ctx)
	require.NoError(t, err)

	// 3 failures total
	assert.Equal(t, int64(3), report.TotalFailures)
	assert.Len(t, report.FailedTasks, 3)

	// Most common reason should be "connection timeout" (2 times)
	assert.Contains(t, report.CommonReasons, "connection timeout")
	assert.Equal(t, int64(2), report.CommonReasons["connection timeout"])

	// Root causes should be identified (only those with count >= 2)
	assert.NotEmpty(t, report.RootCauses)
}

func TestSelfAnalysisService_GenerateImprovements_NoData(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockAnalysisQuerier{}).(*selfAnalysisService)
	ctx := context.Background()

	improvements, err := svc.GenerateImprovements(ctx)
	require.NoError(t, err)

	// With no data, no improvements generated (low task count threshold)
	assert.Len(t, improvements, 0)
}

func TestSelfAnalysisService_GenerateImprovements_LowSuccessRate(t *testing.T) {
	t.Parallel()

	now := time.Now()
	mock := &mockAnalysisQuerier{
		tasks: []db.Task{
			{ID: "task-1", Name: "Task 1", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-2", Name: "Task 2", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-3", Name: "Task 3", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-4", Name: "Task 4", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-5", Name: "Task 5", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-6", Name: "Task 6", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-7", Name: "Task 7", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-8", Name: "Task 8", Status: "failed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-9", Name: "Task 9", Status: "completed", Agency: sql.NullString{String: "a1", Valid: true}},
			{ID: "task-10", Name: "Task 10", Status: "completed", Agency: sql.NullString{String: "a1", Valid: true}},
		},
		taskEvents: []db.TaskEvent{
			{ID: "e1", TaskID: "task-1", EventType: "failed", CreatedAt: now.Unix()},
		},
	}

	svc := NewService(mock).(*selfAnalysisService)
	ctx := context.Background()

	improvements, err := svc.GenerateImprovements(ctx)
	require.NoError(t, err)

	// Should generate improvement for low success rate (20% < 70%)
	found := false
	for _, imp := range improvements {
		if imp.Type == "process" && imp.Impact == "high" {
			found = true
			assert.Contains(t, imp.Description, "below 70%")
			break
		}
	}
	assert.True(t, found, "Expected low success rate improvement")
}

func TestSelfAnalysisService_ApplyInsights_DoNotAutoApply(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockAnalysisQuerier{}).(*selfAnalysisService)
	ctx := context.Background()

	improvements := []Improvement{
		{
			ID:          "imp-1",
			Type:        "process",
			Description: "Test improvement",
			Impact:      "high",
			AutoApply:   false,
		},
	}

	// Should not error even though AutoApply is false
	err := svc.ApplyInsights(ctx, improvements)
	require.NoError(t, err)
}

func TestSelfAnalysisService_RunPeriodicAnalysis_ContextCancel(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockAnalysisQuerier{}).(*selfAnalysisService)
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	// Should return context.Canceled after timeout
	err := svc.RunPeriodicAnalysis(ctx)
	assert.Error(t, err)
	assert.Equal(t, context.DeadlineExceeded, err)
}
