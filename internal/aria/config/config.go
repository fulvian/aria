// Package config provides ARIA-specific configuration loaded from environment variables.
// This is completely separate from opencode/kilocode config via viper.
package config

import (
	"os"
	"strconv"
)

// Config holds ARIA-specific configuration loaded from environment variables.
// This is completely separate from opencode/kilocode config.
type Config struct {
	Enabled bool

	Routing    RoutingConfig
	Agencies   AgenciesConfig
	Skills     SkillsConfig
	Scheduler  SchedulerConfig
	Guardrails GuardrailsConfig
}

// RoutingConfig defines routing behavior.
type RoutingConfig struct {
	DefaultAgency       string
	ConfidenceThreshold float64
	EnableFallback      bool
}

// AgenciesConfig defines which agencies are enabled.
type AgenciesConfig struct {
	Development DevelopmentAgencyConfig
	Weather     WeatherAgencyConfig
}

// WeatherAgencyConfig defines the weather agency configuration.
type WeatherAgencyConfig struct {
	Enabled bool
}

// DevelopmentAgencyConfig defines the development agency configuration.
type DevelopmentAgencyConfig struct {
	Enabled     bool
	CoderBridge bool
}

// SkillsConfig defines skill availability.
type SkillsConfig struct {
	CodeReview bool
	TDD        bool
	Debugging  bool
}

// SchedulerConfig defines task scheduling behavior.
type SchedulerConfig struct {
	MaxConcurrentTasks        int
	DefaultPriority           int
	DispatchIntervalMs        int
	RecurringLookaheadMinutes int
	RecoveryPolicy            string
}

// GuardrailsConfig defines guardrail behavior.
type GuardrailsConfig struct {
	AllowProactive  bool
	MaxDailyActions int
}

// Load reads ARIA configuration from environment variables with ARIA_ prefix.
// Returns a Config with sensible defaults if env vars are not set.
func Load() *Config {
	cfg := &Config{
		Enabled: getEnvBool("ARIA_ENABLED", false),
		Routing: RoutingConfig{
			DefaultAgency:       getEnv("ARIA_ROUTING_DEFAULT_AGENCY", "development"),
			ConfidenceThreshold: getEnvFloat("ARIA_ROUTING_CONFIDENCE_THRESHOLD", 0.7),
			EnableFallback:      getEnvBool("ARIA_ROUTING_ENABLE_FALLBACK", true),
		},
		Agencies: AgenciesConfig{
			Development: DevelopmentAgencyConfig{
				Enabled:     getEnvBool("ARIA_AGENCIES_DEVELOPMENT_ENABLED", true),
				CoderBridge: getEnvBool("ARIA_AGENCIES_DEVELOPMENT_CODER_BRIDGE", true),
			},
			Weather: WeatherAgencyConfig{
				Enabled: getEnvBool("ARIA_AGENCIES_WEATHER_ENABLED", true),
			},
		},
		Skills: SkillsConfig{
			CodeReview: getEnvBool("ARIA_SKILLS_CODE_REVIEW", true),
			TDD:        getEnvBool("ARIA_SKILLS_TDD", true),
			Debugging:  getEnvBool("ARIA_SKILLS_DEBUGGING", true),
		},
		Scheduler: SchedulerConfig{
			MaxConcurrentTasks:        getEnvInt("ARIA_SCHEDULER_MAX_CONCURRENT_TASKS", 3),
			DefaultPriority:           getEnvInt("ARIA_SCHEDULER_DEFAULT_PRIORITY", 50),
			DispatchIntervalMs:        getEnvInt("ARIA_SCHEDULER_DISPATCH_INTERVAL_MS", 1000),
			RecurringLookaheadMinutes: getEnvInt("ARIA_SCHEDULER_RECURRING_LOOKAHEAD_MINUTES", 60),
			RecoveryPolicy:            getEnv("ARIA_SCHEDULER_RECOVERY_POLICY", "requeue"),
		},
		Guardrails: GuardrailsConfig{
			AllowProactive:  getEnvBool("ARIA_GUARDRAILS_ALLOW_PROACTIVE", false),
			MaxDailyActions: getEnvInt("ARIA_GUARDRAILS_MAX_DAILY_ACTIONS", 10),
		},
	}
	return cfg
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

func getEnvBool(key string, defaultVal bool) bool {
	if v := os.Getenv(key); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
	}
	return defaultVal
}

func getEnvFloat(key string, defaultVal float64) float64 {
	if v := os.Getenv(key); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return defaultVal
}
