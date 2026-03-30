package toolgovernance

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestToolGovernance_RegisterTool(t *testing.T) {
	g := NewToolGovernance()

	metadata := ToolMetadata{
		Name:         "test-tool",
		Description:  "A test tool",
		Integration:  IntegrationNative,
		RiskLevel:    RiskLevelLow,
		CostEstimate: CostEstimate{TokenBudget: 100, TimeBudgetMs: 5000},
	}

	err := g.RegisterTool(metadata)
	require.NoError(t, err)

	// Check tool is registered
	decision, err := g.CheckTool(nil, "test-tool")
	require.NoError(t, err)
	assert.True(t, decision.Allowed)
	assert.Equal(t, IntegrationNative, decision.Integration)
}

func TestToolGovernance_RegisterTool_EmptyName(t *testing.T) {
	g := NewToolGovernance()

	err := g.RegisterTool(ToolMetadata{Name: ""})
	assert.Error(t, err)
}

func TestToolGovernance_CheckTool_UnknownTool(t *testing.T) {
	g := NewToolGovernance()

	decision, err := g.CheckTool(nil, "unknown-tool")
	require.NoError(t, err)
	assert.False(t, decision.Allowed)
	assert.Equal(t, "unknown_tool", decision.Reason)
}

func TestToolGovernance_CheckTool_Denylisted(t *testing.T) {
	g := NewToolGovernance()

	err := g.RegisterTool(ToolMetadata{
		Name:        "dangerous-tool",
		Integration: IntegrationNative,
		Denylist:    true,
	})
	require.NoError(t, err)

	decision, err := g.CheckTool(nil, "dangerous-tool")
	require.NoError(t, err)
	assert.False(t, decision.Allowed)
	assert.Equal(t, "denylisted", decision.Reason)
}

func TestToolGovernance_CheckTool_HighRiskRequiresApproval(t *testing.T) {
	g := NewToolGovernance()

	err := g.RegisterTool(ToolMetadata{
		Name:             "high-risk-tool",
		Integration:      IntegrationNative,
		RiskLevel:        RiskLevelHigh,
		RequiresApproval: true,
	})
	require.NoError(t, err)

	decision, err := g.CheckTool(nil, "high-risk-tool")
	require.NoError(t, err)
	assert.True(t, decision.Allowed)
	assert.True(t, decision.RequiresApproval)
}

func TestToolGovernance_SetPolicy(t *testing.T) {
	g := NewToolGovernance()

	// Register a tool first
	err := g.RegisterTool(ToolMetadata{
		Name:        "test-tool",
		Integration: IntegrationNative,
		RiskLevel:   RiskLevelMedium,
	})
	require.NoError(t, err)

	// Set deny policy
	err = g.SetPolicy(ToolPolicy{
		ToolName: "test-tool",
		Allow:    false,
	})
	require.NoError(t, err)

	decision, err := g.CheckTool(nil, "test-tool")
	require.NoError(t, err)
	assert.False(t, decision.Allowed)
	assert.Equal(t, "policy_denied", decision.Reason)
}

func TestToolGovernance_GetPolicy(t *testing.T) {
	g := NewToolGovernance()

	err := g.SetPolicy(ToolPolicy{
		ToolName:        "test-tool",
		Allow:           true,
		RequireApproval: true,
		MaxTokenBudget:  500,
	})
	require.NoError(t, err)

	policy, err := g.GetPolicy("test-tool")
	require.NoError(t, err)
	assert.Equal(t, "test-tool", policy.ToolName)
	assert.True(t, policy.Allow)
	assert.True(t, policy.RequireApproval)
	assert.Equal(t, 500, policy.MaxTokenBudget)
}

func TestToolGovernance_GetPolicy_NotFound(t *testing.T) {
	g := NewToolGovernance()

	_, err := g.GetPolicy("non-existent")
	assert.Error(t, err)
}

func TestToolGovernance_GetPreferredIntegration(t *testing.T) {
	g := NewToolGovernance()

	tests := []struct {
		taskType     string
		expectedType IntegrationType
	}{
		{"file_operations", IntegrationNative},
		{"shell", IntegrationNative},
		{"code_generation", IntegrationNative},
		{"web_fetch", IntegrationDirectAPI},
		{"api_call", IntegrationDirectAPI},
		{"weather", IntegrationDirectAPI},
		{"remote_execution", IntegrationMCP},
		{"unknown_task", IntegrationNative},
	}

	for _, tt := range tests {
		t.Run(tt.taskType, func(t *testing.T) {
			result := g.GetPreferredIntegration(tt.taskType)
			assert.Equal(t, tt.expectedType, result)
		})
	}
}

