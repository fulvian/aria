package decision

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
)

func TestRiskAnalyzer_Standard(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "What is the weather today?",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentQuestion,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexitySimple,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.Less(t, score.Value, 40, "Standard query should have risk < 40")
	assert.Equal(t, RiskStandard, score.Category)
}

func TestRiskAnalyzer_Destructive(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Delete all the files in the directory",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 30, "Destructive query should have risk >= 30")
}

func TestRiskAnalyzer_DangerousCommands(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Run sudo rm -rf / on the server",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 40, "Dangerous command should have high risk")
	assert.Equal(t, RiskSafety, score.Category)
}

func TestRiskAnalyzer_DeployAction(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Deploy the application to production",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 25, "Deploy action should add risk")
}

func TestRiskAnalyzer_SensitiveData(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Store the password in the config file",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexitySimple,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 20, "Sensitive data query should add risk")
}

func TestRiskAnalyzer_ProductionEnvironment(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Update the production database settings",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 20, "Production query should add risk")
}

func TestRiskAnalyzer_FilePath(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Edit the file at /etc/config/app.json",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexitySimple,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 10, "File path should add risk")
}

func TestRiskAnalyzer_CreationInDevelopment(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	query := routing.Query{
		Text:    "Create a new module for the application",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentCreation,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 15, "Creation in development should add risk")
}

func TestRiskAnalyzer_MultipleFactors(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	// Query with multiple risk factors
	query := routing.Query{
		Text:    "Delete all files in /production/data and drop the database",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, score.Value, 60, "Multiple factors should result in high risk")
	assert.Equal(t, RiskIrreversible, score.Category)
}

func TestRiskAnalyzer_CappedAt100(t *testing.T) {
	t.Parallel()

	analyzer := NewRiskAnalyzer()
	ctx := context.Background()

	// Query with maximum risk factors
	query := routing.Query{
		Text:    "sudo rm -rf /production/data delete the database drop all tables and remove everything",
		History: []string{},
	}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex,
	}

	score, err := analyzer.Analyze(ctx, query, class)

	assert.NoError(t, err)
	assert.LessOrEqual(t, score.Value, 100, "Risk score should be capped at 100")
}
