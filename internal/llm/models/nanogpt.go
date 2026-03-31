package models

// NanoGPT model IDs for Pro plan with weekly token allocation
const (
	ProviderNanoGPT ModelProvider = "nanogpt"

	// Pro plan models with weekly token allocation
	NanoGPTMistralLarge3      ModelID = "mistralai/mistral-large-3-675b-instruct-2512"
	NanoGPTGLM51Thinking      ModelID = "zai-org/glm-5.1:thinking"
	NanoGPTKimiK25Thinking    ModelID = "moonshotai/kimi-k2.5:thinking"
	NanoGPTDeepseekV3Speciale ModelID = "deepseek/deepseek-v3.2-speciale"
	NanoGPTDeepseekR10528     ModelID = "deepseek-ai/DeepSeek-R1-0528"
	NanoGPTQwen35Thinking     ModelID = "qwen/qwen3.5-397b-a17b-thinking"
	NanoGPTNemotronUltra253B  ModelID = "nvidia/Llama-3.1-Nemotron-Ultra-253B-v1"
	NanoGPTGPTOss120b         ModelID = "openai/gpt-oss-120b"
)

// NanoGPTModels contains all NanoGPT Pro plan models
var NanoGPTModels = map[ModelID]Model{
	NanoGPTMistralLarge3: {
		ID:                  NanoGPTMistralLarge3,
		Name:                "NanoGPT Pro – Mistral Large 3",
		Provider:            ProviderNanoGPT,
		APIModel:            "mistralai/mistral-large-3-675b-instruct-2512",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           false,
		SupportsAttachments: true,
	},

	NanoGPTGLM51Thinking: {
		ID:                  NanoGPTGLM51Thinking,
		Name:                "NanoGPT Pro – GLM-5.1 Thinking",
		Provider:            ProviderNanoGPT,
		APIModel:            "zai-org/glm-5.1:thinking",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       1_000_000,
		DefaultMaxTokens:    32_000,
		CanReason:           true,
		SupportsAttachments: true,
	},

	NanoGPTKimiK25Thinking: {
		ID:                  NanoGPTKimiK25Thinking,
		Name:                "NanoGPT Pro – Kimi K2.5 Thinking",
		Provider:            ProviderNanoGPT,
		APIModel:            "moonshotai/kimi-k2.5:thinking",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           true,
		SupportsAttachments: true,
	},

	NanoGPTDeepseekV3Speciale: {
		ID:                  NanoGPTDeepseekV3Speciale,
		Name:                "NanoGPT Pro – DeepSeek V3.2 Speciale",
		Provider:            ProviderNanoGPT,
		APIModel:            "deepseek/deepseek-v3.2-speciale",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           true,
		SupportsAttachments: true,
	},

	NanoGPTDeepseekR10528: {
		ID:                  NanoGPTDeepseekR10528,
		Name:                "NanoGPT Pro – DeepSeek R1 0528",
		Provider:            ProviderNanoGPT,
		APIModel:            "deepseek-ai/DeepSeek-R1-0528",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           true,
		SupportsAttachments: true,
	},

	NanoGPTQwen35Thinking: {
		ID:                  NanoGPTQwen35Thinking,
		Name:                "NanoGPT Pro – Qwen 3.5 397B Thinking",
		Provider:            ProviderNanoGPT,
		APIModel:            "qwen/qwen3.5-397b-a17b-thinking",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           true,
		SupportsAttachments: true,
	},

	NanoGPTNemotronUltra253B: {
		ID:                  NanoGPTNemotronUltra253B,
		Name:                "NanoGPT Pro – NVIDIA Nemotron Ultra 253B",
		Provider:            ProviderNanoGPT,
		APIModel:            "nvidia/Llama-3.1-Nemotron-Ultra-253B-v1",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           false,
		SupportsAttachments: true,
	},

	NanoGPTGPTOss120b: {
		ID:                  NanoGPTGPTOss120b,
		Name:                "NanoGPT Pro – GPT OSS 120B",
		Provider:            ProviderNanoGPT,
		APIModel:            "openai/gpt-oss-120b",
		CostPer1MIn:         0, // Pro plan with weekly token allocation
		CostPer1MInCached:   0,
		CostPer1MOutCached:  0,
		CostPer1MOut:        0,
		ContextWindow:       128_000,
		DefaultMaxTokens:    32_000,
		CanReason:           false,
		SupportsAttachments: true,
	},
}
