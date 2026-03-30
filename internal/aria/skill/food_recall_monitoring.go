package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// FoodRecallMonitoringSkill monitors food safety recalls using openFDA API.
type FoodRecallMonitoringSkill struct {
	openFDATool tools.BaseTool
}

// NewFoodRecallMonitoringSkill creates a new food recall monitoring skill.
func NewFoodRecallMonitoringSkill(openFDATool tools.BaseTool) *FoodRecallMonitoringSkill {
	return &FoodRecallMonitoringSkill{
		openFDATool: openFDATool,
	}
}

// Name returns the skill name.
func (s *FoodRecallMonitoringSkill) Name() SkillName {
	return SkillFoodRecallMonitoring
}

// Description returns the skill description.
func (s *FoodRecallMonitoringSkill) Description() string {
	return "Monitors food safety recalls and alerts from FDA"
}

// RequiredTools returns the tools required by this skill.
func (s *FoodRecallMonitoringSkill) RequiredTools() []ToolName {
	return []ToolName{"food_safety_openfda"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *FoodRecallMonitoringSkill) RequiredMCPs() []MCPName {
	return []MCPName{}
}

// Execute searches for food recalls based on parameters.
func (s *FoodRecallMonitoringSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "validate_params", Description: "Validating parameters", Status: "in_progress", DurationMs: 0},
	}

	// Determine operation
	operation := "search"
	var recallID string
	var status string
	var classification string
	var limit int = 50

	// Extract parameters
	if id, ok := params.Input["id"].(string); ok && id != "" {
		recallID = id
		operation = "get"
	} else {
		if st, ok := params.Input["status"].(string); ok && st != "" {
			status = st
		}
		if cls, ok := params.Input["classification"].(string); ok && cls != "" {
			classification = cls
		}
		if lim, ok := params.Input["limit"].(float64); ok && lim > 0 {
			limit = int(lim)
		}
	}

	steps[0].Status = "completed"

	// Step 1: Search recalls
	steps = append(steps, SkillStep{
		Name:        "search_recalls",
		Description: "Searching FDA food recall database",
		Status:      "in_progress",
		DurationMs:  0,
	})

	var toolResult tools.ToolResponse
	var err error

	if operation == "get" {
		toolResult, err = s.openFDATool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "food_safety_openfda",
			Input: toJSONAny(tools.OpenFDAParams{
				Operation: "get",
				ID:        recallID,
			}),
		})
	} else {
		toolResult, err = s.openFDATool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "food_safety_openfda",
			Input: toJSONAny(tools.OpenFDAParams{
				Operation:      "search",
				Status:         status,
				Classification: classification,
				Limit:          limit,
			}),
		})
	}

	steps[1].DurationMs = time.Since(start).Milliseconds()

	if err != nil {
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	if toolResult.IsError {
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      toolResult.Content,
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, fmt.Errorf("openFDA tool error: %s", toolResult.Content)
	}

	steps[1].Status = "completed"

	// Step 2: Parse results
	steps = append(steps, SkillStep{
		Name:        "parse_recalls",
		Description: "Parsing recall data",
		Status:      "in_progress",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	var recallData map[string]any
	if err := json.Unmarshal([]byte(toolResult.Content), &recallData); err != nil {
		steps[2].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      "failed to parse FDA response",
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	recalls := formatRecalls(recallData)
	classifications := summarizeByClassification(recalls)
	statuses := summarizeByStatus(recalls)

	steps[2].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "format_output",
		Description: "Formatting recall results",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":   params.TaskID,
			"operation": operation,
			"recalls":   recalls,
			"count":     len(recalls),
			"filters_applied": map[string]string{
				"status":         status,
				"classification": classification,
			},
			"summary":           formatRecallSummary(recalls),
			"by_classification": classifications,
			"by_status":         statuses,
			"health_alert":      generateHealthAlert(recalls),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *FoodRecallMonitoringSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Food recall monitoring skill is ready"
}

// formatRecalls formats recalls from FDA response.
func formatRecalls(data map[string]any) []map[string]any {
	recalls := []map[string]any{}

	results, ok := data["results"].([]any)
	if !ok || results == nil {
		return recalls
	}

	for _, r := range results {
		recall, ok := r.(map[string]any)
		if !ok {
			continue
		}

		formatted := map[string]any{
			"recall_number":  recall["recall_number"],
			"classification": recall["classification"],
			"status":         recall["status"],
			"recalling_firm": recall["recalling_firm"],
			"product_desc":   recall["product_description"],
			"reason":         recall["reason_for_recall"],
			"product_type":   recall["product_type"],
			"event_id":       recall["event_id"],
			"init_date":      recall["rec_init_date"],
		}

		// Add optional fields if present
		if dist, ok := recall["distribution_pattern"].(string); ok {
			formatted["distribution"] = dist
		}
		if quantity, ok := recall["product_quantity"].(string); ok {
			formatted["quantity"] = quantity
		}
		if termDate, ok := recall["termination_date"].(string); ok {
			formatted["termination_date"] = termDate
		}
		if voluntary, ok := recall["voluntary_mandated"].(string); ok {
			formatted["voluntary"] = voluntary
		}

		recalls = append(recalls, formatted)
	}

	return recalls
}

// summarizeByClassification groups recalls by classification.
func summarizeByClassification(recalls []map[string]any) map[string]int {
	summary := map[string]int{
		"Class I":   0,
		"Class II":  0,
		"Class III": 0,
		"Unknown":   0,
	}

	for _, r := range recalls {
		class, _ := r["classification"].(string)
		switch class {
		case "Class I":
			summary["Class I"]++
		case "Class II":
			summary["Class II"]++
		case "Class III":
			summary["Class III"]++
		default:
			summary["Unknown"]++
		}
	}

	return summary
}

// summarizeByStatus groups recalls by status.
func summarizeByStatus(recalls []map[string]any) map[string]int {
	summary := map[string]int{
		"On-Going":   0,
		"Terminated": 0,
		"Unknown":    0,
	}

	for _, r := range recalls {
		status, _ := r["status"].(string)
		switch status {
		case "On-Going":
			summary["On-Going"]++
		case "Terminated":
			summary["Terminated"]++
		default:
			summary["Unknown"]++
		}
	}

	return summary
}

// formatRecallSummary creates a human-readable summary.
func formatRecallSummary(recalls []map[string]any) string {
	if len(recalls) == 0 {
		return "No food recalls found matching your criteria"
	}

	class1 := 0
	class2 := 0
	class3 := 0
	ongoing := 0

	for _, r := range recalls {
		class, _ := r["classification"].(string)
		status, _ := r["status"].(string)

		switch class {
		case "Class I":
			class1++
		case "Class II":
			class2++
		case "Class III":
			class3++
		}

		if status == "On-Going" {
			ongoing++
		}
	}

	return fmt.Sprintf("Found %d recalls: %d Class I, %d Class II, %d Class III (%d ongoing)",
		len(recalls), class1, class2, class3, ongoing)
}

// generateHealthAlert generates a health alert for serious recalls.
func generateHealthAlert(recalls []map[string]any) string {
	var class1Ongoing []string

	for _, r := range recalls {
		class, _ := r["classification"].(string)
		status, _ := r["status"].(string)
		desc, _ := r["product_desc"].(string)

		if class == "Class I" && status == "On-Going" {
			class1Ongoing = append(class1Ongoing, desc)
		}
	}

	if len(class1Ongoing) == 0 {
		return "No Class I (most serious) ongoing recalls found"
	}

	if len(class1Ongoing) > 3 {
		return fmt.Sprintf("WARNING: %d serious Class I recalls are ongoing. Review affected products immediately.", len(class1Ongoing))
	}

	return fmt.Sprintf("ALERT: %d Class I recalls require attention: %v", len(class1Ongoing), class1Ongoing)
}
