package routing

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPolicyRouter_RouteWithPolicy_Boost(t *testing.T) {
	t.Parallel()

	// Create base router
	baseRouter := NewDefaultRouter()

	// Create capability registry with some agencies
	registry := NewCapabilityRegistry()
	require.NoError(t, registry.RegisterAgency(AgencyCapability{
		Name:     AgencyName("dev-agency"),
		Domain:   DomainDevelopment,
		Skills:   []SkillName{"coding", "testing"},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	// Create policy router
	router := NewPolicyRouter(baseRouter, registry)

	// Policy with priority rule that boosts confidence
	policy := RoutingPolicy{
		ConfidenceThreshold: 0.3, // Low threshold
		PriorityRules: []PriorityRule{
			{
				Name:      "dev-task-boost",
				Condition: "domain=development AND intent=task",
				Boost:     0.2, // Boost by 0.2 when matched
			},
		},
	}

	query := Query{Text: "review my code"}
	class := Classification{
		Intent:     IntentTask,
		Domain:     DomainDevelopment,
		Complexity: ComplexityMedium,
	}

	decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
	require.NoError(t, err)

	// The priority rule should have boosted confidence
	assert.Greater(t, decision.Confidence, 0.5) // Base + boost
}

func TestPolicyRouter_RouteWithPolicy_CapabilityMatch(t *testing.T) {
	t.Parallel()

	// Create base router with lower confidence
	baseRouter := NewDefaultRouter()

	// Create capability registry
	registry := NewCapabilityRegistry()
	require.NoError(t, registry.RegisterAgency(AgencyCapability{
		Name:     AgencyName("superior-agency"),
		Domain:   DomainDevelopment,
		Skills:   []SkillName{"code-review", "refactoring"},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	require.NoError(t, registry.RegisterAgent("superior-agency", AgentCapability{
		Name:     AgentName("expert-coder"),
		Agency:   AgencyName("superior-agency"),
		Skills:   []SkillName{"code-review"},
		Tools:    []string{"bash", "edit", "grep"},
		CostHint: CostHint{TokenBudget: 3000},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	router := NewPolicyRouter(baseRouter, registry)

	// Policy with capability match enabled
	policy := RoutingPolicy{
		CapabilityMatch: true,
		PriorityRules:   []PriorityRule{},
	}

	query := Query{Text: "review this code for bugs"}
	class := Classification{
		Intent:     IntentTask,
		Domain:     DomainDevelopment,
		Complexity: ComplexityMedium,
	}

	decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
	require.NoError(t, err)

	// Should have been overridden by capability match
	assert.Greater(t, decision.Confidence, 0.7) // Boosted
	assert.Contains(t, decision.Explanation, "capability match")
}

func TestPolicyRouter_RouteWithPolicy_Fallback(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry() // Empty registry

	router := NewPolicyRouter(baseRouter, registry)

	// Policy with very high confidence threshold
	policy := RoutingPolicy{
		ConfidenceThreshold: 0.95, // Very high - most decisions will fallback
		PriorityRules:      []PriorityRule{},
	}

	query := Query{Text: "simple question"}
	class := Classification{
		Intent:     IntentQuestion,
		Domain:     DomainGeneral,
		Complexity: ComplexitySimple,
	}

	decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
	require.NoError(t, err)

	// Should fallback due to high threshold
	assert.True(t, decision.Fallback)
	assert.Contains(t, decision.Explanation, "below threshold")
}

func TestPolicyRouter_RouteWithPolicy_CostBudgetExceeded(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()

	router := NewPolicyRouter(baseRouter, registry)

	// Policy with very low cost budget
	policy := RoutingPolicy{
		CostBudget: CostBudget{
			MaxTokens: 10, // Very low - almost any operation would exceed
			MaxTimeMs: 1,  // Very low
		},
		PriorityRules: []PriorityRule{},
	}

	query := Query{Text: "do something"}
	class := Classification{
		Intent:     IntentTask,
		Domain:     DomainDevelopment,
		Complexity: ComplexitySimple,
	}

	decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
	require.NoError(t, err)

	// Should fallback due to low confidence and cost budget
	assert.True(t, decision.Fallback)
}

func TestPolicyRouter_RouteWithPolicy_SafetyBudget(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()

	router := NewPolicyRouter(baseRouter, registry)

	// Policy with very strict safety budget
	policy := RoutingPolicy{
		SafetyBudget: RiskScore{
			Value:      10, // Very low - risky operations will exceed
			Category:   RiskCategoryStandard,
		},
		PriorityRules: []PriorityRule{},
	}

	query := Query{Text: "delete all files and deploy to production"}
	class := Classification{
		Intent:     IntentTask,
		Domain:     DomainDevelopment,
		Complexity: ComplexityComplex,
	}

	decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
	require.NoError(t, err)

	// Should fallback due to safety budget
	assert.True(t, decision.Fallback)
	assert.Contains(t, decision.Explanation, "safety budget")
}

func TestPolicyRouter_SetGetPolicy(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()

	router := NewPolicyRouter(baseRouter, registry)

	// Get initial policy
	initial := router.GetRoutingPolicy()
	assert.Equal(t, 0.5, initial.ConfidenceThreshold)
	assert.False(t, initial.CapabilityMatch)

	// Set new policy
	newPolicy := RoutingPolicy{
		ConfidenceThreshold: 0.8,
		CapabilityMatch:     true,
		PriorityRules: []PriorityRule{
			{Name: "test-rule", Condition: "domain=development", Boost: 0.1},
		},
	}

	err := router.SetRoutingPolicy(newPolicy)
	require.NoError(t, err)

	// Verify policy was updated
	retrieved := router.GetRoutingPolicy()
	assert.Equal(t, 0.8, retrieved.ConfidenceThreshold)
	assert.True(t, retrieved.CapabilityMatch)
	assert.Len(t, retrieved.PriorityRules, 1)
}

func TestPolicyRouter_SetRoutingPolicy_InvalidThreshold(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()

	router := NewPolicyRouter(baseRouter, registry)

	// Test threshold > 1
	err := router.SetRoutingPolicy(RoutingPolicy{
		ConfidenceThreshold: 1.5,
	})
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "confidence threshold")

	// Test threshold < 0
	err = router.SetRoutingPolicy(RoutingPolicy{
		ConfidenceThreshold: -0.5,
	})
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "confidence threshold")
}

func TestPolicyRouter_DelegatesToBaseRouter(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()

	router := NewPolicyRouter(baseRouter, registry)

	// Test Route (delegation)
	query := Query{Text: "debug this error"}
	class := Classification{
		Intent:     IntentTask,
		Domain:     DomainDevelopment,
		Complexity: ComplexityMedium,
	}

	decision, err := router.Route(context.Background(), query, class)
	require.NoError(t, err)
	assert.NotEmpty(t, decision.Explanation)

	// Test GetRules (delegation)
	rules := router.GetRules()
	assert.NotEmpty(t, rules)

	// Test AddRule (delegation) - count rules before and after
	rulesBeforeAdd := len(router.GetRules())

	newRule := RoutingRule{
		ID:          "test-rule-delegation",
		Priority:    50,
		Name:        "Test Rule",
		Description: "A test rule",
		Intents:     []Intent{IntentTask},
		Domains:     []DomainName{DomainDevelopment},
		Target:      TargetAgency,
		Confidence:  0.8,
	}

	err = router.AddRule(newRule)
	require.NoError(t, err)

	// Verify rule was added
	rules = router.GetRules()
	assert.Len(t, rules, rulesBeforeAdd+1)

	// Test RemoveRule (delegation)
	err = router.RemoveRule("test-rule-delegation")
	require.NoError(t, err)

	// Verify rule was removed
	rulesAfterRemove := router.GetRules()
	assert.Len(t, rulesAfterRemove, rulesBeforeAdd)
}

func TestPolicyRouter_PriorityConditionMatching(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()
	router := NewPolicyRouter(baseRouter, registry)

	tests := []struct {
		name      string
		condition string
		query     Query
		class     Classification
		expected  bool
	}{
		{
			name:      "domain match",
			condition: "domain=development",
			query:     Query{Text: "test"},
			class:     Classification{Domain: DomainDevelopment},
			expected:  true,
		},
		{
			name:      "domain no match",
			condition: "domain=development",
			query:     Query{Text: "test"},
			class:     Classification{Domain: DomainCreative},
			expected:  false,
		},
		{
			name:      "intent match",
			condition: "intent=task",
			query:     Query{Text: "test"},
			class:     Classification{Intent: IntentTask},
			expected:  true,
		},
		{
			name:      "complexity match",
			condition: "complexity=simple",
			query:     Query{Text: "test"},
			class:     Classification{Complexity: ComplexitySimple},
			expected:  true,
		},
		{
			name:      "query contains match",
			condition: "query=review",
			query:     Query{Text: "please review this code"},
			class:     Classification{},
			expected:  true,
		},
		{
			name:      "AND condition - both match",
			condition: "domain=development AND intent=task",
			query:     Query{Text: "test"},
			class:     Classification{Domain: DomainDevelopment, Intent: IntentTask},
			expected:  true,
		},
		{
			name:      "AND condition - one fails",
			condition: "domain=development AND intent=task",
			query:     Query{Text: "test"},
			class:     Classification{Domain: DomainDevelopment, Intent: IntentQuestion},
			expected:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := router.matchesPriorityCondition(tt.query, tt.class, tt.condition)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestPolicyRouter_RouteWithPolicy_AllCapabilitiesMatch(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	registry := NewCapabilityRegistry()

	// Setup multiple agencies and agents
	require.NoError(t, registry.RegisterAgency(AgencyCapability{
		Name:     AgencyName("dev"),
		Domain:   DomainDevelopment,
		Skills:   []SkillName{"coding", "testing"},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	require.NoError(t, registry.RegisterAgent("dev", AgentCapability{
		Name:     AgentName("agent-1"),
		Agency:   AgencyName("dev"),
		Skills:   []SkillName{"coding"},
		Tools:    []string{"bash"},
		CostHint: CostHint{TokenBudget: 5000},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	require.NoError(t, registry.RegisterAgent("dev", AgentCapability{
		Name:     AgentName("agent-2"),
		Agency:   AgencyName("dev"),
		Skills:   []SkillName{"testing"},
		Tools:    []string{"bash", "test"},
		CostHint: CostHint{TokenBudget: 3000},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	router := NewPolicyRouter(baseRouter, registry)

	policy := RoutingPolicy{
		CapabilityMatch: true,
	}

	t.Run("capability match improves routing", func(t *testing.T) {
		// Create a query that the base router doesn't have specific rules for
		query := Query{Text: "implement a new feature"}
		class := Classification{
			Intent:     IntentTask,
			Domain:     DomainDevelopment,
			Complexity: ComplexityMedium,
		}

		// First get base routing decision
		baseDecision, err := baseRouter.Route(context.Background(), query, class)
		require.NoError(t, err)

		// With capability match, we should get a better decision
		decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
		require.NoError(t, err)

		// The capability match should have been applied
		assert.GreaterOrEqual(t, decision.Confidence, baseDecision.Confidence)
	})

	t.Run("capability match overrides base routing", func(t *testing.T) {
		// Query that routes to specific agency
		query := Query{Text: "debug this error"}
		class := Classification{
			Intent:     IntentTask,
			Domain:     DomainDevelopment,
			Complexity: ComplexityMedium,
		}

		decision, err := router.RouteWithPolicy(context.Background(), query, class, policy)
		require.NoError(t, err)

		// Should have higher confidence due to capability match
		assert.GreaterOrEqual(t, decision.Confidence, 0.85)
	})
}

func TestPolicyRouter_RouteWithPolicy_NilCapabilities(t *testing.T) {
	t.Parallel()

	baseRouter := NewDefaultRouter()
	// Create router with nil capabilities
	router := &defaultPolicyRouter{
		baseRouter:   baseRouter,
		capabilities: nil,
		policy:       RoutingPolicy{},
	}

	query := Query{Text: "simple task"}
	class := Classification{
		Intent:     IntentTask,
		Domain:     DomainDevelopment,
		Complexity: ComplexitySimple,
	}

	decision, err := router.RouteWithPolicy(context.Background(), query, class, RoutingPolicy{
		CapabilityMatch: true, // Should not crash even with nil capabilities
	})
	require.NoError(t, err)
	// Should fall back to base routing
	assert.NotEmpty(t, decision.Explanation)
}
