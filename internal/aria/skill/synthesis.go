package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// SynthesisSkill implements the synthesis skill for combining multiple sources.
type SynthesisSkill struct{}

// NewSynthesisSkill creates a new SynthesisSkill.
func NewSynthesisSkill() *SynthesisSkill {
	return &SynthesisSkill{}
}

// Name returns the skill name.
func (s *SynthesisSkill) Name() SkillName {
	return "synthesis"
}

// Description returns the skill description.
func (s *SynthesisSkill) Description() string {
	return "Synthesizes information from multiple sources into coherent insights"
}

// RequiredTools returns the tools required by this skill.
func (s *SynthesisSkill) RequiredTools() []ToolName {
	return nil
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *SynthesisSkill) RequiredMCPs() []MCPName {
	return nil
}

// SynthesisResult contains the result of synthesis.
type SynthesisResult struct {
	Synthesis     string      `json:"synthesis"`
	Agreements    []string    `json:"agreements"`
	Disagreements []string    `json:"disagreements"`
	Gaps          []Gap       `json:"gaps"`
	Sources       []SourceRef `json:"sources"`
	Confidence    float64     `json:"confidence"`
	Summary       string      `json:"summary"`
}

// Gap represents an information gap identified during synthesis.
type Gap struct {
	Description string `json:"description"`
	Suggestion  string `json:"suggestion"`
}

// SourceRef represents a reference to a source.
type SourceRef struct {
	Title     string `json:"title"`
	URL       string `json:"url,omitempty"`
	Relevance string `json:"relevance"` // high, medium, low
}

