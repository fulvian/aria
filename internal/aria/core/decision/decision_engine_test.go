package decision

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDecisionEngine_Integration(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	query := routing.Query{
		Text:    "What is the weather today?",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentQuestion,
		Domain:        routing.DomainGeneral,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	assert.NotEmpty(t, decision.Explanation)
	assert.NotNil(t, decision.RoutingHint)
	assert.Equal(t, PathFast, decision.Path)
}

func TestDecisionEngine_FastPath(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Hello!",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentConversation,
		Domain:        routing.DomainGeneral,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	assert.Equal(t, PathFast, decision.Path)
}

func TestDecisionEngine_DeepPath(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	// Complex query that should trigger deep path
	query := routing.Query{
		Text:    "Refactor the entire architecture and migrate to a new system with multiple modules and classes and then also deploy to production",
		History: []string{"msg1", "msg2", "msg3", "msg4", "msg5", "msg6"},
	}
	class := routing.Classification{
		Intent:        routing.IntentAnalysis,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityComplex,
		RequiresState: true,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	assert.Equal(t, PathDeep, decision.Path)
}

func TestDecisionEngine_Config(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	cfg := engine.GetConfig()

	assert.Equal(t, 55, cfg.ComplexityThreshold)
	assert.Equal(t, 40, cfg.RiskThreshold)
	assert.NotNil(t, cfg.ComplexityAnalyzer)
	assert.NotNil(t, cfg.RiskAnalyzer)
	assert.NotNil(t, cfg.TriggerPolicy)
	assert.NotNil(t, cfg.PathSelector)
}

func TestDecisionEngine_CustomConfig(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngine(
		NewComplexityAnalyzer(),
		NewRiskAnalyzer(),
		NewTriggerPolicyWithConfig(60, 50, 15, 15000),
		NewPathSelector(),
		60,
		50,
	)

	cfg := engine.GetConfig()
	assert.Equal(t, 60, cfg.ComplexityThreshold)
	assert.Equal(t, 50, cfg.RiskThreshold)
}

func TestDecisionEngine_HighRiskQuery(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Delete all files and drop the database in production",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentTask,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityMedium,
		RequiresState: false,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	assert.Equal(t, PathDeep, decision.Path)
	assert.Greater(t, decision.Risk.Value, 40)
	assert.Equal(t, RiskIrreversible, decision.Risk.Category)
}

func TestDecisionEngine_AnalysisQuery(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	// Analysis query with complex classification
	query := routing.Query{
		Text:    "Analyze the architecture and refactor the entire system",
		History: []string{"msg1", "msg2", "msg3", "msg4", "msg5"},
	}
	class := routing.Classification{
		Intent:        routing.IntentAnalysis,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityComplex,
		RequiresState: true,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	assert.Equal(t, PathDeep, decision.Path)
}

func TestDecisionEngine_RoutingHint(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Test query",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentTask,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityComplex,
		RequiresState: false,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	require.NotNil(t, decision.RoutingHint)
	assert.NotZero(t, decision.RoutingHint.BudgetTokenMax)
}

func TestDecisionEngine_Explanation(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Simple question",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentQuestion,
		Domain:        routing.DomainGeneral,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	decision, err := engine.Decide(ctx, query, class)

	require.NoError(t, err)
	assert.Contains(t, decision.Explanation, "fast")
}

func TestDecisionEngine_MultipleRuns(t *testing.T) {
	t.Parallel()

	engine := NewDecisionEngineWithDefaults()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Test",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentQuestion,
		Domain:        routing.DomainGeneral,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	// Run multiple times to ensure consistency
	for i := 0; i < 5; i++ {
		decision, err := engine.Decide(ctx, query, class)
		require.NoError(t, err)
		assert.Equal(t, PathFast, decision.Path)
	}
}
