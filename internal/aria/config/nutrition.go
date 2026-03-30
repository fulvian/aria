package config

import "os"

type NutritionConfig struct {
	Enabled bool
	// Provider settings
	USDA_APIKey             string
	OpenFoodFacts_UserAgent string
	MealDB_APIKey           string
	OpenFDA_APIKey          string
	// Defaults
	DefaultLocale           string
	DefaultCountry          string
	MaxDailyPlans           int
	EnableMedicalGuardrails bool
}

func DefaultNutritionConfig() NutritionConfig {
	return NutritionConfig{
		Enabled:                 getEnvBool("ARIA_AGENCIES_NUTRITION_ENABLED", false),
		USDA_APIKey:             os.Getenv("ARIA_NUTRITION_USDA_API_KEY"),
		OpenFoodFacts_UserAgent: getEnv("ARIA_NUTRITION_OPENFOODFACTS_USER_AGENT", "ARIA/1.0"),
		MealDB_APIKey:           getEnv("ARIA_NUTRITION_MEALDB_API_KEY", "1"),
		OpenFDA_APIKey:          os.Getenv("ARIA_NUTRITION_OPENFDA_API_KEY"),
		DefaultLocale:           getEnv("ARIA_NUTRITION_DEFAULT_LOCALE", "en-US"),
		DefaultCountry:          getEnv("ARIA_NUTRITION_DEFAULT_COUNTRY", "US"),
		MaxDailyPlans:           getEnvInt("ARIA_NUTRITION_MAX_DAILY_PLANS", 20),
		EnableMedicalGuardrails: getEnvBool("ARIA_NUTRITION_ENABLE_MEDICAL_GUARDRAILS", true),
	}
}

func (c NutritionConfig) IsConfigured() bool {
	return c.Enabled && c.USDA_APIKey != ""
}
