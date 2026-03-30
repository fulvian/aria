package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// RecipeSearchSkill searches for recipes using TheMealDB API.
type RecipeSearchSkill struct {
	mealDBTool tools.BaseTool
}

// NewRecipeSearchSkill creates a new recipe search skill.
func NewRecipeSearchSkill(mealDBTool tools.BaseTool) *RecipeSearchSkill {
	return &RecipeSearchSkill{
		mealDBTool: mealDBTool,
	}
}

// Name returns the skill name.
func (s *RecipeSearchSkill) Name() SkillName {
	return SkillRecipeSearch
}

// Description returns the skill description.
func (s *RecipeSearchSkill) Description() string {
	return "Searches for recipes by name, category, area, or main ingredient"
}

// RequiredTools returns the tools required by this skill.
func (s *RecipeSearchSkill) RequiredTools() []ToolName {
	return []ToolName{"recipes_mealdb"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *RecipeSearchSkill) RequiredMCPs() []MCPName {
	return []MCPName{}
}

// Execute searches for recipes based on query parameters.
func (s *RecipeSearchSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "validate_params", Description: "Validating parameters", Status: "in_progress", DurationMs: 0},
	}

	// Determine operation type
	operation := "search"
	var query string
	var mealID int

	// Extract query parameters
	if q, ok := params.Input["query"].(string); ok && q != "" {
		query = q
		operation = "search"
	} else if id, ok := params.Input["id"].(float64); ok && id > 0 {
		mealID = int(id)
		operation = "lookup"
	} else if _, ok := params.Input["random"].(bool); ok {
		operation = "random"
	} else if category, ok := params.Input["category"].(string); ok && category != "" {
		query = category
		operation = "category"
	} else if area, ok := params.Input["area"].(string); ok && area != "" {
		query = area
		operation = "area"
	} else if ingredient, ok := params.Input["ingredient"].(string); ok && ingredient != "" {
		query = ingredient
		operation = "ingredient"
	} else if letter, ok := params.Input["letter"].(string); ok && len(letter) == 1 {
		query = letter
		operation = "filter"
	} else {
		steps[0].Status = "failed"
		return SkillResult{
			Success: false,
			Error:   "query, id, random, category, area, ingredient, or letter is required",
			Steps:   steps,
		}, fmt.Errorf("search parameters required")
	}

	// Extract includeDetails flag
	includeDetails := false
	if det, ok := params.Input["includeDetails"].(bool); ok {
		includeDetails = det
	}

	steps[0].Status = "completed"

	// Step 1: Search recipes
	steps = append(steps, SkillStep{
		Name:        "search_recipes",
		Description: fmt.Sprintf("Searching recipes with operation: %s", operation),
		Status:      "in_progress",
		DurationMs:  0,
	})

	var toolResult tools.ToolResponse
	var err error

	switch operation {
	case "search":
		toolResult, err = s.mealDBTool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "recipes_mealdb",
			Input: toJSONAny(tools.MealDBParams{
				Operation: "search",
				Query:     query,
			}),
		})

	case "lookup":
		toolResult, err = s.mealDBTool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "recipes_mealdb",
			Input: toJSONAny(tools.MealDBParams{
				Operation: "lookup",
				ID:        mealID,
			}),
		})

	case "random":
		toolResult, err = s.mealDBTool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "recipes_mealdb",
			Input: toJSONAny(tools.MealDBParams{
				Operation: "random",
			}),
		})

	case "category":
		toolResult, err = s.searchByFilter(ctx, params.TaskID, "c", query)

	case "area":
		toolResult, err = s.searchByFilter(ctx, params.TaskID, "a", query)

	case "ingredient":
		toolResult, err = s.searchByFilter(ctx, params.TaskID, "i", query)

	case "filter":
		toolResult, err = s.mealDBTool.Run(ctx, tools.ToolCall{
			ID:   params.TaskID,
			Name: "recipes_mealdb",
			Input: toJSONAny(tools.MealDBParams{
				Operation: "filter",
				Letter:    query,
			}),
		})

	default:
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      fmt.Sprintf("unknown operation: %s", operation),
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, fmt.Errorf("unknown operation: %s", operation)
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
		}, fmt.Errorf("MealDB tool error: %s", toolResult.Content)
	}

	steps[1].Status = "completed"

	// Step 2: Parse results
	steps = append(steps, SkillStep{
		Name:        "parse_results",
		Description: "Parsing recipe data",
		Status:      "in_progress",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	var mealData map[string]any
	if err := json.Unmarshal([]byte(toolResult.Content), &mealData); err != nil {
		steps[2].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      "failed to parse MealDB response",
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	// If includeDetails is true and we have meals, get full details for each
	recipes := formatRecipes(mealData, includeDetails)

	steps[2].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "format_output",
		Description: "Formatting recipe results",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":   params.TaskID,
			"operation": operation,
			"query":     query,
			"recipes":   recipes,
			"count":     len(recipes),
			"summary":   formatRecipeSummary(operation, query, len(recipes)),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// searchByFilter searches meals by category, area, or ingredient.
func (s *RecipeSearchSkill) searchByFilter(ctx context.Context, taskID string, filterType string, value string) (tools.ToolResponse, error) {
	// First get the list, then optionally get details
	return s.mealDBTool.Run(ctx, tools.ToolCall{
		ID:   taskID,
		Name: "recipes_mealdb",
		Input: toJSONAny(tools.MealDBParams{
			Operation: "search",
			Query:     value,
		}),
	})
}

// formatRecipes formats recipes from MealDB response.
func formatRecipes(data map[string]any, includeDetails bool) []map[string]any {
	recipes := []map[string]any{}

	meals, ok := data["meals"].([]any)
	if !ok || meals == nil {
		return recipes
	}

	for _, m := range meals {
		meal, ok := m.(map[string]any)
		if !ok {
			continue
		}

		recipe := map[string]any{
			"id":       meal["id"],
			"name":     meal["name"],
			"category": meal["category"],
			"area":     meal["area"],
		}

		if includeDetails {
			if thumb, ok := meal["thumbnail"].(string); ok {
				recipe["thumbnail"] = thumb
			}
			if instructions, ok := meal["instructions"].(string); ok {
				recipe["instructions"] = instructions
			}
			if ingredients, ok := meal["ingredients"].([]any); ok {
				recipe["ingredients"] = ingredients
			}
		}

		recipes = append(recipes, recipe)
	}

	return recipes
}

// formatRecipeSummary creates a human-readable summary.
func formatRecipeSummary(operation string, query string, count int) string {
	if count == 0 {
		return fmt.Sprintf("No recipes found for %s", query)
	}
	return fmt.Sprintf("Found %d recipes for %s: %s", count, operation, query)
}

// CanExecute checks if the skill can execute.
func (s *RecipeSearchSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Recipe search skill is ready"
}
