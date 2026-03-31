package knowledge

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// TavilyProvider implements SearchProvider for Tavily API.
type TavilyProvider struct {
	apiKey     string
	timeout    time.Duration
	maxRetries int
	baseURL    string
}

// TavilyResponse represents the Tavily API response.
type TavilyResponse struct {
	Results []TavilyResult `json:"results"`
	Answer  string         `json:"answer,omitempty"`
}

// TavilyResult represents a single Tavily search result.
type TavilyResult struct {
	Title       string `json:"title"`
	URL         string `json:"url"`
	Description string `json:"description"`
	Content     string `json:"content"`
	PublishedAt string `json:"published_date,omitempty"`
}

// NewTavilyProvider creates a new Tavily provider.
func NewTavilyProvider(apiKey string, timeout time.Duration) *TavilyProvider {
	return &TavilyProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.tavily.com/search",
	}
}

// Name returns the provider name.
func (p *TavilyProvider) Name() string {
	return "tavily"
}

// IsConfigured returns true if Tavily is properly configured.
func (p *TavilyProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using Tavily API.
func (p *TavilyProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Prepare request body
	tavilyReq := map[string]any{
		"query":           req.Query,
		"max_results":     req.MaxResults,
		"include_answer":  true,
		"include_domains": []string{},
	}

	if req.Language != "" {
		tavilyReq["search_depth"] = "basic"
	}

	body, err := json.Marshal(tavilyReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	httpReq, err := http.NewRequestWithContext(reqCtx, "POST", p.baseURL, bytes.NewReader(body))
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)

	// Execute request with retry
	var resp *http.Response
	for attempt := 0; attempt <= p.maxRetries; attempt++ {
		if attempt > 0 {
			// Wait before retry with exponential backoff
			waitTime := time.Duration(300*attempt) * time.Millisecond
			select {
			case <-ctx.Done():
				return SearchResponse{}, ctx.Err()
			case <-time.After(waitTime):
			}
		}

		httpResp, err := http.DefaultClient.Do(httpReq)
		if err != nil {
			lastErr := err
			if attempt == p.maxRetries {
				return SearchResponse{}, fmt.Errorf("request failed after %d attempts: %w", p.maxRetries, lastErr)
			}
			continue
		}

		resp = httpResp
		break
	}

	if resp == nil {
		return SearchResponse{}, fmt.Errorf("request failed: no response")
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to read response: %w", err)
	}

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return SearchResponse{}, fmt.Errorf("unexpected status code: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var tavilyResp TavilyResponse
	if err := json.Unmarshal(respBody, &tavilyResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, len(tavilyResp.Results))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for i, r := range tavilyResp.Results {
		results[i] = SearchResult{
			Title:       r.Title,
			URL:         r.URL,
			Description: r.Description,
			Content:     r.Content,
			PublishedAt: r.PublishedAt,
		}
		citations = append(citations, r.URL)
		sources = append(sources, r.URL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   tavilyResp.Answer,
	}, nil
}
