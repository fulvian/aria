// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"context"
	"math"

	"github.com/fulvian/aria/internal/aria/contracts"
)

// SemanticTaskRouter uses embeddings for intelligent task routing.
// It combines semantic similarity matching with keyword-based fallback
// for robust task routing to appropriate agents.
type SemanticTaskRouter struct {
	registry        *AgentRegistry
	embeddings      Embedder
	agentEmbeddings map[TaskCategory][]float32
	threshold       float32
	fallbackRouter  *TaskRouter // Keyword-based fallback
}

// Embedder interface for getting text embeddings.
// Production implementations would use OpenAI, local models, or specialized
// embedding services. This interface allows for easy testing and swapping.
type Embedder interface {
	Encode(ctx context.Context, text string) ([]float32, error)
}

// NewSemanticTaskRouter creates a new semantic router with the given registry and embedder.
func NewSemanticTaskRouter(registry *AgentRegistry, embeddings Embedder) *SemanticTaskRouter {
	return &SemanticTaskRouter{
		registry:        registry,
		embeddings:      embeddings,
		agentEmbeddings: initAgentEmbeddings(),
		threshold:       0.65, // Configurable similarity threshold
		fallbackRouter:  NewTaskRouter(registry),
	}
}

// Route selects the best agent using semantic similarity.
// It first tries to encode the task description and find the best matching
// category based on cosine similarity. If the similarity score is below
// the threshold, it falls back to keyword-based routing.
func (r *SemanticTaskRouter) Route(ctx context.Context, task contracts.Task) (*RegisteredAgent, error) {
	// Encode task description
	queryVec, err := r.embeddings.Encode(ctx, task.Description)
	if err != nil {
		// Fallback to keyword-based routing on error
		return r.fallbackRouter.Route(task)
	}

	// Find best matching category
	bestCategory := CategoryGeneral
	bestScore := float32(0)

	for category, descVec := range r.agentEmbeddings {
		score := cosineSimilarity(queryVec, descVec)
		if score > bestScore {
			bestScore = score
			bestCategory = category
		}
	}

	// If semantic score is below threshold, use keyword fallback
	if bestScore < r.threshold {
		return r.fallbackRouter.Route(task)
	}

	// Get agents for category
	agents := r.registry.GetByCategory(bestCategory)
	if len(agents) == 0 {
		return r.fallbackRouter.Route(task)
	}

	return agents[0], nil
}

// RouteWithFallback routes using semantic matching with fallback chain.
func (r *SemanticTaskRouter) RouteWithFallback(ctx context.Context, task contracts.Task) ([]*RegisteredAgent, error) {
	// First try semantic routing
	primaryAgent, err := r.Route(ctx, task)
	if err != nil {
		return nil, err
	}

	// Build list starting with the primary agent
	var agents []*RegisteredAgent
	agents = append(agents, primaryAgent)

	// Get category from primary agent and find other agents in same category
	category := primaryAgent.Category
	categoryAgents := r.registry.GetByCategory(category)
	for _, agent := range categoryAgents {
		if agent.Name != primaryAgent.Name {
			agents = append(agents, agent)
		}
	}

	// Fallback to web-search if no other agents found
	if len(agents) == 1 { // Only the primary agent
		webSearchAgents := r.registry.GetByCategory(CategoryWebSearch)
		for _, agent := range webSearchAgents {
			if agent.Name != primaryAgent.Name {
				agents = append(agents, agent)
			}
		}
	}

	return agents, nil
}

// cosineSimilarity computes cosine similarity between two vectors.
// Returns a value between 0 and 1, where 1 means identical vectors.
func cosineSimilarity(a, b []float32) float32 {
	if len(a) != len(b) || len(a) == 0 {
		return 0
	}

	var dotProduct, normA, normB float32
	for i := range a {
		dotProduct += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}

	if normA == 0 || normB == 0 {
		return 0
	}

	return dotProduct / (float32(math.Sqrt(float64(normA))) * float32(math.Sqrt(float64(normB))))
}

// initAgentEmbeddings initializes predefined embeddings for agent categories.
// These are placeholder embeddings - in production would use trained embeddings
// from actual text vectors for each category's representative terms.
func initAgentEmbeddings() map[TaskCategory][]float32 {
	// Each category has a 10-dimensional embedding vector
	// Dimensions represent: academic, news, code, research, search,
	// historical, document, web, analysis, learn
	return map[TaskCategory][]float32{
		CategoryAcademic:   {0.9, 0.1, 0.2, 0.8, 0.3, 0.1, 0.4, 0.2, 0.5, 0.6},
		CategoryNews:       {0.1, 0.9, 0.1, 0.2, 0.4, 0.1, 0.2, 0.6, 0.3, 0.2},
		CategoryCode:       {0.2, 0.1, 0.9, 0.1, 0.2, 0.1, 0.3, 0.1, 0.4, 0.2},
		CategoryHistorical: {0.3, 0.2, 0.1, 0.4, 0.2, 0.9, 0.5, 0.2, 0.3, 0.4},
		CategoryWebSearch:  {0.3, 0.4, 0.2, 0.3, 0.8, 0.2, 0.3, 0.7, 0.4, 0.5},
		CategoryGeneral:    {0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4},
	}
}

// SetThreshold sets the similarity threshold for semantic routing.
// Tasks with similarity scores below this threshold will use keyword fallback.
func (r *SemanticTaskRouter) SetThreshold(threshold float32) {
	r.threshold = threshold
}

// GetThreshold returns the current similarity threshold.
func (r *SemanticTaskRouter) GetThreshold() float32 {
	return r.threshold
}
