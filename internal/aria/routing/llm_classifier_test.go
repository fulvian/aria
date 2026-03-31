package routing

import (
	"context"
	"errors"
	"testing"

	"github.com/fulvian/aria/internal/llm/models"
	"github.com/fulvian/aria/internal/llm/provider"
	"github.com/fulvian/aria/internal/llm/tools"
	"github.com/fulvian/aria/internal/message"
)

// mockLLMProvider is a mock LLM provider for testing
type mockLLMProvider struct {
	responseContent string
	responseError   error
}

func (m *mockLLMProvider) SendMessages(ctx context.Context, messages []message.Message, tools []tools.BaseTool) (*provider.ProviderResponse, error) {
	if m.responseError != nil {
		return nil, m.responseError
	}
	return &provider.ProviderResponse{
		Content: m.responseContent,
	}, nil
}

func (m *mockLLMProvider) StreamResponse(ctx context.Context, messages []message.Message, tools []tools.BaseTool) <-chan provider.ProviderEvent {
	ch := make(chan provider.ProviderEvent)
	close(ch)
	return ch
}

func (m *mockLLMProvider) Model() models.Model {
	return models.Model{}
}

func (m *mockLLMProvider) CreateEmbedding(ctx context.Context, text string) ([]float32, error) {
	return nil, errors.New("embedding not supported")
}

// Ensure mockLLMProvider implements provider.Provider
var _ provider.Provider = (*mockLLMProvider)(nil)

func TestLLMClassifier_Classify_Success(t *testing.T) {
	prov := &mockLLMProvider{
		responseContent: `{"intent":"task","domain":"development","complexity":"medium","urgency":"now","confidence":0.9}`,
	}

	classifier := NewLLMClassifier(prov, models.ModelID("test-model"))

	query := Query{
		Text:    "帮我写一个函数",
		History: []string{"Hello"},
	}

	result, err := classifier.Classify(context.Background(), query)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if result.Intent != IntentTask {
		t.Errorf("expected IntentTask, got %v", result.Intent)
	}

	if result.Domain != DomainDevelopment {
		t.Errorf("expected DomainDevelopment, got %v", result.Domain)
	}

	if result.Complexity != ComplexityMedium {
		t.Errorf("expected ComplexityMedium, got %v", result.Complexity)
	}

	if result.Urgency != UrgencyNow {
		t.Errorf("expected UrgencyNow, got %v", result.Urgency)
	}

	if result.Confidence != 0.9 {
		t.Errorf("expected 0.9 confidence, got %f", result.Confidence)
	}
}

func TestLLMClassifier_Classify_FallbackOnError(t *testing.T) {
	prov := &mockLLMProvider{
		responseError: errors.New("provider error"),
	}

	classifier := NewLLMClassifier(prov, models.ModelID("test-model"))

	query := Query{
		Text: "what is go language?",
	}

	result, err := classifier.Classify(context.Background(), query)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Should fallback to baseline classification
	// "what is" indicates a question intent
	if result.Intent != IntentQuestion {
		t.Errorf("expected IntentQuestion (fallback), got %v", result.Intent)
	}
}

func TestLLMClassifier_Classify_FallbackOnParseError(t *testing.T) {
	prov := &mockLLMProvider{
		responseContent: "invalid json response",
	}

	classifier := NewLLMClassifier(prov, models.ModelID("test-model"))

	query := Query{
		Text: "帮我debug这个问题",
	}

	result, err := classifier.Classify(context.Background(), query)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Should fallback to baseline classification
	// Note: "帮我" matches task words first, so IntentTask is returned
	// (debug would be checked after, but we never get there due to "帮我" match)
	if result.Intent != IntentTask {
		t.Errorf("expected IntentTask (fallback via '帮我'), got %v", result.Intent)
	}
}

func TestLLMClassifier_Classify_WithHistory(t *testing.T) {
	prov := &mockLLMProvider{
		responseContent: `{"intent":"task","domain":"development","complexity":"complex","urgency":"soon","confidence":0.85}`,
	}

	classifier := NewLLMClassifier(prov, models.ModelID("test-model"))

	query := Query{
		Text: "refactor it",
		History: []string{
			"帮我写一个函数",
			"现在帮我优化它",
		},
	}

	result, err := classifier.Classify(context.Background(), query)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if result.Intent != IntentTask {
		t.Errorf("expected IntentTask, got %v", result.Intent)
	}

	if result.Complexity != ComplexityComplex {
		t.Errorf("expected ComplexityComplex, got %v", result.Complexity)
	}
}

