package skill

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// DataAnalysisSkill implements the data analysis skill for analyzing datasets.
type DataAnalysisSkill struct{}

// NewDataAnalysisSkill creates a new DataAnalysisSkill.
func NewDataAnalysisSkill() *DataAnalysisSkill {
	return &DataAnalysisSkill{}
}

// Name returns the skill name.
func (s *DataAnalysisSkill) Name() SkillName {
	return SkillDataAnalysis
}

// Description returns the skill description.
func (s *DataAnalysisSkill) Description() string {
	return "Analyzes datasets to find patterns, trends, and insights"
}

// RequiredTools returns the tools required by this skill.
func (s *DataAnalysisSkill) RequiredTools() []ToolName {
	return nil
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *DataAnalysisSkill) RequiredMCPs() []MCPName {
	return nil
}

// DataAnalysisResult contains the result of data analysis.
type DataAnalysisResult struct {
	Findings   []Finding  `json:"findings"`
	Patterns   []Pattern  `json:"patterns"`
	Statistics Statistics `json:"statistics"`
	Confidence float64    `json:"confidence"`
	Summary    string     `json:"summary"`
}

// Finding represents a key finding from the analysis.
type Finding struct {
	Statement string `json:"statement"`
	Evidence  string `json:"evidence"`
	Relevance string `json:"relevance"` // high, medium, low
}

// Pattern represents a detected pattern.
type Pattern struct {
	Type        string  `json:"type"` // trend, correlation, anomaly, distribution
	Description string  `json:"description"`
	Direction   string  `json:"direction"` // increasing, decreasing, stable, cyclic
	Strength    float64 `json:"strength"`  // 0.0 - 1.0
}

// Statistics contains basic statistics about the data.
type Statistics struct {
	RowCount    int     `json:"row_count"`
	ColumnCount int     `json:"column_count"`
	NumericCols int     `json:"numeric_columns"`
	TextCols    int     `json:"text_columns"`
	MissingData float64 `json:"missing_data_pct"`
}

