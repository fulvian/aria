package skill

import (
	"context"
	"fmt"
	"time"
)

// DietPlanGenerationSkill generates personalized meal plans.
type DietPlanGenerationSkill struct {
	nutritionAnalyzer Skill
	recipeSearch      Skill
}

// NewDietPlanGenerationSkill creates a new diet plan generation skill.
func NewDietPlanGenerationSkill(analyzer Skill, recipeSearch Skill) *DietPlanGenerationSkill {
	return &DietPlanGenerationSkill{
		nutritionAnalyzer: analyzer,
		recipeSearch:      recipeSearch,
	}
}

// Name returns the skill name.
func (s *DietPlanGenerationSkill) Name() SkillName {
	return SkillDietPlanGeneration
}

// Description returns the skill description.
func (s *DietPlanGenerationSkill) Description() string {
	return "Generates personalized meal plans based on user profile and dietary goals"
}

// RequiredTools returns the tools required by this skill.
func (s *DietPlanGenerationSkill) RequiredTools() []ToolName {
	return []ToolName{} // Uses other skills, not direct tools
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *DietPlanGenerationSkill) RequiredMCPs() []MCPName {
	return []MCPName{}
}

// Execute generates a personalized meal plan.
func (s *DietPlanGenerationSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "validate_params", Description: "Validating parameters", Status: "in_progress", DurationMs: 0},
	}

	// Extract user profile
	userProfile := extractUserProfile(params.Input)

	// Validate required parameters
	if userProfile.Goal == "" {
		steps[0].Status = "failed"
		return SkillResult{
			Success: false,
			Error:   "goal is required (weight-loss, maintenance, weight-gain, muscle-gain)",
			Steps:   steps,
		}, fmt.Errorf("goal is required")
	}

	if userProfile.DailyCalories <= 0 {
		steps[0].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      "daily_calories must be provided and greater than 0",
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, fmt.Errorf("daily_calories is required")
	}

	steps[0].Status = "completed"

	// Step 1: Calculate macro targets
	steps = append(steps, SkillStep{
		Name:        "calculate_macros",
		Description: "Calculating macro targets based on user goal",
		Status:      "in_progress",
		DurationMs:  0,
	})

	macroTargets := calculateMacroTargets(userProfile)

	steps[1].Status = "completed"

	// Step 2: Generate meal schedule
	steps = append(steps, SkillStep{
		Name:        "generate_meals",
		Description: "Generating meal suggestions",
		Status:      "in_progress",
		DurationMs:  0,
	})

	meals := generateMealPlan(userProfile, macroTargets)

	steps[2].Status = "completed"

	// Step 3: Format meal plan
	steps = append(steps, SkillStep{
		Name:        "format_plan",
		Description: "Formatting meal plan output",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":       params.TaskID,
			"user_profile":  userProfile,
			"macro_targets": macroTargets,
			"meals":         meals,
			"plan_summary":  formatMealPlanSummary(userProfile, macroTargets, meals),
			"tips":          generateMealPlanTips(userProfile),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *DietPlanGenerationSkill) CanExecute(ctx context.Context) (bool, string) {
	if s.nutritionAnalyzer == nil {
		return false, "Nutrition analyzer skill is not available"
	}
	if s.recipeSearch == nil {
		return false, "Recipe search skill is not available"
	}
	return true, "Diet plan generation skill is ready"
}

// UserProfile contains user dietary preferences and goals.
type UserProfile struct {
	Goal          string   // weight-loss, maintenance, weight-gain, muscle-gain
	DailyCalories float64  // Target daily calories
	MealsPerDay   int      // Number of meals (default: 3)
	Restrictions  []string // vegetarian, vegan, gluten-free, dairy-free, nut-free, etc.
	Allergies     []string
	Preferences   []string // Preferred cuisines
	Dislikes      []string // Foods to avoid
	ActivityLevel string   // sedentary, light, moderate, active, very-active
}

// MacroTargets contains calculated macro targets.
type MacroTargets struct {
	Protein   float64 // grams
	Carbs     float64 // grams
	Fat       float64 // grams
	Fiber     float64 // grams
	Breakfast float64 // calories
	Lunch     float64 // calories
	Dinner    float64 // calories
	Snacks    float64 // calories
}

// Meal represents a single meal in the plan.
type Meal struct {
	Name        string   `json:"name"`
	Time        string   `json:"time"`
	Calories    float64  `json:"calories"`
	Protein     float64  `json:"protein"`
	Carbs       float64  `json:"carbs"`
	Fat         float64  `json:"fat"`
	Recipes     []string `json:"recipes,omitempty"`
	Ingredients []string `json:"ingredients,omitempty"`
	Notes       string   `json:"notes,omitempty"`
}

// extractUserProfile extracts user profile from input parameters.
func extractUserProfile(input map[string]any) UserProfile {
	profile := UserProfile{
		Goal:          "maintenance",
		MealsPerDay:   3,
		ActivityLevel: "moderate",
	}

	if goal, ok := input["goal"].(string); ok {
		profile.Goal = goal
	}
	if cal, ok := input["daily_calories"].(float64); ok {
		profile.DailyCalories = cal
	}
	if meals, ok := input["meals_per_day"].(float64); ok {
		profile.MealsPerDay = int(meals)
	}
	if rest, ok := input["restrictions"].([]any); ok {
		for _, r := range rest {
			if s, ok := r.(string); ok {
				profile.Restrictions = append(profile.Restrictions, s)
			}
		}
	}
	if allergies, ok := input["allergies"].([]any); ok {
		for _, a := range allergies {
			if s, ok := a.(string); ok {
				profile.Allergies = append(profile.Allergies, s)
			}
		}
	}
	if prefs, ok := input["preferences"].([]any); ok {
		for _, p := range prefs {
			if s, ok := p.(string); ok {
				profile.Preferences = append(profile.Preferences, s)
			}
		}
	}
	if dislikes, ok := input["dislikes"].([]any); ok {
		for _, d := range dislikes {
			if s, ok := d.(string); ok {
				profile.Dislikes = append(profile.Dislikes, s)
			}
		}
	}
	if activity, ok := input["activity_level"].(string); ok {
		profile.ActivityLevel = activity
	}

	return profile
}

// calculateMacroTargets calculates macro targets based on user profile.
func calculateMacroTargets(profile UserProfile) MacroTargets {
	// Calculate protein based on goal (0.8-1.2g per lb bodyweight for muscle, 1.2-1.6g for weight loss)
	proteinMultiplier := 1.0
	carbMultiplier := 0.5
	fatMultiplier := 0.3

	switch profile.Goal {
	case "weight-loss":
		proteinMultiplier = 1.2
		carbMultiplier = 0.4
		fatMultiplier = 0.3
	case "muscle-gain":
		proteinMultiplier = 1.1
		carbMultiplier = 0.55
		fatMultiplier = 0.25
	case "weight-gain":
		proteinMultiplier = 0.9
		carbMultiplier = 0.6
		fatMultiplier = 0.3
	}

	// Activity level adjustments
	activityMultiplier := 1.0
	switch profile.ActivityLevel {
	case "sedentary":
		activityMultiplier = 0.9
	case "light":
		activityMultiplier = 1.0
	case "moderate":
		activityMultiplier = 1.1
	case "active":
		activityMultiplier = 1.2
	case "very-active":
		activityMultiplier = 1.3
	}

	// Calculate calories per macro (protein and carbs = 4 cal/g, fat = 9 cal/g)
	proteinCalories := profile.DailyCalories * 0.3 * proteinMultiplier
	carbCalories := profile.DailyCalories * carbMultiplier * activityMultiplier
	fatCalories := profile.DailyCalories * fatMultiplier

	targets := MacroTargets{
		Protein: proteinCalories / 4,
		Carbs:   carbCalories / 4,
		Fat:     fatCalories / 9,
		Fiber:   14, // grams per 1000 calories
	}

	// Distribute calories across meals
	switch profile.MealsPerDay {
	case 2:
		targets.Breakfast = profile.DailyCalories * 0.35
		targets.Lunch = profile.DailyCalories * 0.40
		targets.Dinner = profile.DailyCalories * 0.25
	case 3:
		targets.Breakfast = profile.DailyCalories * 0.25
		targets.Lunch = profile.DailyCalories * 0.40
		targets.Dinner = profile.DailyCalories * 0.25
		targets.Snacks = profile.DailyCalories * 0.10
	case 4:
		targets.Breakfast = profile.DailyCalories * 0.25
		targets.Lunch = profile.DailyCalories * 0.30
		targets.Dinner = profile.DailyCalories * 0.25
		targets.Snacks = profile.DailyCalories * 0.20
	default:
		targets.Breakfast = profile.DailyCalories * 0.25
		targets.Lunch = profile.DailyCalories * 0.40
		targets.Dinner = profile.DailyCalories * 0.25
		targets.Snacks = profile.DailyCalories * 0.10
	}

	return targets
}

// generateMealPlan generates a meal plan based on targets.
func generateMealPlan(profile UserProfile, targets MacroTargets) []Meal {
	meals := []Meal{}

	// Breakfast
	meals = append(meals, Meal{
		Name:     "Breakfast",
		Time:     "7:00 AM",
		Calories: targets.Breakfast,
		Protein:  targets.Protein * 0.30,
		Carbs:    targets.Carbs * 0.35,
		Fat:      targets.Fat * 0.25,
		Notes:    getMealNotes(profile, "breakfast"),
	})

	// Lunch
	meals = append(meals, Meal{
		Name:     "Lunch",
		Time:     "12:30 PM",
		Calories: targets.Lunch,
		Protein:  targets.Protein * 0.35,
		Carbs:    targets.Carbs * 0.40,
		Fat:      targets.Fat * 0.35,
		Notes:    getMealNotes(profile, "lunch"),
	})

	// Dinner
	meals = append(meals, Meal{
		Name:     "Dinner",
		Time:     "6:30 PM",
		Calories: targets.Dinner,
		Protein:  targets.Protein * 0.30,
		Carbs:    targets.Carbs * 0.20,
		Fat:      targets.Fat * 0.35,
		Notes:    getMealNotes(profile, "dinner"),
	})

	// Snacks
	if profile.MealsPerDay > 3 || (profile.MealsPerDay == 3 && targets.Snacks > 100) {
		meals = append(meals, Meal{
			Name:     "Snacks",
			Time:     "3:00 PM & 8:00 PM",
			Calories: targets.Snacks,
			Protein:  targets.Protein * 0.05,
			Carbs:    targets.Carbs * 0.05,
			Fat:      targets.Fat * 0.05,
			Notes:    "Healthy snacks like nuts, fruits, or yogurt",
		})
	}

	return meals
}

// getMealNotes returns meal-specific notes based on restrictions.
func getMealNotes(profile UserProfile, mealType string) string {
	for _, restriction := range profile.Restrictions {
		switch restriction {
		case "vegetarian":
			return "Include plant-based protein sources"
		case "vegan":
			return "Ensure all animal products are excluded"
		case "gluten-free":
			return "Use gluten-free grains and alternatives"
		case "dairy-free":
			return "Use non-dairy alternatives"
		case "nut-free":
			return "Ensure all nut products are excluded"
		}
	}
	return ""
}

// formatMealPlanSummary creates a summary of the meal plan.
func formatMealPlanSummary(profile UserProfile, targets MacroTargets, meals []Meal) string {
	totalCalories := 0.0
	for _, meal := range meals {
		totalCalories += meal.Calories
	}

	return fmt.Sprintf("%s plan: ~%.0f cal/day, %.0fg protein, %.0fg carbs, %.0fg fat across %d meals",
		profile.Goal, totalCalories, targets.Protein, targets.Carbs, targets.Fat, len(meals))
}

// generateMealPlanTips generates helpful tips based on user profile.
func generateMealPlanTips(profile UserProfile) []string {
	tips := []string{}

	switch profile.Goal {
	case "weight-loss":
		tips = append(tips, "Focus on protein-rich foods to maintain muscle mass")
		tips = append(tips, "Drink plenty of water before meals")
		tips = append(tips, "Avoid eating after dinner")
	case "muscle-gain":
		tips = append(tips, "Eat protein within 30 minutes after workouts")
		tips = append(tips, "Complex carbs before training for energy")
		tips = append(tips, "Get adequate sleep for muscle recovery")
	case "weight-gain":
		tips = append(tips, "Add healthy calorie-dense foods like nuts and avocados")
		tips = append(tips, "Eat more frequent, smaller meals")
	}

	if len(profile.Restrictions) > 0 {
		tips = append(tips, fmt.Sprintf("Remember your dietary restrictions: %v", profile.Restrictions))
	}

	return tips
}
