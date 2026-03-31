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

// BingProvider implements SearchProvider for Bing Search API.
type BingProvider struct {
	apiKey   string
	endpoint string
	timeout  time.Duration
}

// BingResponse represents the Bing API response.
type BingResponse struct {
	Type            string       `json:"type"`
	QueryContext    BingContext  `json:"queryContext"`
	WebPages        BingWebPages `json:"webPages"`
	Images          interface{}  `json:"images"`
	News            interface{}  `json:"news"`
	RelatedSearches interface{}  `json:"relatedSearches"`
	RankingResponse interface{}  `json:"rankingResponse"`
}

// BingContext represents the query context.
type BingContext struct {
	OriginalQuery string `json:"originalQuery"`
}

// BingWebPages represents the web pages result.
type BingWebPages struct {
	WebSearchURL          string     `json:"webSearchUrl"`
	TotalEstimatedMatches int64      `json:"totalEstimatedMatches"`
	Value                 []BingPage `json:"value"`
}

// BingPage represents a single Bing search result.
type BingPage struct {
	ID              string     `json:"id"`
	Name            string     `json:"name"`
	URL             string     `json:"url"`
	IsNavigational  bool       `json:"isNavigational"`
	IsTrending      bool       `json:"isTrending"`
	DisplayURL      string     `json:"displayUrl"`
	Snippet         string     `json:"snippet"`
	DateLastCrawled string     `json:"dateLastCrawled,omitempty"`
	OpenGraphImage  *BingImage `json:"openGraphImage,omitempty"`
	CachedPageURL   string     `json:"cachedPageUrl,omitempty"`
	Language        string     `json:"language,omitempty"`
}

// BingImage represents an image from Bing.
type BingImage struct {
	URL       string              `json:"url"`
	Thumbnail *BingImageThumbnail `json:"thumbnail,omitempty"`
}

// BingImageThumbnail represents a thumbnail image.
type BingImageThumbnail struct {
	Width  int    `json:"width"`
	Height int    `json:"height"`
	Source string `json:"sourceUrl"`
}

// NewBingProvider creates a new Bing provider.
func NewBingProvider(apiKey string, timeout time.Duration) *BingProvider {
	return &BingProvider{
		apiKey:   apiKey,
		endpoint: "https://api.bing.microsoft.com/v7.0/search",
		timeout:  timeout,
	}
}

// Name returns the provider name.
func (p *BingProvider) Name() string {
	return "bing"
}

// IsConfigured returns true if Bing API key is provided.
func (p *BingProvider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using Bing API.
func (p *BingProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Build URL with query parameters
	params := url.Values{}
	params.Set("q", req.Query)
	params.Set("count", fmt.Sprintf("%d", req.MaxResults))
	params.Set("mkt", req.Language)
	params.Set("setLang", req.Language)

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	searchURL := fmt.Sprintf("%s?%s", p.endpoint, params.Encode())
	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", searchURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Ocp-Apim-Subscription-Key", p.apiKey)
	httpReq.Header.Set("Accept", "application/json")

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
	var bingResp BingResponse
	if err := json.NewDecoder(resp.Body).Decode(&bingResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(bingResp.WebPages.Value))
	citations := make([]string, 0, len(bingResp.WebPages.Value))
	sources := make([]string, 0, len(bingResp.WebPages.Value))

	for _, r := range bingResp.WebPages.Value {
		results = append(results, SearchResult{
			Title:       r.Name,
			URL:         r.URL,
			Description: r.Snippet,
			Content:     r.Snippet,
			PublishedAt: r.DateLastCrawled,
		})
		citations = append(citations, r.URL)
		sources = append(sources, r.URL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d results from Bing", len(results)),
	}, nil
}
