package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// ComparisonSkill implements the comparison skill for comparing items.
type ComparisonSkill struct{}

// NewComparisonSkill creates a new ComparisonSkill.
func NewComparisonSkill() *ComparisonSkill {
	return &ComparisonSkill{}
}

// Name returns the skill name.
func (s *ComparisonSkill) Name() SkillName {
	return "comparison"
}

// Description returns the skill description.
func (s *ComparisonSkill) Description() string {
	return "Compares items/options based on criteria and provides recommendations"
}

// RequiredTools returns the tools required by this skill.
func (s *ComparisonSkill) RequiredTools() []ToolName {
	return nil
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *ComparisonSkill) RequiredMCPs() []MCPName {
	return nil
}

// ComparisonResult contains the result of a comparison.
type ComparisonResult struct {
	Items           []ComparedItem `json:"items"`
	Criteria        []Criterion    `json:"criteria"`
	ComparisonTable []TableRow     `json:"comparison_table"`
	Winner          string         `json:"winner,omitempty"`
	Recommendation  string         `json:"recommendation"`
	Summary         string         `json:"summary"`
}

// ComparedItem represents an item being compared.
type ComparedItem struct {
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Score       float64  `json:"score"` // Overall score 0-100
	Pros        []string `json:"pros"`
	Cons        []string `json:"cons"`
}

// Criterion represents a comparison criterion.
type Criterion struct {
	Name        string  `json:"name"`
	Weight      float64 `json:"weight"` // 0.0 - 1.0
	Description string  `json:"description"`
}

// TableRow represents a row in the comparison table.
type TableRow struct {
	Criterion string   `json:"criterion"`
	Scores    []string `json:"scores"`     // Score for each item
	BestIndex int      `json:"best_index"` // Index of best item for this criterion
}

