package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// ExamplesSkill implements the examples skill for generating examples.
type ExamplesSkill struct{}

// NewExamplesSkill creates a new ExamplesSkill.
func NewExamplesSkill() *ExamplesSkill {
	return &ExamplesSkill{}
}

// Name returns the skill name.
func (s *ExamplesSkill) Name() SkillName {
	return "examples"
}

// Description returns the skill description.
func (s *ExamplesSkill) Description() string {
	return "Generates examples and counter-examples to illustrate concepts"
}

// RequiredTools returns the tools required by this skill.
func (s *ExamplesSkill) RequiredTools() []ToolName {
	return nil
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *ExamplesSkill) RequiredMCPs() []MCPName {
	return nil
}

// Example represents a single example.
type Example struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Domain      string `json:"domain,omitempty"`
	Relevance   string `json:"relevance,omitempty"`
}

// Execute generates examples for a concept.
func (s *ExamplesSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	concept := s.extractString(params.Input, "concept")
	if concept == "" {
		concept = s.extractString(params.Input, "topic")
	}
	if concept == "" {
		concept = s.extractString(params.Context, "concept")
	}
	if concept == "" {
		return SkillResult{
			Success:    false,
			Error:      "concept is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	domain := s.extractString(params.Input, "domain")
	count := s.extractInt(params.Input, "count", 5)

	// Generate examples and anti-examples
	examples := s.generateExamples(concept, domain, count)
	antiExamples := s.generateAntiExamples(concept, domain, count)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"concept":       concept,
			"domain":        domain,
			"examples":      examples,
			"anti_examples": antiExamples,
			"count":         len(examples) + len(antiExamples),
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *ExamplesSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// extractInt extracts an int from a map.
func (s *ExamplesSkill) extractInt(m map[string]any, key string, defaultVal int) int {
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

// generateExamples generates positive examples.
func (s *ExamplesSkill) generateExamples(concept string, domain string, count int) []Example {
	examples := make([]Example, 0)

	// Determine domain if not specified
	if domain == "" {
		domain = s.inferDomain(concept)
	}

	// Generate examples based on domain
	switch domain {
	case "programming", "software", "code", "development":
		examples = s.generateCodeExamples(concept, count)
	case "science", "physics", "chemistry", "biology":
		examples = s.generateScienceExamples(concept, count)
	case "math", "mathematics":
		examples = s.generateMathExamples(concept, count)
	case "language", "writing", "grammar":
		examples = s.generateLanguageExamples(concept, count)
	case "business", "management":
		examples = s.generateBusinessExamples(concept, count)
	case "health", "medical":
		examples = s.generateHealthExamples(concept, count)
	default:
		examples = s.generateGeneralExamples(concept, count)
	}

	return examples
}

// generateAntiExamples generates counter-examples.
func (s *ExamplesSkill) generateAntiExamples(concept string, domain string, count int) []Example {
	antiExamples := make([]Example, 0)

	// Generate counter-examples based on domain
	switch domain {
	case "programming", "software", "code", "development":
		antiExamples = s.generateCodeAntiExamples(concept, count)
	case "science":
		antiExamples = s.generateScienceAntiExamples(concept, count)
	case "math":
		antiExamples = s.generateMathAntiExamples(concept, count)
	default:
		antiExamples = s.generateGeneralAntiExamples(concept, count)
	}

	return antiExamples
}

// inferDomain attempts to determine the domain from the concept.
func (s *ExamplesSkill) inferDomain(concept string) string {
	conceptLower := strings.ToLower(concept)

	domains := map[string][]string{
		"programming": {"code", "function", "algorithm", "loop", "variable", "programming", "software", "developer"},
		"science":     {"science", "experiment", "theory", "hypothesis", "research", "physics", "chemistry", "biology"},
		"math":        {"math", "number", "equation", "calculation", "geometry", "algebra", "calculus"},
		"language":    {"language", "grammar", "writing", "vocabulary", "sentence", "paragraph"},
		"business":    {"business", "management", "marketing", "strategy", "company", "revenue"},
		"health":      {"health", "medical", "disease", "treatment", "patient", "doctor"},
	}

	for domain, keywords := range domains {
		for _, kw := range keywords {
			if strings.Contains(conceptLower, kw) {
				return domain
			}
		}
	}

	return "general"
}

// generateCodeExamples generates programming-related examples.
func (s *ExamplesSkill) generateCodeExamples(concept string, count int) []Example {
	examples := []Example{
		{
			Title:       "Simple Implementation",
			Description: fmt.Sprintf("A basic %s implementation showing core functionality", concept),
			Domain:      "programming",
			Relevance:   "high",
		},
		{
			Title:       "Production-Grade Code",
			Description: fmt.Sprintf("A robust, well-tested %s implementation suitable for production use", concept),
			Domain:      "programming",
			Relevance:   "high",
		},
		{
			Title:       "Tutorial Example",
			Description: fmt.Sprintf("A step-by-step example of %s designed for learning purposes", concept),
			Domain:      "programming",
			Relevance:   "medium",
		},
		{
			Title:       "Real-World Application",
			Description: fmt.Sprintf("How %s is used in a real application to solve an actual problem", concept),
			Domain:      "programming",
			Relevance:   "high",
		},
		{
			Title:       "Testing Example",
			Description: fmt.Sprintf("Example of %s with proper test coverage and edge cases", concept),
			Domain:      "programming",
			Relevance:   "medium",
		},
	}

	if count < len(examples) {
		return examples[:count]
	}
	return examples
}

// generateCodeAntiExamples generates programming anti-examples.
func (s *ExamplesSkill) generateCodeAntiExamples(concept string, count int) []Example {
	antiExamples := []Example{
		{
			Title:       "Copy-Paste Code",
			Description: fmt.Sprintf("Blindly copying %s without understanding how it works", concept),
			Domain:      "programming",
			Relevance:   "common mistake",
		},
		{
			Title:       "Hardcoded Values",
			Description: fmt.Sprintf("Using %s with hardcoded values instead of configuration", concept),
			Domain:      "programming",
			Relevance:   "common mistake",
		},
		{
			Title:       "Ignoring Error Handling",
			Description: fmt.Sprintf("Implementing %s without proper error handling or validation", concept),
			Domain:      "programming",
			Relevance:   "critical mistake",
		},
	}

	if count < len(antiExamples) {
		return antiExamples[:count]
	}
	return antiExamples
}

// generateScienceExamples generates science-related examples.
func (s *ExamplesSkill) generateScienceExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Controlled Experiment",
			Description: fmt.Sprintf("A properly controlled experiment demonstrating %s", concept),
			Domain:      "science",
			Relevance:   "high",
		},
		{
			Title:       "Real-World Observation",
			Description: fmt.Sprintf("Natural occurrence of %s observed in the wild", concept),
			Domain:      "science",
			Relevance:   "high",
		},
		{
			Title:       "Research Application",
			Description: fmt.Sprintf("How %s is applied in current scientific research", concept),
			Domain:      "science",
			Relevance:   "medium",
		},
	}
}

// generateScienceAntiExamples generates science anti-examples.
func (s *ExamplesSkill) generateScienceAntiExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Unverified Claim",
			Description: fmt.Sprintf("Accepting %s as fact without proper peer review", concept),
			Domain:      "science",
			Relevance:   "common mistake",
		},
		{
			Title:       "Correlation Confusion",
			Description: fmt.Sprintf("Confusing correlation with causation in %s", concept),
			Domain:      "science",
			Relevance:   "critical mistake",
		},
	}
}

