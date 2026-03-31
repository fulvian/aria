// Package agency provides tests for the SemanticTaskRouter implementation.
package agency

import (
	"context"
	"strings"
	"testing"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCosineSimilarity(t *testing.T) {
	tests := []struct {
		name     string
		a        []float32
		b        []float32
		expected float32
	}{
		{
			name:     "identical vectors",
			a:        []float32{1.0, 0.0, 0.0},
			b:        []float32{1.0, 0.0, 0.0},
			expected: 1.0,
		},
		{
			name:     "orthogonal vectors",
			a:        []float32{1.0, 0.0, 0.0},
			b:        []float32{0.0, 1.0, 0.0},
			expected: 0.0,
		},
		{
			name:     "opposite vectors",
			a:        []float32{1.0, 0.0, 0.0},
			b:        []float32{-1.0, 0.0, 0.0},
			expected: -1.0,
		},
		{
			name:     "partial similarity",
			a:        []float32{1.0, 1.0, 0.0},
			b:        []float32{1.0, 0.0, 0.0},
			expected: 0.707, // ~1/sqrt(2)
		},
		{
			name:     "empty vectors",
			a:        []float32{},
			b:        []float32{},
			expected: 0.0,
		},
		{
			name:     "different length vectors",
			a:        []float32{1.0, 0.0},
			b:        []float32{1.0, 0.0, 0.0},
			expected: 0.0,
		},
		{
			name:     "zero vector",
			a:        []float32{0.0, 0.0, 0.0},
			b:        []float32{1.0, 1.0, 1.0},
			expected: 0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := cosineSimilarity(tt.a, tt.b)
			assert.InDelta(t, tt.expected, result, 0.01)
		})
	}
}

func TestSimpleEmbedder_Encode(t *testing.T) {
	embedder := NewSimpleEmbedder()

	tests := []struct {
		name           string
		text           string
		expectAcademic float32
		expectCode     float32
		expectNews     float32
	}{
		{
			name:           "academic text",
			text:           "find recent papers on machine learning from arxiv",
			expectAcademic: 0.8,
			expectCode:     0.2,
			expectNews:     0.2,
		},
		{
			name:           "code text",
			text:           "search github for python api implementation",
			expectAcademic: 0.2,
			expectCode:     0.8,
			expectNews:     0.2,
		},
		{
			name:           "news text",
			text:           "latest headlines about current events",
			expectAcademic: 0.2,
			expectCode:     0.2,
			expectNews:     0.8,
		},
		{
			name:           "neutral text",
			text:           "hello world",
			expectAcademic: 0.2,
			expectCode:     0.2,
			expectNews:     0.2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			vec, err := embedder.Encode(context.Background(), tt.text)
			require.NoError(t, err)
			assert.Len(t, vec, 10)
			assert.Equal(t, tt.expectAcademic, vec[0])
			assert.Equal(t, tt.expectCode, vec[2])
			assert.Equal(t, tt.expectNews, vec[1])
		})
	}
}

func TestSemanticTaskRouter_Route_SemanticMatch(t *testing.T) {
	// Create registry with test agents
	registry := NewAgentRegistry()
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Web search agent",
		Skills:      []string{"web-research"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Academic research agent",
		Skills:      []string{"academic-search"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentNews,
		Category:    CategoryNews,
		Description: "News agent",
		Skills:      []string{"news-search"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentCodeResearch,
		Category:    CategoryCode,
		Description: "Code research agent",
		Skills:      []string{"code-search"},
	})

	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	tests := []struct {
		name        string
		task        contracts.Task
		expectedCat TaskCategory
	}{
		{
			name: "academic query with arxiv keyword",
			task: contracts.Task{
				ID:          "task-1",
				Name:        "research paper",
				Description: "trova paper su arxiv",
			},
			expectedCat: CategoryAcademic,
		},
		{
			name: "news query semantically matches",
			task: contracts.Task{
				ID:          "task-2",
				Name:        "news search",
				Description: "cerca notizie recenti",
			},
			expectedCat: CategoryNews,
		},
		{
			name: "code query with programming keyword",
			task: contracts.Task{
				ID:          "task-3",
				Name:        "code search",
				Description: "cerca codice programming github",
			},
			expectedCat: CategoryCode,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			agent, err := router.Route(context.Background(), tt.task)
			require.NoError(t, err)
			assert.Equal(t, tt.expectedCat, agent.Category)
		})
	}
}

func TestSemanticTaskRouter_Route_Fallback(t *testing.T) {
	// Create registry with test agents
	registry := NewAgentRegistry()
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Web search agent",
		Skills:      []string{"web-research"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Academic research agent",
		Skills:      []string{"academic-search"},
	})

	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)
	router.SetThreshold(0.95) // Set high threshold to force fallback

	task := contracts.Task{
		ID:          "task-fallback",
		Name:        "search",
		Description: "cercalo su arxiv",
	}

	agent, err := router.Route(context.Background(), task)
	require.NoError(t, err)
	// Should use keyword fallback since similarity will be low
	assert.NotNil(t, agent)
}

func TestSemanticTaskRouter_Route_EmptyCategory(t *testing.T) {
	// Create registry without agents for the semantic match
	registry := NewAgentRegistry()
	// Only register a web search agent
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Web search agent",
		Skills:      []string{"web-research"},
	})

	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	task := contracts.Task{
		ID:          "task-empty",
		Name:        "academic search",
		Description: "find research paper",
	}

	// Should fallback to web search since academic category is empty
	agent, err := router.Route(context.Background(), task)
	require.NoError(t, err)
	assert.Equal(t, CategoryWebSearch, agent.Category)
}

