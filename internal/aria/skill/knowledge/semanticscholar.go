package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// SemanticScholarProvider implements SearchProvider for Semantic Scholar API.
type SemanticScholarProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// SemanticScholarResponse represents the Semantic Scholar API response.
type SemanticScholarResponse struct {
	Total  int                    `json:"total"`
	Offset int                    `json:"offset"`
	Next   int                    `json:"next"`
	Data   []SemanticScholarPaper `json:"data"`
}

// SemanticScholarPaper represents a paper in Semantic Scholar.
type SemanticScholarPaper struct {
	PaperID       string `json:"paperId"`
	Title         string `json:"title"`
	Abstract      string `json:"abstract"`
	Year          int    `json:"year"`
	CitationCount int    `json:"citationCount"`
	OpenAccessPDF *struct {
		URL string `json:"url"`
	} `json:"openAccessPdf"`
	ExternalIDs *struct {
		DOI    string `json:"DOI"`
		PubMed string `json:"PubMed"`
		ArXiv  string `json:"ArXiv"`
	} `json:"externalIds"`
	Authors []struct {
		AuthorID string `json:"authorId"`
		Name     string `json:"name"`
	} `json:"authors"`
	URL   string `json:"url"`
	Venue string `json:"venue"`
}

// NewSemanticScholarProvider creates a new Semantic Scholar provider.
func NewSemanticScholarProvider(apiKey string, timeout time.Duration) *SemanticScholarProvider {
	return &SemanticScholarProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.semanticscholar.org/graph/v1/paper/search",
	}
}

// Name returns the provider name.
func (p *SemanticScholarProvider) Name() string {
	return "semanticscholar"
}

// IsConfigured returns true if API key is provided (or empty for limited access).
func (p *SemanticScholarProvider) IsConfigured() bool {
	return true // Works without API key but limited
}

// Search performs a search using Semantic Scholar API with exponential backoff for rate limits.
func (p *SemanticScholarProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Build query parameters
	params := url.Values{}
	params.Set("query", req.Query)
	params.Set("limit", fmt.Sprintf("%d", req.MaxResults))
	params.Set("offset", "0")
	params.Set("fields", "title,abstract,year,citationCount,openAccessPdf,externalIds,authors,url,venue")
	params.Set("sort", "relevance")

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	searchURL := fmt.Sprintf("%s?%s", p.baseURL, params.Encode())

	// Retry with exponential backoff for rate limit (429) responses
	maxRetries := 3
	var lastErr error

	for attempt := 0; attempt < maxRetries; attempt++ {
		if attempt > 0 {
			// Exponential backoff: 5-15 seconds + jitter
			// Semantic Scholar rate limit is 100 requests per 5 minutes
			backoffDuration := time.Duration(5+rand.Intn(10)) * time.Second
			if p.apiKey != "" {
				// With API key, backoff can be shorter
				backoffDuration = time.Duration(2+rand.Intn(3)) * time.Second
			}

			select {
			case <-ctx.Done():
				return SearchResponse{}, ctx.Err()
			case <-time.After(backoffDuration):
			}
		}

		httpReq, err := http.NewRequestWithContext(reqCtx, "GET", searchURL, nil)
		if err != nil {
			return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
		}

		httpReq.Header.Set("Accept", "application/json")
		if p.apiKey != "" {
			httpReq.Header.Set("x-api-key", p.apiKey)
		}

		// Execute request
		resp, err := http.DefaultClient.Do(httpReq)
		if err != nil {
			lastErr = fmt.Errorf("Semantic Scholar request failed: %w", err)
			continue // Retry on connection errors
		}
		defer resp.Body.Close()

		// Check for rate limiting
		if resp.StatusCode == http.StatusTooManyRequests {
			respBody, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("Semantic Scholar rate limited: %s", string(respBody))
			continue // Retry with backoff
		}

		// Check status code
		if resp.StatusCode != http.StatusOK {
			respBody, _ := io.ReadAll(resp.Body)
			return SearchResponse{}, fmt.Errorf("Semantic Scholar unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
		}

		// Parse response
		var ssResp SemanticScholarResponse
		if err := json.NewDecoder(resp.Body).Decode(&ssResp); err != nil {
			return SearchResponse{}, fmt.Errorf("failed to parse Semantic Scholar response: %w", err)
		}

		// Convert to SearchResponse
		results := make([]SearchResult, 0, len(ssResp.Data))
		citations := make([]string, 0, len(ssResp.Data))
		sources := make([]string, 0, len(ssResp.Data))

		for _, paper := range ssResp.Data {
			// Build citation info
			doi := ""
			if paper.ExternalIDs != nil && paper.ExternalIDs.DOI != "" {
				doi = fmt.Sprintf("https://doi.org/%s", paper.ExternalIDs.DOI)
			}

			// Get authors string
			authors := make([]string, len(paper.Authors))
			for i, a := range paper.Authors {
				authors[i] = a.Name
			}
			authorsStr := strings.Join(authors, ", ")
			if len(authorsStr) > 100 {
				authorsStr = authorsStr[:100] + "..."
			}

			// Get PDF URL
			pdfURL := paper.URL
			if paper.OpenAccessPDF != nil {
				pdfURL = paper.OpenAccessPDF.URL
			}

			abstract := paper.Abstract
			if abstract == "" {
				abstract = "No abstract available"
			}

			title := paper.Title
			if paper.Venue != "" {
				title = fmt.Sprintf("%s [%s]", paper.Title, paper.Venue)
			}

			description := fmt.Sprintf("%d citations | %d | %s", paper.CitationCount, paper.Year, authorsStr)

			results = append(results, SearchResult{
				Title:       title,
				URL:         paper.URL,
				Description: description,
				Content:     abstract,
				PublishedAt: fmt.Sprintf("%d", paper.Year),
			})

			if doi != "" {
				citations = append(citations, doi)
			}
			citations = append(citations, paper.URL)
			sources = append(sources, paper.URL)

			_ = pdfURL
		}

		return SearchResponse{
			Results:   results,
			Sources:   sources,
			Citations: citations,
			Summary:   fmt.Sprintf("Found %d papers from Semantic Scholar (AI-powered academic search)", len(results)),
		}, nil
	}

	return SearchResponse{}, lastErr
}