// generateMathExamples generates math-related examples.
func (s *ExamplesSkill) generateMathExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Basic Calculation",
			Description: fmt.Sprintf("Simple illustration of %s with small numbers", concept),
			Domain:      "math",
			Relevance:   "high",
		},
		{
			Title:       "Word Problem",
			Description: fmt.Sprintf("Real-world problem solved using %s", concept),
			Domain:      "math",
			Relevance:   "medium",
		},
		{
			Title:       "Proof Example",
			Description: fmt.Sprintf("Formal proof demonstrating %s", concept),
			Domain:      "math",
			Relevance:   "high",
		},
	}
}

// generateMathAntiExamples generates math anti-examples.
func (s *ExamplesSkill) generateMathAntiExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Unit Confusion",
			Description: fmt.Sprintf("Mixing up units when applying %s", concept),
			Domain:      "math",
			Relevance:   "common mistake",
		},
	}
}

// generateLanguageExamples generates language-related examples.
func (s *ExamplesSkill) generateLanguageExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Correct Usage",
			Description: fmt.Sprintf("Proper example of %s in a well-constructed sentence", concept),
			Domain:      "language",
			Relevance:   "high",
		},
		{
			Title:       "Literary Example",
			Description: fmt.Sprintf("%s used in classic literature", concept),
			Domain:      "language",
			Relevance:   "medium",
		},
	}
}

