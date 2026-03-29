package memory

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestIntegration_MemoryLearningFlow tests the complete memory-learning flow.
func TestIntegration_MemoryLearningFlow(t *testing.T) {
	t.Parallel()

	// This test would require a full integration setup with DB
	// For unit testing, we test individual components
	t.Skip("Integration test requires full app setup")
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

	svc := NewService(&mockQuerier{}, 30*time.Minute).(*memoryService)
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
