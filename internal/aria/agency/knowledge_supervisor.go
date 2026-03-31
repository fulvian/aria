// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"context"
	"fmt"
	"strings"

	"github.com/fulvian/aria/internal/aria/contracts"
)

// TaskCategory represents the category of a task for routing.
type TaskCategory string

const (
	CategoryWebSearch  TaskCategory = "web-search"
	CategoryAcademic   TaskCategory = "academic"
	CategoryNews       TaskCategory = "news"
	CategoryCode       TaskCategory = "code"
	CategoryHistorical TaskCategory = "historical"
	CategoryGeneral    TaskCategory = "general"
	CategoryUnknown    TaskCategory = "unknown"
)

// TaskRouter routes tasks to appropriate agents based on capabilities.
type TaskRouter struct {
	agentRegistry *AgentRegistry
}

// AgentRegistry maintains a registry of available agents and their capabilities.
type AgentRegistry struct {
	agents map[contracts.AgentName]*RegisteredAgent
}

// RegisteredAgent represents an agent with its metadata.
type RegisteredAgent struct {
	Name        contracts.AgentName
	Category    TaskCategory
	Description string
	Skills      []string
	Executor    TaskExecutor
}

// TaskExecutor defines the interface for executing tasks.
type TaskExecutor interface {
	Execute(ctx context.Context, task contracts.Task) (map[string]any, error)
}

// NewAgentRegistry creates a new agent registry.
func NewAgentRegistry() *AgentRegistry {
	return &AgentRegistry{
		agents: make(map[contracts.AgentName]*RegisteredAgent),
	}
}

// Register adds an agent to the registry.
func (r *AgentRegistry) Register(agent *RegisteredAgent) {
	r.agents[agent.Name] = agent
}

// Get returns an agent by name.
func (r *AgentRegistry) Get(name contracts.AgentName) (*RegisteredAgent, error) {
	agent, ok := r.agents[name]
	if !ok {
		return nil, fmt.Errorf("agent not found: %s", name)
	}
	return agent, nil
}

// GetByCategory returns all agents that can handle a category.
func (r *AgentRegistry) GetByCategory(category TaskCategory) []*RegisteredAgent {
	var result []*RegisteredAgent
	for _, agent := range r.agents {
		if agent.Category == category {
			result = append(result, agent)
		}
	}
	return result
}

// List returns all registered agents.
func (r *AgentRegistry) List() []*RegisteredAgent {
	var result []*RegisteredAgent
	for _, agent := range r.agents {
		result = append(result, agent)
	}
	return result
}

// NewTaskRouter creates a new task router.
func NewTaskRouter(registry *AgentRegistry) *TaskRouter {
	return &TaskRouter{
		agentRegistry: registry,
	}
}

// Route determines which agent should handle a task.
func (r *TaskRouter) Route(task contracts.Task) (*RegisteredAgent, error) {
	category := r.classifyTask(task)

	// Get agents for this category
	agents := r.agentRegistry.GetByCategory(category)
	if len(agents) == 0 {
		// Fallback to general category
		agents = r.agentRegistry.GetByCategory(CategoryGeneral)
		if len(agents) == 0 {
			// Final fallback to web-search (always has agents)
			agents = r.agentRegistry.GetByCategory(CategoryWebSearch)
			if len(agents) == 0 {
				return nil, fmt.Errorf("no agent available for task: %s", task.Name)
			}
		}
	}

	// For now, return the first available agent
	// TODO: Add load balancing, agent availability, etc.
	return agents[0], nil
}

// RouteWithFallback routes to primary agent with fallback chain.
func (r *TaskRouter) RouteWithFallback(task contracts.Task) ([]*RegisteredAgent, error) {
	category := r.classifyTask(task)

	// Get agents for this category
	agents := r.agentRegistry.GetByCategory(category)
	if len(agents) == 0 {
		agents = r.agentRegistry.GetByCategory(CategoryGeneral)
	}

	if len(agents) == 0 {
		return nil, fmt.Errorf("no agent available for task: %s", task.Name)
	}

	return agents, nil
}

// classifyTask determines the category of a task.
func (r *TaskRouter) classifyTask(task contracts.Task) TaskCategory {
	desc := strings.ToLower(task.Description)
	name := strings.ToLower(task.Name)
	combined := name + " " + desc

	// Check skills first - MORE SPECIFIC patterns must come BEFORE less specific
	if len(task.Skills) > 0 {
		skill := strings.ToLower(task.Skills[0])
		switch {
		// Most specific first - check for unique identifiers
		case strings.Contains(skill, "academic"):
			return CategoryAcademic
		case strings.Contains(skill, "historical") || strings.Contains(skill, "archive"):
			return CategoryHistorical
		case strings.Contains(skill, "code") || strings.Contains(skill, "api-docs"):
			return CategoryCode
		case strings.Contains(skill, "news"):
			return CategoryNews
		case strings.Contains(skill, "web") && !strings.Contains(skill, "search"):
			return CategoryWebSearch
		case strings.Contains(skill, "search"):
			// Generic search - check description for more specific routing
			return r.classifyByDescription(combined)
		}
	}

	// No skills - use description
	return r.classifyByDescription(combined)
}

// classifyByDescription classifies based on description keywords.
func (r *TaskRouter) classifyByDescription(combined string) TaskCategory {
	// Most specific academic terms first
	if supervisorContainsAny(combined, "arxiv", "pubmed", "semantic scholar", "academic",
		"scientific", "research paper", "study", "journal", "doi", "openalex", "arxiv.org") {
		return CategoryAcademic
	}

	// News terms
	if supervisorContainsAny(combined, "news", "current events", "breaking", "headlines",
		"newspaper", "reuters", "ap news", "bbc") {
		return CategoryNews
	}

	// Code/API terms
	if supervisorContainsAny(combined, "github", "api documentation", "context7", "stackoverflow",
		"programming", "function", "library", "sdk", "sdk", "api reference") {
		return CategoryCode
	}

	// Historical terms
	if supervisorContainsAny(combined, "wayback", "archive", "chronicling america",
		"old newspaper", "historical archive", "past newspaper") {
		return CategoryHistorical
	}

	// Web search fallback
	if supervisorContainsAny(combined, "google", "find information", "look up",
		"search for", "who is", "what is", "when did", "where is", "definition of") {
		return CategoryWebSearch
	}

	// General/educational
	if supervisorContainsAny(combined, "explain", "understand", "learn", "teach", "what does", "how does") {
		return CategoryGeneral
	}

	// Compare queries should use web-search (for parallel execution)
	if supervisorContainsAny(combined, "compare", "comparison") {
		return CategoryWebSearch
	}

	return CategoryGeneral
}

// supervisorContainsAny checks if text contains any of the substrings.
func supervisorContainsAny(text string, substrs ...string) bool {
	for _, s := range substrs {
		if strings.Contains(text, s) {
			return true
		}
	}
	return false
}

// RouteToAgent routes a task to a specific agent by name.
func (r *TaskRouter) RouteToAgent(task contracts.Task, agentName contracts.AgentName) (*RegisteredAgent, error) {
	agent, err := r.agentRegistry.Get(agentName)
	if err != nil {
		return nil, err
	}
	return agent, nil
}