// generateBusinessExamples generates business-related examples.
func (s *ExamplesSkill) generateBusinessExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Startup Application",
			Description: fmt.Sprintf("How a startup successfully applied %s", concept),
			Domain:      "business",
			Relevance:   "high",
		},
		{
			Title:       "Enterprise Implementation",
			Description: fmt.Sprintf("Large-scale implementation of %s in a corporate setting", concept),
			Domain:      "business",
			Relevance:   "high",
		},
	}
}

// generateHealthExamples generates health-related examples.
func (s *ExamplesSkill) generateHealthExamples(concept string, count int) []Example {
	return []Example{
		{
			Title:       "Clinical Case",
			Description: fmt.Sprintf("Documented case study showing %s in practice", concept),
			Domain:      "health",
			Relevance:   "high",
		},
		{
			Title:       "Preventive Application",
			Description: fmt.Sprintf("How %s is used for disease prevention", concept),
			Domain:      "health",
			Relevance:   "high",
		},
	}
}

// generateGeneralExamples generates general examples.
func (s *ExamplesSkill) generateGeneralExamples(concept string, count int) []Example {
	examples := []Example{
		{
			Title:       "Everyday Example",
			Description: fmt.Sprintf("A common, relatable example of %s from daily life", concept),
			Relevance:   "high",
		},
		{
			Title:       "Historical Example",
			Description: fmt.Sprintf("How %s has been understood or applied historically", concept),
			Relevance:   "medium",
		},
		{
			Title:       "Analogy Example",
			Description: fmt.Sprintf("Using analogy to explain %s", concept),
			Relevance:   "high",
		},
		{
			Title:       "Practical Application",
			Description: fmt.Sprintf("Real-world application of %s in a familiar context", concept),
			Relevance:   "high",
		},
		{
			Title:       "Educational Example",
			Description: fmt.Sprintf("How teachers explain %s to students", concept),
			Relevance:   "medium",
		},
	}

	if count < len(examples) {
		return examples[:count]
	}
	return examples
}

// generateGeneralAntiExamples generates general anti-examples.
func (s *ExamplesSkill) generateGeneralAntiExamples(concept string, count int) []Example {
	antiExamples := []Example{
		{
			Title:       "Oversimplification",
			Description: fmt.Sprintf("Taking %s to an extreme by oversimplifying it", concept),
			Relevance:   "common mistake",
		},
		{
			Title:       "Misapplication",
			Description: fmt.Sprintf("Applying %s in an inappropriate context", concept),
			Relevance:   "common mistake",
		},
		{
			Title:       "Overgeneralization",
			Description: fmt.Sprintf("Making sweeping claims about %s that don't hold generally", concept),
			Relevance:   "common mistake",
		},
	}

	if count < len(antiExamples) {
		return antiExamples[:count]
	}
	return antiExamples
}

// CanExecute checks if the skill can execute.
func (s *ExamplesSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
