// Package toolgovernance provides tool governance and cost control for ARIA.
// It implements the tool governance layer defined in Blueprint Section WS-G.
//
// Key principles:
// - Native-first: Prefer tools that run directly in the environment
// - Direct API second: Use direct API calls when native tools are insufficient
// - MCP last resort: Use MCP only when neither native nor direct API is available
//
// Reference: Production-Ready Plan WS-G
package toolgovernance

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// IntegrationType defines how a tool is integrated.
type IntegrationType string

const (
	// IntegrationNative means the tool runs directly in the environment (e.g., bash, file edit)
	IntegrationNative IntegrationType = "native"

	// IntegrationDirectAPI means the tool uses direct API calls (e.g., weather, fetch)
	IntegrationDirectAPI IntegrationType = "direct_api"

	// IntegrationMCP means the tool uses Model Context Protocol (e.g., remote tools)
	IntegrationMCP IntegrationType = "mcp"
)

// RiskLevel defines the risk level of a tool.
type RiskLevel string

const (
	RiskLevelLow      RiskLevel = "low"
	RiskLevelMedium   RiskLevel = "medium"
	RiskLevelHigh     RiskLevel = "high"
	RiskLevelCritical RiskLevel = "critical"
)

// ToolMetadata contains metadata about a tool for governance purposes.
type ToolMetadata struct {
	Name             string
	Description      string
	Integration      IntegrationType
	RiskLevel        RiskLevel
	CostEstimate     CostEstimate
	RequiresApproval bool
	Denylist         bool
}

// CostEstimate estimates the cost of using a tool.
type CostEstimate struct {
	TokenBudget  int // Estimated tokens consumed
	TimeBudgetMs int // Estimated time in milliseconds
	MoneyCost    int // Estimated cost in cents (optional)
}

// ToolPolicy defines the policy for a tool.
type ToolPolicy struct {
	ToolName        string
	Allow           bool
	RequireApproval bool
	MaxTokenBudget  int
	MaxTimeBudgetMs int
	Priority        int // Higher priority tools are preferred
}

// GovernanceDecision is the result of a governance check.
type GovernanceDecision struct {
	Allowed           bool
	Reason            string
	ToolName          string
	Integration       IntegrationType
	RiskLevel         RiskLevel
	CostEstimate      CostEstimate
	RequiresApproval  bool
	PolicyExplanation string
}

// ToolGovernance service interface.
type ToolGovernance interface {
	// RegisterTool registers a tool with its metadata
	RegisterTool(metadata ToolMetadata) error

	// CheckTool checks if a tool is allowed and returns governance decision
	CheckTool(ctx context.Context, toolName string) (GovernanceDecision, error)

	// GetPreferredIntegration returns the preferred integration type for a task
	GetPreferredIntegration(taskType string) IntegrationType

	// RecordUsage records tool usage for cost tracking
	RecordUsage(toolName string, usage UsageRecord)

	// GetCostSummary returns cost summary for a time period
	GetCostSummary(since time.Time) CostSummary

	// SetPolicy updates the policy for a tool
	SetPolicy(policy ToolPolicy) error

	// GetPolicy returns the policy for a tool
	GetPolicy(toolName string) (ToolPolicy, error)
}

// UsageRecord records a single tool usage event.
type UsageRecord struct {
	ToolName   string
	Timestamp  time.Time
	TokensUsed int
	DurationMs int
	Success    bool
	AgencyID   string
	AgentID    string
	TaskID     string
}

// CostSummary provides aggregated cost information.
type CostSummary struct {
	TotalTokens   int
	TotalTimeMs   int
	TotalCalls    int
	ByTool        map[string]int
	ByAgency      map[string]int
	ByIntegration map[IntegrationType]int
}

// defaultToolGovernance is the default implementation of ToolGovernance.
type defaultToolGovernance struct {
	mu       sync.RWMutex
	tools    map[string]ToolMetadata
	policies map[string]ToolPolicy
	usage    []UsageRecord
	maxUsage int // Maximum usage records to keep
}

// NewToolGovernance creates a new tool governance service.
func NewToolGovernance() *defaultToolGovernance {
	return &defaultToolGovernance{
		tools:    make(map[string]ToolMetadata),
		policies: make(map[string]ToolPolicy),
		usage:    make([]UsageRecord, 0, 1000),
		maxUsage: 10000,
	}
}

