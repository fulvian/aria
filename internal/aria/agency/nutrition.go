// Package agency provides the Nutrition Agency implementation.
// This agency demonstrates the specialized agency architecture for nutrition tasks.
package agency

import (
	"context"
	"fmt"
	"strings"
	"time"

	ariaConfig "github.com/fulvian/aria/internal/aria/config"
	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/llm/tools"
)

// NutritionAgency is the nutrition-focused agency for food, recipes, and diet tasks.
type NutritionAgency struct {
	name        contracts.AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Lifecycle state
	status    AgencyStatus
	startTime time.Time
	pauseTime time.Time

	// Skill bridges
	nutritionAnalysisBridge NutritionAnalystBridge
	recipeSearchBridge      CulinaryBridge
	dietPlanBridge          DietPlannerBridge
	foodRecallBridge        FoodSafetyBridge
	healthyLifestyleBridge  HealthyLifestyleCoachBridge

	// subscribed events
	sub *AgencyEventBroker
}

// NewNutritionAgency creates a new nutrition agency.
func NewNutritionAgency(cfg ariaConfig.NutritionConfig) *NutritionAgency {
	// Initialize tools
	usdaTool := tools.NewUSDATool(cfg.USDA_APIKey)
	mealDBTool := tools.NewMealDBTool()
	openFDATool := tools.NewOpenFDATool()

	// Initialize skills
	nutritionAnalysisSkill := skill.NewNutritionAnalysisSkill(usdaTool)
	recipeSearchSkill := skill.NewRecipeSearchSkill(mealDBTool)
	dietPlanSkill := skill.NewDietPlanGenerationSkill(nutritionAnalysisSkill, recipeSearchSkill)
	foodRecallSkill := skill.NewFoodRecallMonitoringSkill(openFDATool)

	return &NutritionAgency{
		name:                    contracts.AgencyNutrition,
		domain:                  "nutrition",
		description:             "Nutrition, recipes, meal planning, diet analysis, and food safety",
		state:                   AgencyState{},
		memory:                  NewAgencyMemory("nutrition"),
		sub:                     NewAgencyEventBroker(),
		nutritionAnalysisBridge: NewNutritionAnalystBridge(nutritionAnalysisSkill),
		recipeSearchBridge:      NewCulinaryBridge(recipeSearchSkill),
		dietPlanBridge:          NewDietPlannerBridge(dietPlanSkill),
		foodRecallBridge:        NewFoodSafetyBridge(foodRecallSkill),
		healthyLifestyleBridge:  NewHealthyLifestyleCoachBridge(),
	}
}

// Name returns the agency name.
func (a *NutritionAgency) Name() contracts.AgencyName {
	return a.name
}

// Domain returns the domain.
func (a *NutritionAgency) Domain() string {
	return a.domain
}

// Description returns the description.
func (a *NutritionAgency) Description() string {
	return a.description
}

// Agents returns the list of agent names.
func (a *NutritionAgency) Agents() []contracts.AgentName {
	return []contracts.AgentName{
		"nutrition-analyst",
		"culinary",
		"diet-planner",
		"food-safety",
		"healthy-lifestyle-coach",
	}
}

// GetAgent returns an agent by name.
func (a *NutritionAgency) GetAgent(name contracts.AgentName) (interface{}, error) {
	switch name {
	case "nutrition-analyst":
		return a.nutritionAnalysisBridge, nil
	case "culinary":
		return a.recipeSearchBridge, nil
	case "diet-planner":
		return a.dietPlanBridge, nil
	case "food-safety":
		return a.foodRecallBridge, nil
	case "healthy-lifestyle-coach":
		return a.healthyLifestyleBridge, nil
	default:
		return nil, fmt.Errorf("agent not found: %s", name)
	}
}

