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

// ChroniclingAmericaProvider implements SearchProvider for Chronicling America API.
// Chronicling America provides access to historic American newspapers from 1756-1963.
// API documentation: https://chroniclingamerica.loc.gov/about/api/
// NO API KEY REQUIRED - This is a free public API from Library of Congress.
type ChroniclingAmericaProvider struct {
	timeout time.Duration
	baseURL string
}

// ChroniclingAmericaResponse represents the response from Chronicling America API.
type ChroniclingAmericaResponse struct {
	TotalItems   int                         `json:"totalItems"`
	StartIndex   int                         `json:"startIndex"`
	ItemsPerPage int                         `json:"itemsPerPage"`
	Items        []ChroniclingAmericaArticle `json:"items"`
}

// ChroniclingAmericaArticle represents a single article from Chronicling America.
type ChroniclingAmericaArticle struct {
	Title            string `json:"title"`
	Date             string `json:"date"`
	JPEG             string `json:"jpeg"`
	PDF              string `json:"pdf"`
	OCR              string `json:"ocr"`
	SEQ              string `json:"seq"`
	Language         string `json:"language"`
	TitleAbreviation string `json:"titleAbreviation"`
	Edition          string `json:"edition"`
	Page             string `json:"page"`
	Sequence         string `json:"sequence"`
	Context          string `json:"context"`
	ID               string `json:"id"`
	Url              string `json:"url"`
}

// NewChroniclingAmericaProvider creates a new Chronicling America provider.
// No API key required - this is a free public API.
func NewChroniclingAmericaProvider(timeout time.Duration) *ChroniclingAmericaProvider {
	return &ChroniclingAmericaProvider{
		timeout: timeout,
		baseURL: "https://chroniclingamerica.loc.gov",
	}
}

// Name returns the provider name.
func (p *ChroniclingAmericaProvider) Name() string {
	return "chroniclingamerica"
}

// IsConfigured returns true - Chronicling America requires no API key.
func (p *ChroniclingAmericaProvider) IsConfigured() bool {
	return true
}

// Search performs a search using Chronicling America API.
func (p *ChroniclingAmericaProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build search URL - use the JSON API endpoint
	// Format: /search/pages/results/?date1=YYYY&date2=YYYY&searchTerms=keyword
	urlStr := fmt.Sprintf("%s/search/pages/results/", p.baseURL)

	params := url.Values{}
	params.Set("searchTerms", req.Query)
	params.Set("format", "json")
	params.Set("start", "1")
	if req.MaxResults > 0 {
		params.Set("count", fmt.Sprintf("%d", req.MaxResults))
	} else {
		params.Set("count", "10")
	}

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0 (contact@aria.ai)")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("ChroniclingAmerica request failed: %w", err)
	}
	defer resp.Body.Close()

	// Note: This API may return 200 with HTML error content for bad searches
	contentType := resp.Header.Get("Content-Type")
	if !strings.Contains(contentType, "application/json") {
		respBody, _ := io.ReadAll(resp.Body)
		// If it's HTML, try to parse anyway or return empty results
		if strings.Contains(string(respBody), "<html") {
			return SearchResponse{
				Results: []SearchResult{},
				Summary: "No historic newspaper results found in Chronicling America (1756-1963)",
			}, nil
		}
		return SearchResponse{}, fmt.Errorf("ChroniclingAmerica unexpected content type: %s", contentType)
	}

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("ChroniclingAmerica unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var apiResp ChroniclingAmericaResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		// If decode fails, return empty results (some searches return HTML on error)
		return SearchResponse{
			Results: []SearchResult{},
			Summary: "No historic newspaper results found (1756-1963)",
		}, nil
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(apiResp.Items))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, article := range apiResp.Items {
		// Build description from OCR text (truncated)
		description := article.OCR
		if len(description) > 500 {
			description = description[:500] + "..."
		}

		results = append(results, SearchResult{
			Title:       article.Title,
			URL:         article.Url,
			Description: description,
			Content:     article.OCR,
			PublishedAt: article.Date,
		})
		citations = append(citations, article.Url)
		sources = append(sources, "Chronicling America (Library of Congress)")
	}

	summary := fmt.Sprintf("Found %d historic newspaper pages from Chronicling America (1756-1963, %d total items)",
		len(apiResp.Items), apiResp.TotalItems)

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   summary,
	}, nil
}

// SearchByDate searches for newspapers within a specific date range.
func (p *ChroniclingAmericaProvider) SearchByDate(ctx context.Context, query string, date1 string, date2 string, maxResults int) ([]ChroniclingAmericaArticle, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	urlStr := fmt.Sprintf("%s/search/pages/results/", p.baseURL)

	params := url.Values{}
	params.Set("searchTerms", query)
	params.Set("date1", date1)
	params.Set("date2", date2)
	params.Set("format", "json")
	params.Set("start", "1")
	if maxResults > 0 {
		params.Set("count", fmt.Sprintf("%d", maxResults))
	} else {
		params.Set("count", "10")
	}

	fullURL := urlStr + "?" + params.Encode()

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", fullURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("ChroniclingAmerica request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("ChroniclingAmerica unexpected status: %d", resp.StatusCode)
	}

	var apiResp ChroniclingAmericaResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return apiResp.Items, nil
}