// RegisterTool registers a tool with its metadata.
func (g *defaultToolGovernance) RegisterTool(metadata ToolMetadata) error {
	if metadata.Name == "" {
		return fmt.Errorf("tool name cannot be empty")
	}

	g.mu.Lock()
	defer g.mu.Unlock()

	g.tools[metadata.Name] = metadata
	return nil
}

// CheckTool checks if a tool is allowed and returns governance decision.
func (g *defaultToolGovernance) CheckTool(ctx context.Context, toolName string) (GovernanceDecision, error) {
	g.mu.RLock()
	defer g.mu.RUnlock()

	metadata, exists := g.tools[toolName]
	if !exists {
		// Unknown tool - default to require approval
		return GovernanceDecision{
			Allowed:           false,
			Reason:            "unknown_tool",
			ToolName:          toolName,
			RequiresApproval:  true,
			PolicyExplanation: "Tool not registered in governance system",
		}, nil
	}

	// Check if tool is denylisted
	if metadata.Denylist {
		return GovernanceDecision{
			Allowed:           false,
			Reason:            "denylisted",
			ToolName:          toolName,
			Integration:       metadata.Integration,
			RiskLevel:         metadata.RiskLevel,
			PolicyExplanation: "Tool is explicitly denylisted",
		}, nil
	}

	// Check policy
	policy, hasPolicy := g.policies[toolName]
	if hasPolicy {
		if !policy.Allow {
			return GovernanceDecision{
				Allowed:           false,
				Reason:            "policy_denied",
				ToolName:          toolName,
				Integration:       metadata.Integration,
				RiskLevel:         metadata.RiskLevel,
				PolicyExplanation: "Tool is denied by policy",
			}, nil
		}

		if policy.RequireApproval {
			return GovernanceDecision{
				Allowed:           true,
				Reason:            "requires_approval",
				ToolName:          toolName,
				Integration:       metadata.Integration,
				RiskLevel:         metadata.RiskLevel,
				CostEstimate:      metadata.CostEstimate,
				RequiresApproval:  true,
				PolicyExplanation: fmt.Sprintf("Tool requires approval (policy: %s)", policy.ToolName),
			}, nil
		}
	}

	// Default behavior based on risk level
	if metadata.RiskLevel == RiskLevelCritical || metadata.RiskLevel == RiskLevelHigh {
		if metadata.RequiresApproval {
			return GovernanceDecision{
				Allowed:           true,
				Reason:            "high_risk_requires_approval",
				ToolName:          toolName,
				Integration:       metadata.Integration,
				RiskLevel:         metadata.RiskLevel,
				CostEstimate:      metadata.CostEstimate,
				RequiresApproval:  true,
				PolicyExplanation: fmt.Sprintf("High-risk tool (%s) requires approval", metadata.RiskLevel),
			}, nil
		}
	}

	return GovernanceDecision{
		Allowed:           true,
		Reason:            "allowed",
		ToolName:          toolName,
		Integration:       metadata.Integration,
		RiskLevel:         metadata.RiskLevel,
		CostEstimate:      metadata.CostEstimate,
		RequiresApproval:  metadata.RequiresApproval,
		PolicyExplanation: "Tool allowed by governance",
	}, nil
}

// GetPreferredIntegration returns the preferred integration type for a task.
// It follows the principle: Native > Direct API > MCP
func (g *defaultToolGovernance) GetPreferredIntegration(taskType string) IntegrationType {
	// For most tasks, native is preferred
	switch taskType {
	case "file_operations", "shell", "code_generation", "code_review":
		return IntegrationNative
	case "web_fetch", "api_call", "weather", "data_retrieval":
		return IntegrationDirectAPI
	case "remote_execution", "external_service":
		return IntegrationMCP
	default:
		return IntegrationNative // Default to native
	}
}

// RecordUsage records tool usage for cost tracking.
func (g *defaultToolGovernance) RecordUsage(toolName string, usage UsageRecord) {
	g.mu.Lock()
	defer g.mu.Unlock()

	usage.ToolName = toolName
	usage.Timestamp = time.Now()
	g.usage = append(g.usage, usage)

	// Trim old records if needed
	if len(g.usage) > g.maxUsage {
		g.usage = g.usage[len(g.usage)-g.maxUsage:]
	}
}

