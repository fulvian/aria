package routing

import (
	"context"
	"strings"
)

// BaselineClassifier is a rules-based classifier for initial implementation.
type BaselineClassifier struct {
	supportedIntents []Intent
	supportedDomains []DomainName
}

// NewBaselineClassifier creates a new baseline classifier.
func NewBaselineClassifier() *BaselineClassifier {
	return &BaselineClassifier{
		supportedIntents: []Intent{
			IntentQuestion,
			IntentTask,
			IntentCreation,
			IntentAnalysis,
			IntentLearning,
			IntentPlanning,
			IntentConversation,
		},
		supportedDomains: []DomainName{
			DomainGeneral,
			DomainDevelopment,
			DomainKnowledge,
			DomainCreative,
			DomainProductivity,
			DomainPersonal,
			DomainAnalytics,
		},
	}
}

// Classify determines the characteristics of a query using simple rules.
func (c *BaselineClassifier) Classify(ctx context.Context, query Query) (Classification, error) {
	text := strings.ToLower(query.Text)

	// Determine intent
	intent := c.classifyIntent(text)

	// Determine domain
	domain := c.classifyDomain(text)

	// Determine complexity
	complexity := c.classifyComplexity(text, query.History)

	// Determine urgency (default for now)
	urgency := UrgencyNow

	// Determine suggested target
	target := c.suggestTarget(intent, complexity)

	// Calculate confidence
	confidence := c.calculateConfidence(text, intent, domain)

	return Classification{
		Intent:          intent,
		Domain:          domain,
		Complexity:      complexity,
		RequiresState:   complexity == ComplexityComplex,
		Urgency:         urgency,
		SuggestedTarget: target,
		Confidence:      confidence,
		Reason:          c.getReason(intent, domain, complexity),
	}, nil
}

func (c *BaselineClassifier) classifyIntent(text string) Intent {
	// Check for question indicators
	questionWords := []string{"what", "how", "why", "when", "where", "who", "which", "?"}
	for _, word := range questionWords {
		if strings.Contains(text, word) {
			return IntentQuestion
		}
	}

	// Check for creation indicators
	creationWords := []string{"create", "write", "build", "make", "add", "new"}
	for _, word := range creationWords {
		if strings.Contains(text, word) {
			return IntentCreation
		}
	}

	// Check for task indicators
	taskWords := []string{"do", "run", "execute", "process", "handle", "帮我", "执行"}
	for _, word := range taskWords {
		if strings.Contains(text, word) {
			return IntentTask
		}
	}

	// Check for analysis indicators
	analysisWords := []string{"analyze", "check", "review", "examine", "investigate", "debug"}
	for _, word := range analysisWords {
		if strings.Contains(text, word) {
			return IntentAnalysis
		}
	}

	// Check for planning indicators
	planningWords := []string{"plan", "schedule", "organize", "安排", "计划"}
	for _, word := range planningWords {
		if strings.Contains(text, word) {
			return IntentPlanning
		}
	}

	// Check for learning indicators
	learningWords := []string{"learn", "explain", "teach", "understand", "what is", "什么是"}
	for _, word := range learningWords {
		if strings.Contains(text, word) {
			return IntentLearning
		}
	}

	// Default to task for development context
	return IntentTask
}

func (c *BaselineClassifier) classifyDomain(text string) DomainName {
	// Development domain indicators
	devWords := []string{"code", "function", "class", "file", "bug", "error", "test", "debug", "implement", "refactor", "api", "database", "commit", "git", "docker", "kubernetes", "deploy"}
	for _, word := range devWords {
		if strings.Contains(text, word) {
			return DomainDevelopment
		}
	}

	// Knowledge domain indicators
	knowledgeWords := []string{"what is", "who is", "explain", "definition", "learn", "research", "search", "什么是", "谁"}
	for _, word := range knowledgeWords {
		if strings.Contains(text, word) {
			return DomainKnowledge
		}
	}

	// Creative domain indicators
	creativeWords := []string{"write", "story", "blog", "article", "creative", "design", "write"}
	for _, word := range creativeWords {
		if strings.Contains(text, word) {
			return DomainCreative
		}
	}

	// Default to general
	return DomainGeneral
}

func (c *BaselineClassifier) classifyComplexity(text string, history []string) ComplexityLevel {
	// Simple indicators: short text, no history
	if len(text) < 50 && len(history) == 0 {
		return ComplexitySimple
	}

	// Complex indicators: multi-part requests, code context
	complexWords := []string{"and then", "also", "plus", "multiple", "several", "all", "整个", "并且"}
	for _, word := range complexWords {
		if strings.Contains(text, word) {
			return ComplexityComplex
		}
	}

	// Code-related complex tasks
	if strings.Contains(text, "refactor") || strings.Contains(text, "migrate") ||
		strings.Contains(text, "architecture") || strings.Contains(text, "design") {
		return ComplexityComplex
	}

	// Medium for everything else
	return ComplexityMedium
}

func (c *BaselineClassifier) suggestTarget(intent Intent, complexity ComplexityLevel) RoutingTarget {
	if complexity == ComplexitySimple {
		return TargetSkill
	}
	if complexity == ComplexityComplex {
		return TargetAgency
	}
	return TargetAgency
}

func (c *BaselineClassifier) calculateConfidence(text string, intent Intent, domain DomainName) float64 {
	confidence := 0.5

	// Boost confidence if domain-specific keywords found
	if domain == DomainDevelopment {
		devKeywords := []string{"code", "function", "bug", "error", "test", "file", "class"}
		for _, kw := range devKeywords {
			if strings.Contains(text, kw) {
				confidence += 0.1
			}
		}
	}

	// Cap at 0.95
	if confidence > 0.95 {
		confidence = 0.95
	}

	return confidence
}

func (c *BaselineClassifier) getReason(intent Intent, domain DomainName, complexity ComplexityLevel) string {
	return "classified as " + string(intent) + " intent, " + string(domain) + " domain, " + string(complexity) + " complexity"
}

// GetSupportedIntents returns all supported intents.
func (c *BaselineClassifier) GetSupportedIntents() []Intent {
	return c.supportedIntents
}

// GetSupportedDomains returns all supported domains.
func (c *BaselineClassifier) GetSupportedDomains() []DomainName {
	return c.supportedDomains
}
