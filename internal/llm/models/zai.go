package models

const (
	ProviderZAI ModelProvider = "zai"

	GLM51     ModelID = "glm-5.1"
	GLM5Turbo ModelID = "glm-5-turbo"
	GLM47     ModelID = "glm-4.7"
	GLM46     ModelID = "glm-4.6"
	GLM45Air  ModelID = "glm-4.5-air"
)

var ZAIModels = map[ModelID]Model{
	GLM51: {
		ID:                  GLM51,
		Name:                "GLM-5.1",
		Provider:            ProviderZAI,
		APIModel:            "GLM-5.1",
		CostPer1MIn:         0,
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       1_000_000,
		DefaultMaxTokens:    8000,
		SupportsAttachments: true,
	},
	GLM5Turbo: {
		ID:                  GLM5Turbo,
		Name:                "GLM-5 Turbo",
		Provider:            ProviderZAI,
		APIModel:            "GLM-5-Turbo",
		CostPer1MIn:         0,
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       1_000_000,
		DefaultMaxTokens:    8000,
		SupportsAttachments: true,
	},
	GLM47: {
		ID:                  GLM47,
		Name:                "GLM-4.7",
		Provider:            ProviderZAI,
		APIModel:            "GLM-4.7",
		CostPer1MIn:         0,
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       1_000_000,
		DefaultMaxTokens:    8000,
		SupportsAttachments: true,
	},
	GLM46: {
		ID:                  GLM46,
		Name:                "GLM-4.6",
		Provider:            ProviderZAI,
		APIModel:            "GLM-4.6",
		CostPer1MIn:         0,
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       1_000_000,
		DefaultMaxTokens:    8000,
		SupportsAttachments: true,
	},
	GLM45Air: {
		ID:                  GLM45Air,
		Name:                "GLM-4.5 Air",
		Provider:            ProviderZAI,
		APIModel:            "GLM-4.5-Air",
		CostPer1MIn:         0,
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       1_000_000,
		DefaultMaxTokens:    8000,
		SupportsAttachments: true,
	},
}
