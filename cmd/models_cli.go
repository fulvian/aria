package cmd

import (
	"fmt"
	"slices"
	"strings"

	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/llm/models"
	"github.com/joho/godotenv"
	"github.com/spf13/cobra"
)

func init() {
	rootCmd.AddCommand(modelsCmd)
	rootCmd.AddCommand(providersCmd)
}

// modelsCmd displays all available models grouped by provider
var modelsCmd = &cobra.Command{
	Use:   "models",
	Short: "List all available models",
	Long: `Display all available models grouped by provider.
Shows only models from providers that are configured and enabled.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		// Load .env file automatically if present
		_ = godotenv.Load()

		cfg, err := config.Load("", false)
		if err != nil {
			return fmt.Errorf("failed to load config: %w", err)
		}

		enabledProviders := getEnabledProvidersWithConfig(cfg)
		if len(enabledProviders) == 0 {
			fmt.Println("No providers configured. Configure API keys in ~/.aria.json")
			return nil
		}

		currentModel := cfg.Agents[config.AgentCoder].Model

		for _, provider := range enabledProviders {
			providerModels := getModelsForProvider(provider)
			if len(providerModels) == 0 {
				continue
			}

			// Get provider display name
			providerDisplay := getProviderDisplayName(provider)
			fmt.Printf("\n📦 %s\n", providerDisplay)
			fmt.Println(strings.Repeat("─", len(providerDisplay)+3))

			for _, model := range providerModels {
				selected := ""
				if model.ID == currentModel {
					selected = " ✓"
				}
				canReason := ""
				if model.CanReason {
					canReason = " 🧠"
				}
				fmt.Printf("  • %s%s%s\n", model.Name, canReason, selected)
			}
		}

		return nil
	},
}

// providersCmd displays all configured providers and their status
var providersCmd = &cobra.Command{
	Use:   "providers",
	Short: "List all configured providers",
	Long: `Display all configured providers and their status.
Shows API key status, enabled/disabled state, and provider priority.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		// Load .env file automatically if present
		_ = godotenv.Load()

		cfg, err := config.Load("", false)
		if err != nil {
			return fmt.Errorf("failed to load config: %w", err)
		}

		fmt.Println("Configured Providers")
		fmt.Println(strings.Repeat("═", 50))

		// Get sorted providers
		var allProviders []models.ModelProvider
		for provider := range cfg.Providers {
			allProviders = append(allProviders, provider)
		}

		// Sort by popularity
		slices.SortFunc(allProviders, func(a, b models.ModelProvider) int {
			return models.ProviderPopularity[a] - models.ProviderPopularity[b]
		})

		for i, provider := range allProviders {
			providerCfg := cfg.Providers[provider]
			apiKeyStatus := "❌ Not set"
			if providerCfg.APIKey != "" {
				apiKeyStatus = "✅ Set"
			}

			status := "⚠️  Disabled"
			if !providerCfg.Disabled {
				status = "✅ Enabled"
			}

			priority := models.ProviderPopularity[provider]
			providerDisplay := getProviderDisplayName(provider)

			fmt.Printf("%d. %s\n", i+1, providerDisplay)
			fmt.Printf("   Provider ID: %s\n", provider)
			fmt.Printf("   API Key: %s | Status: %s\n", apiKeyStatus, status)
			fmt.Printf("   Priority: %d\n", priority)

			// Show number of models for this provider
			modelCount := len(getModelsForProvider(provider))
			if modelCount > 0 {
				fmt.Printf("   Models: %d available\n", modelCount)
			}

			// Show current default model if this is the active provider
			currentModel := cfg.Agents[config.AgentCoder].Model
			if models.SupportedModels[currentModel].Provider == provider {
				fmt.Printf("   Current default: %s\n", models.SupportedModels[currentModel].Name)
			}

			if i < len(allProviders)-1 {
				fmt.Println()
			}
		}

		fmt.Println()
		fmt.Println("Legend:")
		fmt.Println("  ✅ = Configured/enabled  ❌ = Not set  ⚠️  = Disabled")
		fmt.Printf("\nUse 'aria use-model <provider/model>' to switch models.\n")

		return nil
	},
}

