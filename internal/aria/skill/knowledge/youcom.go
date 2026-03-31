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

// YouProvider implements SearchProvider for You.com API.
// You.com provides LLM-optimized search with real-time results and citations.
type YouProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// YouSearchResponse represents the You.com search API response.
type YouSearchResponse struct {
	Hits []YouHit `json:"hits"`
}

// YouHit represents a single search hit.
type YouHit struct {
	URL         string `json:"url"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Age         string `json:"age"`
	Thumbnail   string `json:"thumbnail"`
	Language    string `json:"language"`
	Country     string `json:"country"`
}

// YouNewsResponse represents news search results.
type YouNewsResponse struct {
	Hits []YouNewsHit `json:"hits"`
}

// YouNewsHit represents a news article.
type YouNewsHit struct {
	URL         string `json:"url"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Age         string `json:"age"`
	Source      string `json:"source"`
	Thumbnail   string `json:"thumbnail"`
}

// YouDeepSearchResponse represents deep search results.
type YouDeepSearchResponse struct {
	Results []YouDeepResult `json:"results"`
}

// YouDeepResult represents a deep search result with expanded content.
type YouDeepResult struct {
	Title       string `json:"title"`
	URL         string `json:"url"`
	Description string `json:"description"`
	Content     string `json:"content"`
	PublishedAt string `json:"publishedAt"`
	Author      string `json:"author"`
	Source      string `json:"source"`
}

// NewYouProvider creates a new You.com provider.
// You.com has a free tier with API access.
func NewYouProvider(timeout time.Duration) *YouProvider {
	return &YouProvider{
		timeout: timeout,
		baseURL: "https://api.ydc.ninja",
	}
}

// NewYouProviderWithKey creates a You.com provider with API key.
func NewYouProviderWithKey(apiKey string, timeout time.Duration) *YouProvider {
	return &YouProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.ydc.ninja",
	}
}

// Name returns the provider name.
func (p *YouProvider) Name() string {
	return "youcom"
}

// IsConfigured returns true - You.com works with or without API key (rate limited without).
func (p *YouProvider) IsConfigured() bool {
	return true
}

// Search performs a search using You.com API.
func (p *YouProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	maxResults := req.MaxResults
	if maxResults == 0 {
		maxResults = 10
	}

	query := url.QueryEscape(req.Query)

	// You.com search endpoint
	urlStr := fmt.Sprintf("%s/search?q=%s&num=%d", p.baseURL, query, maxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodGet, urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("You.com request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("You.com unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var youResp YouSearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&youResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse You.com response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(youResp.Hits))
	citations := make([]string, 0, len(youResp.Hits))
	sources := make([]string, 0, len(youResp.Hits))

	for _, hit := range youResp.Hits {
		results = append(results, SearchResult{
			Title:       hit.Title,
			URL:         hit.URL,
			Description: hit.Description,
			Content:     "",
			PublishedAt: hit.Age,
		})
		citations = append(citations, hit.URL)
		sources = append(sources, extractDomainYou(hit.URL))
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d results from You.com (LLM-optimized search)", len(results)),
	}, nil
}

// SearchNews performs a news search using You.com API.
func (p *YouProvider) SearchNews(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	maxResults := req.MaxResults
	if maxResults == 0 {
		maxResults = 10
	}

	query := url.QueryEscape(req.Query)

	// You.com news endpoint
	urlStr := fmt.Sprintf("%s/news?q=%s&num=%d", p.baseURL, query, maxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodGet, urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("You.com news request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("You.com news unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var newsResp YouNewsResponse
	if err := json.NewDecoder(resp.Body).Decode(&newsResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse You.com news response: %w", err)
	}

	results := make([]SearchResult, 0, len(newsResp.Hits))
	citations := make([]string, 0, len(newsResp.Hits))
	sources := make([]string, 0, len(newsResp.Hits))

	for _, hit := range newsResp.Hits {
		results = append(results, SearchResult{
			Title:       hit.Title,
			URL:         hit.URL,
			Description: hit.Description,
			Content:     fmt.Sprintf("Source: %s", hit.Source),
			PublishedAt: hit.Age,
		})
		citations = append(citations, hit.URL)
		sources = append(sources, hit.Source)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d news results from You.com", len(results)),
	}, nil
}

// DeepSearch performs a deep search using You.com API for comprehensive results.
func (p *YouProvider) DeepSearch(ctx context.Context, req SearchRequest) (*YouDeepSearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	maxResults := req.MaxResults
	if maxResults == 0 {
		maxResults = 10
	}

	query := url.QueryEscape(req.Query)

	// You.com deep search endpoint
	urlStr := fmt.Sprintf("%s/deep?q=%s&num=%d", p.baseURL, query, maxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodGet, urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("You.com deep search request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("You.com deep search unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var deepResp YouDeepSearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&deepResp); err != nil {
		return nil, fmt.Errorf("failed to parse You.com deep search response: %w", err)
	}

	return &deepResp, nil
}

// GetMCPConfig returns the MCP server configuration for You.com integration.
func (p *YouProvider) GetMCPConfig() map[string]interface{} {
	return map[string]interface{}{
		"name":        "youcom",
		"description": "You.com MCP server for LLM-optimized web search and deep research",
		"github":      "https://github.com/you com/you-mcp",
		"features":    []string{"web search", "news search", "deep search", "real-time results"},
	}
}

// extractDomainYou extracts domain from URL.
func extractDomainYou(urlStr string) string {
	parsed, err := url.Parse(urlStr)
	if err != nil {
		return urlStr
	}
	return strings.TrimPrefix(parsed.Host, "www.")
}

// SearchWithContent performs a search and fetches content for top results.
// This is useful for getting full article content alongside search results.
func (p *YouProvider) SearchWithContent(ctx context.Context, req SearchRequest, contentFetcher func(context.Context, string) (string, error)) ([]SearchResult, error) {
	// First perform the search
	resp, err := p.Search(ctx, req)
	if err != nil {
		return nil, err
	}

	// Fetch content for top results (limit to avoid rate limiting)
	maxContentFetch := req.MaxResults
	if maxContentFetch > 5 {
		maxContentFetch = 5
	}

	for i := 0; i < maxContentFetch && i < len(resp.Results); i++ {
		content, err := contentFetcher(ctx, resp.Results[i].URL)
		if err != nil {
			continue // Skip failed content fetches
		}
		resp.Results[i].Content = content
	}

	return resp.Results, nil
}