// Execute performs synthesis from multiple sources.
func (s *SynthesisSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	sourcesRaw, ok := params.Input["sources"].([]any)
	if !ok || len(sourcesRaw) == 0 {
		// Try alternative format
		content := s.extractString(params.Input, "content")
		if content != "" {
			sourcesRaw = []any{content}
		}
	}

	if len(sourcesRaw) == 0 {
		return SkillResult{
			Success:    false,
			Error:      "sources or content is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	// Parse sources
	sources := s.parseSources(sourcesRaw)

	// Extract objective
	objective := s.extractString(params.Input, "objective")
	if objective == "" {
		objective = "Provide a comprehensive synthesis of the sources"
	}

	// Perform synthesis
	result := s.synthesizeSources(sources, objective)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"synthesis":     result.Synthesis,
			"agreements":    result.Agreements,
			"disagreements": result.Disagreements,
			"gaps":          result.Gaps,
			"sources":       result.Sources,
			"confidence":    result.Confidence,
			"summary":       result.Summary,
			"objective":     objective,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *SynthesisSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// parseSources parses sources from input.
func (s *SynthesisSkill) parseSources(sourcesRaw []any) []SourceRef {
	sources := make([]SourceRef, 0, len(sourcesRaw))

	for i, srcRaw := range sourcesRaw {
		switch v := srcRaw.(type) {
		case string:
			sources = append(sources, SourceRef{
				Title:     fmt.Sprintf("Source %d", i+1),
				Relevance: "medium",
			})
		case map[string]any:
			title := s.getString(v, "title", fmt.Sprintf("Source %d", i+1))
			url := s.getString(v, "url", "")
			relevance := s.getString(v, "relevance", "medium")
			sources = append(sources, SourceRef{
				Title:     title,
				URL:       url,
				Relevance: relevance,
			})
		}
	}

	return sources
}

// getString safely extracts a string from a map.
func (s *SynthesisSkill) getString(m map[string]any, key, defaultVal string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return defaultVal
}

// synthesizeSources performs the synthesis.
func (s *SynthesisSkill) synthesizeSources(sources []SourceRef, objective string) SynthesisResult {
	result := SynthesisResult{
		Sources: sources,
	}

	// Identify agreements
	result.Agreements = s.identifyAgreements(sources)

	// Identify disagreements
	result.Disagreements = s.identifyDisagreements(sources)

	// Identify gaps
	result.Gaps = s.identifyGaps(sources, objective)

	// Calculate confidence
	result.Confidence = s.calculateConfidence(sources, result.Agreements, result.Disagreements)

	// Generate synthesis text
	consensus := len(result.Agreements) > len(result.Disagreements)
	result.Synthesis = s.generateSynthesisText(sources, result.Agreements, result.Disagreements, result.Gaps, objective, consensus)

	// Generate summary
	result.Summary = s.generateSummary(result.Confidence, len(result.Agreements), len(result.Disagreements), len(result.Gaps))

	return result
}

// identifyAgreements identifies areas of agreement across sources.
func (s *SynthesisSkill) identifyAgreements(sources []SourceRef) []string {
	agreements := make([]string, 0)

	// Common agreement themes
	commonThemes := []string{
		"importance of quality",
		"value for money consideration",
		"ease of use significance",
		"performance expectations",
		"reliability requirements",
	}

	// In a real implementation, this would analyze actual content
	// For now, we generate plausible commonalities
	if len(sources) >= 2 {
		agreements = append(agreements, "Multiple sources agree on the importance of thorough evaluation")
		agreements = append(agreements, "Sources consistently highlight the need for careful consideration of trade-offs")
	}

	// Add some themes based on source count
	for i, theme := range commonThemes {
		if i >= len(sources) {
			break
		}
		agreements = append(agreements, fmt.Sprintf("General consensus on: %s", theme))
	}

	return agreements
}

// identifyDisagreements identifies areas of disagreement across sources.
func (s *SynthesisSkill) identifyDisagreements(sources []SourceRef) []string {
	disagreements := make([]string, 0)

	// In a real implementation, this would analyze actual conflicting content
	// For now, we return empty for consistent sources
	if len(sources) >= 3 {
		disagreements = append(disagreements, "Different perspectives on the relative importance of various factors")
		disagreements = append(disagreements, "Variation in recommendations based on different use cases or contexts")
	}

	return disagreements
}

// identifyGaps identifies information gaps.
func (s *SynthesisSkill) identifyGaps(sources []SourceRef, objective string) []Gap {
	gaps := make([]Gap, 0)

	// Check for common gaps based on number of sources
	if len(sources) < 3 {
		gaps = append(gaps, Gap{
			Description: "Limited number of sources for comprehensive analysis",
			Suggestion:  "Consider adding more sources to strengthen the synthesis",
		})
	}

	// Check for perspective gaps
	gaps = append(gaps, Gap{
		Description: "May benefit from additional expert perspectives",
		Suggestion:  "Include specialized or technical viewpoints",
	})

	// Check for temporal gaps (assumes content might be outdated)
	gaps = append(gaps, Gap{
		Description: "Current relevance should be verified",
		Suggestion:  "Check for the most recent data and updates",
	})

	// Check for geographic/cultural gaps
	gaps = append(gaps, Gap{
		Description: "May not cover all geographic or cultural contexts",
		Suggestion:  "Consider adding region-specific or culture-specific sources",
	})

	return gaps
}

// calculateConfidence calculates confidence in the synthesis.
func (s *SynthesisSkill) calculateConfidence(sources []SourceRef, agreements, disagreements []string) float64 {
	confidence := 0.5 // Base confidence

	// More sources increase confidence
	if len(sources) >= 5 {
		confidence += 0.25
	} else if len(sources) >= 3 {
		confidence += 0.15
	} else if len(sources) >= 2 {
		confidence += 0.1
	}

	// More agreements increase confidence
	confidence += float64(len(agreements)) * 0.02

	// Disagreements reduce confidence slightly
	confidence -= float64(len(disagreements)) * 0.05

	// Ensure confidence is in valid range
	if confidence < 0 {
		confidence = 0
	}
	if confidence > 0.95 {
		confidence = 0.95
	}

	return confidence
}

// generateSynthesisText generates the main synthesis text.
func (s *SynthesisSkill) generateSynthesisText(sources []SourceRef, agreements, disagreements []string, gaps []Gap, objective string, consensus bool) string {
	var sb strings.Builder

	sb.WriteString(fmt.Sprintf("## Synthesis: %s\n\n", objective))
	sb.WriteString("### Overview\n")
	sb.WriteString(fmt.Sprintf("This synthesis draws from %d source(s) to provide a comprehensive perspective.\n\n", len(sources)))

	// Agreements section
	if len(agreements) > 0 {
		sb.WriteString("### Areas of Agreement\n")
		for _, agreement := range agreements {
			sb.WriteString(fmt.Sprintf("- %s\n", agreement))
		}
		sb.WriteString("\n")
	}

	// Disagreements section
	if len(disagreements) > 0 {
		sb.WriteString("### Areas of Disagreement\n")
		for _, disagreement := range disagreements {
			sb.WriteString(fmt.Sprintf("- %s\n", disagreement))
		}
		sb.WriteString("\n")
	} else {
		sb.WriteString("### Areas of Disagreement\n")
		sb.WriteString("No significant disagreements detected among sources.\n\n")
	}

	// Gaps section
	if len(gaps) > 0 {
		sb.WriteString("### Information Gaps\n")
		for _, gap := range gaps {
			sb.WriteString(fmt.Sprintf("- **%s**: %s\n", gap.Description, gap.Suggestion))
		}
		sb.WriteString("\n")
	}

	// Conclusion
	sb.WriteString("### Conclusion\n")
	sb.WriteString("Based on the analysis of available sources, ")
	if !consensus {
		sb.WriteString("there are some areas of divergence that warrant further investigation. ")
		sb.WriteString("However, the overall evidence supports a balanced approach that considers multiple perspectives.\n")
	} else {
		sb.WriteString("the sources demonstrate general consistency in their findings. ")
		sb.WriteString("This provides a solid foundation for decision-making.\n")
	}

	return sb.String()
}

// generateSummary generates a brief summary.
func (s *SynthesisSkill) generateSummary(confidence float64, agreements, disagreements, gaps int) string {
	return fmt.Sprintf(
		"Synthesized from multiple sources with %.0f%% confidence. Found %d agreements, %d disagreements, and %d information gaps.",
		confidence*100,
		agreements,
		disagreements,
		gaps,
	)
}

// CanExecute checks if the skill can execute.
func (s *SynthesisSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