func TestLLMClassifier_GetSupportedIntents(t *testing.T) {
	prov := &mockLLMProvider{
		responseContent: `{"intent":"task","domain":"development","complexity":"medium","urgency":"now","confidence":0.9}`,
	}

	classifier := NewLLMClassifier(prov, models.ModelID("test-model"))

	intents := classifier.GetSupportedIntents()
	if len(intents) == 0 {
		t.Error("expected non-empty intents list")
	}

	// Verify all expected intents are present
	expectedIntents := []Intent{
		IntentQuestion,
		IntentTask,
		IntentCreation,
		IntentAnalysis,
		IntentLearning,
		IntentPlanning,
		IntentConversation,
	}

	for _, expected := range expectedIntents {
		found := false
		for _, intent := range intents {
			if intent == expected {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("expected intent %v not found", expected)
		}
	}
}

func TestLLMClassifier_GetSupportedDomains(t *testing.T) {
	prov := &mockLLMProvider{
		responseContent: `{"intent":"task","domain":"development","complexity":"medium","urgency":"now","confidence":0.9}`,
	}

	classifier := NewLLMClassifier(prov, models.ModelID("test-model"))

	domains := classifier.GetSupportedDomains()
	if len(domains) == 0 {
		t.Error("expected non-empty domains list")
	}

	// Verify all expected domains are present
	expectedDomains := []DomainName{
		DomainGeneral,
		DomainDevelopment,
		DomainKnowledge,
		DomainCreative,
		DomainProductivity,
		DomainPersonal,
		DomainAnalytics,
		// DomainNutrition is not in baseline
	}

	for _, expected := range expectedDomains {
		found := false
		for _, domain := range domains {
			if domain == expected {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("expected domain %v not found", expected)
		}
	}
}

func TestParseLLMResponse_ValidJSON(t *testing.T) {
	content := `{"intent":"creation","domain":"creative","complexity":"simple","urgency":"eventually","confidence":0.95}`

	result, err := parseLLMResponse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if result.Intent != IntentCreation {
		t.Errorf("expected IntentCreation, got %v", result.Intent)
	}

	if result.Domain != DomainCreative {
		t.Errorf("expected DomainCreative, got %v", result.Domain)
	}

	if result.Complexity != ComplexitySimple {
		t.Errorf("expected ComplexitySimple, got %v", result.Complexity)
	}

	if result.Urgency != UrgencyEventually {
		t.Errorf("expected UrgencyEventually, got %v", result.Urgency)
	}

	if result.Confidence != 0.95 {
		t.Errorf("expected 0.95 confidence, got %f", result.Confidence)
	}
}

func TestParseLLMResponse_InvalidJSON(t *testing.T) {
	content := "not valid json at all"

	_, err := parseLLMResponse(content)
	if err == nil {
		t.Error("expected error for invalid JSON")
	}
}

func TestParseLLMResponse_EmptyContent(t *testing.T) {
	content := ""

	_, err := parseLLMResponse(content)
	if err == nil {
		t.Error("expected error for empty content")
	}
}

func TestParseLLMResponse_ExtraTextAroundJSON(t *testing.T) {
	content := "Here is the classification: {\"intent\":\"analysis\",\"domain\":\"knowledge\",\"complexity\":\"medium\",\"urgency\":\"now\",\"confidence\":0.8}\nThanks!"

	result, err := parseLLMResponse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if result.Intent != IntentAnalysis {
		t.Errorf("expected IntentAnalysis, got %v", result.Intent)
	}

	if result.Domain != DomainKnowledge {
		t.Errorf("expected DomainKnowledge, got %v", result.Domain)
	}
}

func TestClassifyIntent(t *testing.T) {
	tests := []struct {
		input    string
		expected Intent
	}{
		{"question", IntentQuestion},
		{"task", IntentTask},
		{"creation", IntentCreation},
		{"analysis", IntentAnalysis},
		{"learning", IntentLearning},
		{"planning", IntentPlanning},
		{"conversation", IntentConversation},
		{"unknown", IntentTask},      // default
		{"QUESTION", IntentQuestion}, // case insensitive
	}

	for _, tt := range tests {
		result := classifyIntent(tt.input)
		if result != tt.expected {
			t.Errorf("classifyIntent(%q) = %v, want %v", tt.input, result, tt.expected)
		}
	}
}

func TestClassifyDomain(t *testing.T) {
	tests := []struct {
		input    string
		expected DomainName
	}{
		{"general", DomainGeneral},
		{"development", DomainDevelopment},
		{"knowledge", DomainKnowledge},
		{"creative", DomainCreative},
		{"productivity", DomainProductivity},
		{"personal", DomainPersonal},
		{"analytics", DomainAnalytics},
		{"nutrition", DomainNutrition},
		{"unknown", DomainGeneral},         // default
		{"DEVELOPMENT", DomainDevelopment}, // case insensitive
	}

	for _, tt := range tests {
		result := classifyDomain(tt.input)
		if result != tt.expected {
			t.Errorf("classifyDomain(%q) = %v, want %v", tt.input, result, tt.expected)
		}
	}
}

func TestClassifyComplexity(t *testing.T) {
	tests := []struct {
		input    string
		expected ComplexityLevel
	}{
		{"simple", ComplexitySimple},
		{"medium", ComplexityMedium},
		{"complex", ComplexityComplex},
		{"unknown", ComplexityMedium}, // default
		{"SIMPLE", ComplexitySimple},  // case insensitive
	}

	for _, tt := range tests {
		result := classifyComplexity(tt.input)
		if result != tt.expected {
			t.Errorf("classifyComplexity(%q) = %v, want %v", tt.input, result, tt.expected)
		}
	}
}

func TestClassifyUrgency(t *testing.T) {
	tests := []struct {
		input    string
		expected UrgencyLevel
	}{
		{"now", UrgencyNow},
		{"soon", UrgencySoon},
		{"eventually", UrgencyEventually},
		{"unknown", UrgencyNow}, // default
		{"NOW", UrgencyNow},     // case insensitive
	}

	for _, tt := range tests {
		result := classifyUrgency(tt.input)
		if result != tt.expected {
			t.Errorf("classifyUrgency(%q) = %v, want %v", tt.input, result, tt.expected)
		}
	}
}

func TestSuggestTarget(t *testing.T) {
	tests := []struct {
		intent     Intent
		complexity ComplexityLevel
		expected   RoutingTarget
	}{
		{IntentTask, ComplexitySimple, TargetSkill},
		{IntentQuestion, ComplexityMedium, TargetAgency},
		{IntentTask, ComplexityMedium, TargetAgency},
		{IntentTask, ComplexityComplex, TargetAgency},
		{IntentAnalysis, ComplexityComplex, TargetAgency},
	}

	for _, tt := range tests {
		result := suggestTarget(tt.intent, tt.complexity)
		if result != tt.expected {
			t.Errorf("suggestTarget(%v, %v) = %v, want %v", tt.intent, tt.complexity, result, tt.expected)
		}
	}
}

func TestBuildUserPrompt(t *testing.T) {
	query := Query{
		Text:    "帮我写一个函数",
		History: []string{"Hello", "World"},
	}

	prompt := buildUserPrompt(query)

	expectedContains := []string{
		"Classify this query:",
		"帮我写一个函数",
		"History:",
		"- Hello",
		"- World",
	}

	for _, substr := range expectedContains {
		found := false
		for i := 0; i <= len(prompt)-len(substr); i++ {
			if prompt[i:i+len(substr)] == substr {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("buildUserPrompt() should contain %q, got:\n%s", substr, prompt)
		}
	}
}

func TestBuildUserPrompt_NoHistory(t *testing.T) {
	query := Query{
		Text: "what is go?",
	}

	prompt := buildUserPrompt(query)

	foundClassify := false
	foundQuery := false
	for i := 0; i <= len(prompt)-len("Classify this query:"); i++ {
		if prompt[i:i+len("Classify this query:")] == "Classify this query:" {
			foundClassify = true
			break
		}
	}
	for i := 0; i <= len(prompt)-len("what is go?"); i++ {
		if prompt[i:i+len("what is go?")] == "what is go?" {
			foundQuery = true
			break
		}
	}
	foundHistory := false
	for i := 0; i <= len(prompt)-len("History:"); i++ {
		if prompt[i:i+len("History:")] == "History:" {
			foundHistory = true
			break
		}
	}

	if !foundClassify {
		t.Errorf("buildUserPrompt() should contain 'Classify this query:', got:\n%s", prompt)
	}
	if !foundQuery {
		t.Errorf("buildUserPrompt() should contain query text, got:\n%s", prompt)
	}
	if foundHistory {
		t.Errorf("buildUserPrompt() should not contain 'History:' when no history, got:\n%s", prompt)
	}
}
