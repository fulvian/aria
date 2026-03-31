package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// BraveProvider implements SearchProvider for Brave Search API.
type BraveProvider struct {
	apiKey     string
	timeout    time.Duration
	maxRetries int
	baseURL    string
}

// BraveResponse represents the Brave API response.
type BraveResponse struct {
	WebResults BraveWebResults `json:"web"`
}

// BraveWebResults wraps the web search results.
type BraveWebResults struct {
	Results []BraveResult `json:"results"`
}

// BraveResult represents a single Brave search result.
type BraveResult struct {
	Title       string `json:"title"`
	URL         string `json:"url"`
	Description string `json:"description"`
	PageAge     string `json:"page_age,omitempty"`
}

// NewBraveProvider creates a new Brave provider.
func NewBraveProvider(apiKey string, timeout time.Duration) *BraveProvider {
	return &BraveProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.search.brave.com/res/v1/web/search",
	}
}

// Name returns the provider name.
func (p *BraveProvider) Name() string {
	return "brave"
}

// IsConfigured returns true if Brave is properly configured.
func (p *BraveProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using Brave API.
func (p *BraveProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Build URL with query parameters
	params := url.Values{}
	params.Set("q", req.Query)
	params.Set("count", fmt.Sprintf("%d", req.MaxResults))

	if req.Language != "" {
		params.Set("lang", req.Language)
	}

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", p.baseURL+"?"+params.Encode(), nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("X-Subscription-Token", p.apiKey)

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("unexpected status code: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var braveResp BraveResponse
	if err := json.NewDecoder(resp.Body).Decode(&braveResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(braveResp.WebResults.Results))
	citations := make([]string, 0, len(braveResp.WebResults.Results))
	sources := make([]string, 0, len(braveResp.WebResults.Results))

	for _, r := range braveResp.WebResults.Results {
		results = append(results, SearchResult{
			Title:       r.Title,
			URL:         r.URL,
			Description: r.Description,
			PublishedAt: r.PageAge,
		})
		citations = append(citations, r.URL)
		sources = append(sources, r.URL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
	}, nil
}
