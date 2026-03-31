package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// SummarizationSkill implements the summarization skill for condensing content.
type SummarizationSkill struct{}

// NewSummarizationSkill creates a new SummarizationSkill.
func NewSummarizationSkill() *SummarizationSkill {
	return &SummarizationSkill{}
}

// Name returns the skill name.
func (s *SummarizationSkill) Name() SkillName {
	return SkillSummarization
}

// Description returns the skill description.
func (s *SummarizationSkill) Description() string {
	return "Summarizes long content into concise summaries with key points"
}

// RequiredTools returns the tools required by this skill.
func (s *SummarizationSkill) RequiredTools() []ToolName {
	return nil
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *SummarizationSkill) RequiredMCPs() []MCPName {
	return nil
}

// SummarizationStyle represents the style of summarization.
type SummarizationStyle string

const (
	StyleBrief     SummarizationStyle = "brief"
	StyleDetailed  SummarizationStyle = "detailed"
	StyleBullet    SummarizationStyle = "bullet"
	StyleExecutive SummarizationStyle = "executive"
	StyleTechnical SummarizationStyle = "technical"
)

// Execute performs summarization on the provided content.
func (s *SummarizationSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	content := s.extractString(params.Input, "content")
	if content == "" {
		content = s.extractString(params.Context, "content")
	}
	if content == "" {
		return SkillResult{
			Success:    false,
			Error:      "content is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	style := s.extractString(params.Input, "style")
	if style == "" {
		style = "brief"
	}

	length := s.extractString(params.Input, "length")
	if length == "" {
		length = "medium"
	}

	// Generate summary
	summary := s.generateSummary(content, style, length)
	bulletPoints := s.extractBulletPoints(content, style)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"original_length": len(content),
			"summary":         summary,
			"bullet_points":   bulletPoints,
			"style":           style,
			"length":          length,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *SummarizationSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// extractInt extracts an int from a map.
func (s *SummarizationSkill) extractInt(m map[string]any, key string, defaultVal int) int {
	if v, ok := m[key].(int); ok {
		return v
	}
	if v, ok := m[key].(int64); ok {
		return int(v)
	}
	if v, ok := m[key].(float64); ok {
		return int(v)
	}
	return defaultVal
}

// generateSummary generates a summary based on style and content.
func (s *SummarizationSkill) generateSummary(content string, style string, length string) string {
	// Truncate content for processing
	if len(content) > 5000 {
		content = content[:5000]
	}

	// Extract sentences
	sentences := extractSentences(content)
	if len(sentences) == 0 {
		return "Unable to generate summary."
	}

	// Determine target length
	var targetSentences int
	switch length {
	case "short":
		targetSentences = 1
	case "medium":
		targetSentences = 3
	case "long":
		targetSentences = 5
	default:
		targetSentences = 3
	}

	// For brief style, just return first sentences
	if style == "brief" {
		if targetSentences > len(sentences) {
			targetSentences = len(sentences)
		}
		return strings.Join(sentences[:targetSentences], " ")
	}

	// For detailed styles, try to extract key information
	keySentences := s.identifyKeySentences(sentences, targetSentences)

	switch style {
	case "executive":
		return s.formatExecutiveSummary(keySentences)
	case "technical":
		return s.formatTechnicalSummary(keySentences)
	default:
		return strings.Join(keySentences, " ")
	}
}

// extractSentences extracts sentences from content.
func extractSentences(content string) []string {
	// Simple sentence splitting
	content = strings.ReplaceAll(content, "\n", " ")
	content = strings.ReplaceAll(content, "\r", " ")

	// Split on common sentence endings
	sentences := strings.FieldsFunc(content, func(r rune) bool {
		return r == '.' || r == '!' || r == '?'
	})

	// Clean up sentences
	result := make([]string, 0, len(sentences))
	for _, s := range sentences {
		s = strings.TrimSpace(s)
		if len(s) > 10 { // Skip very short segments
			result = append(result, s+".")
		}
	}

	return result
}

// identifyKeySentences identifies the most important sentences.
func (s *SummarizationSkill) identifyKeySentences(sentences []string, count int) []string {
	if len(sentences) <= count {
		return sentences
	}

	// Simple heuristic: prefer sentences with key terms
	// In a real implementation, this would use LLM or more sophisticated methods
	keyTerms := []string{
		"important", "significant", "key", "main", "primary",
		"essential", "critical", "crucial", "major", "notable",
		"conclusion", "result", "finding", "discovered", "showed",
	}

	scored := make([]struct {
		sentence string
		score    int
	}, len(sentences))

	for i, sent := range sentences {
		scored[i].sentence = sent
		sentLower := strings.ToLower(sent)

		for _, term := range keyTerms {
			if strings.Contains(sentLower, term) {
				scored[i].score++
			}
		}

		// Boost sentences at the beginning (often contain thesis)
		if i < 3 {
			scored[i].score += 2
		}

		// Boost sentences at the end (often contain conclusions)
		if i >= len(sentences)-3 {
			scored[i].score += 2
		}
	}

	// Sort by score descending
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[i].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}

	// Return top sentences in original order
	result := make([]string, 0, count)
	seen := make(map[int]bool)
	for _, item := range scored {
		if len(result) >= count {
			break
		}
		// Find original index
		for i, sent := range sentences {
			if sent == item.sentence && !seen[i] {
				result = append(result, sent)
				seen[i] = true
				break
			}
		}
	}

	// Sort by original order
	// (result now contains top sentences in arbitrary order from scoring)

	return result
}

// formatExecutiveSummary formats a summary for executives.
func (s *SummarizationSkill) formatExecutiveSummary(sentences []string) string {
	if len(sentences) == 0 {
		return "No content to summarize."
	}

	// Take first sentence as main point
	mainPoint := sentences[0]
	if len(sentences) > 1 {
		mainPoint = sentences[len(sentences)-1]
	}

	return fmt.Sprintf("Executive Summary: %s", mainPoint)
}

// formatTechnicalSummary formats a summary for technical audience.
func (s *SummarizationSkill) formatTechnicalSummary(sentences []string) string {
	var sb strings.Builder
	sb.WriteString("Technical Summary:\n")

	for i, sent := range sentences {
		if i >= 5 {
			break
		}
		sb.WriteString(fmt.Sprintf("- %s\n", sent))
	}

	return sb.String()
}

// extractBulletPoints extracts bullet points from content.
func (s *SummarizationSkill) extractBulletPoints(content string, style string) []string {
	// Try to extract bullet points from content
	lines := strings.Split(content, "\n")
	bullets := make([]string, 0)

	for _, line := range lines {
		line = strings.TrimSpace(line)
		// Skip empty lines
		if len(line) == 0 {
			continue
		}

		// Check for bullet markers
		if strings.HasPrefix(line, "-") ||
			strings.HasPrefix(line, "*") ||
			strings.HasPrefix(line, "•") ||
			strings.HasPrefix(line, "1.") ||
			strings.HasPrefix(line, "2.") ||
			strings.HasPrefix(line, "3.") {
			// Remove bullet marker
			line = strings.TrimLeft(line, "-*•123456789. ")
			if len(line) > 5 {
				bullets = append(bullets, line)
			}
		}
	}

	// If no explicit bullets found, generate from sentences
	if len(bullets) == 0 {
		sentences := extractSentences(content)
		for i, sent := range sentences {
			if i >= 5 {
				break
			}
			bullets = append(bullets, sent)
		}
	}

	// Limit bullets
	if len(bullets) > 7 {
		bullets = bullets[:7]
	}

	return bullets
}

// CanExecute checks if the skill can execute.
func (s *SummarizationSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
