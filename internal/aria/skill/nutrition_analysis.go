package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// NutritionAnalysisSkill analyzes nutritional content of foods using USDA FDC API.
type NutritionAnalysisSkill struct {
	usdaTool tools.BaseTool
}

// NewNutritionAnalysisSkill creates a new nutrition analysis skill.
func NewNutritionAnalysisSkill(usdaTool tools.BaseTool) *NutritionAnalysisSkill {
	return &NutritionAnalysisSkill{
		usdaTool: usdaTool,
	}
}

// Name returns the skill name.
func (s *NutritionAnalysisSkill) Name() SkillName {
	return SkillNutritionAnalysis
}

// Description returns the skill description.
func (s *NutritionAnalysisSkill) Description() string {
	return "Analyzes nutritional content of foods and meals including calories, protein, carbs, and fat"
}

// RequiredTools returns the tools required by this skill.
func (s *NutritionAnalysisSkill) RequiredTools() []ToolName {
	return []ToolName{"nutrition_usda"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *NutritionAnalysisSkill) RequiredMCPs() []MCPName {
	return []MCPName{}
}

// Execute analyzes nutritional content of foods.
func (s *NutritionAnalysisSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "validate_params", Description: "Validating parameters", Status: "in_progress", DurationMs: 0},
	}

	// Extract food name or ID from input
	var foodName string
	var fdcID int
	var servings float64 = 1.0

	if name, ok := params.Input["food"].(string); ok && name != "" {
		foodName = name
	} else if id, ok := params.Input["fdcId"].(float64); ok && id > 0 {
		fdcID = int(id)
	} else {
		steps[0].Status = "failed"
		return SkillResult{
			Success: false,
			Error:   "food name or fdcId is required",
			Steps:   steps,
		}, fmt.Errorf("food name or fdcId is required")
	}

	// Extract servings
	if srv, ok := params.Input["servings"].(float64); ok && srv > 0 {
		servings = srv
	}

	steps[0].Status = "completed"

	// Step 1: Search or lookup food
	steps = append(steps, SkillStep{
		Name:        "fetch_food_data",
		Description: fmt.Sprintf("Fetching nutrition data for: %s", foodName),
		Status:      "in_progress",
		DurationMs:  0,
	})

	var toolResult tools.ToolResponse
	var err error

	if fdcID > 0 {
		toolResult, err = s.usdaTool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "nutrition_usda",
			Input: toJSONAny(tools.USDAParams{
				FDC_ID: fdcID,
			}),
		})
	} else {
		toolResult, err = s.usdaTool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "nutrition_usda",
			Input: toJSONAny(tools.USDAParams{
				Query:    foodName,
				PageSize: 10,
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
		}, fmt.Errorf("USDA tool error: %s", toolResult.Content)
	}

	steps[1].Status = "completed"

	// Step 2: Parse and analyze nutrition data
	steps = append(steps, SkillStep{
		Name:        "analyze_nutrition",
		Description: "Analyzing nutritional content",
		Status:      "in_progress",
		DurationMs:  0,
	})

	var usdaData map[string]any
	if err := json.Unmarshal([]byte(toolResult.Content), &usdaData); err != nil {
		steps[2].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      "failed to parse USDA response",
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	// Extract nutrition facts
	nutritionFacts := extractNutritionFacts(usdaData, servings)
	dietaryComparison := compareToDietaryTargets(nutritionFacts)

	steps[2].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "format_results",
		Description: "Formatting nutrition analysis results",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":         params.TaskID,
			"food_name":       foodName,
			"fdc_id":          fdcID,
			"servings":        servings,
			"nutrition_facts": nutritionFacts,
			"dietary_targets": getDietaryTargets(),
			"comparison":      dietaryComparison,
			"summary":         formatNutritionSummary(nutritionFacts, dietaryComparison),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *NutritionAnalysisSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Nutrition analysis skill is ready"
}

// extractNutritionFacts extracts and calculates nutrition information.
func extractNutritionFacts(data map[string]any, servings float64) map[string]any {
	facts := map[string]any{
		"calories":      0.0,
		"protein":       0.0,
		"carbohydrates": 0.0,
		"fat":           0.0,
		"fiber":         0.0,
		"sugar":         0.0,
		"sodium":        0.0,
		"cholesterol":   0.0,
	}

	// Get foods array
	foods, ok := data["foods"].([]any)
	if !ok || len(foods) == 0 {
		return facts
	}

	// Get first food
	food, ok := foods[0].(map[string]any)
	if !ok {
		return facts
	}

	// Extract nutrients
	if nutrients, ok := food["foodNutrients"].([]any); ok {
		for _, n := range nutrients {
			nutrient, ok := n.(map[string]any)
			if !ok {
				continue
			}

			name, _ := nutrient["nutrientName"].(string)
			value, _ := nutrient["value"].(float64)

			// Apply serving multiplier
			value *= servings

			switch name {
			case "Energy", "Calories":
				facts["calories"] = value
			case "Protein":
				facts["protein"] = value
			case "Carbohydrate, by difference":
				facts["carbohydrates"] = value
			case "Total lipid (fat)":
				facts["fat"] = value
			case "Fiber, total dietary":
				facts["fiber"] = value
			case "Sugars, total":
				facts["sugar"] = value
			case "Sodium, Na":
				facts["sodium"] = value
			case "Cholesterol":
				facts["cholesterol"] = value
			}
		}
	}

	return facts
}

// getDietaryTargets returns standard daily dietary targets.
func getDietaryTargets() map[string]any {
	return map[string]any{
		"calories":      2000.0,
		"protein":       50.0,
		"carbohydrates": 275.0,
		"fat":           78.0,
		"fiber":         28.0,
		"sugar":         50.0,
		"sodium":        2300.0,
		"cholesterol":   300.0,
	}
}

// compareToDietaryTargets compares nutrition facts to dietary targets.
func compareToDietaryTargets(facts map[string]any) map[string]any {
	targets := getDietaryTargets()
	comparison := map[string]any{}

	for key, value := range facts {
		if target, ok := targets[key]; ok {
			targetVal, _ := target.(float64)
			valueVal, _ := value.(float64)

			if targetVal > 0 {
				percentage := (valueVal / targetVal) * 100
				comparison[key] = map[string]any{
					"amount":     valueVal,
					"target":     targetVal,
					"percentage": percentage,
					"status":     getNutrientStatus(key, percentage),
				}
			}
		}
	}

	return comparison
}

// getNutrientStatus returns status based on percentage of daily value.
func getNutrientStatus(nutrient string, percentage float64) string {
	// For nutrients where you want to limit (like sodium, fat), high is bad
	limitNutrients := map[string]bool{
		"sodium":      true,
		"cholesterol": true,
		"sugar":       true,
		"fat":         true,
	}

	if limitNutrients[nutrient] {
		if percentage > 100 {
			return "exceeds-limit"
		}
		return "within-limit"
	}

	// For nutrients you want to get enough of
	if percentage < 50 {
		return "low"
	}
	if percentage < 100 {
		return "adequate"
	}
	return "high"
}

// formatNutritionSummary creates a human-readable nutrition summary.
func formatNutritionSummary(facts map[string]any, comparison map[string]any) string {
	calories, _ := facts["calories"].(float64)
	protein, _ := facts["protein"].(float64)
	carbs, _ := facts["carbohydrates"].(float64)
	fat, _ := facts["fat"].(float64)

	return fmt.Sprintf("Nutrition: %.0f cal, %.1fg protein, %.1fg carbs, %.1fg fat", calories, protein, carbs, fat)
}