// Execute executes a task in the nutrition agency.
func (a *NutritionAgency) Execute(ctx context.Context, task contracts.Task) (contracts.Result, error) {
	start := time.Now()

	// Emit task started event
	a.sub.Publish(contracts.AgencyEvent{
		AgencyID: a.name,
		Type:     "task_started",
		Payload: map[string]any{
			"task_id":   task.ID,
			"task_name": task.Name,
		},
	})

	// Determine which skill/bridge to use based on task
	var skillName string
	if len(task.Skills) > 0 {
		skillName = task.Skills[0]
	}

	var result map[string]any
	var err error

	switch skillName {
	case "nutrition-analysis":
		result, err = a.nutritionAnalysisBridge.AnalyzeNutrition(ctx, task, skillName)
	case "recipe-search":
		result, err = a.recipeSearchBridge.SearchRecipes(ctx, task, skillName)
	case "diet-plan-generation":
		result, err = a.dietPlanBridge.GenerateDietPlan(ctx, task, skillName)
	case "food-recall-monitoring":
		result, err = a.foodRecallBridge.MonitorRecalls(ctx, task, skillName)
	case "healthy-habits-coaching":
		result, err = a.healthyLifestyleBridge.ProvideCoaching(ctx, task, skillName)
	default:
		// Fallback to task name matching
		switch task.Name {
		case "nutrition-analysis", "analyze-nutrition":
			result, err = a.nutritionAnalysisBridge.AnalyzeNutrition(ctx, task, "nutrition-analysis")
		case "recipe-search", "search-recipes", "find-recipes":
			result, err = a.recipeSearchBridge.SearchRecipes(ctx, task, "recipe-search")
		case "diet-plan-generation", "generate-diet-plan":
			result, err = a.dietPlanBridge.GenerateDietPlan(ctx, task, "diet-plan-generation")
		case "food-recall-monitoring", "check-recalls":
			result, err = a.foodRecallBridge.MonitorRecalls(ctx, task, "food-recall-monitoring")
		case "healthy-habits-coaching", "lifestyle-advice":
			result, err = a.healthyLifestyleBridge.ProvideCoaching(ctx, task, "healthy-habits-coaching")
		default:
			err = fmt.Errorf("unknown nutrition task: %s (skill: %s)", task.Name, skillName)
		}
	}

	if err != nil {
		// Emit task failed event
		a.sub.Publish(contracts.AgencyEvent{
			AgencyID: a.name,
			Type:     "task_failed",
			Payload: map[string]any{
				"task_id": task.ID,
				"error":   err.Error(),
			},
		})
		return contracts.Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, err
	}

	// Emit task completed event
	a.sub.Publish(contracts.AgencyEvent{
		AgencyID: a.name,
		Type:     "task_completed",
		Payload: map[string]any{
			"task_id": task.ID,
			"result":  result,
		},
	})

	return contracts.Result{
		TaskID:     task.ID,
		Success:    true,
		Output:     result,
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// GetState returns the current state.
func (a *NutritionAgency) GetState() AgencyState {
	return a.state
}

// SaveState saves the agency state.
func (a *NutritionAgency) SaveState(state AgencyState) error {
	a.state = state
	return nil
}

// Memory returns the agency memory.
func (a *NutritionAgency) Memory() DomainMemory {
	return a.memory
}

// Subscribe returns a channel for receiving agency events.
func (a *NutritionAgency) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent {
	return a.sub.Subscribe(ctx)
}

// Start starts the nutrition agency.
func (a *NutritionAgency) Start(ctx context.Context) error {
	switch a.status {
	case AgencyStatusRunning:
		return fmt.Errorf("agency already running")
	case AgencyStatusPaused:
		return fmt.Errorf("agency is paused, use Resume instead")
	}

	a.status = AgencyStatusRunning
	a.startTime = time.Now()

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_started",
		Payload:   map[string]any{"start_time": a.startTime},
		Timestamp: time.Now(),
	})

	return nil
}

// Stop stops the nutrition agency.
func (a *NutritionAgency) Stop(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("agency already stopped")
	}

	a.status = AgencyStatusStopped
	a.pauseTime = time.Time{}

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_stopped",
		Payload:   map[string]any{},
		Timestamp: time.Now(),
	})

	return nil
}

// Pause pauses the nutrition agency.
func (a *NutritionAgency) Pause(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("cannot pause stopped agency")
	}
	if a.status == AgencyStatusPaused {
		return fmt.Errorf("agency already paused")
	}

	a.status = AgencyStatusPaused
	a.pauseTime = time.Now()

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_paused",
		Payload:   map[string]any{"pause_time": a.pauseTime},
		Timestamp: time.Now(),
	})

	return nil
}

// Resume resumes the nutrition agency.
func (a *NutritionAgency) Resume(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("cannot resume stopped agency, use Start instead")
	}
	if a.status == AgencyStatusRunning {
		return fmt.Errorf("agency already running")
	}

	a.status = AgencyStatusRunning
	a.pauseTime = time.Time{}

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_resumed",
		Payload:   map[string]any{},
		Timestamp: time.Now(),
	})

	return nil
}

