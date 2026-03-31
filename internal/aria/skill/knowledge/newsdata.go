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

// NewsDataProvider implements SearchProvider for NewsData.io API.
// NewsData.io provides real-time and historical news from 206 countries.
// API documentation: https://newsdata.io/documentation
type NewsDataProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// NewsDataResponse represents the response from NewsData.io API.
type NewsDataResponse struct {
	Status       string            `json:"status"`
	TotalResults int               `json:"totalResults"`
	Results      []NewsDataArticle `json:"results"`
	NextPage     string            `json:"nextPage,omitempty"`
}

// NewsDataArticle represents a single article from NewsData.io.
type NewsDataArticle struct {
	ArticleID      string   `json:"article_id"`
	Title          string   `json:"title"`
	Link           string   `json:"link"`
	Keywords       []string `json:"keywords,omitempty"`
	Creator        []string `json:"creator,omitempty"`
	VideoURL       string   `json:"video_url,omitempty"`
	Description    string   `json:"description,omitempty"`
	Content        string   `json:"content,omitempty"`
	PubDate        string   `json:"pubDate"`
	ImageURL       string   `json:"image_url,omitempty"`
	SourceID       string   `json:"source_id"`
	SourceName     string   `json:"source_name"`
	SourceURL      string   `json:"source_url,omitempty"`
	SourcePriority int      `json:"source_priority,omitempty"`
	Country        []string `json:"country,omitempty"`
	Category       []string `json:"category,omitempty"`
	Language       string   `json:"language"`
}

// NewNewsDataProvider creates a new NewsData.io provider.
func NewNewsDataProvider(apiKey string, timeout time.Duration) *NewsDataProvider {
	return &NewsDataProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://newsdata.io/api/1",
	}
}

// Name returns the provider name.
func (p *NewsDataProvider) Name() string {
	return "newsdata"
}

// IsConfigured returns true if NewsData.io is properly configured.
func (p *NewsDataProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using NewsData.io API.
func (p *NewsDataProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build search URL
	urlStr := fmt.Sprintf("%s/news", p.baseURL)

	params := url.Values{}
	params.Set("apikey", p.apiKey)
	params.Set("q", req.Query)
	params.Set("language", "en")
	params.Set("size", fmt.Sprintf("%d", req.MaxResults))
	if req.Region != "" {
		params.Set("country", req.Region)
	}

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("NewsData request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("NewsData unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp NewsDataResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse NewsData response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(apiResp.Results))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, article := range apiResp.Results {
		content := article.Description
		if content == "" {
			content = article.Content
		}

		results = append(results, SearchResult{
			Title:       article.Title,
			URL:         article.Link,
			Description: article.Description,
			Content:     content,
			PublishedAt: article.PubDate,
		})
		citations = append(citations, article.Link)
		sources = append(sources, article.SourceName)
	}

	summary := fmt.Sprintf("Found %d articles from NewsData.io (total: %d)", len(apiResp.Results), apiResp.TotalResults)

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   summary,
	}, nil
}

// GetLatest retrieves the latest news.
func (p *NewsDataProvider) GetLatest(ctx context.Context, category string, country string) ([]NewsDataArticle, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	urlStr := fmt.Sprintf("%s/news", p.baseURL)

	params := url.Values{}
	params.Set("apikey", p.apiKey)
	if category != "" {
		params.Set("category", category)
	}
	if country != "" {
		params.Set("country", country)
	}
	params.Set("language", "en")
	params.Set("size", "10")

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("NewsData request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("NewsData unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp NewsDataResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return apiResp.Results, nil
}
