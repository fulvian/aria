// Package skill provides skill implementations for the ARIA system.
package skill

import (
	"context"
	"time"

	"github.com/fulvian/aria/internal/aria/skill/knowledge"
)

// WebResearchSkill implements the web research skill.
type WebResearchSkill struct {
	providerChain *knowledge.ProviderChain
}

// NewWebResearchSkill creates a new WebResearchSkill.
func NewWebResearchSkill(chain *knowledge.ProviderChain) *WebResearchSkill {
	return &WebResearchSkill{
		providerChain: chain,
	}
}

// Name returns the skill name.
func (s *WebResearchSkill) Name() SkillName {
	return SkillWebResearch
}

// Description returns the skill description.
func (s *WebResearchSkill) Description() string {
	return "Performs web research using search providers to find information on a topic"
}

// RequiredTools returns the tools required by this skill.
func (s *WebResearchSkill) RequiredTools() []ToolName {
	return nil // Uses direct API calls, not tools
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *WebResearchSkill) RequiredMCPs() []MCPName {
	return nil
}

// Execute performs web research.
func (s *WebResearchSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	// Extract parameters
	query := extractString(params.Input, "query")
	if query == "" {
		query = extractString(params.Context, "query")
	}
	if query == "" {
		return SkillResult{
			Success:    false,
			Error:      "query is required",
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	maxResults := extractInt(params.Input, "max_results", 10)
	language := extractString(params.Input, "language")
	if language == "" {
		language = "en"
	}

	// Perform search
	searchResp, err := s.providerChain.Search(ctx, knowledge.SearchRequest{
		Query:      query,
		MaxResults: maxResults,
		Language:   language,
	})

	if err != nil {
		return SkillResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	// Check if search returned an error
	if searchResp.Error != "" {
		return SkillResult{
			Success:    false,
			Error:      searchResp.Error,
			DurationMs: time.Since(start).Milliseconds(),
		}, nil
	}

	// Format results
	sources := make([]map[string]any, len(searchResp.Results))
	for i, r := range searchResp.Results {
		sources[i] = map[string]any{
			"title":       r.Title,
			"url":         r.URL,
			"description": r.Description,
			"content":     r.Content,
			"published":   r.PublishedAt,
		}
	}

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"query":         query,
			"sources":       sources,
			"summary":       searchResp.Summary,
			"citations":     searchResp.Citations,
			"total_results": len(searchResp.Results),
		},
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// CanExecute checks if the skill can execute with the given parameters.
func (s *WebResearchSkill) CanExecute(ctx context.Context) (bool, string) {
	if s.providerChain == nil {
		return false, "no search providers configured"
	}
	return true, ""
}

// extractString extracts a string from a map.
func extractString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// extractInt extracts an int from a map.
func extractInt(m map[string]any, key string, defaultVal int) int {
	if v, ok := m[key].(int); ok {
		return v
	}
	if v, ok := m[key].(int64); ok {
		return int(v)
	}
	if v, ok := m[key].(float64); ok {
		return int(v)
	}
	return defaultVal
}
