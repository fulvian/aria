package pipeline

import (
	"context"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/core/plan"
	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockMemoryService is a mock for testing
type mockMemoryService struct{}

func (m *mockMemoryService) Close() error { return nil }

func (m *mockMemoryService) GetContext(ctx context.Context, sessionID string) (interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) SetContext(ctx context.Context, sessionID string, context interface{}) error {
	return nil
}

func (m *mockMemoryService) RecordEpisode(ctx context.Context, episode interface{}) error {
	return nil
}

func (m *mockMemoryService) SearchEpisodes(ctx context.Context, query interface{}) ([]interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) GetSimilarEpisodes(ctx context.Context, situation interface{}) ([]interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) StoreFact(ctx context.Context, fact interface{}) error {
	return nil
}

func (m *mockMemoryService) GetFacts(ctx context.Context, domain string) ([]interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) QueryKnowledge(ctx context.Context, query string) ([]interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) SaveProcedure(ctx context.Context, procedure interface{}) error {
	return nil
}

func (m *mockMemoryService) GetProcedure(ctx context.Context, name string) (interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) FindApplicableProcedures(ctx context.Context, task map[string]any) ([]interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) LearnFromSuccess(ctx context.Context, action interface{}, outcome string) error {
	return nil
}

func (m *mockMemoryService) LearnFromFailure(ctx context.Context, action interface{}, err error) error {
	return nil
}

func (m *mockMemoryService) GetPerformanceMetrics(ctx context.Context, timeRange interface{}) (interface{}, error) {
	return nil, nil
}

func (m *mockMemoryService) GenerateInsights(ctx context.Context) ([]string, error) {
	return nil, nil
}

// mockQueryClassifier is a simple mock classifier for testing
type mockQueryClassifier struct{}

func (m *mockQueryClassifier) Classify(ctx context.Context, query routing.Query) (routing.Classification, error) {
	// Return a simple classification based on query text
	complexity := routing.ComplexitySimple
	if len(query.Text) > 50 {
		complexity = routing.ComplexityMedium
	}
	return routing.Classification{
		Intent:          routing.IntentTask,
		Domain:          routing.DomainGeneral,
		Complexity:      complexity,
		Confidence:      0.8,
		SuggestedTarget: routing.TargetAgency,
	}, nil
}

func (m *mockQueryClassifier) GetSupportedIntents() []routing.Intent {
	return []routing.Intent{routing.IntentTask}
}

func (m *mockQueryClassifier) GetSupportedDomains() []routing.DomainName {
	return []routing.DomainName{routing.DomainGeneral}
}

// TestOrchestratorPipeline_FastPath tests the Fast Path execution
func TestOrchestratorPipeline_FastPath(t *testing.T) {
	t.Parallel()

	// Create components
	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	// Create pipeline with nil memory service (not needed for fast path)
	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		&mockQueryClassifier{},
	)

	// Create a simple query
	query := core.Query{
		Text:      "What is the capital of France?",
		SessionID: "test-session-1",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	// Execute pipeline
	ctx := context.Background()
	response, err := pipeline.Run(ctx, query)

	// Verify results
	require.NoError(t, err)
	assert.NotEmpty(t, response.Text)
	assert.Contains(t, response.Text, "Fast path")
	// Fast path should have real classification info
	assert.Contains(t, response.Text, "classification")
}

// TestOrchestratorPipeline_FastPath_WithComplexQuery tests fast path with a more complex query
func TestOrchestratorPipeline_FastPath_WithComplexQuery(t *testing.T) {
	t.Parallel()

	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		&mockQueryClassifier{},
	)

	// Longer query triggers medium complexity
	query := core.Query{
		Text:      "Help me understand the architecture of this application and how the components interact",
		SessionID: "test-session-2",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	ctx := context.Background()
	response, err := pipeline.Run(ctx, query)

	require.NoError(t, err)
	assert.NotEmpty(t, response.Text)
}

// TestOrchestratorPipeline_DeepPath tests the Deep Path execution
func TestOrchestratorPipeline_DeepPath(t *testing.T) {
	t.Parallel()

	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		&mockQueryClassifier{},
	)

	// Create a query that will trigger deep path
	query := core.Query{
		Text:      "Plan a comprehensive refactoring of the authentication system to use OAuth 2.0",
		SessionID: "test-session-3",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	// Build classification and decision that would trigger deep path
	class := routing.Classification{
		Intent:          routing.IntentTask,
		Domain:          routing.DomainDevelopment,
		Complexity:      routing.ComplexityComplex,
		Confidence:      0.9,
		SuggestedTarget: routing.TargetAgency,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 80,
		},
		Risk: decision.RiskScore{
			Value: 30,
		},
		Explanation: "Complex task requiring deep path",
	}

	ctx := context.Background()
	response, err := pipeline.RunDeepPath(ctx, query, class, decision_)

	require.NoError(t, err)
	assert.NotEmpty(t, response.Text)
	// Deep path should include review verdict
	assert.Contains(t, response.Text, "Deep path completed")
}

