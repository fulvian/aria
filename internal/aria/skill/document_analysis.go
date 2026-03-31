package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// DocumentAnalysisSkill implements the document analysis skill.
type DocumentAnalysisSkill struct{}

// NewDocumentAnalysisSkill creates a new DocumentAnalysisSkill.
func NewDocumentAnalysisSkill() *DocumentAnalysisSkill {
	return &DocumentAnalysisSkill{}
}

// Name returns the skill name.
func (s *DocumentAnalysisSkill) Name() SkillName {
	return SkillDocAnalysis
}

// Description returns the skill description.
func (s *DocumentAnalysisSkill) Description() string {
	return "Analyzes documents to extract key points, entities, and summaries"
}

// RequiredTools returns the tools required by this skill.
func (s *DocumentAnalysisSkill) RequiredTools() []ToolName {
	return nil // Would require file read tools in a full implementation
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *DocumentAnalysisSkill) RequiredMCPs() []MCPName {
	return nil
}

// AnalysisMode represents the mode of document analysis.
type AnalysisMode string

const (
	ModeExtract   AnalysisMode = "extract"   // Extract key information
	ModeSummarize AnalysisMode = "summarize" // Summarize content
	ModeQA        AnalysisMode = "qa"        // Question answering
	ModeFull      AnalysisMode = "full"      // Full analysis
)

// DocumentAnalysisResult contains the result of document analysis.
type DocumentAnalysisResult struct {
	Summary   string   `json:"summary"`
	KeyPoints []string `json:"key_points"`
	Entities  []Entity `json:"entities"`
	Questions []QAPair `json:"questions,omitempty"`
	Mode      string   `json:"mode"`
	WordCount int      `json:"word_count"`
	ReadTime  string   `json:"read_time"`
	Topics    []string `json:"topics"`
	Sentiment string   `json:"sentiment,omitempty"`
}

// Entity represents a named entity found in the document.
type Entity struct {
	Text  string `json:"text"`
	Type  string `json:"type"`  // person, organization, location, date, etc.
	Count int    `json:"count"` // frequency in document
}

// QAPair represents a question-answer pair.
type QAPair struct {
	Question string `json:"question"`
	Answer   string `json:"answer"`
}

