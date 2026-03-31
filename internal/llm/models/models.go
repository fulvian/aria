package models

import "maps"

type (
	ModelID       string
	ModelProvider string
)

// EmbeddingModel represents a model that can generate embeddings.
type EmbeddingModel struct {
	ID         ModelID       `json:"id"`
	Name       string        `json:"name"`
	Provider   ModelProvider `json:"provider"`
	APIModel   string        `json:"api_model"`
	Dimensions int           `json:"dimensions"`
}

// EmbeddingModelIDs defines the IDs for available embedding models.
const (
	// OpenAI embedding models
	EmbeddingText3Small ModelID = "text-embedding-3-small"
	EmbeddingText3Large ModelID = "text-embedding-3-large"
	EmbeddingTextAda002 ModelID = "text-embedding-ada-002"

	// Local/LM Studio embedding models
	EmbeddingMXBaiLarge ModelID = "text-embedding-mxbai-embed-large-v1"
	EmbeddingNomicText  ModelID = "text-embedding-nomic-embed-text-v1.5"
)

// SupportedEmbeddingModels maps embedding model IDs to their definitions.
var SupportedEmbeddingModels = map[ModelID]EmbeddingModel{
	EmbeddingText3Small: {
		ID:         EmbeddingText3Small,
		Name:       "Text Embedding 3 Small",
		Provider:   ProviderOpenAI,
		APIModel:   "text-embedding-3-small",
		Dimensions: 1536,
	},
	EmbeddingText3Large: {
		ID:         EmbeddingText3Large,
		Name:       "Text Embedding 3 Large",
		Provider:   ProviderOpenAI,
		APIModel:   "text-embedding-3-large",
		Dimensions: 3072,
	},
	EmbeddingTextAda002: {
		ID:         EmbeddingTextAda002,
		Name:       "Text Embedding Ada 002",
		Provider:   ProviderOpenAI,
		APIModel:   "text-embedding-ada-002",
		Dimensions: 1536,
	},
	// LM Studio / Local embedding models
	EmbeddingMXBaiLarge: {
		ID:         EmbeddingMXBaiLarge,
		Name:       "MXBai Embed Large v1",
		Provider:   ProviderLocal,
		APIModel:   "text-embedding-mxbai-embed-large-v1",
		Dimensions: 1024,
	},
	EmbeddingNomicText: {
		ID:         EmbeddingNomicText,
		Name:       "Nomic Embed Text v1.5",
		Provider:   ProviderLocal,
		APIModel:   "text-embedding-nomic-embed-text-v1.5",
		Dimensions: 768,
	},
}

type Model struct {
	ID                  ModelID       `json:"id"`
	Name                string        `json:"name"`
	Provider            ModelProvider `json:"provider"`
	APIModel            string        `json:"api_model"`
	CostPer1MIn         float64       `json:"cost_per_1m_in"`
	CostPer1MOut        float64       `json:"cost_per_1m_out"`
	CostPer1MInCached   float64       `json:"cost_per_1m_in_cached"`
	CostPer1MOutCached  float64       `json:"cost_per_1m_out_cached"`
	ContextWindow       int64         `json:"context_window"`
	DefaultMaxTokens    int64         `json:"default_max_tokens"`
	CanReason           bool          `json:"can_reason"`
	SupportsAttachments bool          `json:"supports_attachments"`
}

// Model IDs
const ( // GEMINI
	// Bedrock
	BedrockClaude37Sonnet ModelID = "bedrock.claude-3.7-sonnet"
)

const (
	ProviderBedrock ModelProvider = "bedrock"
	// ForTests
	ProviderMock ModelProvider = "__mock"
)

// Providers in order of popularity
var ProviderPopularity = map[ModelProvider]int{
	ProviderZAI:        0,
	ProviderCopilot:    1,
	ProviderAnthropic:  2,
	ProviderOpenAI:     3,
	ProviderGemini:     4,
	ProviderGROQ:       5,
	ProviderOpenRouter: 6,
	ProviderBedrock:    7,
	ProviderAzure:      8,
	ProviderVertexAI:   9,
}

var SupportedModels = map[ModelID]Model{
	//
	// // GEMINI
	// GEMINI25: {
	// 	ID:                 GEMINI25,
	// 	Name:               "Gemini 2.5 Pro",
	// 	Provider:           ProviderGemini,
	// 	APIModel:           "gemini-2.5-pro-exp-03-25",
	// 	CostPer1MIn:        0,
	// 	CostPer1MInCached:  0,
	// 	CostPer1MOutCached: 0,
	// 	CostPer1MOut:       0,
	// },
	//
	// GRMINI20Flash: {
	// 	ID:                 GRMINI20Flash,
	// 	Name:               "Gemini 2.0 Flash",
	// 	Provider:           ProviderGemini,
	// 	APIModel:           "gemini-2.0-flash",
	// 	CostPer1MIn:        0.1,
	// 	CostPer1MInCached:  0,
	// 	CostPer1MOutCached: 0.025,
	// 	CostPer1MOut:       0.4,
	// },
	//
	// // Bedrock
	BedrockClaude37Sonnet: {
		ID:                 BedrockClaude37Sonnet,
		Name:               "Bedrock: Claude 3.7 Sonnet",
		Provider:           ProviderBedrock,
		APIModel:           "anthropic.claude-3-7-sonnet-20250219-v1:0",
		CostPer1MIn:        3.0,
		CostPer1MInCached:  3.75,
		CostPer1MOutCached: 0.30,
		CostPer1MOut:       15.0,
	},
}

func init() {
	maps.Copy(SupportedModels, ZAIModels)
	maps.Copy(SupportedModels, AnthropicModels)
	maps.Copy(SupportedModels, OpenAIModels)
	maps.Copy(SupportedModels, GeminiModels)
	maps.Copy(SupportedModels, GroqModels)
	maps.Copy(SupportedModels, AzureModels)
	maps.Copy(SupportedModels, OpenRouterModels)
	maps.Copy(SupportedModels, XAIModels)
	maps.Copy(SupportedModels, VertexAIGeminiModels)
	maps.Copy(SupportedModels, CopilotModels)
}
