package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// DDGProvider implements SearchProvider for DuckDuckGo HTML API (free, no API key required).
type DDGProvider struct {
	timeout time.Duration
	baseURL string
}

// DDGResponse represents the DuckDuckGo API response.
type DDGResponse struct {
	Results []DDGResult `json:"Results"`
}

// DDGResult represents a single DuckDuckGo search result.
type DDGResult struct {
	Title       string `json:"Title"`
	URL         string `json:"URL"`
	Description string `json:"Description"`
}

// NewDDGProvider creates a new DuckDuckGo provider.
func NewDDGProvider(timeout time.Duration) *DDGProvider {
	return &DDGProvider{
		timeout: timeout,
		baseURL: "https://api.duckduckgo.com/",
	}
}

// Name returns the provider name.
func (p *DDGProvider) Name() string {
	return "duckduckgo"
}

// IsConfigured always returns true for DuckDuckGo (no API key required).
func (p *DDGProvider) IsConfigured() bool {
	return true
}

// Search performs a search using DuckDuckGo API.
func (p *DDGProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Build URL with query parameters
	params := url.Values{}
	params.Set("q", req.Query)
	params.Set("format", "json")
	params.Set("no_html", "1")
	params.Set("skip_disambig", "1")

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", p.baseURL+"?"+params.Encode(), nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "Mozilla/5.0 (compatible; ARIA/1.0)")

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
	var ddgResp DDGResponse
	if err := json.NewDecoder(resp.Body).Decode(&ddgResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert to SearchResponse
	// DuckDuckGo API returns RelatedTopics which contain the actual results
	results := make([]SearchResult, 0, len(ddgResp.Results))
	citations := make([]string, 0, len(ddgResp.Results))
	sources := make([]string, 0, len(ddgResp.Results))

	for _, r := range ddgResp.Results {
		if r.URL == "" {
			continue
		}
		results = append(results, SearchResult{
			Title:       cleanHTML(r.Title),
			URL:         r.URL,
			Description: cleanHTML(r.Description),
			Content:     cleanHTML(r.Description),
		})
		citations = append(citations, r.URL)
		sources = append(sources, r.URL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d results from DuckDuckGo", len(results)),
	}, nil
}

// cleanHTML removes HTML tags from a string.
func cleanHTML(s string) string {
	// Simple HTML tag removal
	s = strings.ReplaceAll(s, "<b>", "")
	s = strings.ReplaceAll(s, "</b>", "")
	s = strings.ReplaceAll(s, "<em>", "")
	s = strings.ReplaceAll(s, "</em>", "")
	s = strings.ReplaceAll(s, "&amp;", "&")
	s = strings.ReplaceAll(s, "&lt;", "<")
	s = strings.ReplaceAll(s, "&gt;", ">")
	s = strings.ReplaceAll(s, "&quot;", "\"")
	s = strings.ReplaceAll(s, "&#39;", "'")
	return strings.TrimSpace(s)
}
