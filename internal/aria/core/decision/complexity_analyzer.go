// Package decision provides the decision engine components for orchestrator
// path selection (fast vs deep) based on complexity and risk analysis.
package decision

import (
	"context"
	"fmt"
	"strings"

	"github.com/fulvian/aria/internal/aria/routing"
)

// ComplexityAnalyzer calculates complexity scores for queries.
type ComplexityAnalyzer interface {
	Analyze(ctx context.Context, query routing.Query, class routing.Classification) (ComplexityScore, error)
}

// ComplexityScore represents the complexity level of a query.
type ComplexityScore struct {
	Value       int                // 0-100
	Factors     []ComplexityFactor // contributing factors
	Explanation string             // human-readable explanation
}

// ComplexityFactor identifies a contributing factor to complexity.
type ComplexityFactor struct {
	Name   string
	Weight int // contribution in points
	Reason string
}

// DefaultComplexityAnalyzer is the default implementation of ComplexityAnalyzer.
type DefaultComplexityAnalyzer struct{}

// NewComplexityAnalyzer creates a new DefaultComplexityAnalyzer.
func NewComplexityAnalyzer() *DefaultComplexityAnalyzer {
	return &DefaultComplexityAnalyzer{}
}

// Analyze calculates the complexity score for a query.
func (a *DefaultComplexityAnalyzer) Analyze(ctx context.Context, query routing.Query, class routing.Classification) (ComplexityScore, error) {
	var factors []ComplexityFactor
	var total int

	// Query length > 200 chars: +10
	if len(query.Text) > 200 {
		factors = append(factors, ComplexityFactor{
			Name:   "query_length",
			Weight: 10,
			Reason: "Query exceeds 200 characters",
		})
		total += 10
	}

	// History length > 5: +15
	if len(query.History) > 5 {
		factors = append(factors, ComplexityFactor{
			Name:   "history_length",
			Weight: 15,
			Reason: "Conversation history exceeds 5 messages",
		})
		total += 15
	}

	// Contains "and then", "also", "plus": +20 (each)
	lowerQuery := strings.ToLower(query.Text)
	multiStepKeywords := []string{"and then", "also", "plus"}
	multiStepCount := 0
	for _, kw := range multiStepKeywords {
		if strings.Contains(lowerQuery, kw) {
			multiStepCount++
		}
	}
	if multiStepCount > 0 {
		weight := multiStepCount * 20
		factors = append(factors, ComplexityFactor{
			Name:   "multi_step_keywords",
			Weight: weight,
			Reason: fmt.Sprintf("Query contains %d multi-step indicators", multiStepCount),
		})
		total += weight
	}

	// Contains "refactor", "migrate", "architecture": +25 (each)
	architecturalKeywords := []string{"refactor", "migrate", "architecture"}
	archCount := 0
	for _, kw := range architecturalKeywords {
		if strings.Contains(lowerQuery, kw) {
			archCount++
		}
	}
	if archCount > 0 {
		weight := archCount * 25
		factors = append(factors, ComplexityFactor{
			Name:   "architectural_keywords",
			Weight: weight,
			Reason: fmt.Sprintf("Query contains %d architectural keywords", archCount),
		})
		total += weight
	}

	// Contains "multiple", "several", "all": +20 (each)
	multiTargetKeywords := []string{"multiple", "several", "all"}
	multiTargetCount := 0
	for _, kw := range multiTargetKeywords {
		if strings.Contains(lowerQuery, kw) {
			multiTargetCount++
		}
	}
	if multiTargetCount > 0 {
		weight := multiTargetCount * 20
		factors = append(factors, ComplexityFactor{
			Name:   "multi_target_keywords",
			Weight: weight,
			Reason: fmt.Sprintf("Query contains %d multi-target keywords", multiTargetCount),
		})
		total += weight
	}

	// Intent = Analysis: +15
	if class.Intent == routing.IntentAnalysis {
		factors = append(factors, ComplexityFactor{
			Name:   "intent_analysis",
			Weight: 15,
			Reason: "Intent is Analysis",
		})
		total += 15
	}

	// ComplexityLevel existing = complex: +20
	if class.Complexity == routing.ComplexityComplex {
		factors = append(factors, ComplexityFactor{
			Name:   "existing_complexity",
			Weight: 20,
			Reason: "Already classified as complex",
		})
		total += 20
	}

	// RequiresState = true: +15
	if class.RequiresState {
		factors = append(factors, ComplexityFactor{
			Name:   "requires_state",
			Weight: 15,
			Reason: "Query requires state/context",
		})
		total += 15
	}

	// Domain = development + contains code terms: +10
	codeTerms := []string{"function", "class", "code", "file", "variable", "method", "module", "import", "export"}
	if class.Domain == routing.DomainDevelopment {
		for _, term := range codeTerms {
			if strings.Contains(lowerQuery, term) {
				factors = append(factors, ComplexityFactor{
					Name:   "development_domain",
					Weight: 10,
					Reason: "Development domain with code terms",
				})
				total += 10
				break
			}
		}
	}

	// Cap at 100
	if total > 100 {
		total = 100
	}

	return ComplexityScore{
		Value:       total,
		Factors:     factors,
		Explanation: buildComplexityExplanation(factors),
	}, nil
}

// buildComplexityExplanation creates a human-readable explanation.
func buildComplexityExplanation(factors []ComplexityFactor) string {
	if len(factors) == 0 {
		return "Simple query with minimal complexity"
	}
	return "Complexity influenced by multiple factors"
}
