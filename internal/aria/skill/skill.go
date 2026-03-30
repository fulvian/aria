// Package skill provides the Skill system - modular reusable capabilities
// that agents can use to perform tasks. Skills wrap tools and provide
// higher-level abstractions.
//
// This package implements the Skill interface defined in Blueprint Section 2.2.4.
package skill

import (
	"context"
)

// SkillName identifies a specific skill.
type SkillName string

// Skill constants for development domain (initial implementation target)
const (
	// Knowledge skills
	SkillWebResearch SkillName = "web-research"
	SkillDocAnalysis SkillName = "document-analysis"
	SkillFactCheck   SkillName = "fact-check"

	// Development skills (target: first 3 to implement)
	SkillCodeReview  SkillName = "code-review"
	SkillTDD         SkillName = "test-driven-dev"
	SkillDebugging   SkillName = "systematic-debugging"
	SkillRefactoring SkillName = "refactoring"

	// Creative skills
	SkillWriting       SkillName = "creative-writing"
	SkillSummarization SkillName = "summarization"
	SkillTranslation   SkillName = "translation"

	// Productivity skills
	SkillPlanning   SkillName = "planning"
	SkillScheduling SkillName = "scheduling"
	SkillReminders  SkillName = "reminders"

	// Analytics skills
	SkillDataAnalysis  SkillName = "data-analysis"
	SkillVisualization SkillName = "visualization"

	// Weather skills
	SkillWeatherCurrent    SkillName = "weather-current"
	SkillWeatherForecast   SkillName = "weather-forecast"
	SkillWeatherAlerts     SkillName = "weather-alerts"
	SkillWeatherHistorical SkillName = "weather-historical"

	// Nutrition skills
	SkillRecipeSearch          SkillName = "recipe-search"
	SkillNutritionAnalysis     SkillName = "nutrition-analysis"
	SkillDietPlanGeneration    SkillName = "diet-plan-generation"
	SkillFoodRecallMonitoring  SkillName = "food-recall-monitoring"
	SkillRecipeAdaptation      SkillName = "recipe-adaptation"
	SkillMealPlanOptimization  SkillName = "meal-plan-optimization"
	SkillHealthyHabitsCoaching SkillName = "healthy-habits-coaching"
	SkillNutritionEducation    SkillName = "nutrition-education"
)

// ToolName represents the name of a tool required by a skill.
type ToolName string

// MCPName represents the name of an MCP server required by a skill.
type MCPName string

// SkillParams contains parameters for skill execution.
type SkillParams struct {
	TaskID   string
	Input    map[string]any
	Context  map[string]any
	Settings map[string]any
}

// SkillResult contains the output of skill execution.
type SkillResult struct {
	Success    bool
	Output     map[string]any
	Error      string
	DurationMs int64
	Steps      []SkillStep
}

// SkillStep represents a step in skill execution for logging/debugging.
type SkillStep struct {
	Name        string
	Description string
	Status      string // started, completed, failed
	DurationMs  int64
}

// Skill defines a modular reusable capability that an agent can use.
// Skills are the building blocks of agent functionality, combining
// tools and procedures into meaningful units of work.
//
// Reference: Blueprint Section 2.2.4
type Skill interface {
	// Identity
	Name() SkillName
	Description() string

	// Requirements - what tools/MCPs this skill needs
	RequiredTools() []ToolName
	RequiredMCPs() []MCPName

	// Execution
	Execute(ctx context.Context, params SkillParams) (SkillResult, error)

	// Validation - can this skill execute now?
	CanExecute(ctx context.Context) (bool, string)
}

// SkillRegistry maintains available skills and their configurations.
type SkillRegistry interface {
	// Get returns a skill by name.
	Get(name SkillName) (Skill, error)

	// List returns all registered skills.
	List() []Skill

	// Register adds a skill to the registry.
	Register(s Skill) error

	// Unregister removes a skill from the registry.
	Unregister(name SkillName) error

	// FindByTool returns skills that require a specific tool.
	FindByTool(tool ToolName) []Skill

	// FindByMCP returns skills that require a specific MCP.
	FindByMCP(mcp MCPName) []Skill
}
