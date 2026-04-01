package checkers

import (
	"context"
	"fmt"
	"os"

	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/llm/models"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/startup"
)

// LLMProviderChecker verifies LLM provider configuration.
type LLMProviderChecker struct {
	cwd   string
	debug bool
}

// NewLLMProviderChecker creates a new LLMProviderChecker.
func NewLLMProviderChecker(cwd string, debug bool) *LLMProviderChecker {
	return &LLMProviderChecker{
		cwd:   cwd,
		debug: debug,
	}
}

// Name returns the checker name.
func (c *LLMProviderChecker) Name() string {
	return "llm-provider"
}

// Priority returns the priority (150).
func (c *LLMProviderChecker) Priority() int {
	return 150
}

// Check verifies the LLM provider configuration is valid.
func (c *LLMProviderChecker) Check(ctx context.Context) error {
	cfg, err := config.Load(c.cwd, c.debug)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	// Check if there are any providers configured
	if len(cfg.Providers) == 0 {
		// No providers configured - this might be intentional for local-only usage
		// Check if LOCAL_ENDPOINT is set which indicates local provider usage
		if localEndpoint := os.Getenv("LOCAL_ENDPOINT"); localEndpoint != "" {
			logging.Debug("No providers configured, but LOCAL_ENDPOINT is set",
				"endpoint", localEndpoint)
			return nil
		}
		return fmt.Errorf("no LLM providers configured")
	}

	// Check for at least one enabled provider with an API key
	for providerName, provider := range cfg.Providers {
		if provider.Disabled {
			continue
		}

		// Check API key presence
		if provider.APIKey != "" {
			// Found a valid provider configuration
			logging.Debug("LLM provider configured",
				"provider", providerName,
				"hasApiKey", true)
			return nil
		}

		// Try to get from environment variable
		apiKey := getAPIKeyFromEnv(models.ModelProvider(providerName))
		if apiKey != "" {
			logging.Debug("LLM provider configured via env",
				"provider", providerName)
			return nil
		}
	}

	// No valid provider found
	return fmt.Errorf("no valid LLM provider with API key found")
}

// getAPIKeyFromEnv returns the API key from environment variable.
func getAPIKeyFromEnv(provider models.ModelProvider) string {
	envVars := map[models.ModelProvider]string{
		models.ProviderAnthropic:  "ANTHROPIC_API_KEY",
		models.ProviderOpenAI:     "OPENAI_API_KEY",
		models.ProviderGemini:     "GEMINI_API_KEY",
		models.ProviderGROQ:       "GROQ_API_KEY",
		models.ProviderOpenRouter: "OPENROUTER_API_KEY",
		models.ProviderAzure:      "AZURE_OPENAI_API_KEY",
		models.ProviderZAI:        "ZAI_API_KEY",
		models.ProviderNanoGPT:    "NANOGPT_API_KEY",
		"lmstudio":                "LMSTUDIO_API_KEY",
		"local":                   "LOCAL_ENDPOINT",
		"ollama":                  "OLLAMA_HOST",
	}

	if envVar, ok := envVars[provider]; ok {
		return os.Getenv(envVar)
	}
	return ""
}

// Ensure implementation satisfies the interface
var _ startup.Checker = (*LLMProviderChecker)(nil)
