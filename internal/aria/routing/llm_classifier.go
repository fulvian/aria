package routing

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/fulvian/aria/internal/llm/models"
	"github.com/fulvian/aria/internal/llm/provider"
	"github.com/fulvian/aria/internal/llm/tools"
	"github.com/fulvian/aria/internal/message"
)

// LLMClassifier uses LLM for intelligent query classification
type LLMClassifier struct {
	provider provider.Provider
	fallback *BaselineClassifier
	modelID  models.ModelID
}

// NewLLMClassifier creates a new LLM-based classifier
func NewLLMClassifier(p provider.Provider, modelID models.ModelID) *LLMClassifier {
	return &LLMClassifier{
		provider: p,
		fallback: NewBaselineClassifier(),
		modelID:  modelID,
	}
}

// Classify determines query characteristics using LLM
func (c *LLMClassifier) Classify(ctx context.Context, query Query) (Classification, error) {
	// Build prompt for classification
	systemPrompt := `You are a query classifier. Classify user queries into:
- intent: question|task|creation|analysis|learning|planning|conversation
- domain: general|development|knowledge|creative|productivity|personal|analytics|nutrition
- complexity: simple|medium|complex
- urgency: now|soon|eventually
- confidence: 0.0-1.0

Respond with ONLY valid JSON: {"intent":"...","domain":"...","complexity":"...","urgency":"...","confidence":0.9}`

	userPrompt := buildUserPrompt(query)

	// Call LLM
	messages := []message.Message{
		{
			Role:  message.System,
			Parts: []message.ContentPart{message.TextContent{Text: systemPrompt}},
		},
		{
			Role:  message.User,
			Parts: []message.ContentPart{message.TextContent{Text: userPrompt}},
		},
	}

	resp, err := c.provider.SendMessages(ctx, messages, []tools.BaseTool{})
	if err != nil {
		// Fallback to baseline on error
		return c.fallback.Classify(ctx, query)
	}

	// Parse response
	class, err := parseLLMResponse(resp.Content)
	if err != nil {
		// Fallback to baseline on parse error
		return c.fallback.Classify(ctx, query)
	}

	return class, nil
}

func buildUserPrompt(query Query) string {
	prompt := "Classify this query:\n" + query.Text
	if len(query.History) > 0 {
		prompt += "\n\nHistory:\n"
		for _, h := range query.History {
			prompt += "- " + h + "\n"
		}
	}
	return prompt
}

func parseLLMResponse(content string) (Classification, error) {
	// Try to extract JSON from response
	content = strings.TrimSpace(content)

	// Find JSON object
	start := strings.Index(content, "{")
	end := strings.LastIndex(content, "}") + 1
	if start == -1 || end == 0 {
		return Classification{}, ErrNoJSONInResponse
	}

	jsonStr := content[start:end]

	var raw struct {
		Intent     string  `json:"intent"`
		Domain     string  `json:"domain"`
		Complexity string  `json:"complexity"`
		Urgency    string  `json:"urgency"`
		Confidence float64 `json:"confidence"`
	}

	if err := json.Unmarshal([]byte(jsonStr), &raw); err != nil {
		return Classification{}, err
	}

	// Validate and normalize
	intent := classifyIntent(raw.Intent)
	domain := classifyDomain(raw.Domain)
	complexity := classifyComplexity(raw.Complexity)
	urgency := classifyUrgency(raw.Urgency)

	return Classification{
		Intent:          intent,
		Domain:          domain,
		Complexity:      complexity,
		RequiresState:   complexity == ComplexityComplex,
		Urgency:         urgency,
		SuggestedTarget: suggestTarget(intent, complexity),
		Confidence:      raw.Confidence,
		Reason:          "LLM classified",
	}, nil
}

var ErrNoJSONInResponse = &parseError{message: "no JSON found in response"}

type parseError struct {
	message string
}

func (e *parseError) Error() string {
	return e.message
}

func classifyIntent(s string) Intent {
	s = strings.ToLower(s)
	switch s {
	case "question":
		return IntentQuestion
	case "task":
		return IntentTask
	case "creation":
		return IntentCreation
	case "analysis":
		return IntentAnalysis
	case "learning":
		return IntentLearning
	case "planning":
		return IntentPlanning
	case "conversation":
		return IntentConversation
	default:
		return IntentTask
	}
}

func classifyDomain(s string) DomainName {
	s = strings.ToLower(s)
	switch s {
	case "general":
		return DomainGeneral
	case "development":
		return DomainDevelopment
	case "knowledge":
		return DomainKnowledge
	case "creative":
		return DomainCreative
	case "productivity":
		return DomainProductivity
	case "personal":
		return DomainPersonal
	case "analytics":
		return DomainAnalytics
	case "nutrition":
		return DomainNutrition
	default:
		return DomainGeneral
	}
}

func classifyComplexity(s string) ComplexityLevel {
	s = strings.ToLower(s)
	switch s {
	case "simple":
		return ComplexitySimple
	case "medium":
		return ComplexityMedium
	case "complex":
		return ComplexityComplex
	default:
		return ComplexityMedium
	}
}

func classifyUrgency(s string) UrgencyLevel {
	s = strings.ToLower(s)
	switch s {
	case "now":
		return UrgencyNow
	case "soon":
		return UrgencySoon
	case "eventually":
		return UrgencyEventually
	default:
		return UrgencyNow
	}
}

func suggestTarget(intent Intent, complexity ComplexityLevel) RoutingTarget {
	if complexity == ComplexitySimple {
		return TargetSkill
	}
	return TargetAgency
}

// GetSupportedIntents returns supported intents
func (c *LLMClassifier) GetSupportedIntents() []Intent {
	return c.fallback.GetSupportedIntents()
}

// GetSupportedDomains returns supported domains
func (c *LLMClassifier) GetSupportedDomains() []DomainName {
	return c.fallback.GetSupportedDomains()
}
