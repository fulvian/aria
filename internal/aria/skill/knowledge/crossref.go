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

// CrossRefProvider implements SearchProvider for CrossRef API (DOI resolution, citations).
type CrossRefProvider struct {
	email   string // Required by CrossRef for polite pool
	timeout time.Duration
	baseURL string
}

// CrossRefResponse represents the CrossRef API response.
type CrossRefResponse struct {
	Status      string       `json:"status"`
	MessageType string       `json:"message-type"`
	Message     CrossRefWork `json:"message"`
}

// CrossRefWork represents a CrossRef work (article/book/chapter).
type CrossRefWork struct {
	DOI                 string           `json:"DOI"`
	Title               []string         `json:"title"`
	Author              []CrossRefAuthor `json:"author"`
	ContainerTitle      []string         `json:"container-title"` // Journal name
	Published           CrossRefDate     `json:"published"`
	Publisher           string           `json:"publisher"`
	Type                string           `json:"type"`
	URL                 string           `json:"URL"`
	Abstract            string           `json:"abstract"`
	Subject             []string         `json:"subject"`
	IsReferencedByCount int              `json:"is-referenced-by-count"`
}

// CrossRefAuthor represents an author in CrossRef.
type CrossRefAuthor struct {
	Given       string `json:"given"`
	Family      string `json:"family"`
	Sequence    string `json:"sequence"`
	Affiliation []struct {
		Name string `json:"name"`
	} `json:"affiliation,omitempty"`
}

// CrossRefDate represents a date in CrossRef.
type CrossRefDate struct {
	DateParts [][]int `json:"date-parts"`
}

// CrossRefWorksResponse represents a CrossRef works query response.
type CrossRefWorksResponse struct {
	Status      string `json:"status"`
	MessageType string `json:"message-type"`
	Message     struct {
		Items []CrossRefWork `json:"items"`
		Total int            `json:"total-results"`
	} `json:"message"`
}

// NewCrossRefProvider creates a new CrossRef provider.
func NewCrossRefProvider(email string, timeout time.Duration) *CrossRefProvider {
	return &CrossRefProvider{
		email:   email,
		timeout: timeout,
		baseURL: "https://api.crossref.org",
	}
}

// Name returns the provider name.
func (p *CrossRefProvider) Name() string {
	return "crossref"
}

// IsConfigured returns true if email is provided (required by CrossRef).
func (p *CrossRefProvider) IsConfigured() bool {
	return p.email != ""
}

// Search performs search using CrossRef API.
func (p *CrossRefProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build query URL
	query := url.QueryEscape(req.Query)
	urlStr := fmt.Sprintf("%s/works?query=%s&rows=%d&mailto=%s",
		p.baseURL, query, req.MaxResults, p.email)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0 (mailto:"+p.email+")")

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("CrossRef request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("CrossRef unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var worksResp CrossRefWorksResponse
	if err := json.NewDecoder(resp.Body).Decode(&worksResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse CrossRef response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(worksResp.Message.Items))
	citations := make([]string, 0, len(worksResp.Message.Items))
	sources := make([]string, 0, len(worksResp.Message.Items))

	for _, work := range worksResp.Message.Items {
		// Build author string
		authors := make([]string, 0)
		for _, author := range work.Author {
			if author.Family != "" {
				authors = append(authors, author.Family+", "+author.Given)
			}
		}

		// Get publication year
		year := ""
		if len(work.Published.DateParts) > 0 && len(work.Published.DateParts[0]) > 0 {
			year = fmt.Sprintf("%d", work.Published.DateParts[0][0])
		}

		// Get journal name
		journal := ""
		if len(work.ContainerTitle) > 0 {
			journal = work.ContainerTitle[0]
		}

		// Build description
		desc := fmt.Sprintf("%s | %s | %s citations", year, journal, formatInt(work.IsReferencedByCount))
		if len(authors) > 0 {
			if len(authors) <= 3 {
				desc = fmt.Sprintf("%s (%s) | %s", joinAuthors(authors), year, journal)
			} else {
				desc = fmt.Sprintf("%s et al. (%s) | %s", authors[0], year, journal)
			}
		}

		doiURL := fmt.Sprintf("https://doi.org/%s", work.DOI)

		results = append(results, SearchResult{
			Title:       work.Title[0],
			URL:         doiURL,
			Description: desc,
			Content:     work.Abstract,
			PublishedAt: year,
		})
		citations = append(citations, doiURL)
		sources = append(sources, work.URL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d works from CrossRef (academic citations, DOI resolution)", worksResp.Message.Total),
	}, nil
}

// ResolveDOI resolves a DOI to paper metadata.
func (p *CrossRefProvider) ResolveDOI(ctx context.Context, doi string) (*CrossRefWork, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	urlStr := fmt.Sprintf("%s/works/%s?mailto=%s", p.baseURL, doi, p.email)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0 (mailto:"+p.email+")")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("CrossRef DOI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("CrossRef DOI unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var crossRefResp CrossRefResponse
	if err := json.NewDecoder(resp.Body).Decode(&crossRefResp); err != nil {
		return nil, fmt.Errorf("failed to parse CrossRef response: %w", err)
	}

	return &crossRefResp.Message, nil
}

// joinAuthors joins author names with commas.
func joinAuthors(authors []string) string {
	if len(authors) == 0 {
		return ""
	}
	if len(authors) == 1 {
		return authors[0]
	}
	result := authors[0]
	for i := 1; i < len(authors)-1; i++ {
		result += ", " + authors[i]
	}
	result += " & " + authors[len(authors)-1]
	return result
}

// formatInt formats an int with thousand separators.
func formatInt(n int) string {
	if n < 1000 {
		return fmt.Sprintf("%d", n)
	}
	return fmt.Sprintf("%d,%03d", n/1000, n%1000)
}
