package skill

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/fulvian/aria/internal/aria/skill/knowledge"
)

// FactCheckSkill implements the fact-check skill for verifying claims.
type FactCheckSkill struct {
	providerChain *knowledge.ProviderChain
}

// NewFactCheckSkill creates a new FactCheckSkill.
func NewFactCheckSkill(chain *knowledge.ProviderChain) *FactCheckSkill {
	return &FactCheckSkill{
		providerChain: chain,
	}
}

// Name returns the skill name.
func (s *FactCheckSkill) Name() SkillName {
	return SkillFactCheck
}

// Description returns the skill description.
func (s *FactCheckSkill) Description() string {
	return "Verifies claims by researching multiple sources and determining veracity"
}

// RequiredTools returns the tools required by this skill.
func (s *FactCheckSkill) RequiredTools() []ToolName {
	return nil // Uses direct API calls
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *FactCheckSkill) RequiredMCPs() []MCPName {
	return nil
}

// FactCheckResult contains the result of a fact-check operation.
type FactCheckResult struct {
	Claim      string         `json:"claim"`
	Verdict    string         `json:"verdict"`    // "true", "false", "partial", "unverified"
	Confidence float64        `json:"confidence"` // 0.0 - 1.0
	Evidence   []FactEvidence `json:"evidence"`
	Conflicts  []FactConflict `json:"conflicts"`
	Summary    string         `json:"summary"`
}

// FactEvidence represents supporting or contradicting evidence.
type FactEvidence struct {
	Source    string `json:"source"`
	URL       string `json:"url"`
	Statement string `json:"statement"`
	Relevance string `json:"relevance"` // "supports", "contradicts", "neutral"
}

// FactConflict represents a conflict between sources.
type FactConflict struct {
	Source1 string `json:"source1"`
	Source2 string `json:"source2"`
	Issue   string `json:"issue"`
}

