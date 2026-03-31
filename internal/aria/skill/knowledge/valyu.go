package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ValyuProvider implements SearchProvider for Valyu API (semantic academic search).
type ValyuProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// ValyuResponse represents the Valyu API response.
type ValyuResponse struct {
	Success       bool          `json:"success"`
	Type          string        `json:"type"`
	Query         string        `json:"query"`
	ResultCount   int           `json:"result_count"`
	Results       []ValyuResult `json:"results"`
	Cost          float64       `json:"cost"`
	SetupRequired bool          `json:"setup_required,omitempty"`
	Error         string        `json:"error,omitempty"`
}

// ValyuResult represents a single Valyu search result.
type ValyuResult struct {
	Title          string   `json:"title"`
	URL            string   `json:"url"`
	Content        string   `json:"content"`
	Source         string   `json:"source"`
	RelevanceScore float64  `json:"relevance_score"`
	Images         []string `json:"images"`
}

// NewValyuProvider creates a new Valyu provider.
func NewValyuProvider(apiKey string, timeout time.Duration) *ValyuProvider {
	return &ValyuProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.valyu.ai/v1/search",
	}
}

// Name returns the provider name.
func (p *ValyuProvider) Name() string {
	return "valyu"
}

// IsConfigured returns true if API key is provided.
func (p *ValyuProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs semantic search using Valyu API.
func (p *ValyuProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build URL with query params
	url := fmt.Sprintf("%s?query=%s&included_sources=valyu/valyu-arxiv&max_results=%d",
		p.baseURL,
		req.Query,
		req.MaxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", url, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("X-API-Key", p.apiKey)

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("Valyu request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("Valyu unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var valyuResp ValyuResponse
	if err := json.NewDecoder(resp.Body).Decode(&valyuResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse Valyu response: %w", err)
	}

	if !valyuResp.Success {
		if valyuResp.SetupRequired {
			return SearchResponse{}, fmt.Errorf("Valyu API key required - get one free at https://platform.valyu.ai")
		}
		return SearchResponse{}, fmt.Errorf("Valyu search failed: %s", valyuResp.Error)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(valyuResp.Results))
	citations := make([]string, 0, len(valyuResp.Results))
	sources := make([]string, 0, len(valyuResp.Results))

	for _, r := range valyuResp.Results {
		results = append(results, SearchResult{
			Title:       r.Title,
			URL:         r.URL,
			Description: truncateString(r.Content, 300),
			Content:     r.Content,
			PublishedAt: "",
		})
		citations = append(citations, r.URL)
		sources = append(sources, r.Source)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d results from Valyu semantic search (arxiv, full-text)", valyuResp.ResultCount),
	}, nil
}

// truncateString truncates a string to maxLen characters.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
