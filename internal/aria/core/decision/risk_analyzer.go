package decision

import (
	"context"
	"fmt"
	"strings"

	"github.com/fulvian/aria/internal/aria/routing"
)

// RiskAnalyzer calculates risk scores for queries.
type RiskAnalyzer interface {
	Analyze(ctx context.Context, query routing.Query, class routing.Classification) (RiskScore, error)
}

// RiskScore represents the risk level of a query.
type RiskScore struct {
	Value      int
	Category   RiskCategory
	Factors    []RiskFactor
	Mitigation string
}

// RiskCategory categorizes the type of risk.
type RiskCategory string

const (
	RiskIrreversible RiskCategory = "irreversible" // Non-revertible actions
	RiskExpensive    RiskCategory = "expensive"    // High resource consumption
	RiskSafety       RiskCategory = "safety"       // Potentially dangerous actions
	RiskStandard     RiskCategory = "standard"     // Normal risk
)

// RiskFactor identifies a contributing factor to risk.
type RiskFactor struct {
	Name   string
	Weight int
	Reason string
}

// DefaultRiskAnalyzer is the default implementation of RiskAnalyzer.
type DefaultRiskAnalyzer struct{}

// NewRiskAnalyzer creates a new DefaultRiskAnalyzer.
func NewRiskAnalyzer() *DefaultRiskAnalyzer {
	return &DefaultRiskAnalyzer{}
}

// Analyze calculates the risk score for a query.
func (a *DefaultRiskAnalyzer) Analyze(ctx context.Context, query routing.Query, class routing.Classification) (RiskScore, error) {
	var factors []RiskFactor
	var total int
	var highestCategory RiskCategory = RiskStandard

	lowerQuery := strings.ToLower(query.Text)

	// Contains "delete", "drop", "remove": +30 (each)
	destructiveWords := []string{"delete", "drop", "remove"}
	destCount := 0
	for _, word := range destructiveWords {
		if strings.Contains(lowerQuery, word) {
			destCount++
		}
	}
	if destCount > 0 {
		weight := destCount * 30
		factors = append(factors, RiskFactor{
			Name:   "destructive_action",
			Weight: weight,
			Reason: fmt.Sprintf("Query contains %d destructive actions", destCount),
		})
		total += weight
		if destCount >= 1 {
			highestCategory = RiskIrreversible
		}
	}

	// Contains "deploy", "push", "submit": +25 (each)
	deployWords := []string{"deploy", "push", "submit"}
	deployCount := 0
	for _, word := range deployWords {
		if strings.Contains(lowerQuery, word) {
			deployCount++
		}
	}
	if deployCount > 0 {
		weight := deployCount * 25
		factors = append(factors, RiskFactor{
			Name:   "external_modification",
			Weight: weight,
			Reason: fmt.Sprintf("Query contains %d external modifications", deployCount),
		})
		total += weight
		if highestCategory == RiskStandard && deployCount >= 1 {
			highestCategory = RiskExpensive
		}
	}

	// Contains "rm -rf", "sudo", "kill": +40 (each)
	dangerousCommands := []string{"rm -rf", "sudo", "kill"}
	dangerCount := 0
	for _, cmd := range dangerousCommands {
		if strings.Contains(lowerQuery, cmd) {
			dangerCount++
		}
	}
	if dangerCount > 0 {
		weight := dangerCount * 40
		factors = append(factors, RiskFactor{
			Name:   "dangerous_command",
			Weight: weight,
			Reason: fmt.Sprintf("Query contains %d dangerous commands", dangerCount),
		})
		total += weight
		highestCategory = RiskSafety
	}

	// Contains "password", "secret", "api_key": +20
	sensitiveWords := []string{"password", "secret", "api_key", "apikey", "token"}
	for _, word := range sensitiveWords {
		if strings.Contains(lowerQuery, word) {
			factors = append(factors, RiskFactor{
				Name:   "sensitive_data",
				Weight: 20,
				Reason: "Query contains sensitive information",
			})
			total += 20
			if highestCategory == RiskStandard {
				highestCategory = RiskSafety
			}
			break
		}
	}

	// Intent = Creation + Domain = development: +15
	if class.Intent == routing.IntentCreation && class.Domain == routing.DomainDevelopment {
		factors = append(factors, RiskFactor{
			Name:   "creation_development",
			Weight: 15,
			Reason: "Creation intent in development domain",
		})
		total += 15
	}

	// Contains file path: +10
	filePathIndicators := []string{"/", "\\", ".go", ".js", ".ts", ".py", ".md", ".json", ".yaml", ".yml"}
	for _, indicator := range filePathIndicators {
		if strings.Contains(query.Text, indicator) && len(indicator) > 1 {
			factors = append(factors, RiskFactor{
				Name:   "file_path_present",
				Weight: 10,
				Reason: "Query references file path",
			})
			total += 10
			break
		}
	}

	// Query about production environment: +20
	prodIndicators := []string{"production", "prod ", " production/", "prod/", "--production"}
	for _, indicator := range prodIndicators {
		if strings.Contains(lowerQuery, indicator) {
			factors = append(factors, RiskFactor{
				Name:   "production_environment",
				Weight: 20,
				Reason: "Query targets production environment",
			})
			total += 20
			if highestCategory == RiskStandard {
				highestCategory = RiskExpensive
			}
			break
		}
	}

	// Cap at 100
	if total > 100 {
		total = 100
	}

	// Determine final category based on score if not already set
	if total >= 70 && highestCategory == RiskStandard {
		highestCategory = RiskExpensive
	} else if total >= 40 && highestCategory == RiskStandard {
		highestCategory = RiskExpensive
	}

	return RiskScore{
		Value:      total,
		Category:   highestCategory,
		Factors:    factors,
		Mitigation: buildRiskMitigation(highestCategory, factors),
	}, nil
}

// buildRiskMitigation creates mitigation strategy based on risk.
func buildRiskMitigation(category RiskCategory, factors []RiskFactor) string {
	switch category {
	case RiskIrreversible:
		return "High-risk irreversible action. Ensure backup exists and user has confirmed."
	case RiskExpensive:
		return "Consider using dry-run mode or asking for confirmation."
	case RiskSafety:
		return "Verify user intentions and ensure safety guardrails are in place."
	default:
		if len(factors) > 0 {
			return "Standard operation. No special mitigation required."
		}
		return "Minimal risk. Proceed with standard execution."
	}
}
