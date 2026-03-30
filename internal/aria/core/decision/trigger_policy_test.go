package decision

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
)

func TestTriggerPolicy_DeepPath(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 60}
	risk := RiskScore{Value: 45, Category: RiskExpensive}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Should use deep path when complexity 60 + risk 45")
}

func TestTriggerPolicy_FastPath(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 20}
	risk := RiskScore{Value: 10, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentQuestion,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexitySimple,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.False(t, decision.UseDeepPath, "Should force fast path when complexity <= 20")
}

func TestTriggerPolicy_NonTrigger(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	// Simple Q&A with Question intent and Simple complexity
	complexity := ComplexityScore{Value: 15}
	risk := RiskScore{Value: 5, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentQuestion,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexitySimple,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.False(t, decision.UseDeepPath, "Simple Q&A should force fast path")
}

func TestTriggerPolicy_ComplexityThreshold(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	// Complexity exactly at threshold (55)
	complexity := ComplexityScore{Value: 55}
	risk := RiskScore{Value: 10, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexityMedium,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Complexity at threshold should trigger deep path")
}

func TestTriggerPolicy_RiskThreshold(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 30}
	risk := RiskScore{Value: 40, Category: RiskExpensive}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexitySimple,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Risk at threshold should trigger deep path")
}

func TestTriggerPolicy_ComplexClassification(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 40}
	risk := RiskScore{Value: 20, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityComplex, // +80 trigger
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Complex classification should trigger deep path")
}

func TestTriggerPolicy_AnalysisIntent(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 30}
	risk := RiskScore{Value: 20, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentAnalysis, // +60 trigger
		Domain:     routing.DomainAnalytics,
		Complexity: routing.ComplexityMedium,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Analysis intent should trigger deep path")
}

func TestTriggerPolicy_PlanningIntent(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 30}
	risk := RiskScore{Value: 20, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentPlanning, // +60 trigger
		Domain:     routing.DomainGeneral,
		Complexity: routing.ComplexityMedium,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Planning intent should trigger deep path")
}

func TestTriggerPolicy_HighRiskCategory(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	complexity := ComplexityScore{Value: 30}
	risk := RiskScore{Value: 25, Category: RiskIrreversible} // +85 trigger
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexitySimple,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.True(t, decision.UseDeepPath, "Irreversible risk category should trigger deep path")
}

func TestTriggerPolicy_DefaultTimeout(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()

	assert.Equal(t, 12, policy.MaxThoughts)
	assert.Equal(t, 12000, policy.TimeoutMs)
}

func TestTriggerPolicy_CustomConfig(t *testing.T) {
	t.Parallel()

	policy := NewTriggerPolicyWithConfig(60, 45, 15, 15000)

	assert.Equal(t, 60, policy.ComplexityThreshold)
	assert.Equal(t, 45, policy.RiskThreshold)
	assert.Equal(t, 15, policy.MaxThoughts)
	assert.Equal(t, 15000, policy.TimeoutMs)
}

func TestTriggerPolicy_NoTriggerLowComplexity(t *testing.T) {
	t.Parallel()

	policy := NewDefaultTriggerPolicy()
	ctx := context.Background()

	// Even with some triggers, low complexity forces fast path
	complexity := ComplexityScore{Value: 25}
	risk := RiskScore{Value: 35, Category: RiskStandard}
	class := routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexitySimple,
	}

	decision, err := policy.ShouldUseDeepPath(ctx, complexity, risk, class)

	assert.NoError(t, err)
	assert.False(t, decision.UseDeepPath, "Low complexity should force fast path even with some risk")
}
