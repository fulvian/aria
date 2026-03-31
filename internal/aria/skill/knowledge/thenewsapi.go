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

// TheNewsAPIProvider implements SearchProvider for The News API.
// The News API provides free access to live and historical news from 40,000+ sources.
// API documentation: https://www.thenewsapi.com/documentation
type TheNewsAPIProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// TheNewsAPIResponse represents the response from The News API.
type TheNewsAPIResponse struct {
	Meta *TheNewsAPIMeta     `json:"meta,omitempty"`
	Data []TheNewsAPIArticle `json:"data"`
}

// TheNewsAPIMeta contains metadata about the response.
type TheNewsAPIMeta struct {
	Found    int `json:"found"`
	Returned int `json:"returned"`
	Limit    int `json:"limit"`
	Page     int `json:"page"`
}

// TheNewsAPIArticle represents a single article from The News API.
type TheNewsAPIArticle struct {
	UUID           string   `json:"uuid"`
	Title          string   `json:"title"`
	Description    string   `json:"description"`
	Keywords       string   `json:"keywords"`
	Snippet        string   `json:"snippet"`
	URL            string   `json:"url"`
	ImageURL       string   `json:"image_url"`
	Language       string   `json:"language"`
	PublishedAt    string   `json:"published_at"`
	Source         string   `json:"source"`
	Categories     []string `json:"categories"`
	RelevanceScore *float64 `json:"relevance_score,omitempty"`
	Locale         string   `json:"locale"`
}

// NewTheNewsAPIProvider creates a new The News API provider.
func NewTheNewsAPIProvider(apiKey string, timeout time.Duration) *TheNewsAPIProvider {
	return &TheNewsAPIProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.thenewsapi.com/v1",
	}
}

// Name returns the provider name.
func (p *TheNewsAPIProvider) Name() string {
	return "thenewsapi"
}

// IsConfigured returns true if The News API is properly configured.
func (p *TheNewsAPIProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using The News API.
func (p *TheNewsAPIProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build search URL - use 'all' endpoint for historical search
	urlStr := fmt.Sprintf("%s/news/all", p.baseURL)

	// Add query parameters - use 'search' per API documentation
	params := url.Values{}
	params.Set("api_token", p.apiKey)
	params.Set("search", req.Query)
	params.Set("language", "en")
	if req.MaxResults > 0 {
		params.Set("limit", fmt.Sprintf("%d", req.MaxResults))
	} else {
		params.Set("limit", "10")
	}

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("TheNewsAPI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("TheNewsAPI unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp TheNewsAPIResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse TheNewsAPI response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(apiResp.Data))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, article := range apiResp.Data {
		desc := article.Description
		if desc == "" {
			desc = article.Snippet
		}
		results = append(results, SearchResult{
			Title:       article.Title,
			URL:         article.URL,
			Description: desc,
			Content:     desc,
			PublishedAt: article.PublishedAt,
		})
		citations = append(citations, article.URL)
		sources = append(sources, article.Source)
	}

	var totalFound int
	if apiResp.Meta != nil {
		totalFound = apiResp.Meta.Found
	} else {
		totalFound = len(apiResp.Data)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d articles from The News API (%d shown)", totalFound, len(results)),
	}, nil
}

// GetTopHeadlines retrieves top headlines for a locale.
func (p *TheNewsAPIProvider) GetTopHeadlines(ctx context.Context, locale string, category string) ([]TheNewsAPIArticle, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	urlStr := fmt.Sprintf("%s/news/top", p.baseURL)

	params := url.Values{}
	params.Set("api_token", p.apiKey)
	if locale != "" {
		params.Set("locale", locale)
	}
	if category != "" {
		params.Set("category", category)
	}
	params.Set("limit", "10")

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("TheNewsAPI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("TheNewsAPI unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp TheNewsAPIResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return apiResp.Data, nil
}