// Execute performs data analysis on a dataset.
func (s *DataAnalysisSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	dataset := s.extractString(params.Input, "dataset")
	if dataset == "" {
		dataset = s.extractString(params.Input, "data")
	}
	if dataset == "" {
		return SkillResult{
			Success:    false,
			Error:      "dataset is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	question := s.extractString(params.Input, "question")
	if question == "" {
		question = "What are the key insights from this data?"
	}

	// Analyze the data
	result := s.analyzeData(dataset, question)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"findings":   result.Findings,
			"patterns":   result.Patterns,
			"statistics": result.Statistics,
			"confidence": result.Confidence,
			"summary":    result.Summary,
			"question":   question,
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// extractString extracts a string from a map.
func (s *DataAnalysisSkill) extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// analyzeData performs comprehensive data analysis.
func (s *DataAnalysisSkill) analyzeData(dataset string, question string) DataAnalysisResult {
	result := DataAnalysisResult{
		Findings:   make([]Finding, 0),
		Patterns:   make([]Pattern, 0),
		Statistics: s.calculateStatistics(dataset),
	}

	// Detect patterns
	result.Patterns = s.detectPatterns(dataset)

	// Generate findings based on patterns and question
	result.Findings = s.generateFindings(dataset, question, result.Patterns)

	// Calculate confidence based on data quality and patterns found
	result.Confidence = s.calculateConfidence(dataset, result.Patterns)

	// Generate summary
	result.Summary = s.generateSummary(result.Findings, result.Patterns, result.Confidence)

	return result
}

// calculateStatistics calculates basic statistics about the dataset.
func (s *DataAnalysisSkill) calculateStatistics(dataset string) Statistics {
	stats := Statistics{}

	// Count rows and columns based on newlines and delimiters
	lines := strings.Split(dataset, "\n")
	stats.RowCount = len(lines)

	if stats.RowCount > 0 {
		// Estimate column count from first line
		firstLine := lines[0]
		if strings.Contains(firstLine, "\t") {
			stats.ColumnCount = len(strings.Split(firstLine, "\t"))
		} else if strings.Contains(firstLine, ",") {
			stats.ColumnCount = len(strings.Split(firstLine, ","))
		} else if strings.Contains(firstLine, ";") {
			stats.ColumnCount = len(strings.Split(firstLine, ";"))
		} else {
			stats.ColumnCount = 1
		}
	}

	// Count numeric vs text columns
	for _, line := range lines {
		if strings.HasPrefix(line, "#") || strings.HasPrefix(line, "//") {
			continue // Skip comments
		}

		fields := s.splitLine(line)
		for _, field := range fields {
			field = strings.TrimSpace(field)
			if s.isNumeric(field) {
				stats.NumericCols++
			} else if len(field) > 0 {
				stats.TextCols++
			}
		}
	}

	// Estimate missing data
	nonEmpty := 0
	total := stats.RowCount * stats.ColumnCount
	for _, line := range lines {
		if len(strings.TrimSpace(line)) > 0 {
			nonEmpty++
		}
	}
	if total > 0 {
		stats.MissingData = float64(total-nonEmpty) / float64(total) * 100
	}

	return stats
}

// splitLine splits a line by common delimiters.
func (s *DataAnalysisSkill) splitLine(line string) []string {
	if strings.Contains(line, "\t") {
		return strings.Split(line, "\t")
	}
	if strings.Contains(line, ",") {
		return strings.Split(line, ",")
	}
	if strings.Contains(line, ";") {
		return strings.Split(line, ";")
	}
	return strings.Fields(line)
}

// isNumeric checks if a string represents a numeric value.
func (s *DataAnalysisSkill) isNumeric(str string) bool {
	str = strings.TrimSpace(str)
	// Remove common prefixes/suffixes
	str = strings.TrimPrefix(str, "$")
	str = strings.TrimPrefix(str, "€")
	str = strings.TrimPrefix(str, "£")
	str = strings.TrimPrefix(str, "%")
	str = strings.TrimSuffix(str, "%")

	// Check if numeric
	_, err := strconv.ParseFloat(str, 64)
	return err == nil
}

// detectPatterns detects patterns in the dataset.
func (s *DataAnalysisSkill) detectPatterns(dataset string) []Pattern {
	patterns := make([]Pattern, 0)

	lines := strings.Split(dataset, "\n")
	if len(lines) < 3 {
		return patterns
	}

	// Look for numeric sequences
	numericValues := make([]float64, 0)
	for _, line := range lines {
		fields := s.splitLine(line)
		for _, field := range fields {
			field = strings.TrimSpace(field)
			if val, err := strconv.ParseFloat(field, 64); err == nil {
				numericValues = append(numericValues, val)
			}
		}
	}

	if len(numericValues) >= 3 {
		// Detect trend
		trend := s.detectTrend(numericValues)
		if trend != "" {
			patterns = append(patterns, Pattern{
				Type:        "trend",
				Description: fmt.Sprintf("A %s trend detected in numeric values", trend),
				Direction:   trend,
				Strength:    s.calculateTrendStrength(numericValues),
			})
		}

		// Detect anomalies (values far from mean)
		anomalies := s.detectAnomalies(numericValues)
		if len(anomalies) > 0 {
			patterns = append(patterns, Pattern{
				Type:        "anomaly",
				Description: fmt.Sprintf("%d outlier(s) detected in the data", len(anomalies)),
				Direction:   "varies",
				Strength:    float64(len(anomalies)) / float64(len(numericValues)),
			})
		}
	}

	// Look for correlation patterns in structured data
	if len(lines) >= 2 {
		header := lines[0]
		if strings.Contains(header, " vs ") || strings.Contains(header, " vs. ") {
			patterns = append(patterns, Pattern{
				Type:        "correlation",
				Description: "Comparative data structure detected",
				Direction:   "comparison",
				Strength:    0.7,
			})
		}
	}

	// Detect distribution patterns
	if len(numericValues) > 0 {
		distribution := s.analyzeDistribution(numericValues)
		if distribution != "" {
			patterns = append(patterns, Pattern{
				Type:        "distribution",
				Description: fmt.Sprintf("Data shows %s distribution", distribution),
				Direction:   distribution,
				Strength:    0.6,
			})
		}
	}

	return patterns
}

// detectTrend detects if there's an increasing or decreasing trend.
func (s *DataAnalysisSkill) detectTrend(values []float64) string {
	if len(values) < 3 {
		return ""
	}

	// Simple linear regression slope
	sumX := 0.0
	sumY := 0.0
	sumXY := 0.0
	sumX2 := 0.0

	for i, v := range values {
		sumX += float64(i)
		sumY += v
		sumXY += float64(i) * v
		sumX2 += float64(i) * float64(i)
	}

	n := float64(len(values))
	slope := (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)

	// Determine trend direction
	if slope > 0.1 {
		return "increasing"
	}
	if slope < -0.1 {
		return "decreasing"
	}
	return "stable"
}

// calculateTrendStrength calculates the strength of a trend.
func (s *DataAnalysisSkill) calculateTrendStrength(values []float64) float64 {
	if len(values) < 3 {
		return 0
	}

	// Calculate coefficient of variation for trend
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	mean := sum / float64(len(values))

	// Calculate how much values deviate from mean over time
	variance := 0.0
	for i, v := range values {
		expected := mean + float64(i-len(values)/2)*(values[len(values)-1]-values[0])/float64(len(values)-1)
		variance += (v - expected) * (v - expected)
	}
	variance /= float64(len(values))

	// Return strength as inverse of normalized variance
	strength := 1.0 - (variance / (mean*mean + 1))
	if strength < 0 {
		strength = 0
	}
	if strength > 1 {
		strength = 1
	}

	return strength
}

// detectAnomalies detects outliers in numeric values.
func (s *DataAnalysisSkill) detectAnomalies(values []float64) []float64 {
	if len(values) < 3 {
		return nil
	}

	// Calculate mean and standard deviation
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	mean := sum / float64(len(values))

	variance := 0.0
	for _, v := range values {
		variance += (v - mean) * (v - mean)
	}
	variance /= float64(len(values))
	stdDev := variance

	if stdDev == 0 {
		return nil
	}

	// Find values more than 2 standard deviations from mean
	anomalies := make([]float64, 0)
	for _, v := range values {
		if (v-mean)*(v-mean) > 4*stdDev*stdDev {
			anomalies = append(anomalies, v)
		}
	}

	return anomalies
}

// analyzeDistribution determines the distribution type.
func (s *DataAnalysisSkill) analyzeDistribution(values []float64) string {
	if len(values) < 3 {
		return ""
	}

	// Calculate skewness (simple version)
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	mean := sum / float64(len(values))

	variance := 0.0
	for _, v := range values {
		variance += (v - mean) * (v - mean)
	}
	variance /= float64(len(values))
	stdDev := variance

	if stdDev == 0 {
		return "uniform"
	}

	// Calculate skewness
	skewness := 0.0
	for _, v := range values {
		skewness += (v - mean) * (v - mean) * (v - mean)
	}
	skewness /= float64(len(values)) * stdDev * stdDev * stdDev

	if skewness > 0.5 {
		return "right-skewed"
	}
	if skewness < -0.5 {
		return "left-skewed"
	}

	return "approximately normal"
}

// generateFindings generates key findings based on analysis.
func (s *DataAnalysisSkill) generateFindings(dataset string, question string, patterns []Pattern) []Finding {
	findings := make([]Finding, 0)

	// Generate findings based on patterns
	for _, p := range patterns {
		switch p.Type {
		case "trend":
			findings = append(findings, Finding{
				Statement: fmt.Sprintf("A %s trend is observed in the data with %.0f%% confidence", p.Direction, p.Strength*100),
				Evidence:  "Statistical analysis of numeric values",
				Relevance: "high",
			})
		case "anomaly":
			findings = append(findings, Finding{
				Statement: fmt.Sprintf("Outliers detected that deviate significantly from the norm"),
				Evidence:  p.Description,
				Relevance: "medium",
			})
		case "distribution":
			findings = append(findings, Finding{
				Statement: fmt.Sprintf("Data follows a %s distribution pattern", p.Direction),
				Evidence:  "Distribution analysis",
				Relevance: "medium",
			})
		case "correlation":
			findings = append(findings, Finding{
				Statement: "The data structure suggests comparative analysis is possible",
				Evidence:  "Structured multi-column format detected",
				Relevance: "high",
			})
		}
	}

	// Generate findings based on statistics
	stats := s.calculateStatistics(dataset)
	if stats.MissingData > 10 {
		findings = append(findings, Finding{
			Statement: fmt.Sprintf("Data quality concern: %.1f%% of cells appear to be missing", stats.MissingData),
			Evidence:  "Analysis of empty vs non-empty cells",
			Relevance: "high",
		})
	}

	// Add general insight based on question
	if strings.Contains(strings.ToLower(question), "key") ||
		strings.Contains(strings.ToLower(question), "insight") {
		if len(patterns) > 0 {
			findings = append(findings, Finding{
				Statement: fmt.Sprintf("The most significant pattern is: %s", patterns[0].Description),
				Evidence:  "Pattern with highest strength",
				Relevance: "high",
			})
		}
	}

	return findings
}

// calculateConfidence calculates confidence in the analysis results.
func (s *DataAnalysisSkill) calculateConfidence(dataset string, patterns []Pattern) float64 {
	confidence := 0.5 // Base confidence

	stats := s.calculateStatistics(dataset)

	// Increase confidence based on data quality
	if stats.MissingData < 5 {
		confidence += 0.2
	} else if stats.MissingData < 20 {
		confidence += 0.1
	}

	// Increase confidence based on patterns found
	if len(patterns) > 0 {
		avgStrength := 0.0
		for _, p := range patterns {
			avgStrength += p.Strength
		}
		avgStrength /= float64(len(patterns))
		confidence += avgStrength * 0.3
	}

	// Cap confidence
	if confidence > 0.95 {
		confidence = 0.95
	}

	return confidence
}

// generateSummary generates a human-readable summary.
func (s *DataAnalysisSkill) generateSummary(findings []Finding, patterns []Pattern, confidence float64) string {
	var summary strings.Builder

	summary.WriteString(fmt.Sprintf("Analysis complete with %.0f%% confidence.\n\n", confidence*100))

	if len(findings) > 0 {
		summary.WriteString("Key Findings:\n")
		for i, f := range findings {
			if i >= 3 {
				break
			}
			summary.WriteString(fmt.Sprintf("• %s\n", f.Statement))
		}
	}

	if len(patterns) > 0 {
		summary.WriteString("\nPatterns Detected:\n")
		for _, p := range patterns {
			summary.WriteString(fmt.Sprintf("• %s (strength: %.0f%%)\n", p.Description, p.Strength*100))
		}
	}

	return summary.String()
}

// CanExecute checks if the skill can execute.
func (s *DataAnalysisSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, ""
}
