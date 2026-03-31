package scheduler

import (
	"context"
	"database/sql"
	"testing"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/pubsub"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockRecoveryQuerier is a mock implementation of db.Querier for testing.
type mockRecoveryQuerier struct {
	runningTasks []db.Task
	queuedTasks  []db.Task
	updateErr    error
	createErr    error
}

func (m *mockRecoveryQuerier) ListTasksByStatus(ctx context.Context, arg db.ListTasksByStatusParams) ([]db.Task, error) {
	switch arg.Status {
	case string(TaskStatusRunning):
		return m.runningTasks, nil
	case string(TaskStatusQueued):
		return m.queuedTasks, nil
	}
	return nil, nil
}

func (m *mockRecoveryQuerier) UpdateTaskStatus(ctx context.Context, arg db.UpdateTaskStatusParams) error {
	return m.updateErr
}

func (m *mockRecoveryQuerier) CreateTaskEvent(ctx context.Context, arg db.CreateTaskEventParams) (db.TaskEvent, error) {
	return db.TaskEvent{}, m.createErr
}

// Unused methods - panic if called (not needed for recovery tests)
func (m *mockRecoveryQuerier) AddTaskDependency(ctx context.Context, arg db.AddTaskDependencyParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CancelTask(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CountTasksByStatus(ctx context.Context, status string) (int64, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CountEpisodesByOutcome(ctx context.Context, arg db.CountEpisodesByOutcomeParams) (db.CountEpisodesByOutcomeRow, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateAgency(ctx context.Context, arg db.CreateAgencyParams) (db.Agency, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateEpisode(ctx context.Context, arg db.CreateEpisodeParams) (db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateFact(ctx context.Context, arg db.CreateFactParams) (db.Fact, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateFile(ctx context.Context, arg db.CreateFileParams) (db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateMessage(ctx context.Context, arg db.CreateMessageParams) (db.Message, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateProcedure(ctx context.Context, arg db.CreateProcedureParams) (db.Procedure, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateSession(ctx context.Context, arg db.CreateSessionParams) (db.Session, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreateTask(ctx context.Context, arg db.CreateTaskParams) (db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteAgency(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteEpisode(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteFact(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteFile(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteMessage(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteOldEpisodes(ctx context.Context, createdAt int64) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteProcedure(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteSession(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteSessionFiles(ctx context.Context, sessionID string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteSessionMessages(ctx context.Context, sessionID string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteTask(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteExpiredContexts(ctx context.Context) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteWorkingContext(ctx context.Context, sessionID string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetWorkingContext(ctx context.Context, sessionID string) (db.WorkingMemoryContext, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SaveWorkingContext(ctx context.Context, arg db.SaveWorkingContextParams) (db.WorkingMemoryContext, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetAgencyByID(ctx context.Context, id string) (db.Agency, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetAgencyByName(ctx context.Context, name string) (db.Agency, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetAgencyState(ctx context.Context, agencyID string) (db.AgencyState, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpsertAgencyState(ctx context.Context, arg db.UpsertAgencyStateParams) (db.AgencyState, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteAgencyState(ctx context.Context, agencyID string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetDependentTasks(ctx context.Context, dependsOn string) ([]db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetEpisodeByID(ctx context.Context, id string) (db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetFactByID(ctx context.Context, id string) (db.Fact, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetFile(ctx context.Context, id string) (db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetFileByPathAndSession(ctx context.Context, arg db.GetFileByPathAndSessionParams) (db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetMessage(ctx context.Context, id string) (db.Message, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetProcedureByID(ctx context.Context, id string) (db.Procedure, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetProcedureByName(ctx context.Context, name string) (db.Procedure, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetRecentTaskEvents(ctx context.Context, limit int64) ([]db.TaskEvent, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetSessionByID(ctx context.Context, id string) (db.Session, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetTaskByID(ctx context.Context, id string) (db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetTaskDependencies(ctx context.Context, taskID string) ([]db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetTaskEvents(ctx context.Context, taskID string) ([]db.TaskEvent, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) IncrementFactUsage(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListAgencies(ctx context.Context) ([]db.Agency, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListAgenciesByStatus(ctx context.Context, status string) ([]db.Agency, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListEpisodes(ctx context.Context, arg db.ListEpisodesParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListEpisodesByAgency(ctx context.Context, arg db.ListEpisodesByAgencyParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListEpisodesBySession(ctx context.Context, arg db.ListEpisodesBySessionParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListFactsByCategory(ctx context.Context, category sql.NullString) ([]db.Fact, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListFactsByDomain(ctx context.Context, domain string) ([]db.Fact, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListFilesByPath(ctx context.Context, path string) ([]db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListFilesBySession(ctx context.Context, sessionID string) ([]db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListLatestSessionFiles(ctx context.Context, sessionID string) ([]db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListNewFiles(ctx context.Context) ([]db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListMessagesBySession(ctx context.Context, sessionID string) ([]db.Message, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListPendingTasks(ctx context.Context, arg db.ListPendingTasksParams) ([]db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListProcedures(ctx context.Context) ([]db.Procedure, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListProceduresByTrigger(ctx context.Context, triggerType string) ([]db.Procedure, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListSessions(ctx context.Context) ([]db.Session, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListTasks(ctx context.Context, arg db.ListTasksParams) ([]db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListTasksByAgency(ctx context.Context, arg db.ListTasksByAgencyParams) ([]db.Task, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) RemoveTaskDependency(ctx context.Context, arg db.RemoveTaskDependencyParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SearchEpisodes(ctx context.Context, arg db.SearchEpisodesParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SearchEpisodesByAgent(ctx context.Context, arg db.SearchEpisodesByAgentParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SearchEpisodesByTimeRange(ctx context.Context, arg db.SearchEpisodesByTimeRangeParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SearchEpisodesFull(ctx context.Context, arg db.SearchEpisodesFullParams) ([]db.Episode, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SearchFacts(ctx context.Context, arg db.SearchFactsParams) ([]db.Fact, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) SearchProcedures(ctx context.Context, arg db.SearchProceduresParams) ([]db.Procedure, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateAgencyStatus(ctx context.Context, arg db.UpdateAgencyStatusParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateFactConfidence(ctx context.Context, arg db.UpdateFactConfidenceParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateFile(ctx context.Context, arg db.UpdateFileParams) (db.File, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateMessage(ctx context.Context, arg db.UpdateMessageParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateProcedureStats(ctx context.Context, arg db.UpdateProcedureStatsParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateSession(ctx context.Context, arg db.UpdateSessionParams) (db.Session, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateTaskProgress(ctx context.Context, arg db.UpdateTaskProgressParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateTaskScheduleExpr(ctx context.Context, arg db.UpdateTaskScheduleExprParams) error {
	panic("not implemented")
}

// Guardrail and Permission mock methods
func (m *mockRecoveryQuerier) CreateGuardrailAuditEntry(ctx context.Context, arg db.CreateGuardrailAuditEntryParams) (db.GuardrailAudit, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreatePermissionRequest(ctx context.Context, arg db.CreatePermissionRequestParams) (db.PermissionRequest, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreatePermissionResponse(ctx context.Context, arg db.CreatePermissionResponseParams) (db.PermissionResponse, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) CreatePermissionRule(ctx context.Context, arg db.CreatePermissionRuleParams) (db.PermissionRule, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteExpiredPermissionRules(ctx context.Context) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteOldGuardrailAudit(ctx context.Context, dollar_1 sql.NullString) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeleteOldPermissionRequests(ctx context.Context, dollar_1 sql.NullString) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) DeletePermissionRule(ctx context.Context, id string) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetGuardrailBudget(ctx context.Context, actionType string) (db.GuardrailBudget, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetGuardrailPreferences(ctx context.Context) (db.GuardrailPreference, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetPermissionRequestByID(ctx context.Context, id string) (db.PermissionRequest, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetPermissionResponseByRequestID(ctx context.Context, requestID string) (db.PermissionResponse, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) GetPermissionRuleByID(ctx context.Context, id string) (db.PermissionRule, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListGuardrailAuditByTimeRange(ctx context.Context, arg db.ListGuardrailAuditByTimeRangeParams) ([]db.GuardrailAudit, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListGuardrailAuditByType(ctx context.Context, arg db.ListGuardrailAuditByTypeParams) ([]db.GuardrailAudit, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListGuardrailBudgets(ctx context.Context) ([]db.GuardrailBudget, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListPermissionRequestsByAgency(ctx context.Context, arg db.ListPermissionRequestsByAgencyParams) ([]db.PermissionRequest, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListPermissionRequestsByAgent(ctx context.Context, arg db.ListPermissionRequestsByAgentParams) ([]db.PermissionRequest, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ListPermissionRulesByAgency(ctx context.Context, agencyID string) ([]db.PermissionRule, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) ResetGuardrailBudgets(ctx context.Context, resetAt int64) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpdateGuardrailBudgetUsed(ctx context.Context, arg db.UpdateGuardrailBudgetUsedParams) error {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpsertGuardrailBudget(ctx context.Context, arg db.UpsertGuardrailBudgetParams) (db.GuardrailBudget, error) {
	panic("not implemented")
}
func (m *mockRecoveryQuerier) UpsertGuardrailPreferences(ctx context.Context, arg db.UpsertGuardrailPreferencesParams) (db.GuardrailPreference, error) {
	panic("not implemented")
}

// Embedding-related methods for mockRecoveryQuerier
func (m *mockRecoveryQuerier) CountEpisodeEmbeddings(ctx context.Context) (int64, error) {
	return 0, nil
}
func (m *mockRecoveryQuerier) CountFactEmbeddings(ctx context.Context) (int64, error) {
	return 0, nil
}
func (m *mockRecoveryQuerier) CreateEpisodeEmbedding(ctx context.Context, arg db.CreateEpisodeEmbeddingParams) (db.EpisodeEmbedding, error) {
	return db.EpisodeEmbedding{}, nil
}
func (m *mockRecoveryQuerier) CreateFactEmbedding(ctx context.Context, arg db.CreateFactEmbeddingParams) (db.FactEmbedding, error) {
	return db.FactEmbedding{}, nil
}
func (m *mockRecoveryQuerier) DeleteEpisodeEmbedding(ctx context.Context, episodeID string) error {
	return nil
}
func (m *mockRecoveryQuerier) DeleteFactEmbedding(ctx context.Context, factID string) error {
	return nil
}
func (m *mockRecoveryQuerier) GetEpisodeEmbedding(ctx context.Context, episodeID string) (db.EpisodeEmbedding, error) {
	return db.EpisodeEmbedding{}, nil
}
func (m *mockRecoveryQuerier) GetEpisodeEmbeddingByHash(ctx context.Context, arg db.GetEpisodeEmbeddingByHashParams) (db.EpisodeEmbedding, error) {
	return db.EpisodeEmbedding{}, nil
}
func (m *mockRecoveryQuerier) GetFactEmbedding(ctx context.Context, factID string) (db.FactEmbedding, error) {
	return db.FactEmbedding{}, nil
}
func (m *mockRecoveryQuerier) GetFactEmbeddingByHash(ctx context.Context, arg db.GetFactEmbeddingByHashParams) (db.FactEmbedding, error) {
	return db.FactEmbedding{}, nil
}
func (m *mockRecoveryQuerier) ListEpisodeEmbeddings(ctx context.Context, arg db.ListEpisodeEmbeddingsParams) ([]db.EpisodeEmbedding, error) {
	return []db.EpisodeEmbedding{}, nil
}
func (m *mockRecoveryQuerier) ListFactEmbeddings(ctx context.Context, arg db.ListFactEmbeddingsParams) ([]db.FactEmbedding, error) {
	return []db.FactEmbedding{}, nil
}

func TestRecoveryManager_Recover_NoOrphanedTasks(t *testing.T) {
	t.Parallel()

	mock := &mockRecoveryQuerier{
		runningTasks: nil,
		queuedTasks:  nil,
	}
	broker := pubsub.NewBroker[TaskEvent]()
	rm := NewRecoveryManager(mock, broker, PolicyRequeue)

	err := rm.Recover(context.Background())
	require.NoError(t, err)
}

func TestRecoveryManager_Recover_PolicyRequeue(t *testing.T) {
	t.Parallel()

	runningTasks := []db.Task{
		{
			ID:       "task-1",
			Name:     "Orphaned Task 1",
			Status:   string(TaskStatusRunning),
			Priority: 50,
		},
		{
			ID:       "task-2",
			Name:     "Orphaned Task 2",
			Status:   string(TaskStatusRunning),
			Priority: 50,
		},
	}

	mock := &mockRecoveryQuerier{
		runningTasks: runningTasks,
		queuedTasks:  nil,
	}

	broker := pubsub.NewBroker[TaskEvent]()
	rm := NewRecoveryManager(mock, broker, PolicyRequeue)

	err := rm.Recover(context.Background())
	require.NoError(t, err)
}

func TestRecoveryManager_Recover_PolicyFail(t *testing.T) {
	t.Parallel()

	runningTasks := []db.Task{
		{
			ID:       "task-1",
			Name:     "Orphaned Task 1",
			Status:   string(TaskStatusRunning),
			Priority: 50,
		},
	}

	mock := &mockRecoveryQuerier{
		runningTasks: runningTasks,
		queuedTasks:  nil,
	}

	broker := pubsub.NewBroker[TaskEvent]()
	rm := NewRecoveryManager(mock, broker, PolicyFail)

	err := rm.Recover(context.Background())
	require.NoError(t, err)
}

func TestRecoveryManager_Recover_QueuedTasksLeftInQueue(t *testing.T) {
	t.Parallel()

	queuedTasks := []db.Task{
		{
			ID:       "task-1",
			Name:     "Queued Task 1",
			Status:   string(TaskStatusQueued),
			Priority: 50,
		},
		{
			ID:       "task-2",
			Name:     "Queued Task 2",
			Status:   string(TaskStatusQueued),
			Priority: 50,
		},
	}

	mock := &mockRecoveryQuerier{
		runningTasks: nil,
		queuedTasks:  queuedTasks,
	}

	broker := pubsub.NewBroker[TaskEvent]()
	rm := NewRecoveryManager(mock, broker, PolicyRequeue)

	err := rm.Recover(context.Background())
	require.NoError(t, err)
}

func TestRecoveryManager_requeueTask(t *testing.T) {
	t.Parallel()

	taskID := TaskID("test-task-id")
	mock := &mockRecoveryQuerier{
		runningTasks: []db.Task{{ID: string(taskID), Status: string(TaskStatusRunning)}},
	}
	broker := pubsub.NewBroker[TaskEvent]()
	rm := NewRecoveryManager(mock, broker, PolicyRequeue)

	err := rm.requeueTask(context.Background(), taskID)
	require.NoError(t, err)
}

func TestRecoveryManager_failTask(t *testing.T) {
	t.Parallel()

	taskID := TaskID("test-task-id")
	mock := &mockRecoveryQuerier{
		runningTasks: []db.Task{{ID: string(taskID), Status: string(TaskStatusRunning)}},
	}
	broker := pubsub.NewBroker[TaskEvent]()
	rm := NewRecoveryManager(mock, broker, PolicyFail)

	err := rm.failTask(context.Background(), taskID, "test recovery failure")
	require.NoError(t, err)
}

func TestRecoveryPolicy_Constants(t *testing.T) {
	t.Parallel()

	assert.Equal(t, RecoveryPolicy("requeue_running"), PolicyRequeue)
	assert.Equal(t, RecoveryPolicy("fail_running"), PolicyFail)
}

func TestNewRecoveryManager(t *testing.T) {
	t.Parallel()

	mock := &mockRecoveryQuerier{}
	broker := pubsub.NewBroker[TaskEvent]()

	rm := NewRecoveryManager(mock, broker, PolicyRequeue)

	assert.NotNil(t, rm)
	assert.Equal(t, mock, rm.db)
	assert.Equal(t, broker, rm.eventBroker)
	assert.Equal(t, PolicyRequeue, rm.policy)
}
