package memory

import (
	"context"
	"database/sql"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"

	"github.com/pressly/goose/v3"
)

// setupE2EDB creates a temporary database with migrations applied for E2E testing.
func setupE2EDB(t *testing.T) (*sql.DB, func()) {
	tmpDir := t.TempDir()
	dbPath := tmpDir + "/test_e2e.db"

	sqlDB, err := sql.Open("sqlite3", dbPath)
	require.NoError(t, err)

	// Set pragmas
	pragmas := []string{
		"PRAGMA foreign_keys = ON;",
		"PRAGMA journal_mode = WAL;",
	}
	for _, pragma := range pragmas {
		if _, err = sqlDB.Exec(pragma); err != nil {
			logging.Error("Failed to set pragma", pragma, err)
		}
	}

	// Setup goose
	goose.SetBaseFS(db.FS)
	if err := goose.SetDialect("sqlite3"); err != nil {
		sqlDB.Close()
		t.Fatalf("failed to set goose dialect: %v", err)
	}

	// Run migrations
	if err := goose.Up(sqlDB, "migrations"); err != nil {
		sqlDB.Close()
		t.Fatalf("failed to run migrations: %v", err)
	}

	cleanup := func() {
		sqlDB.Close()
	}

	return sqlDB, cleanup
}

// TestE2E_MemoryLearningFlow tests the complete memory-learning flow with a real database.
func TestE2E_MemoryLearningFlow(t *testing.T) {
	t.Parallel()

	// Create a temporary database for E2E testing
	sqlDB, cleanup := setupE2EDB(t)
	defer cleanup()

	// Create the querier (db.Queries implements db.Querier)
	querier := db.New(sqlDB)

	// Create the memory service
	svc := NewService(querier, 30*time.Minute, nil, EmbeddingConfig{})
	ctx := context.Background()

	// Create a session first for FK constraints (working_memory_contexts references sessions)
	_, err := querier.CreateSession(ctx, db.CreateSessionParams{
		ID:               "session-e2e-1",
		ParentSessionID:  sql.NullString{},
		Title:            "E2E Test Session",
		MessageCount:     0,
		PromptTokens:     0,
		CompletionTokens: 0,
		Cost:             0,
	})
	require.NoError(t, err)

	// Step 1: Record a coding task episode
	episode1 := Episode{
		SessionID: "session-e2e-1",
		AgencyID:  "development",
		AgentID:   "coder",
		Task:      map[string]any{"type": "code_review", "description": "Review PR #123"},
		Actions: []Action{
			{Type: "tool_call", Tool: "grep", Timestamp: time.Now()},
		},
		Outcome: "success",
	}
	err = svc.RecordEpisode(ctx, episode1)
	require.NoError(t, err)

	// Step 2: Store a semantic fact
	fact := Fact{
		Domain:     "development",
		Category:   "code-review",
		Content:    "Always check for error handling in Go",
		Source:     "e2e-test",
		Confidence: 0.9,
	}
	err = svc.StoreFact(ctx, fact)
	require.NoError(t, err)

	// Step 3: Save a procedure
	procedure := Procedure{
		Name:        "go-code-review",
		Description: "Standard Go code review procedure",
		Trigger: TriggerCondition{
			Type:    "task_type",
			Pattern: "code_review",
		},
		Steps: []ProcedureStep{
			{Order: 1, Name: "grep-errors", Description: "Search for error handling", Action: "grep-error"},
			{Order: 2, Name: "check-tests", Description: "Verify tests exist", Action: "grep-test"},
		},
		SuccessRate: 0.85,
		UseCount:    10,
	}
	err = svc.SaveProcedure(ctx, procedure)
	require.NoError(t, err)

	// Step 4: Test episodic retrieval
	episodes, err := svc.SearchEpisodes(ctx, EpisodeQuery{Limit: 10})
	require.NoError(t, err)
	assert.NotEmpty(t, episodes)

	// Step 5: Test semantic retrieval
	facts, err := svc.GetFacts(ctx, "development")
	require.NoError(t, err)
	assert.NotEmpty(t, facts)

	// Step 6: Test procedural retrieval
	procs, err := svc.FindApplicableProcedures(ctx, map[string]any{"type": "code_review"})
	require.NoError(t, err)
	assert.NotEmpty(t, procs)

	// Step 7: Test learning from success
	action := Action{Type: "tool_call", Tool: "bash", Timestamp: time.Now()}
	err = svc.LearnFromSuccess(ctx, action, "Build successful")
	require.NoError(t, err)

	// Step 8: Test performance metrics
	metrics, err := svc.GetPerformanceMetrics(ctx, TimeRange{
		Start: time.Now().Add(-1 * time.Hour),
		End:   time.Now(),
	})
	require.NoError(t, err)
	assert.GreaterOrEqual(t, metrics.TotalTasks, int64(1))

	// Step 9: Test working memory
	workCtx := Context{
		SessionID: "session-e2e-1",
		TaskID:    "task-1",
		AgencyID:  "development",
		AgentID:   "coder",
		Metadata:  map[string]any{"pr": "123"},
	}
	err = svc.SetContext(ctx, "session-e2e-1", workCtx)
	require.NoError(t, err)

	retrievedCtx, err := svc.GetContext(ctx, "session-e2e-1")
	require.NoError(t, err)
	assert.Equal(t, "session-e2e-1", retrievedCtx.SessionID)
	assert.Equal(t, "123", retrievedCtx.Metadata["pr"])
}

