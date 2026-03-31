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

// WikipediaProvider implements SearchProvider for Wikipedia API.
type WikipediaProvider struct {
	timeout time.Duration
	baseURL string
}

// WikipediaResponse represents the Wikipedia API response.
type WikipediaResponse struct {
	Query *WikipediaQuery `json:"query,omitempty"`
}

// WikipediaQuery represents the query part of Wikipedia response.
type WikipediaQuery struct {
	Pages map[string]WikipediaPage `json:"pages"`
}

// WikipediaPage represents a Wikipedia page in search results.
type WikipediaPage struct {
	PageID  int    `json:"pageid"`
	Title   string `json:"title"`
	Extract string `json:"extract,omitempty"`
	FullURL string `json:"fullurl,omitempty"`
}

// NewWikipediaProvider creates a new Wikipedia provider.
func NewWikipediaProvider(timeout time.Duration) *WikipediaProvider {
	return &WikipediaProvider{
		timeout: timeout,
		baseURL: "https://en.wikipedia.org/w/api.php",
	}
}

// Name returns the provider name.
func (p *WikipediaProvider) Name() string {
	return "wikipedia"
}

// IsConfigured always returns true for Wikipedia (no API key required).
func (p *WikipediaProvider) IsConfigured() bool {
	return true
}

// Search performs a search using Wikipedia API.
func (p *WikipediaProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Build URL with query parameters for search
	params := url.Values{}
	params.Set("action", "query")
	params.Set("list", "search")
	params.Set("srsearch", req.Query)
	params.Set("srlimit", fmt.Sprintf("%d", req.MaxResults))
	params.Set("format", "json")
	params.Set("origin", "*")

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", p.baseURL+"?"+params.Encode(), nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0 (https://github.com/fulvian/aria)")

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
	var wikiResp WikipediaSearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&wikiResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(wikiResp.Query.Search))
	citations := make([]string, 0, len(wikiResp.Query.Search))
	sources := make([]string, 0, len(wikiResp.Query.Search))

	for _, r := range wikiResp.Query.Search {
		pageURL := fmt.Sprintf("https://en.wikipedia.org/wiki/%s", strings.ReplaceAll(url.QueryEscape(r.Title), "+", "_"))
		results = append(results, SearchResult{
			Title:       r.Title,
			URL:         pageURL,
			Description: r.Snippet,
			Content:     r.Snippet,
			PublishedAt: r.Timestamp,
		})
		citations = append(citations, pageURL)
		sources = append(sources, pageURL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d results from Wikipedia", len(results)),
	}, nil
}

// WikipediaSearchResponse represents Wikipedia search API response.
type WikipediaSearchResponse struct {
	Query *WikipediaSearchQuery `json:"query"`
}

// WikipediaSearchQuery represents the query part of Wikipedia search response.
type WikipediaSearchQuery struct {
	Search []WikipediaSearchResult `json:"search"`
}

// WikipediaSearchResult represents a single Wikipedia search result.
type WikipediaSearchResult struct {
	PageID    int    `json:"pageid"`
	Title     string `json:"title"`
	Snippet   string `json:"snippet"`
	Timestamp string `json:"timestamp"`
}
