// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"fmt"
	"sort"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
)

// ResultSynthesizer combines results from multiple agents/sources.
type ResultSynthesizer struct {
	dedupEnabled   bool
	rankingEnabled bool
	summaryEnabled bool
}

// SynthesisOptions controls synthesis behavior.
type SynthesisOptions struct {
	Deduplicate     bool
	RankResults     bool
	GenerateSummary bool
	MaxResults      int
}

// DefaultSynthesisOptions returns the default synthesis options.
func DefaultSynthesisOptions() SynthesisOptions {
	return SynthesisOptions{
		Deduplicate:     true,
		RankResults:     true,
		GenerateSummary: true,
		MaxResults:      20,
	}
}

// NewResultSynthesizer creates a new result synthesizer.
func NewResultSynthesizer() *ResultSynthesizer {
	return &ResultSynthesizer{
		dedupEnabled:   true,
		rankingEnabled: true,
		summaryEnabled: true,
	}
}

// Synthesize combines multiple results into a single coherent response.
func (s *ResultSynthesizer) Synthesize(taskID string, results []map[string]any, opts SynthesisOptions) (map[string]any, error) {
	if len(results) == 0 {
		return map[string]any{
			"task_id": taskID,
			"results": []map[string]any{},
			"count":   0,
		}, nil
	}

	// Merge all results
	allSources := s.mergeResults(results, opts.MaxResults)

	// Deduplicate if enabled
	if opts.Deduplicate {
		allSources = s.deduplicateResults(allSources)
	}

	// Rank if enabled
	if opts.RankResults {
		allSources = s.rankResults(allSources)
	}

	// Generate summary if enabled
	var summary string
	if opts.GenerateSummary {
		summary = s.generateSummary(taskID, allSources)
	}

	return map[string]any{
		"task_id":  taskID,
		"results":  allSources,
		"count":    len(allSources),
		"summary":  summary,
		"metadata": s.generateMetadata(results),
	}, nil
}

// mergeResults combines results from multiple sources.
func (s *ResultSynthesizer) mergeResults(results []map[string]any, maxResults int) []map[string]any {
	var allSources []map[string]any

	for _, result := range results {
		if result == nil {
			continue
		}

		// Extract sources from various possible formats
		switch v := result["results"].(type) {
		case []map[string]any:
			allSources = append(allSources, v...)
		case []any:
			for _, item := range v {
				if m, ok := item.(map[string]any); ok {
					allSources = append(allSources, m)
				}
			}
		case map[string]any:
			// Single result object
			allSources = append(allSources, v)
		}

		// Also check for "sources" field
		switch v := result["sources"].(type) {
		case []map[string]any:
			allSources = append(allSources, v...)
		}
	}

	// Limit results
	if maxResults > 0 && len(allSources) > maxResults {
		allSources = allSources[:maxResults]
	}

	return allSources
}

// deduplicateResults removes duplicate URLs/titles.
func (s *ResultSynthesizer) deduplicateResults(results []map[string]any) []map[string]any {
	seen := make(map[string]bool)
	var deduped []map[string]any

	for _, r := range results {
		// Use URL as primary key, fallback to title
		key := ""
		if url, ok := r["url"].(string); ok && url != "" {
			key = url
		} else if title, ok := r["title"].(string); ok && title != "" {
			key = title
		}

		if key != "" && !seen[key] {
			seen[key] = true
			deduped = append(deduped, r)
		}
	}

	return deduped
}

// rankResults sorts results by relevance (simulated).
func (s *ResultSynthesizer) rankResults(results []map[string]any) []map[string]any {
	// Simple ranking based on presence of description and content
	scored := make([]struct {
		result map[string]any
		score  int
	}, len(results))

	for i, r := range results {
		score := 0
		if _, ok := r["description"]; ok {
			score += 5
		}
		if _, ok := r["content"]; ok {
			score += 3
		}
		if _, ok := r["title"]; ok {
			score += 2
		}
		if _, ok := r["url"]; ok {
			score += 1
		}
		scored[i] = struct {
			result map[string]any
			score  int
		}{r, score}
	}

	// Sort by score descending
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	// Extract sorted results
	sorted := make([]map[string]any, len(scored))
	for i, item := range scored {
		sorted[i] = item.result
	}

	return sorted
}

// generateSummary creates a text summary of results.
func (s *ResultSynthesizer) generateSummary(taskID string, results []map[string]any) string {
	if len(results) == 0 {
		return "No results found for the query."
	}

	count := len(results)
	var sources []string
	for _, r := range results {
		if title, ok := r["title"].(string); ok {
			sources = append(sources, title)
		}
	}

	summary := fmt.Sprintf("Found %d results for task %s. ", count, taskID)
	if len(sources) > 0 {
		summary += fmt.Sprintf("Top sources include: %s", sources[0])
		if len(sources) > 1 {
			summary += fmt.Sprintf(", %s", sources[1])
		}
		if len(sources) > 2 {
			summary += fmt.Sprintf(", and %d others", len(sources)-2)
		}
	}

	return summary
}

// generateMetadata creates metadata about the synthesis.
func (s *ResultSynthesizer) generateMetadata(results []map[string]any) map[string]any {
	metadata := map[string]any{
		"synthesized_at": time.Now().Format(time.RFC3339),
		"sources_count":  len(results),
		"deduplication":  s.dedupEnabled,
		"ranking":        s.rankingEnabled,
	}

	// Count sources by type
	sourceTypes := make(map[string]int)
	for _, result := range results {
		if source, ok := result["source"].(string); ok {
			sourceTypes[source]++
		} else if agent, ok := result["agent"].(string); ok {
			sourceTypes[agent]++
		}
	}
	metadata["source_types"] = sourceTypes

	return metadata
}

// SynthesizeFromAgents synthesizes results specifically from multiple agents.
func (s *ResultSynthesizer) SynthesizeFromAgents(taskID string, agentResults map[contracts.AgentName]map[string]any) (map[string]any, error) {
	if len(agentResults) == 0 {
		return map[string]any{
			"task_id": taskID,
			"results": []map[string]any{},
			"count":   0,
		}, nil
	}

	// Convert to slice format
	var results []map[string]any
	var agentOrder []string

	for agentName, result := range agentResults {
		if result != nil {
			result["_agent_name"] = string(agentName)
			results = append(results, result)
			agentOrder = append(agentOrder, string(agentName))
		}
	}

	// Synthesize
	synth := map[string]any{
		"task_id":        taskID,
		"results":        results,
		"count":          len(results),
		"agents_used":    agentOrder,
		"synthesized_at": time.Now().Format(time.RFC3339),
	}

	return synth, nil
}

// MergeAgentResults combines results from different agents into a unified response.
func MergeAgentResults(primary map[string]any, fallback map[string]any) map[string]any {
	if primary == nil && fallback == nil {
		return nil
	}

	if primary == nil {
		return fallback
	}

	if fallback == nil {
		return primary
	}

	// Merge with primary taking precedence
	merged := make(map[string]any)

	// Copy fallback first
	for k, v := range fallback {
		merged[k] = v
	}

	// Override with primary
	for k, v := range primary {
		merged[k] = v
	}

	// Add metadata about merge
	merged["_merged"] = true
	merged["_fallback_used"] = true

	return merged
}