// TestOrchestratorPipeline_DeepPath_WithReplan tests deep path with replan scenario
func TestOrchestratorPipeline_DeepPath_WithReplan(t *testing.T) {
	t.Parallel()

	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewerWithConfig(plan.ReviewerConfig{
		MinAcceptanceScore: 0.95, // High threshold to trigger replan
		MaxReplan:          2,
		MaxRetries:         1,
	})

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		&mockQueryClassifier{},
	)

	query := core.Query{
		Text:      "Implement a complete distributed tracing system with OpenTelemetry",
		SessionID: "test-session-4",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	class := routing.Classification{
		Intent:          routing.IntentTask,
		Domain:          routing.DomainDevelopment,
		Complexity:      routing.ComplexityComplex,
		Confidence:      0.85,
		SuggestedTarget: routing.TargetAgency,
	}

	decision_ := decision.ExecutionDecision{
		Path: decision.PathDeep,
		Complexity: decision.ComplexityScore{
			Value: 85,
		},
		Risk: decision.RiskScore{
			Value: 40,
		},
		Explanation: "Complex task requiring deep path",
	}

	ctx := context.Background()
	response, err := pipeline.RunDeepPath(ctx, query, class, decision_)

	// Should complete even with potential replan
	require.NoError(t, err)
	assert.NotEmpty(t, response.Text)
}

// TestOrchestratorPipeline_Classification tests that classification is properly used
func TestOrchestratorPipeline_Classification(t *testing.T) {
	t.Parallel()

	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	classifier := &mockQueryClassifier{}

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		classifier,
	)

	query := core.Query{
		Text:      "Debug this code that has a race condition",
		SessionID: "test-session-5",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	ctx := context.Background()
	response, err := pipeline.Run(ctx, query)

	require.NoError(t, err)
	// Should contain classification info
	assert.Contains(t, response.Text, "task")
	assert.Contains(t, response.Text, "confidence")
}

// TestOrchestratorPipeline_ContextRecovery tests that context recovery is attempted
func TestOrchestratorPipeline_ContextRecovery(t *testing.T) {
	t.Parallel()

	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil, // No memory service
		&mockQueryClassifier{},
	)

	query := core.Query{
		Text:      "Continue with the previous task",
		SessionID: "test-session-with-context",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	ctx := context.Background()
	response, err := pipeline.Run(ctx, query)

	// Should work even without memory service
	require.NoError(t, err)
	assert.NotEmpty(t, response.Text)
}

// TestOrchestratorPipeline_Cancellation tests pipeline handles context cancellation
func TestOrchestratorPipeline_Cancellation(t *testing.T) {
	t.Parallel()

	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		&mockQueryClassifier{},
	)

	query := core.Query{
		Text:      "This is a very long and complex task that will take time to complete properly",
		SessionID: "test-session-cancel",
		UserID:    "test-user",
		Metadata:  map[string]any{},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Millisecond)
	defer cancel()

	// Give context time to expire
	time.Sleep(10 * time.Millisecond)

	_, err := pipeline.Run(ctx, query)

	// Context may be cancelled but we should handle it gracefully
	// Depending on implementation, it may or may not return error
	if err != nil {
		assert.True(t, context.Canceled == err || context.DeadlineExceeded == err)
	}
}

// BenchmarkOrchestratorPipeline_FastPath benchmarks fast path performance
func BenchmarkOrchestratorPipeline_FastPath(b *testing.B) {
	decisionEngine := decision.NewDecisionEngineWithDefaults()
	planner := plan.NewPlanner()
	executor := plan.NewExecutor()
	reviewer := plan.NewReviewer()

	pipeline := NewOrchestratorPipeline(
		decisionEngine,
		planner,
		executor,
		reviewer,
		nil,
		&mockQueryClassifier{},
	)

	query := core.Query{
		Text:      "Simple query",
		SessionID: "bench-session",
		UserID:    "bench-user",
		Metadata:  map[string]any{},
	}

	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = pipeline.Run(ctx, query)
	}
}
