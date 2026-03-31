package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// SimplificationSkill implements the simplification skill for explaining concepts simply.
type SimplificationSkill struct{}

// NewSimplificationSkill creates a new SimplificationSkill.
func NewSimplificationSkill() *SimplificationSkill {
	return &SimplificationSkill{}
}

// Name returns the skill name.
func (s *SimplificationSkill) Name() SkillName {
	return "simplification"
}

// Description returns the skill description.
func (s *SimplificationSkill) Description() string {
	return "Explains complex concepts in simple terms for a target audience"
}

// RequiredTools returns the tools required by this skill.
func (s *SimplificationSkill) RequiredTools() []ToolName {
	return nil
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *SimplificationSkill) RequiredMCPs() []MCPName {
	return nil
}

// SimplificationLevel represents the complexity level.
type SimplificationLevel string

const (
	LevelNovice       SimplificationLevel = "novice"       // Elementary understanding
	LevelBeginner     SimplificationLevel = "beginner"     // Basic concepts
	LevelIntermediate SimplificationLevel = "intermediate" // Some background
	LevelAdvanced     SimplificationLevel = "advanced"     // Technical audience
)

// SimplificationResult contains the result of a simplification.
type SimplificationResult struct {
	SimpleExplanation string         `json:"simple_explanation"`
	Glossary          []GlossaryTerm `json:"glossary"`
	Analogies         []string       `json:"analogies"`
	Level             string         `json:"level"`
}

// GlossaryTerm represents a term and its simple definition.
type GlossaryTerm struct {
	Term       string `json:"term"`
	Definition string `json:"definition"`
}