// useModelCmd allows switching the model via CLI
var useModelCmd = &cobra.Command{
	Use:   "use-model [provider/]model",
	Short: "Switch to a different model",
	Long: `Switch the default model for the coder agent.

Examples:
  aria use-model nanogpt/glm-5.1:thinking
  aria use-model mistralai/mistral-large-3-675b-instruct-2512
  aria use-model glm-5.1:thinking
  aria use-model gpt-4.1`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		// Load .env file automatically if present
		_ = godotenv.Load()

		cfg, err := config.Load("", false)
		if err != nil {
			return fmt.Errorf("failed to load config: %w", err)
		}

		modelArg := args[0]
		modelID, provider := resolveModelID(modelArg, cfg)

		if modelID == "" {
			return fmt.Errorf("model not found: %s", modelArg)
		}

		// Verify model exists
		model, exists := models.SupportedModels[modelID]
		if !exists {
			return fmt.Errorf("unknown model: %s", modelID)
		}

		// Verify provider is enabled
		providerCfg, providerExists := cfg.Providers[provider]
		if !providerExists || providerCfg.Disabled {
			return fmt.Errorf("provider %s is not enabled. Run 'aria providers' to see available providers", provider)
		}

		// Update config
		err = config.UpdateAgentModel(config.AgentCoder, modelID)
		if err != nil {
			return fmt.Errorf("failed to update config: %w", err)
		}

		// Also update other agents that were using the same provider
		coderModel := cfg.Agents[config.AgentCoder].Model
		for _, agentName := range []config.AgentName{config.AgentSummarizer, config.AgentTask} {
			if cfg.Agents[agentName].Model == coderModel || models.SupportedModels[cfg.Agents[agentName].Model].Provider == provider {
				// Update to same model if it was same provider
				if models.SupportedModels[cfg.Agents[agentName].Model].Provider == provider {
					config.UpdateAgentModel(agentName, modelID)
				}
			}
		}

		fmt.Printf("✅ Switched to %s (%s)\n", model.Name, provider)
		return nil
	},
}

// resolveModelID resolves a model ID from user input
// Input can be: "provider/model", "model" (partial match), or full model ID
func resolveModelID(input string, cfg *config.Config) (models.ModelID, models.ModelProvider) {
	// Check if input contains "/" (full provider/model format)
	if strings.Contains(input, "/") {
		// Try exact match first
		for id, model := range models.SupportedModels {
			fullName := string(model.Provider) + "/" + strings.Split(string(id), "/")[len(strings.Split(string(id), "/"))-1]
			if strings.EqualFold(fullName, input) || strings.EqualFold(string(id), input) {
				return id, model.Provider
			}
		}
		// Try matching just the APIModel
		for id, model := range models.SupportedModels {
			if strings.EqualFold(model.APIModel, input) {
				return id, model.Provider
			}
		}
	}

	// Try to find by model ID suffix (e.g., "glm-5.1" matches "zai-org/glm-5.1:thinking")
	inputLower := strings.ToLower(input)
	for id, model := range models.SupportedModels {
		// Check if model ID ends with the input (without provider prefix)
		parts := strings.Split(string(id), "/")
		if len(parts) >= 2 {
			modelSuffix := strings.ToLower(parts[len(parts)-1])
			if strings.Contains(modelSuffix, inputLower) || modelSuffix == inputLower {
				return id, model.Provider
			}
		}
		// Also check APIModel
		if strings.Contains(strings.ToLower(model.APIModel), inputLower) {
			return id, model.Provider
		}
	}

	// Try exact model ID match
	for id, model := range models.SupportedModels {
		if strings.EqualFold(string(id), input) {
			return id, model.Provider
		}
	}

	return "", ""
}

// getEnabledProvidersWithConfig returns enabled providers sorted by popularity
func getEnabledProvidersWithConfig(cfg *config.Config) []models.ModelProvider {
	var providers []models.ModelProvider
	for providerId, provider := range cfg.Providers {
		if !provider.Disabled && provider.APIKey != "" {
			providers = append(providers, providerId)
		}
	}

	slices.SortFunc(providers, func(a, b models.ModelProvider) int {
		return models.ProviderPopularity[a] - models.ProviderPopularity[b]
	})

	return providers
}

// getProviderDisplayName returns a human-readable provider name
func getProviderDisplayName(provider models.ModelProvider) string {
	switch provider {
	case models.ProviderNanoGPT:
		return "NanoGPT (Pro)"
	case models.ProviderZAI:
		return "ZAI"
	case models.ProviderAnthropic:
		return "Anthropic"
	case models.ProviderOpenAI:
		return "OpenAI"
	case models.ProviderGemini:
		return "Google Gemini"
	case models.ProviderGROQ:
		return "Groq"
	case models.ProviderOpenRouter:
		return "OpenRouter"
	case models.ProviderBedrock:
		return "AWS Bedrock"
	case models.ProviderAzure:
		return "Azure OpenAI"
	case models.ProviderVertexAI:
		return "Google Vertex AI"
	case models.ProviderCopilot:
		return "GitHub Copilot"
	case models.ProviderXAI:
		return "xAI"
	case models.ProviderLocal:
		return "Local/LM Studio"
	default:
		return string(provider)
	}
}

// getModelsForProvider returns all models for a given provider
func getModelsForProvider(provider models.ModelProvider) []models.Model {
	var providerModels []models.Model
	for _, model := range models.SupportedModels {
		if model.Provider == provider {
			providerModels = append(providerModels, model)
		}
	}

	// Sort by name (reverse alphabetical - latest models first if naming is consistent)
	slices.SortFunc(providerModels, func(a, b models.Model) int {
		if a.Name > b.Name {
			return -1
		} else if a.Name < b.Name {
			return 1
		}
		return 0
	})

	return providerModels
}