// Execute performs document analysis.
func (s *DocumentAnalysisSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	content := s.extractString(params.Input, "content")
	documentPath := s.extractString(params.Input, "document_path")

	if content == "" && documentPath == "" {
		content = s.extractString(params.Context, "content")
	}

	if content == "" && documentPath == "" {
		return SkillResult{
			Success:    false,
			Error:      "content or document_path is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	mode := s.extractString(params.Input, "mode")
	if mode == "" {
		mode = "full"
	}

	// Analyze the document
	result := s.analyzeDocument(content, mode)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"summary":    result.Summary,
			"key_points": result.KeyPoints,
			"entities":   result.Entities,
			"questions":  result.Questions,
			"mode":       result.Mode,
			"word_count": result.WordCount,
			"read_time":  result.ReadTime,
			"topics":     result.Topics,
			"sentiment":  result.Sentiment,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *DocumentAnalysisSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// analyzeDocument performs comprehensive document analysis.
func (s *DocumentAnalysisSkill) analyzeDocument(content string, mode string) DocumentAnalysisResult {
	result := DocumentAnalysisResult{
		Mode: mode,
	}

	// Calculate basic stats
	words := strings.Fields(content)
	result.WordCount = len(words)
	result.ReadTime = calculateReadTime(len(words))

	// Extract topics
	result.Topics = s.extractTopics(content)

	// Extract key points
	result.KeyPoints = s.extractKeyPoints(content)

	// Extract entities
	result.Entities = s.extractEntities(content)

	// Generate summary based on mode
	switch mode {
	case "extract":
		result.Summary = s.extractSummary(content)
	case "summarize":
		result.Summary = s.generateSummary(content)
	case "qa":
		result.Summary = s.generateSummary(content)
		result.Questions = s.generateQuestions(content)
	case "full":
		result.Summary = s.generateSummary(content)
		result.Sentiment = s.analyzeSentiment(content)
	default:
		result.Summary = s.generateSummary(content)
	}

	return result
}

// calculateReadTime estimates reading time.
func calculateReadTime(wordCount int) string {
	// Average reading speed: 200 words per minute
	minutes := wordCount / 200
	if minutes < 1 {
		return "< 1 min read"
	}
	return fmt.Sprintf("%d min read", minutes)
}

// extractTopics identifies main topics in the content.
func (s *DocumentAnalysisSkill) extractTopics(content string) []string {
	topics := make([]string, 0)

	// Common topic indicators
	topicIndicators := map[string][]string{
		"technology":  {"software", "computer", "digital", "data", "system", "network", "ai", "ml", "machine learning"},
		"science":     {"research", "study", "experiment", "hypothesis", "theory", "scientific", "physics", "biology"},
		"business":    {"company", "market", "revenue", "customer", "product", "strategy", "growth", "profit"},
		"health":      {"health", "medical", "patient", "treatment", "disease", "doctor", "hospital", "clinical"},
		"education":   {"learning", "student", "teacher", "education", "course", "school", "university", "study"},
		"politics":    {"government", "policy", "law", "election", "vote", "political", "congress", "parliament"},
		"environment": {"climate", "environment", "sustainable", "energy", "carbon", "green", "pollution"},
		"finance":     {"investment", "stock", "market", "financial", "bank", "economy", "trading"},
	}

	contentLower := strings.ToLower(content)

	for topic, keywords := range topicIndicators {
		for _, keyword := range keywords {
			if strings.Contains(contentLower, keyword) {
				if !containsString(topics, topic) {
					topics = append(topics, topic)
				}
			}
		}
	}

	if len(topics) == 0 {
		topics = append(topics, "general")
	}

	return topics
}

// containsString checks if a string slice contains an element.
func containsString(slice []string, str string) bool {
	for _, s := range slice {
		if s == str {
			return true
		}
	}
	return false
}

// extractKeyPoints extracts key points from content.
func (s *DocumentAnalysisSkill) extractKeyPoints(content string) []string {
	keyPoints := make([]string, 0)

	// Look for sentences that:
	// 1. Are at the beginning (thesis statements)
	// 2. Contain key indicator words
	// 3. Are in list-like structures

	sentences := splitIntoSentences(content)

	keyIndicators := []string{
		"important", "key", "main", "primary", "essential",
		"significant", "crucial", "major", "notable", "fundamental",
		"conclusion", "finding", "result", "discovered", "showed",
	}

	for i, sent := range sentences {
		sentLower := strings.ToLower(sent)

		// Check for key indicators
		for _, indicator := range keyIndicators {
			if strings.Contains(sentLower, indicator) && len(sent) > 30 {
				if !containsString(keyPoints, sent) {
					keyPoints = append(keyPoints, sent)
				}
			}
		}

		// Also add first and last significant sentences
		if i == 0 && len(sent) > 30 {
			keyPoints = append(keyPoints, sent)
		}
		if i == len(sentences)-1 && len(sent) > 30 {
			keyPoints = append(keyPoints, sent)
		}
	}

	// Deduplicate and limit
	uniquePoints := make([]string, 0)
	seen := make(map[string]bool)
	for _, point := range keyPoints {
		normalized := strings.ToLower(strings.TrimSpace(point))
		if !seen[normalized] && len(normalized) > 20 {
			seen[normalized] = true
			uniquePoints = append(uniquePoints, point)
		}
	}

	if len(uniquePoints) > 7 {
		uniquePoints = uniquePoints[:7]
	}

	return uniquePoints
}

// splitIntoSentences splits text into sentences.
func splitIntoSentences(content string) []string {
	sentences := strings.FieldsFunc(content, func(r rune) bool {
		return r == '.' || r == '!' || r == '?'
	})

	result := make([]string, 0, len(sentences))
	for _, s := range sentences {
		s = strings.TrimSpace(s)
		if len(s) > 10 {
			result = append(result, s+".")
		}
	}

	return result
}

// extractEntities extracts named entities from content.
func (s *DocumentAnalysisSkill) extractEntities(content string) []Entity {
	entities := make([]Entity, 0)

	// Simple entity extraction based on capitalization and common patterns
	words := strings.Fields(content)

	// Extract capitalized phrases (potential organizations)
	for i := 0; i < len(words); i++ {
		word := words[i]
		// Check if capitalized (potential proper noun)
		if len(word) > 1 && word[0] >= 'A' && word[0] <= 'Z' {
			// Collect potential multi-word entity
			entity := word
			for j := i + 1; j < len(words) && j < i+3; j++ {
				nextWord := words[j]
				if len(nextWord) > 1 && nextWord[0] >= 'A' && nextWord[0] <= 'Z' {
					entity += " " + nextWord
					i = j
				} else {
					break
				}
			}

			// Add if not already present and meaningful length
			if len(entity) > 2 && !containsEntity(entities, entity) {
				entities = append(entities, Entity{
					Text:  entity,
					Type:  "organization", // Simplified - would need NER for accuracy
					Count: 1,
				})
			}
		}
	}

	// Extract dates (simple pattern)
	datePatterns := []string{
		"January", "February", "March", "April", "May", "June",
		"July", "August", "September", "October", "November", "December",
		"Jan ", "Feb ", "Mar ", "Apr ", "Jun ", "Jul ", "Aug ", "Sep ", "Oct ", "Nov ", "Dec ",
	}

	for _, pattern := range datePatterns {
		if strings.Contains(content, pattern) {
			entities = append(entities, Entity{
				Text:  "Date reference",
				Type:  "date",
				Count: strings.Count(content, pattern),
			})
			break
		}
	}

	// Extract numbers (quantities, percentages)
	if strings.Contains(content, "%") {
		entities = append(entities, Entity{
			Text:  "Percentage",
			Type:  "number",
			Count: strings.Count(content, "%"),
		})
	}

	// Limit to top entities
	if len(entities) > 10 {
		entities = entities[:10]
	}

	return entities
}

// containsEntity checks if an entity already exists in the list.
func containsEntity(entities []Entity, text string) bool {
	for _, e := range entities {
		if e.Text == text {
			return true
		}
	}
	return false
}

// extractSummary extracts a brief summary.
func (s *DocumentAnalysisSkill) extractSummary(content string) string {
	sentences := splitIntoSentences(content)
	if len(sentences) == 0 {
		return "No content to summarize."
	}

	// Return first 2 sentences
	if len(sentences) >= 2 {
		return sentences[0] + " " + sentences[1]
	}
	return sentences[0]
}

// generateSummary generates a comprehensive summary.
func (s *DocumentAnalysisSkill) generateSummary(content string) string {
	sentences := splitIntoSentences(content)
	if len(sentences) == 0 {
		return "No content to summarize."
	}

	// Build summary from key sentences
	var summary strings.Builder

	// Introduction (first 1-2 sentences)
	if len(sentences) > 0 {
		summary.WriteString(sentences[0])
		if len(sentences) > 1 {
			summary.WriteString(" ")
			summary.WriteString(sentences[1])
		}
		summary.WriteString("\n\n")
	}

	// Main points (sentences with key indicators)
	keyIndicators := []string{"important", "key", "main", "significant", "found", "showed"}
	pointCount := 0
	for _, sent := range sentences[2:] {
		if pointCount >= 3 {
			break
		}
		sentLower := strings.ToLower(sent)
		for _, indicator := range keyIndicators {
			if strings.Contains(sentLower, indicator) {
				summary.WriteString("- ")
				summary.WriteString(sent)
				summary.WriteString("\n")
				pointCount++
				break
			}
		}
	}

	return summary.String()
}

// generateQuestions generates Q&A pairs from content.
func (s *DocumentAnalysisSkill) generateQuestions(content string) []QAPair {
	questions := make([]QAPair, 0)

	sentences := splitIntoSentences(content)
	if len(sentences) < 2 {
		return questions
	}

	// Generate simple question patterns based on sentence content
	for i, sent := range sentences {
		if i >= 5 {
			break
		}

		// Skip very short sentences
		if len(sent) < 20 {
			continue
		}

		// Simple question generation based on sentence patterns
		if strings.Contains(strings.ToLower(sent), "is") {
			questions = append(questions, QAPair{
				Question: "What is the main point about " + extractSubject(sent) + "?",
				Answer:   sent,
			})
		}
	}

	return questions
}

// extractSubject extracts a simplified subject from a sentence.
func extractSubject(sentence string) string {
	words := strings.Fields(sentence)
	if len(words) < 2 {
		return "the topic"
	}

	// Return second word as simplified subject (after "This/The/It")
	skipWords := map[string]bool{
		"this": true, "the": true, "it": true, "that": true,
		"these": true, "those": true, "a": true, "an": true,
	}

	for i, word := range words {
		if i > 0 && !skipWords[strings.ToLower(word)] {
			// Capitalize first letter
			if len(word) > 0 {
				return strings.ToUpper(string(word[0])) + word[1:]
			}
			return word
		}
	}

	return "the topic"
}

// analyzeSentiment performs simple sentiment analysis.
func (s *DocumentAnalysisSkill) analyzeSentiment(content string) string {
	contentLower := strings.ToLower(content)

	positiveWords := []string{
		"good", "great", "excellent", "positive", "success", "successful",
		"improve", "improved", "benefit", "beneficial", "happy", "satisfied",
		"effective", "efficient", "advance", "progress", "growth", "innovative",
	}

	negativeWords := []string{
		"bad", "poor", "negative", "failure", "fail", "failed", "problem",
		"issue", "difficult", "challenge", "decline", "decreased", "worse",
		"concern", "concerning", "risk", "threat", "harmful", "loss",
	}

	positiveCount := 0
	negativeCount := 0

	for _, word := range positiveWords {
		positiveCount += strings.Count(contentLower, word)
	}

	for _, word := range negativeWords {
		negativeCount += strings.Count(contentLower, word)
	}

	if positiveCount > negativeCount*2 {
		return "positive"
	}
	if negativeCount > positiveCount*2 {
		return "negative"
	}
	if positiveCount > negativeCount {
		return "mostly positive"
	}
	if negativeCount > positiveCount {
		return "mostly negative"
	}

	return "neutral"
}

// CanExecute checks if the skill can execute.
func (s *DocumentAnalysisSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
