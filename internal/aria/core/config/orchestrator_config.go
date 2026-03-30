// Package config provides configuration structures for the orchestrator.
package config

import (
	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/core/telemetry"
)

// AgencyName represents the name of an agency.
type AgencyName string

// OrchestratorConfigV2 is the extended configuration for the enhanced orchestrator.
type OrchestratorConfigV2 struct {
	EnableFallback      bool
	DefaultAgency       AgencyName
	ConfidenceThreshold float64
	DecisionEngine      DecisionEngineConfig
	Reviewer            ReviewerConfig
	Paths               ExecutionPathsConfig
	Telemetry           telemetry.TelemetryConfig
}

// DecisionEngineConfig contains configuration for the decision engine.
type DecisionEngineConfig struct {
	ComplexityThreshold int
	RiskThreshold       int
	MaxThoughts         int
	TimeoutMs           int
}

// NewDecisionEngineConfig creates a DecisionEngineConfig with default values.
func NewDecisionEngineConfig() DecisionEngineConfig {
	return DecisionEngineConfig{
		ComplexityThreshold: 55,
		RiskThreshold:       40,
		MaxThoughts:         12,
		TimeoutMs:           12000,
	}
}

// ReviewerConfig contains configuration for the reviewer.
type ReviewerConfig struct {
	Enabled            bool
	MinAcceptanceScore float64
	MaxReplan          int
	MaxRetries         int
}

// NewReviewerConfig creates a ReviewerConfig with default values.
func NewReviewerConfig() ReviewerConfig {
	return ReviewerConfig{
		Enabled:            true,
		MinAcceptanceScore: 0.75,
		MaxReplan:          2,
		MaxRetries:         1,
	}
}

// ExecutionPathsConfig contains configuration for execution paths.
type ExecutionPathsConfig struct {
	FastPathEnabled bool
	DeepPathEnabled bool
}

// NewExecutionPathsConfig creates an ExecutionPathsConfig with default values.
func NewExecutionPathsConfig() ExecutionPathsConfig {
	return ExecutionPathsConfig{
		FastPathEnabled: true,
		DeepPathEnabled: true,
	}
}

// DefaultOrchestratorConfigV2 creates an OrchestratorConfigV2 with sensible defaults.
func DefaultOrchestratorConfigV2() OrchestratorConfigV2 {
	return OrchestratorConfigV2{
		EnableFallback:      true,
		ConfidenceThreshold: 0.7,
		DecisionEngine:      NewDecisionEngineConfig(),
		Reviewer:            NewReviewerConfig(),
		Paths:               NewExecutionPathsConfig(),
		Telemetry:           telemetry.DefaultTelemetryConfig(),
	}
}

// DecisionEngineFromConfig creates a decision engine from config.
func DecisionEngineFromConfig(cfg DecisionEngineConfig) decision.DecisionEngine {
	complexityAnalyzer := decision.NewComplexityAnalyzer()
	riskAnalyzer := decision.NewRiskAnalyzer()
	triggerPolicy := decision.NewTriggerPolicyWithConfig(
		cfg.ComplexityThreshold,
		cfg.RiskThreshold,
		cfg.MaxThoughts,
		cfg.TimeoutMs,
	)
	pathSelector := decision.NewPathSelector()

	return decision.NewDecisionEngine(
		complexityAnalyzer,
		riskAnalyzer,
		triggerPolicy,
		pathSelector,
		cfg.ComplexityThreshold,
		cfg.RiskThreshold,
	)
}