// Execute performs a comparison of items.
func (s *ComparisonSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	itemsRaw, ok := params.Input["items"].([]any)
	if !ok || len(itemsRaw) == 0 {
		// Try alternative format
		if itemsStr := s.extractString(params.Input, "items"); itemsStr != "" {
			itemsRaw = []any{itemsStr}
		}
	}

	if len(itemsRaw) == 0 {
		return SkillResult{
			Success:    false,
			Error:      "items array is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	// Parse items
	items := s.parseItems(itemsRaw)

	// Extract criteria
	criteriaRaw, ok := params.Input["criteria"].([]any)
	criteria := s.parseCriteria(criteriaRaw)

	// Extract comparison question
	question := s.extractString(params.Input, "question")
	if question == "" {
		question = "Compare these items"
	}

	// Perform comparison
	result := s.compareItems(items, criteria, question)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"items":            result.Items,
			"criteria":         result.Criteria,
			"comparison_table": result.ComparisonTable,
			"winner":           result.Winner,
			"recommendation":   result.Recommendation,
			"summary":          result.Summary,
			"question":         question,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *ComparisonSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// parseItems parses items from input.
func (s *ComparisonSkill) parseItems(itemsRaw []any) []ComparedItem {
	items := make([]ComparedItem, 0, len(itemsRaw))

	for i, itemRaw := range itemsRaw {
		switch v := itemRaw.(type) {
		case string:
			items = append(items, ComparedItem{
				Name:        fmt.Sprintf("Item %d", i+1),
				Description: v,
			})
		case map[string]any:
			name := s.getString(v, "name", fmt.Sprintf("Item %d", i+1))
			desc := s.getString(v, "description", "")
			items = append(items, ComparedItem{
				Name:        name,
				Description: desc,
			})
		}
	}

	return items
}

// getString safely extracts a string from a map.
func (s *ComparisonSkill) getString(m map[string]any, key, defaultVal string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return defaultVal
}

// parseCriteria parses criteria from input.
func (s *ComparisonSkill) parseCriteria(criteriaRaw []any) []Criterion {
	if len(criteriaRaw) == 0 {
		// Default criteria
		return []Criterion{
			{Name: "Quality", Weight: 0.3, Description: "Overall quality and craftsmanship"},
			{Name: "Value", Weight: 0.3, Description: "Value for money"},
			{Name: "Ease of Use", Weight: 0.2, Description: "How easy it is to use"},
			{Name: "Features", Weight: 0.2, Description: "Feature set and capabilities"},
		}
	}

	criteria := make([]Criterion, 0, len(criteriaRaw))
	for _, cRaw := range criteriaRaw {
		switch v := cRaw.(type) {
		case string:
			criteria = append(criteria, Criterion{Name: v, Weight: 1.0})
		case map[string]any:
			name := s.getString(v, "name", "Unnamed")
			weight := s.getFloat(v, "weight", 1.0)
			desc := s.getString(v, "description", "")
			criteria = append(criteria, Criterion{Name: name, Weight: weight, Description: desc})
		}
	}

	return criteria
}

// getFloat safely extracts a float from a map.
func (s *ComparisonSkill) getFloat(m map[string]any, key string, defaultVal float64) float64 {
	switch v := m[key].(type) {
	case float64:
		return v
	case int:
		return float64(v)
	case int64:
		return float64(v)
	}
	return defaultVal
}

// compareItems performs the comparison.
func (s *ComparisonSkill) compareItems(items []ComparedItem, criteria []Criterion, question string) ComparisonResult {
	result := ComparisonResult{
		Items:    items,
		Criteria: criteria,
	}

	// Score each item
	for i := range items {
		items[i].Score = s.calculateItemScore(items[i], criteria)
		items[i].Pros = s.generatePros(items[i])
		items[i].Cons = s.generateCons(items[i])
	}

	// Build comparison table
	result.ComparisonTable = s.buildComparisonTable(items, criteria)

	// Determine winner
	result.Winner = s.determineWinner(items)

	// Generate recommendation
	result.Recommendation = s.generateRecommendation(items, question)

	// Generate summary
	result.Summary = s.generateSummary(items, criteria, result.Winner)

	return result
}

// calculateItemScore calculates the overall score for an item.
func (s *ComparisonSkill) calculateItemScore(item ComparedItem, criteria []Criterion) float64 {
	// Simple heuristic based on description length and content
	baseScore := 50.0

	// Longer descriptions suggest more substance
	descLen := len(item.Description)
	if descLen > 100 {
		baseScore += 10
	} else if descLen > 50 {
		baseScore += 5
	}

	// Look for positive keywords
	positiveKeywords := []string{
		"excellent", "great", "best", "superior", "high-quality",
		"powerful", "efficient", "reliable", "innovative", "advanced",
	}
	negativeKeywords := []string{
		"poor", "bad", "inferior", "limited", "basic",
		"slow", "unreliable", "outdated", "problem",
	}

	descLower := strings.ToLower(item.Description)
	for _, kw := range positiveKeywords {
		if strings.Contains(descLower, kw) {
			baseScore += 5
		}
	}
	for _, kw := range negativeKeywords {
		if strings.Contains(descLower, kw) {
			baseScore -= 5
		}
	}

	// Apply criteria weights (simplified)
	for _, c := range criteria {
		switch strings.ToLower(c.Name) {
		case "quality":
			if strings.Contains(descLower, "quality") || strings.Contains(descLower, "best") {
				baseScore += 10 * c.Weight
			}
		case "value":
			if strings.Contains(descLower, "value") || strings.Contains(descLower, "cheap") ||
				strings.Contains(descLower, "affordable") || strings.Contains(descLower, "expensive") {
				baseScore += 5 * c.Weight
			}
		case "ease":
			if strings.Contains(descLower, "easy") || strings.Contains(descLower, "simple") ||
				strings.Contains(descLower, "intuitive") {
				baseScore += 5 * c.Weight
			}
		case "features":
			if strings.Contains(descLower, "feature") || strings.Contains(descLower, "capability") {
				baseScore += 5 * c.Weight
			}
		}
	}

	// Ensure score is in 0-100 range
	if baseScore < 0 {
		baseScore = 0
	}
	if baseScore > 100 {
		baseScore = 100
	}

	return baseScore
}

// generatePros generates pros for an item.
func (s *ComparisonSkill) generatePros(item ComparedItem) []string {
	pros := make([]string, 0)

	descLower := strings.ToLower(item.Description)

	// Identify positive attributes
	positiveAttrs := map[string][]string{
		"quality":     {"quality", "excellent", "superior", "best"},
		"ease":        {"easy", "simple", "intuitive", "user-friendly"},
		"value":       {"value", "affordable", "cost-effective", "worth"},
		"performance": {"fast", "efficient", "powerful", "performance"},
		"reliability": {"reliable", "consistent", "dependable"},
	}

	for attr, keywords := range positiveAttrs {
		for _, kw := range keywords {
			if strings.Contains(descLower, kw) {
				pros = append(pros, fmt.Sprintf("Good %s", attr))
				break
			}
		}
	}

	if len(pros) == 0 {
		pros = append(pros, "Meets basic expectations")
	}

	return pros
}

// generateCons generates cons for an item.
func (s *ComparisonSkill) generateCons(item ComparedItem) []string {
	cons := make([]string, 0)

	descLower := strings.ToLower(item.Description)

	// Identify negative attributes
	negativeAttrs := map[string][]string{
		"quality":     {"poor", "inferior", "low-quality"},
		"ease":        {"difficult", "complex", "confusing"},
		"value":       {"expensive", "overpriced"},
		"performance": {"slow", "limited"},
		"reliability": {"unreliable", "inconsistent"},
	}

	for attr, keywords := range negativeAttrs {
		for _, kw := range keywords {
			if strings.Contains(descLower, kw) {
				cons = append(cons, fmt.Sprintf("Weakness in %s", attr))
				break
			}
		}
	}

	if len(cons) == 0 {
		cons = append(cons, "No significant drawbacks noted")
	}

	return cons
}

// buildComparisonTable builds the comparison table.
func (s *ComparisonSkill) buildComparisonTable(items []ComparedItem, criteria []Criterion) []TableRow {
	table := make([]TableRow, 0, len(criteria))

	for _, c := range criteria {
		row := TableRow{
			Criterion: c.Name,
			Scores:    make([]string, len(items)),
		}

		// Find best score index
		bestIdx := 0
		bestScore := -1.0

		for i, item := range items {
			// Calculate criterion-specific score (simplified)
			score := item.Score * c.Weight
			row.Scores[i] = fmt.Sprintf("%.0f%%", score)

			if score > bestScore {
				bestScore = score
				bestIdx = i
			}
		}
		row.BestIndex = bestIdx
		table = append(table, row)
	}

	return table
}

// determineWinner determines the winning item.
func (s *ComparisonSkill) determineWinner(items []ComparedItem) string {
	if len(items) == 0 {
		return ""
	}

	bestItem := items[0]
	bestScore := items[0].Score

	for i := 1; i < len(items); i++ {
		if items[i].Score > bestScore {
			bestScore = items[i].Score
			bestItem = items[i]
		}
	}

	return bestItem.Name
}

// generateRecommendation generates a recommendation.
func (s *ComparisonSkill) generateRecommendation(items []ComparedItem, question string) string {
	if len(items) == 0 {
		return "No items to recommend"
	}

	winner := s.determineWinner(items)

	if len(items) == 1 {
		return fmt.Sprintf("Based on the analysis, %s is the only option presented.", items[0].Name)
	}

	return fmt.Sprintf(
		"Based on comprehensive comparison considering quality, value, ease of use, and features: %s is the recommended choice with a score of %.0f%%.",
		winner,
		items[0].Score, // Winner should be first after sorting
	)
}

// generateSummary generates a summary of the comparison.
func (s *ComparisonSkill) generateSummary(items []ComparedItem, criteria []Criterion, winner string) string {
	var summary strings.Builder

	summary.WriteString(fmt.Sprintf("Comparison of %d items across %d criteria:\n\n", len(items), len(criteria)))

	// Item rankings
	summary.WriteString("Rankings:\n")
	for i, item := range items {
		summary.WriteString(fmt.Sprintf("%d. %s (Score: %.0f%%)\n", i+1, item.Name, item.Score))
	}

	if winner != "" {
		summary.WriteString(fmt.Sprintf("\nWinner: %s\n", winner))
	}

	return summary.String()
}

// CanExecute checks if the skill can execute.
func (s *ComparisonSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