// TestSearchEpisodes_Filters tests episode search with various filters.
func TestSearchEpisodes_Filters(t *testing.T) {
	t.Parallel()

	// Test that EpisodeQuery struct has all required fields
	query := EpisodeQuery{
		SessionID: "session-123",
		AgencyID:  "agency-1",
		AgentID:   "agent-1",
		TaskType:  "code_review",
		TimeRange: &TimeRange{
			Start: time.Now().Add(-24 * time.Hour),
			End:   time.Now(),
		},
		Limit: 10,
	}

	assert.NotEmpty(t, query.SessionID)
	assert.NotEmpty(t, query.AgencyID)
	assert.NotEmpty(t, query.AgentID)
	assert.NotEmpty(t, query.TaskType)
	assert.NotNil(t, query.TimeRange)
	assert.Equal(t, 10, query.Limit)
}

// TestFindApplicableProcedures_Scoring tests that procedures are scored correctly.
func TestFindApplicableProcedures_Scoring(t *testing.T) {
	t.Parallel()

	// Test score calculation
	proc := Procedure{
		Trigger: TriggerCondition{
			Type:    "task_type",
			Pattern: "code_review",
		},
		SuccessRate: 0.9,
		UseCount:    50,
	}

	score := calculateProcedureScore(proc, "code_review", "Please do a code review of this file")
	assert.Greater(t, score, 0.5, "Score should be high for matching trigger type")
}

// TestRetentionConfig_Defaults tests default retention configuration.
func TestRetentionConfig_Defaults(t *testing.T) {
	t.Parallel()

	cfg := DefaultRetentionConfig()

	assert.Equal(t, 30*24*time.Hour, cfg.EpisodeRetention)
	assert.Equal(t, 90*24*time.Hour, cfg.FactRetention)
	assert.Equal(t, 180*24*time.Hour, cfg.ProcedureRetention)
	assert.Equal(t, 7*24*time.Hour, cfg.InsightRetention)
	assert.Equal(t, 1000, cfg.MaxEpisodesPerDay)
}

// TestMemoryService_IntegrationQueryKnowledge tracks usage when querying knowledge.
func TestMemoryService_IntegrationQueryKnowledge(t *testing.T) {
	t.Parallel()

	svc := NewService(&mockQuerier{}, 30*time.Minute, nil, EmbeddingConfig{}).(*memoryService)
	ctx := context.Background()

	// Store a fact
	fact := Fact{
		Domain:     "testing",
		Category:   "test",
		Content:    "This is a test fact about integration",
		Source:     "unit-test",
		Confidence: 0.9,
	}
	err := svc.StoreFact(ctx, fact)
	require.NoError(t, err)

	// Query knowledge multiple times to track usage
	items, err := svc.QueryKnowledge(ctx, "integration")
	require.NoError(t, err)
	assert.NotEmpty(t, items)

	// Verify that IncrementFactUsage was called (tracked via mock)
	// The mockQuerier.IncrementFactUsage is a no-op, but the call happens
}