// Execute performs simplification on the provided content.
func (s *SimplificationSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	topic := s.extractString(params.Input, "topic")
	if topic == "" {
		topic = s.extractString(params.Input, "content")
	}
	if topic == "" {
		topic = s.extractString(params.Context, "content")
	}
	if topic == "" {
		return SkillResult{
			Success:    false,
			Error:      "topic or content is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	audience := s.extractString(params.Input, "audience")
	if audience == "" {
		audience = "general"
	}

	level := s.extractString(params.Input, "level")
	if level == "" {
		level = "beginner"
	}

	// Generate simplified explanation
	result := s.simplifyContent(topic, audience, level)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"simple_explanation": result.SimpleExplanation,
			"glossary":           result.Glossary,
			"analogies":          result.Analogies,
			"level":              result.Level,
			"topic":              topic,
			"audience":           audience,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *SimplificationSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// simplifyContent generates a simplified explanation.
func (s *SimplificationSkill) simplifyContent(topic string, audience string, level string) SimplificationResult {
	result := SimplificationResult{
		Level:     level,
		Glossary:  make([]GlossaryTerm, 0),
		Analogies: make([]string, 0),
	}

	// Normalize topic
	topic = strings.TrimSpace(topic)
	if len(topic) > 200 {
		topic = topic[:200]
	}

	// Generate explanation based on level
	switch level {
	case "novice":
		result.SimpleExplanation = s.explainForNovice(topic)
	case "beginner":
		result.SimpleExplanation = s.explainForBeginner(topic)
	case "intermediate":
		result.SimpleExplanation = s.explainForIntermediate(topic)
	case "advanced":
		result.SimpleExplanation = s.explainForAdvanced(topic)
	default:
		result.SimpleExplanation = s.explainForBeginner(topic)
	}

	// Generate glossary of key terms
	result.Glossary = s.extractGlossaryTerms(topic)

	// Generate analogies
	result.Analogies = s.generateAnalogies(topic)

	return result
}

// explainForNovice creates an explanation for someone with no background.
func (s *SimplificationSkill) explainForNovice(topic string) string {
	return fmt.Sprintf(
		"Let's start from the very beginning:\n\n"+
			"**What is it?**\n"+
			"%s is something that you might encounter in everyday life. Think of it like learning about a new tool - it takes time to understand, but once you do, it can be very useful.\n\n"+
			"**Why does it matter?**\n"+
			"Understanding this can help you make better decisions and know more about the world around you.\n\n"+
			"**A simple way to remember it:**\n"+
			"If you remember just one thing about %s, remember this: it's a way to %s.",
		topic,
		topic,
		s.extractKeyAction(topic),
	)
}

// explainForBeginner creates an explanation for beginners.
func (s *SimplificationSkill) explainForBeginner(topic string) string {
	return fmt.Sprintf(
		"**%s - A Beginner's Guide**\n\n"+
			"At its core, %s is about understanding the fundamental principles. "+
			"It's like building with blocks - you start with the basics and gradually build up to more complex ideas.\n\n"+
			"**Key Points:**\n"+
			"1. Start with the basics - don't rush\n"+
			"2. Practice makes perfect\n"+
			"3. It's okay to make mistakes while learning\n\n"+
			"**Next Steps:**\n"+
			"Once you understand these basics, you'll be ready to explore more advanced topics.",
		topic,
		topic,
	)
}

// explainForIntermediate creates an explanation for those with some background.
func (s *SimplificationSkill) explainForIntermediate(topic string) string {
	return fmt.Sprintf(
		"**%s - Intermediate Perspective**\n\n"+
			"If you already have some familiarity with the basics, here's what you need to know at the next level:\n\n"+
			"**Core Concepts:**\n"+
			"- The main principles build on fundamental ideas\n"+
			"- There are common patterns you'll recognize\n"+
			"- Practical application reinforces learning\n\n"+
			"**Common Pitfalls:**\n"+
			"- Don't skip the fundamentals\n"+
			"- Pay attention to details\n"+
			"- Context matters",
		topic,
	)
}

// explainForAdvanced creates an explanation for technical audience.
func (s *SimplificationSkill) explainForAdvanced(topic string) string {
	return fmt.Sprintf(
		"**%s - Technical Overview**\n\n"+
			"For those with strong background knowledge, this summary covers the essential technical aspects:\n\n"+
			"**Summary:**\n"+
			"This topic involves advanced concepts that require understanding of underlying mechanisms. "+
			"The key is connecting theory to practice while maintaining rigor.\n\n"+
			"**Technical Notes:**\n"+
			"- Implementation requires careful attention to specifics\n"+
			"- Trade-offs exist between competing priorities\n"+
			"- Best practices evolve with new research",
		topic,
	)
}

// extractKeyAction attempts to extract the main action/purpose from topic.
func (s *SimplificationSkill) extractKeyAction(topic string) string {
	// Simple heuristic - in a real implementation, this would use LLM
	topicLower := strings.ToLower(topic)

	actionWords := map[string]string{
		"learning":      "learning new things",
		"understanding": "understanding how things work",
		"building":      "creating something new",
		"analysis":      "breaking down complex information",
		"management":    "organizing and coordinating resources",
		"development":   "creating and improving solutions",
		"research":      "discovering new information",
		"communication": "sharing information effectively",
	}

	for key, action := range actionWords {
		if strings.Contains(topicLower, key) {
			return action
		}
	}

	return "solving problems"
}

// extractGlossaryTerms extracts key terms from the topic.
func (s *SimplificationSkill) extractGlossaryTerms(topic string) []GlossaryTerm {
	glossary := make([]GlossaryTerm, 0)

	// Common terms to look for
	termsToCheck := []string{
		"algorithm", "data", "system", "process", "model",
		"network", "function", "method", "approach", "technique",
		"analysis", "structure", "pattern", "principle", "concept",
	}

	topicLower := strings.ToLower(topic)

	for _, term := range termsToCheck {
		if strings.Contains(topicLower, term) {
			glossary = append(glossary, GlossaryTerm{
				Term:       s.capitalize(term),
				Definition: s.getSimpleDefinition(term),
			})
		}
	}

	// If no terms found, add general entry
	if len(glossary) == 0 {
		glossary = append(glossary, GlossaryTerm{
			Term:       topic,
			Definition: "The main subject or concept being discussed.",
		})
	}

	return glossary
}

// capitalize capitalizes the first letter of a string.
func (s *SimplificationSkill) capitalize(str string) string {
	if len(str) == 0 {
		return str
	}
	return strings.ToUpper(string(str[0])) + str[1:]
}

// getSimpleDefinition returns a simple definition for common terms.
func (s *SimplificationSkill) getSimpleDefinition(term string) string {
	definitions := map[string]string{
		"algorithm": "A step-by-step set of instructions to solve a problem",
		"data":      "Information collected for reference or analysis",
		"system":    "A set of connected parts working together",
		"process":   "A series of actions to achieve a particular result",
		"model":     "A simplified representation of something complex",
		"network":   "A group of connected things or people",
		"function":  "What something does or its purpose",
		"method":    "A particular way of doing something",
		"approach":  "The way you think about and tackle something",
		"technique": "A specific way of doing something well",
		"analysis":  "A detailed examination of something",
		"structure": "The way something is organized",
		"pattern":   "A repeated design or regular way things happen",
		"principle": "A basic truth or rule that guides behavior",
		"concept":   "An abstract idea or general understanding",
	}

	if def, ok := definitions[term]; ok {
		return def
	}
	return "A key concept related to the topic."
}

// generateAnalogies generates simple analogies for the topic.
func (s *SimplificationSkill) generateAnalogies(topic string) []string {
	analogies := make([]string, 0)

	// Generic analogies based on common patterns
	analogies = append(analogies, fmt.Sprintf(
		"Think of %s like learning to ride a bicycle - at first it seems difficult, "+
			"but with practice it becomes second nature.",
		topic,
	))

	analogies = append(analogies, fmt.Sprintf(
		"%s is similar to building with LEGO blocks - you start with simple pieces "+
			"and combine them to create increasingly complex structures.",
		topic,
	))

	analogies = append(analogies, fmt.Sprintf(
		"Just as a chef follows a recipe to create a dish, %s involves following "+
			"structured steps to achieve a desired outcome.",
		topic,
	))

	return analogies
}

// CanExecute checks if the skill can execute.
func (s *SimplificationSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
