package agency

import (
	"context"
	"math"
	"strings"

	"github.com/fulvian/aria/internal/aria/contracts"
)

// KnowledgeCritic performs quality assessment on knowledge results
type KnowledgeCritic struct {
	qualityThreshold float64
}

// ReviewResult contains the quality assessment
type ReviewResult struct {
	QualityScore   float64  // 0.0-1.0
	Confidence     float64  // Confidence in assessment
	Contradictions []string // Contradictions found
	CitationsValid bool     // Are citations verifiable
	Unknowns       []string // Things we don't know
	Pass           bool     // Quality gate pass/fail
	Reasons        []string // Explanation
}

// NewKnowledgeCritic creates a new knowledge critic
func NewKnowledgeCritic(threshold float64) *KnowledgeCritic {
	if threshold <= 0 {
		threshold = 0.7
	}
	return &KnowledgeCritic{qualityThreshold: threshold}
}

// Review assesses the quality of a result
func (c *KnowledgeCritic) Review(ctx context.Context, task contracts.Task, result map[string]any) *ReviewResult {
	qualityScore := c.calculateQualityScore(result)
	confidence := c.assessConfidence(result)
	contradictions := c.detectContradictions(result)
	citationsValid := c.validateCitations(result)
	unknowns := c.identifyUnknowns(result)

	pass := qualityScore >= c.qualityThreshold &&
		len(contradictions) == 0 &&
		citationsValid

	return &ReviewResult{
		QualityScore:   qualityScore,
		Confidence:     confidence,
		Contradictions: contradictions,
		CitationsValid: citationsValid,
		Unknowns:       unknowns,
		Pass:           pass,
		Reasons:        c.explain(qualityScore, contradictions, citationsValid),
	}
}

func (c *KnowledgeCritic) calculateQualityScore(result map[string]any) float64 {
	score := 0.3 // Base score

	// Boost for results array
	if results, ok := result["results"].([]any); ok {
		if len(results) > 0 {
			score += 0.1 * math.Min(float64(len(results)), 5)
		}
	}

	// Boost for summary
	if summary, ok := result["summary"].(string); ok && len(summary) > 50 {
		score += 0.15
	}

	// Boost for source attribution
	if source, ok := result["source"].(string); ok && source != "" {
		score += 0.1
	}

	// Boost for count metadata
	if count, ok := result["count"].(int); ok && count > 0 {
		score += 0.05
	}

	// Cap at 1.0
	return math.Min(score, 1.0)
}

func (c *KnowledgeCritic) assessConfidence(result map[string]any) float64 {
	confidence := 0.5

	// Higher confidence with multiple sources
	if results, ok := result["results"].([]any); ok {
		confidence += 0.1 * math.Min(float64(len(results)), 3)
	}

	// Higher confidence with metadata
	if _, ok := result["source"]; ok {
		confidence += 0.1
	}

	return math.Min(confidence, 1.0)
}

func (c *KnowledgeCritic) detectContradictions(result map[string]any) []string {
	var contradictions []string

	// Simple contradiction detection:
	// Check if same URL appears multiple times with different content
	urls := make(map[string]string)

	if results, ok := result["results"].([]any); ok {
		for _, r := range results {
			if m, ok := r.(map[string]any); ok {
				if url, ok := m["url"].(string); ok {
					if desc, ok := m["description"].(string); ok {
						if existing, exists := urls[url]; exists {
							if existing != desc && !strings.Contains(existing, desc) && !strings.Contains(desc, existing) {
								contradictions = append(contradictions, "Conflicting descriptions for: "+url)
							}
						} else {
							urls[url] = desc
						}
					}
				}
			}
		}
	}

	return contradictions
}

func (c *KnowledgeCritic) validateCitations(result map[string]any) bool {
	// Check if results have URLs (verifiable citations)
	if results, ok := result["results"].([]any); ok {
		validCount := 0
		for _, r := range results {
			if m, ok := r.(map[string]any); ok {
				if url, ok := m["url"].(string); ok && isValidURL(url) {
					validCount++
				}
			}
		}
		// At least 50% should have valid URLs
		return validCount >= len(results)/2
	}
	return false
}

func isValidURL(url string) bool {
	return strings.HasPrefix(url, "http://") || strings.HasPrefix(url, "https://")
}

func (c *KnowledgeCritic) identifyUnknowns(result map[string]any) []string {
	var unknowns []string

	// Check for placeholder or low-quality content
	if results, ok := result["results"].([]any); ok {
		for i, r := range results {
			if m, ok := r.(map[string]any); ok {
				title, _ := m["title"].(string)
				desc, _ := m["description"].(string)

				// Flag low-content results
				if title == "" && desc == "" {
					unknowns = append(unknowns, "Result "+string(rune('0'+i))+" has no title or description")
				}
				if len(desc) < 20 && desc != "" {
					unknowns = append(unknowns, "Result "+string(rune('0'+i))+" has minimal description")
				}
			}
		}
	}

	return unknowns
}

func (c *KnowledgeCritic) explain(score float64, contradictions []string, citationsValid bool) []string {
	var reasons []string

	if score >= 0.8 {
		reasons = append(reasons, "High quality result set")
	} else if score >= 0.5 {
		reasons = append(reasons, "Moderate quality result set")
	} else {
		reasons = append(reasons, "Low quality result set")
	}

	if len(contradictions) > 0 {
		reasons = append(reasons, "Found "+string(rune('0'+len(contradictions)))+" contradictions")
	}

	if citationsValid {
		reasons = append(reasons, "Citations verifiable")
	} else {
		reasons = append(reasons, "Citations may not be verifiable")
	}

	return reasons
}

// PassesGate returns true if result passes the quality gate
func (r *ReviewResult) PassesGate() bool {
	return r.Pass
}