// GetCostSummary returns cost summary for a time period.
func (g *defaultToolGovernance) GetCostSummary(since time.Time) CostSummary {
	g.mu.RLock()
	defer g.mu.RUnlock()

	summary := CostSummary{
		ByTool:        make(map[string]int),
		ByAgency:      make(map[string]int),
		ByIntegration: make(map[IntegrationType]int),
	}

	for _, record := range g.usage {
		if record.Timestamp.After(since) {
			summary.TotalTokens += record.TokensUsed
			summary.TotalTimeMs += record.DurationMs
			summary.TotalCalls++
			summary.ByTool[record.ToolName] += record.TokensUsed

			if record.AgencyID != "" {
				summary.ByAgency[record.AgencyID] += record.TokensUsed
			}

			// Get integration type for tool
			if metadata, ok := g.tools[record.ToolName]; ok {
				summary.ByIntegration[metadata.Integration] += record.TokensUsed
			}
		}
	}

	return summary
}

// SetPolicy updates the policy for a tool.
func (g *defaultToolGovernance) SetPolicy(policy ToolPolicy) error {
	if policy.ToolName == "" {
		return fmt.Errorf("tool name cannot be empty")
	}

	g.mu.Lock()
	defer g.mu.Unlock()

	g.policies[policy.ToolName] = policy
	return nil
}

// GetPolicy returns the policy for a tool.
func (g *defaultToolGovernance) GetPolicy(toolName string) (ToolPolicy, error) {
	g.mu.RLock()
	defer g.mu.RUnlock()

	policy, exists := g.policies[toolName]
	if !exists {
		return ToolPolicy{}, fmt.Errorf("no policy found for tool: %s", toolName)
	}

	return policy, nil
}

// RegisterDefaultTools registers the default set of tools with their metadata.
func RegisterDefaultTools(g ToolGovernance) error {
	defaultTools := []ToolMetadata{
		// Native tools
		{
			Name:             "bash",
			Description:      "Execute shell commands",
			Integration:      IntegrationNative,
			RiskLevel:        RiskLevelHigh,
			CostEstimate:     CostEstimate{TokenBudget: 100, TimeBudgetMs: 30000},
			RequiresApproval: true,
		},
		{
			Name:         "edit",
			Description:  "Edit files",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelMedium,
			CostEstimate: CostEstimate{TokenBudget: 50, TimeBudgetMs: 5000},
		},
		{
			Name:         "write",
			Description:  "Write files",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelMedium,
			CostEstimate: CostEstimate{TokenBudget: 50, TimeBudgetMs: 5000},
		},
		{
			Name:         "view",
			Description:  "View file contents",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 20, TimeBudgetMs: 1000},
		},
		{
			Name:         "glob",
			Description:  "Find files by pattern",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 20, TimeBudgetMs: 1000},
		},
		{
			Name:         "grep",
			Description:  "Search file contents",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 30, TimeBudgetMs: 5000},
		},
		{
			Name:         "ls",
			Description:  "List directory contents",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 10, TimeBudgetMs: 1000},
		},
		{
			Name:         "patch",
			Description:  "Apply patches to files",
			Integration:  IntegrationNative,
			RiskLevel:    RiskLevelMedium,
			CostEstimate: CostEstimate{TokenBudget: 50, TimeBudgetMs: 5000},
		},
		// Direct API tools
		{
			Name:         "weather",
			Description:  "Get weather information",
			Integration:  IntegrationDirectAPI,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 10, TimeBudgetMs: 2000, MoneyCost: 1},
		},
		{
			Name:         "fetch",
			Description:  "Fetch web content",
			Integration:  IntegrationDirectAPI,
			RiskLevel:    RiskLevelMedium,
			CostEstimate: CostEstimate{TokenBudget: 50, TimeBudgetMs: 10000, MoneyCost: 5},
		},
		{
			Name:         "sourcegraph",
			Description:  "Search code using Sourcegraph",
			Integration:  IntegrationDirectAPI,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 20, TimeBudgetMs: 5000},
		},
		{
			Name:         "diagnostics",
			Description:  "Get LSP diagnostics",
			Integration:  IntegrationDirectAPI,
			RiskLevel:    RiskLevelLow,
			CostEstimate: CostEstimate{TokenBudget: 30, TimeBudgetMs: 3000},
		},
		// MCP tools would be registered dynamically
	}

	for _, tool := range defaultTools {
		if err := g.RegisterTool(tool); err != nil {
			return fmt.Errorf("failed to register tool %s: %w", tool.Name, err)
		}
	}

	return nil
}