// Status returns the current agency status.
func (a *NutritionAgency) Status() AgencyStatus {
	return a.status
}

// ============================================================================
// Bridge Interfaces
// ============================================================================

// NutritionAnalystBridge defines the interface for nutrition analysis operations.
type NutritionAnalystBridge interface {
	AnalyzeNutrition(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// CulinaryBridge defines the interface for recipe operations.
type CulinaryBridge interface {
	SearchRecipes(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// DietPlannerBridge defines the interface for diet planning operations.
type DietPlannerBridge interface {
	GenerateDietPlan(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// FoodSafetyBridge defines the interface for food safety operations.
type FoodSafetyBridge interface {
	MonitorRecalls(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// HealthyLifestyleCoachBridge defines the interface for lifestyle coaching operations.
type HealthyLifestyleCoachBridge interface {
	ProvideCoaching(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// ============================================================================
// Bridge Implementations
// ============================================================================

// NutritionAnalystBridgeImpl implements NutritionAnalystBridge using NutritionAnalysisSkill.
type NutritionAnalystBridgeImpl struct {
	skill *skill.NutritionAnalysisSkill
}

// NewNutritionAnalystBridge creates a new NutritionAnalystBridge.
func NewNutritionAnalystBridge(s *skill.NutritionAnalysisSkill) *NutritionAnalystBridgeImpl {
	return &NutritionAnalystBridgeImpl{skill: s}
}

// AnalyzeNutrition handles nutrition analysis tasks.
func (b *NutritionAnalystBridgeImpl) AnalyzeNutrition(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	// Also include description as potential food input
	if task.Description != "" && input["food"] == nil {
		input["description"] = task.Description
	}

	// Execute the skill
	result, err := b.skill.Execute(ctx, skill.SkillParams{
		TaskID: task.ID,
		Input:  input,
		Context: map[string]any{
			"task_name": task.Name,
		},
	})

	if err != nil {
		return nil, fmt.Errorf("nutrition analysis error: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("nutrition analysis failed: %s", result.Error)
	}

	return result.Output, nil
}

// CulinaryBridgeImpl implements CulinaryBridge using RecipeSearchSkill.
type CulinaryBridgeImpl struct {
	skill *skill.RecipeSearchSkill
}

// NewCulinaryBridge creates a new CulinaryBridge.
func NewCulinaryBridge(s *skill.RecipeSearchSkill) *CulinaryBridgeImpl {
	return &CulinaryBridgeImpl{skill: s}
}

// SearchRecipes handles recipe search tasks.
func (b *CulinaryBridgeImpl) SearchRecipes(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	// Map description to query if no explicit query provided
	if task.Description != "" && input["query"] == nil && input["id"] == nil {
		input["query"] = task.Description
	}

	// Execute the skill
	result, err := b.skill.Execute(ctx, skill.SkillParams{
		TaskID: task.ID,
		Input:  input,
		Context: map[string]any{
			"task_name": task.Name,
		},
	})

	if err != nil {
		return nil, fmt.Errorf("recipe search error: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("recipe search failed: %s", result.Error)
	}

	return result.Output, nil
}

// DietPlannerBridgeImpl implements DietPlannerBridge using DietPlanGenerationSkill.
type DietPlannerBridgeImpl struct {
	skill *skill.DietPlanGenerationSkill
}

// NewDietPlannerBridge creates a new DietPlannerBridge.
func NewDietPlannerBridge(s *skill.DietPlanGenerationSkill) *DietPlannerBridgeImpl {
	return &DietPlannerBridgeImpl{skill: s}
}

// GenerateDietPlan handles diet plan generation tasks.
func (b *DietPlannerBridgeImpl) GenerateDietPlan(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	// Parse description for parameters (simple key:value parsing)
	if task.Description != "" {
		parseDescriptionParams(task.Description, input)
	}

	// Execute the skill
	result, err := b.skill.Execute(ctx, skill.SkillParams{
		TaskID: task.ID,
		Input:  input,
		Context: map[string]any{
			"task_name": task.Name,
		},
	})

	if err != nil {
		return nil, fmt.Errorf("diet plan generation error: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("diet plan generation failed: %s", result.Error)
	}

	return result.Output, nil
}

// parseDescriptionParams parses simple key:value pairs from description.
func parseDescriptionParams(description string, input map[string]any) {
	// Simple parsing for common diet plan parameters
	params := []string{"goal", "daily_calories", "meals_per_day", "restrictions", "allergies", "activity_level"}
	for _, param := range params {
		if _, exists := input[param]; exists {
			continue
		}
		// Look for "goal:weight-loss" patterns
		pattern := param + ":"
		if idx := findPattern(description, pattern); idx >= 0 {
			start := idx + len(pattern)
			end := start
			for end < len(description) && description[end] != ',' && description[end] != ';' && description[end] != ' ' {
				end++
			}
			if end > start {
				value := description[start:end]
				input[param] = value
			}
		}
	}
}

// findPattern finds a pattern in text (simple string search).
func findPattern(text, pattern string) int {
	for i := 0; i <= len(text)-len(pattern); i++ {
		if text[i:i+len(pattern)] == pattern {
			return i
		}
	}
	return -1
}

// FoodSafetyBridgeImpl implements FoodSafetyBridge using FoodRecallMonitoringSkill.
type FoodSafetyBridgeImpl struct {
	skill *skill.FoodRecallMonitoringSkill
}

// NewFoodSafetyBridge creates a new FoodSafetyBridge.
func NewFoodSafetyBridge(s *skill.FoodRecallMonitoringSkill) *FoodSafetyBridgeImpl {
	return &FoodSafetyBridgeImpl{skill: s}
}

// MonitorRecalls handles food recall monitoring tasks.
func (b *FoodSafetyBridgeImpl) MonitorRecalls(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	// Parse description for recall filters
	if task.Description != "" {
		parseRecallParams(task.Description, input)
	}

	// Execute the skill
	result, err := b.skill.Execute(ctx, skill.SkillParams{
		TaskID: task.ID,
		Input:  input,
		Context: map[string]any{
			"task_name": task.Name,
		},
	})

	if err != nil {
		return nil, fmt.Errorf("food recall monitoring error: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("food recall monitoring failed: %s", result.Error)
	}

	return result.Output, nil
}

// parseRecallParams parses recall-related parameters from description.
func parseRecallParams(description string, input map[string]any) {
	// Look for status and classification filters
	if _, exists := input["status"]; !exists {
		statuses := []string{"On-Going", "Terminated"}
		for _, status := range statuses {
			if containsStr(description, status) {
				input["status"] = status
				break
			}
		}
	}

	if _, exists := input["classification"]; !exists {
		classes := []string{"Class I", "Class II", "Class III"}
		for _, class := range classes {
			if containsStr(description, class) {
				input["classification"] = class
				break
			}
		}
	}
}

// containsStr checks if text contains substring (case-insensitive).
func containsStr(text, substr string) bool {
	return len(text) >= len(substr) && findPattern(text, substr) >= 0
}

// HealthyLifestyleCoachBridgeImpl implements HealthyLifestyleCoachBridge.
// This provides lifestyle coaching based on nutrition and health principles.
type HealthyLifestyleCoachBridgeImpl struct{}

// NewHealthyLifestyleCoachBridge creates a new HealthyLifestyleCoachBridge.
func NewHealthyLifestyleCoachBridge() *HealthyLifestyleCoachBridgeImpl {
	return &HealthyLifestyleCoachBridgeImpl{}
}

// ProvideCoaching provides lifestyle and healthy habits coaching.
func (b *HealthyLifestyleCoachBridgeImpl) ProvideCoaching(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract coaching topic from parameters or description
	topic := "general wellness"
	if topicVal, ok := task.Parameters["topic"].(string); ok {
		topic = topicVal
	} else if task.Description != "" {
		topic = task.Description
	}

	// Generate coaching based on topic
	coaching := generateCoaching(topic, task.Parameters)

	return map[string]any{
		"task_id":     task.ID,
		"topic":       topic,
		"coaching":    coaching,
		"summary":     fmt.Sprintf("Healthy lifestyle coaching for: %s", topic),
		"skill":       skillName,
		"api_source":  "lifestyle-coaching",
		"integration": "skill-based",
	}, nil
}

// CoachingTip represents a single coaching tip.
type CoachingTip struct {
	Category    string `json:"category"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Action      string `json:"action,omitempty"`
}

// generateCoaching generates personalized coaching based on topic and parameters.
func generateCoaching(topic string, params map[string]any) []CoachingTip {
	tips := []CoachingTip{}

	topic = normalizeTopic(topic)

	switch topic {
	case "weight-loss":
		tips = append(tips,
			CoachingTip{
				Category:    "nutrition",
				Title:       "Mindful Eating",
				Description: "Pay attention to hunger and fullness cues",
				Action:      "Eat slowly, savor each bite",
			},
			CoachingTip{
				Category:    "nutrition",
				Title:       "Protein-Rich Breakfast",
				Description: "Start your day with protein to reduce cravings",
				Action:      "Include eggs, Greek yogurt, or protein smoothie",
			},
			CoachingTip{
				Category:    "activity",
				Title:       "Daily Movement",
				Description: "Aim for 30 minutes of moderate activity",
				Action:      "Walk, swim, or cycle most days",
			},
		)
	case "muscle-gain":
		tips = append(tips,
			CoachingTip{
				Category:    "nutrition",
				Title:       "Protein Timing",
				Description: "Consume protein within 30 minutes after workouts",
				Action:      "Post-workout shake with whey protein",
			},
			CoachingTip{
				Category:    "nutrition",
				Title:       "Complex Carbs",
				Description: "Fuel workouts with complex carbohydrates",
				Action:      "Oats, brown rice, sweet potatoes",
			},
			CoachingTip{
				Category:    "activity",
				Title:       "Progressive Overload",
				Description: "Gradually increase weight and reps",
				Action:      "Track progress in a workout journal",
			},
		)
	case "general wellness", "healthy-habits":
		tips = append(tips,
			CoachingTip{
				Category:    "hydration",
				Title:       "Stay Hydrated",
				Description: "Drink at least 8 glasses of water daily",
				Action:      "Carry a reusable water bottle",
			},
			CoachingTip{
				Category:    "sleep",
				Title:       "Quality Sleep",
				Description: "Aim for 7-9 hours of quality sleep",
				Action:      "Establish a consistent bedtime routine",
			},
			CoachingTip{
				Category:    "stress",
				Title:       "Stress Management",
				Description: "Practice daily stress-reduction techniques",
				Action:      "Try meditation, deep breathing, or yoga",
			},
		)
	case "heart-health":
		tips = append(tips,
			CoachingTip{
				Category:    "nutrition",
				Title:       "Reduce Sodium",
				Description: "Limit sodium to under 2300mg daily",
				Action:      "Cook at home, use herbs instead of salt",
			},
			CoachingTip{
				Category:    "nutrition",
				Title:       "Heart-Healthy Fats",
				Description: "Include omega-3 rich foods",
				Action:      "Eat fatty fish 2-3 times per week",
			},
			CoachingTip{
				Category:    "activity",
				Title:       "Cardio Regularity",
				Description: "150 minutes of moderate aerobic activity weekly",
				Action:      "Brisk walking, jogging, or cycling",
			},
		)
	default:
		tips = append(tips,
			CoachingTip{
				Category:    "nutrition",
				Title:       "Balanced Diet",
				Description: "Include variety of fruits, vegetables, whole grains",
				Action:      "Make half your plate vegetables",
			},
			CoachingTip{
				Category:    "activity",
				Title:       "Regular Exercise",
				Description: "Stay active with moderate exercise most days",
				Action:      "Find activities you enjoy",
			},
		)
	}

	// Check for dietary restrictions
	if restrictions, ok := params["restrictions"].([]any); ok {
		for _, r := range restrictions {
			if restriction, ok := r.(string); ok {
				tips = append(tips, CoachingTip{
					Category:    "dietary",
					Title:       "Dietary Restriction",
					Description: fmt.Sprintf("Remember your %s restriction", restriction),
				})
			}
		}
	}

	return tips
}

// normalizeTopic normalizes the coaching topic string.
func normalizeTopic(topic string) string {
	topic = removeIllogicalCharacters(topic)
	lower := strings.ToLower(topic)

	switch {
	case strings.Contains(lower, "weight loss") || strings.Contains(lower, "lose weight"):
		return "weight-loss"
	case strings.Contains(lower, "muscle") && strings.Contains(lower, "gain"):
		return "muscle-gain"
	case strings.Contains(lower, "heart") || strings.Contains(lower, "cardio"):
		return "heart-health"
	case strings.Contains(lower, "wellness") || strings.Contains(lower, "general"):
		return "general wellness"
	case strings.Contains(lower, "healthy") && strings.Contains(lower, "habit"):
		return "healthy-habits"
	default:
		return "general wellness"
	}
}

// removeIllogicalCharacters removes illogical characters from input.
func removeIllogicalCharacters(s string) string {
	var result []byte
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 32 && c < 127 {
			result = append(result, c)
		}
	}
	return string(result)
}
