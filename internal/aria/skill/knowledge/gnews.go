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

// GNewsProvider implements SearchProvider for GNews API.
// GNews provides news from 80,000+ sources with up to 6 years of historical data.
// API documentation: https://gnews.io/
type GNewsProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// GNewsResponse represents the response from GNews API.
type GNewsResponse struct {
	TotalArticles int            `json:"totalArticles"`
	Articles      []GNewsArticle `json:"articles"`
}

// GNewsArticle represents a single article from GNews.
type GNewsArticle struct {
	Title       string      `json:"title"`
	Description string      `json:"description"`
	Content     string      `json:"content"`
	URL         string      `json:"url"`
	Image       string      `json:"image"`
	PublishedAt string      `json:"publishedAt"`
	Source      GNewsSource `json:"source"`
}

// GNewsSource represents the source of a GNews article.
type GNewsSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
}

// NewGNewsProvider creates a new GNews provider.
func NewGNewsProvider(apiKey string, timeout time.Duration) *GNewsProvider {
	return &GNewsProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://gnews.io/api/v4",
	}
}

// Name returns the provider name.
func (p *GNewsProvider) Name() string {
	return "gnews"
}

// IsConfigured returns true if GNews is properly configured.
func (p *GNewsProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using GNews API.
func (p *GNewsProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build search URL
	urlStr := fmt.Sprintf("%s/search", p.baseURL)

	params := url.Values{}
	params.Set("apikey", p.apiKey)
	params.Set("q", req.Query)
	params.Set("lang", "en")
	params.Set("max", fmt.Sprintf("%d", req.MaxResults))

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("GNews request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("GNews unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp GNewsResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse GNews response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(apiResp.Articles))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, article := range apiResp.Articles {
		results = append(results, SearchResult{
			Title:       article.Title,
			URL:         article.URL,
			Description: article.Description,
			Content:     article.Content,
			PublishedAt: article.PublishedAt,
		})
		citations = append(citations, article.URL)
		sources = append(sources, article.Source.Name)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d articles from GNews (total: %d, 80,000+ sources)", len(apiResp.Articles), apiResp.TotalArticles),
	}, nil
}

// GetTopHeadlines retrieves top headlines for a topic.
func (p *GNewsProvider) GetTopHeadlines(ctx context.Context, topic string, country string) ([]GNewsArticle, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	urlStr := fmt.Sprintf("%s/top-headlines", p.baseURL)

	params := url.Values{}
	params.Set("apikey", p.apiKey)
	if topic != "" {
		params.Set("topic", topic)
	}
	if country != "" {
		params.Set("country", country)
	}
	params.Set("lang", "en")
	params.Set("max", "10")

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("GNews request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GNews unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp GNewsResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return apiResp.Articles, nil
}