func TestSemanticTaskRouter_RouteWithFallback(t *testing.T) {
	registry := NewAgentRegistry()
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Web search agent",
		Skills:      []string{"web-research"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Academic research agent",
		Skills:      []string{"academic-search"},
	})

	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	task := contracts.Task{
		ID:          "task-fallback-chain",
		Name:        "research",
		Description: "trova paper recenti su ML",
	}

	agents, err := router.RouteWithFallback(context.Background(), task)
	require.NoError(t, err)
	assert.NotEmpty(t, agents)
}

func TestSemanticTaskRouter_Threshold(t *testing.T) {
	registry := NewAgentRegistry()
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Web search agent",
		Skills:      []string{"web-research"},
	})

	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	// Test default threshold
	assert.Equal(t, float32(0.65), router.GetThreshold())

	// Test setting threshold
	router.SetThreshold(0.5)
	assert.Equal(t, float32(0.5), router.GetThreshold())
}

func TestSemanticTaskRouter_Embeddings(t *testing.T) {
	registry := NewAgentRegistry()
	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	// Verify agent embeddings are initialized
	assert.NotNil(t, router.agentEmbeddings)
	assert.Len(t, router.agentEmbeddings, 6) // 6 categories

	// Check that all expected categories are present
	expectedCategories := []TaskCategory{
		CategoryAcademic,
		CategoryNews,
		CategoryCode,
		CategoryHistorical,
		CategoryWebSearch,
		CategoryGeneral,
	}

	for _, cat := range expectedCategories {
		vec, ok := router.agentEmbeddings[cat]
		assert.True(t, ok, "Expected category %s to be in embeddings", cat)
		assert.Len(t, vec, 10, "Expected embedding vector of length 10 for category %s", cat)
	}
}

func TestSemanticTaskRouter_Integration(t *testing.T) {
	// Integration test with full registry (like knowledge agency)
	registry := NewAgentRegistry()

	// Register all knowledge agents
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Web search agent",
		Skills:      []string{"web-research"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Academic research agent",
		Skills:      []string{"academic-search"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentNews,
		Category:    CategoryNews,
		Description: "News agent",
		Skills:      []string{"news-search"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentCodeResearch,
		Category:    CategoryCode,
		Description: "Code research agent",
		Skills:      []string{"code-search"},
	})
	registry.Register(&RegisteredAgent{
		Name:        AgentHistorical,
		Category:    CategoryHistorical,
		Description: "Historical research agent",
		Skills:      []string{"historical-search"},
	})

	embedder := NewSimpleEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	tests := []struct {
		name        string
		description string
		expectedCat TaskCategory
	}{
		{
			name:        "italian academic query",
			description: "trova paper su arxiv machine learning",
			expectedCat: CategoryAcademic,
		},
		{
			name:        "italian news query",
			description: "cerca notizie recenti",
			expectedCat: CategoryNews,
		},
		{
			name:        "italian code query",
			description: "cerca codice programming github",
			expectedCat: CategoryCode,
		},
		{
			name:        "italian historical query",
			description: "cerca archivi storici",
			expectedCat: CategoryHistorical,
		},
		{
			name:        "italian search query",
			description: "cerca informazioni su",
			expectedCat: CategoryWebSearch,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			task := contracts.Task{
				ID:          "integration-test",
				Name:        "search",
				Description: tt.description,
			}

			agent, err := router.Route(context.Background(), task)
			require.NoError(t, err)
			assert.Equal(t, tt.expectedCat, agent.Category,
				"Expected category %s but got %s for description: %s",
				tt.expectedCat, agent.Category, tt.description)
		})
	}
}

// mockEmbedder is a test embedder that returns predefined vectors
type mockEmbedder struct {
	vectors map[string][]float32
}

func newMockEmbedder() *mockEmbedder {
	return &mockEmbedder{
		vectors: map[string][]float32{
			"academic": {0.9, 0.1, 0.2, 0.8, 0.3, 0.1, 0.4, 0.2, 0.5, 0.6},
			"news":     {0.1, 0.9, 0.1, 0.2, 0.4, 0.1, 0.2, 0.6, 0.3, 0.2},
			"code":     {0.2, 0.1, 0.9, 0.1, 0.2, 0.1, 0.3, 0.1, 0.4, 0.2},
			"search":   {0.3, 0.4, 0.2, 0.3, 0.8, 0.2, 0.3, 0.7, 0.4, 0.5},
		},
	}
}

func (m *mockEmbedder) Encode(ctx context.Context, text string) ([]float32, error) {
	// Return a vector based on text keywords
	lower := strings.ToLower(text)
	for key, vec := range m.vectors {
		if strings.Contains(lower, key) {
			return vec, nil
		}
	}
	// Default to search vector
	return m.vectors["search"], nil
}

func TestSemanticTaskRouter_MockEmbedder(t *testing.T) {
	registry := NewAgentRegistry()
	registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Academic research agent",
		Skills:      []string{"academic-search"},
	})

	embedder := newMockEmbedder()
	router := NewSemanticTaskRouter(registry, embedder)

	task := contracts.Task{
		ID:          "mock-test",
		Name:        "research",
		Description: "academic paper search",
	}

	agent, err := router.Route(context.Background(), task)
	require.NoError(t, err)
	assert.Equal(t, CategoryAcademic, agent.Category)
}