func TestToolGovernance_RecordUsage(t *testing.T) {
	g := NewToolGovernance()

	err := g.RegisterTool(ToolMetadata{
		Name:        "test-tool",
		Integration: IntegrationNative,
		RiskLevel:   RiskLevelLow,
	})
	require.NoError(t, err)

	g.RecordUsage("test-tool", UsageRecord{
		TokensUsed: 100,
		DurationMs: 5000,
		Success:    true,
		AgencyID:   "test-agency",
	})

	// Get summary for last hour
	summary := g.GetCostSummary(time.Now().Add(-1 * time.Hour))
	assert.Equal(t, 100, summary.TotalTokens)
	assert.Equal(t, 5000, summary.TotalTimeMs)
	assert.Equal(t, 1, summary.TotalCalls)
	assert.Equal(t, 100, summary.ByTool["test-tool"])
	assert.Equal(t, 100, summary.ByAgency["test-agency"])
}

func TestToolGovernance_CostSummary_IntegrationBreakdown(t *testing.T) {
	g := NewToolGovernance()

	// Register tools of different integration types
	err := g.RegisterTool(ToolMetadata{
		Name:        "native-tool",
		Integration: IntegrationNative,
		RiskLevel:   RiskLevelLow,
	})
	require.NoError(t, err)

	err = g.RegisterTool(ToolMetadata{
		Name:        "api-tool",
		Integration: IntegrationDirectAPI,
		RiskLevel:   RiskLevelLow,
	})
	require.NoError(t, err)

	g.RecordUsage("native-tool", UsageRecord{TokensUsed: 100, Success: true})
	g.RecordUsage("api-tool", UsageRecord{TokensUsed: 50, Success: true})

	summary := g.GetCostSummary(time.Now().Add(-1 * time.Hour))
	assert.Equal(t, 150, summary.TotalTokens)
	assert.Equal(t, 100, summary.ByIntegration[IntegrationNative])
	assert.Equal(t, 50, summary.ByIntegration[IntegrationDirectAPI])
}

func TestToolGovernance_RegisterDefaultTools(t *testing.T) {
	g := NewToolGovernance()

	err := RegisterDefaultTools(g)
	require.NoError(t, err)

	// Check some default tools are registered
	decision, err := g.CheckTool(nil, "bash")
	require.NoError(t, err)
	assert.True(t, decision.Allowed)
	assert.Equal(t, IntegrationNative, decision.Integration)
	assert.Equal(t, RiskLevelHigh, decision.RiskLevel)

	decision, err = g.CheckTool(nil, "weather")
	require.NoError(t, err)
	assert.True(t, decision.Allowed)
	assert.Equal(t, IntegrationDirectAPI, decision.Integration)

	decision, err = g.CheckTool(nil, "edit")
	require.NoError(t, err)
	assert.True(t, decision.Allowed)
}

func TestGovernanceDecision_Fields(t *testing.T) {
	decision := GovernanceDecision{
		Allowed:           true,
		Reason:            "allowed",
		ToolName:          "test-tool",
		Integration:       IntegrationNative,
		RiskLevel:         RiskLevelMedium,
		CostEstimate:      CostEstimate{TokenBudget: 100, TimeBudgetMs: 5000},
		RequiresApproval:  false,
		PolicyExplanation: "Tool allowed by governance",
	}

	assert.True(t, decision.Allowed)
	assert.Equal(t, "allowed", decision.Reason)
	assert.Equal(t, "test-tool", decision.ToolName)
	assert.Equal(t, IntegrationNative, decision.Integration)
	assert.Equal(t, RiskLevelMedium, decision.RiskLevel)
	assert.Equal(t, 100, decision.CostEstimate.TokenBudget)
	assert.False(t, decision.RequiresApproval)
}

func TestCostEstimate_Fields(t *testing.T) {
	estimate := CostEstimate{
		TokenBudget:  500,
		TimeBudgetMs: 10000,
		MoneyCost:    10,
	}

	assert.Equal(t, 500, estimate.TokenBudget)
	assert.Equal(t, 10000, estimate.TimeBudgetMs)
	assert.Equal(t, 10, estimate.MoneyCost)
}