// Execute performs fact-checking on a claim.
func (s *FactCheckSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	claim := s.extractString(params.Input, "claim")
	if claim == "" {
		claim = s.extractString(params.Context, "claim")
	}
	if claim == "" {
		return SkillResult{
			Success:    false,
			Error:      "claim is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	// Get optional sources to check
	sourceURLs := s.extractStringArray(params.Input, "sources")

	// Perform web research on the claim
	searchResp, err := s.providerChain.Search(ctx, knowledge.SearchRequest{
		Query:      claim,
		MaxResults: 10,
		Language:   "en",
	})

	if err != nil {
		return SkillResult{
			Success:    false,
			Error:      fmt.Sprintf("search failed: %s", err.Error()),
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	// Analyze results and determine verdict
	result := s.analyzeClaim(claim, searchResp.Results, sourceURLs)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"claim":      result.Claim,
			"verdict":    result.Verdict,
			"confidence": result.Confidence,
			"evidence":   result.Evidence,
			"conflicts":  result.Conflicts,
			"summary":    result.Summary,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *FactCheckSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// extractStringArray extracts a string array from a map.
func (s *FactCheckSkill) extractStringArray(m map[string]any, key string) []string {
	if arr, ok := m[key].([]any); ok {
		result := make([]string, 0, len(arr))
		for _, v := range arr {
			if s, ok := v.(string); ok {
				result = append(result, s)
			}
		}
		return result
	}
	return nil
}

// analyzeClaim analyzes a claim against search results.
func (s *FactCheckSkill) analyzeClaim(claim string, results []knowledge.SearchResult, specificSources []string) FactCheckResult {
	result := FactCheckResult{
		Claim:     claim,
		Evidence:  make([]FactEvidence, 0),
		Conflicts: make([]FactConflict, 0),
	}

	if len(results) == 0 {
		result.Verdict = "unverified"
		result.Confidence = 0.0
		result.Summary = "No sources found to verify this claim."
		return result
	}

	// Normalize claim for comparison
	normalizedClaim := normalizeForComparison(claim)

	// Analyze each result
	supportingCount := 0
	contradictingCount := 0
	neutralCount := 0

	for _, r := range results {
		relevance := s.determineRelevance(normalizedClaim, r.Content)

		evidence := FactEvidence{
			Source:    r.Title,
			URL:       r.URL,
			Statement: truncateString(r.Content, 200),
			Relevance: relevance,
		}
		result.Evidence = append(result.Evidence, evidence)

		switch relevance {
		case "supports":
			supportingCount++
		case "contradicts":
			contradictingCount++
		default:
			neutralCount++
		}
	}

	// Detect conflicts between sources
	result.Conflicts = s.detectConflicts(result.Evidence)

	// Determine verdict based on evidence
	result.Verdict, result.Confidence = s.determineVerdict(supportingCount, contradictingCount, neutralCount, len(results))

	// Generate summary
	result.Summary = s.generateSummary(claim, result.Verdict, result.Confidence, len(result.Evidence))

	return result
}

// normalizeForComparison normalizes text for comparison.
func normalizeForComparison(text string) string {
	text = strings.ToLower(text)
	text = strings.ReplaceAll(text, "'", "")
	text = strings.ReplaceAll(text, "\"", "")
	return text
}

// truncateString truncates a string to maxLength characters.
func truncateString(s string, maxLength int) string {
	if len(s) <= maxLength {
		return s
	}
	return s[:maxLength] + "..."
}

// determineRelevance determines if a source supports, contradicts, or is neutral to the claim.
func (s *FactCheckSkill) determineRelevance(claim string, content string) string {
	claimWords := strings.Fields(claim)
	contentLower := strings.ToLower(content)

	// Check for negation patterns that might indicate contradiction
	negationPatterns := []string{"not true", "false", "incorrect", "myth", "hoax", "fake", "denied", "rejected"}
	supportPatterns := []string{"true", "confirmed", "verified", "fact", "official", "according to"}

	claimWordCount := 0
	for _, word := range claimWords {
		if len(word) > 3 && strings.Contains(contentLower, word) {
			claimWordCount++
		}
	}

	// Calculate relevance score
	coverage := float64(claimWordCount) / float64(len(claimWords))

	// Check for contradiction indicators
	for _, pattern := range negationPatterns {
		if strings.Contains(contentLower, pattern) && coverage > 0.3 {
			// Check if the negation applies to our claim
			for _, word := range claimWords {
				if strings.Contains(contentLower, pattern+" "+word) ||
					strings.Contains(contentLower, word+" "+pattern) {
					return "contradicts"
				}
			}
		}
	}

	// Check for support indicators
	for _, pattern := range supportPatterns {
		if strings.Contains(contentLower, pattern) && coverage > 0.3 {
			return "supports"
		}
	}

	if coverage > 0.5 {
		return "supports"
	}

	return "neutral"
}

// detectConflicts detects conflicts between sources.
func (s *FactCheckSkill) detectConflicts(evidence []FactEvidence) []FactConflict {
	conflicts := make([]FactConflict, 0)

	// Simple conflict detection: if we have both supports and contradicts
	hasSupport := false
	hasContradict := false
	var supportSource, contradictSource string

	for _, e := range evidence {
		if e.Relevance == "supports" && !hasSupport {
			hasSupport = true
			supportSource = e.Source
		}
		if e.Relevance == "contradicts" && !hasContradict {
			hasContradict = true
			contradictSource = e.Source
		}
	}

	if hasSupport && hasContradict {
		conflicts = append(conflicts, FactConflict{
			Source1: supportSource,
			Source2: contradictSource,
			Issue:   "Conflicting information about the same claim",
		})
	}

	return conflicts
}

// determineVerdict determines the verdict and confidence based on evidence counts.
func (s *FactCheckSkill) determineVerdict(supporting, contradicting, neutral, total int) (string, float64) {
	if total == 0 {
		return "unverified", 0.0
	}

	// Calculate confidence based on evidence strength
	confidence := float64(supporting+contradicting) / float64(total)

	if supporting > contradicting*2 && supporting >= 2 {
		return "true", confidence
	}
	if contradicting > supporting*2 && contradicting >= 2 {
		return "false", confidence
	}
	if supporting > contradicting && supporting >= 1 {
		return "partial", confidence
	}
	if contradicting > supporting && contradicting >= 1 {
		return "partial", confidence
	}

	return "unverified", confidence
}

// generateSummary generates a human-readable summary.
func (s *FactCheckSkill) generateSummary(claim string, verdict string, confidence float64, evidenceCount int) string {
	verdictDesc := map[string]string{
		"true":       "confirmed by sources",
		"false":      "disproven by sources",
		"partial":    "partially supported by sources",
		"unverified": "could not be verified",
	}

	return fmt.Sprintf(
		"Claim '%s' was determined to be %s (%.0f%% confidence) based on %d sources.",
		truncateString(claim, 50),
		verdictDesc[verdict],
		confidence*100,
		evidenceCount,
	)
}

// CanExecute checks if the skill can execute with the given parameters.
func (s *FactCheckSkill) CanExecute(ctx context.Context) (bool, string) {
	if s.providerChain == nil {
		return false, "no search providers configured"
	}
	return true, ""
}
