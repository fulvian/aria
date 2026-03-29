package decision

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
)

func TestComplexityAnalyzer_Simple(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "What is the weather?",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentQuestion,
		Domain:        routing.DomainGeneral,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.Empty(t, score.Factors, "Simple query should have no complexity factors")
	assert.Less(t, score.Value, 36, "Simple query should have score < 36")
}

func TestComplexityAnalyzer_MultiStep(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	// Query with "and then" and "also" and additional complexity factors
	query := routing.Query{
		Text:    "First do X and then do Y also do Z plus all the refactoring",
		History: []string{"msg1", "msg2", "msg3", "msg4", "msg5", "msg6"},
	}
	class := routing.Classification{
		Intent:        routing.IntentTask,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityComplex,
		RequiresState: true,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 55, "Multi-step query should have score >= 55")
}

func TestComplexityAnalyzer_Architectural(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	// Query with refactor and architecture keywords
	query := routing.Query{
		Text:    "We need to refactor the entire architecture",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentTask,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityComplex,
		RequiresState: false,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 70, "Architectural query should have score >= 70")
}

func TestComplexityAnalyzer_WithHistory(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Continue with the implementation",
		History: []string{"msg1", "msg2", "msg3", "msg4", "msg5", "msg6"},
	}
	class := routing.Classification{
		Intent:        routing.IntentTask,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityMedium,
		RequiresState: true,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 30, "Query with long history should have elevated score")
}

func TestComplexityAnalyzer_DevelopmentWithCodeTerms(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Create a new function in the class",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentCreation,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	// Should include development domain factor (+10)
	hasDevFactor := false
	for _, f := range score.Factors {
		if f.Name == "development_domain" {
			hasDevFactor = true
			break
		}
	}
	assert.True(t, hasDevFactor, "Should have development_domain factor")
}

func TestComplexityAnalyzer_AnalysisIntent(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Analyze the performance metrics",
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentAnalysis,
		Domain:        routing.DomainAnalytics,
		Complexity:    routing.ComplexityMedium,
		RequiresState: false,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 15, "Analysis intent should add 15 points")
}

func TestComplexityAnalyzer_LongQuery(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	// Create a query longer than 200 chars
	longText := "This is a very long query that exceeds two hundred characters and should therefore add complexity points to the overall calculation for testing purposes."
	for len(longText) < 250 {
		longText += " Adding more text to make it longer."
	}

	query := routing.Query{
		Text:    longText,
		History: []string{},
	}
	class := routing.Classification{
		Intent:        routing.IntentTask,
		Domain:        routing.DomainGeneral,
		Complexity:    routing.ComplexitySimple,
		RequiresState: false,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 10, "Long query should add 10 points")
}

func TestComplexityAnalyzer_CappedAt100(t *testing.T) {
	t.Parallel()

	analyzer := NewComplexityAnalyzer()
	ctx := context.Background()

	// Create a complex query with multiple factors
	query := routing.Query{
		Text:    "Refactor the entire architecture and migrate all the codebases to the new system with multiple modules and classes and then also deploy to production",
		History: []string{"msg1", "msg2", "msg3", "msg4", "msg5", "msg6"},
	}
	class := routing.Classification{
		Intent:        routing.IntentAnalysis,
		Domain:        routing.DomainDevelopment,
		Complexity:    routing.ComplexityComplex,
		RequiresState: true,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.LessOrEqual(t, score.Value, 100, "Score should be capped at 100")
}
