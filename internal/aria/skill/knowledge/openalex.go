package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// OpenAlexProvider implements SearchProvider for OpenAlex API.
// OpenAlex is a free and open catalog of scholarly works covering 250M+ papers,
// authors, institutions, and citations. No API key required.
type OpenAlexProvider struct {
	timeout time.Duration
	baseURL string
	email   string // polite pool email (optional but recommended)
}

// OpenAlexResponse represents the OpenAlex API response for works.
type OpenAlexResponse struct {
	Meta    OpenAlexMeta   `json:"meta"`
	Results []OpenAlexWork `json:"results"`
}

// OpenAlexMeta contains pagination and request metadata.
type OpenAlexMeta struct {
	Count            int `json:"count"`
	DBResponseTimeMs int `json:"db_response_time_ms"`
	Page             int `json:"page"`
	PerPage          int `json:"per_page"`
}

// OpenAlexWork represents a scholarly work in OpenAlex.
type OpenAlexWork struct {
	ID                     string            `json:"id"` // e.g., "W2893585111"
	Title                  string            `json:"title"`
	DisplayName            string            `json:"display_name"`
	PublicationYear        int               `json:"publication_year"`
	Type                   string            `json:"type"` // "article", "book", etc.
	Doi                    string            `json:"doi"`
	URL                    string            `json:"url"`
	Abstract               any               `json:"abstract_inverted_index"`
	OpenAccessStatus       string            `json:"open_access_status"`
	CitedByCount           int               `json:"cited_by_count"`
	CitationCount          int               `json:"citation_count"`
	ReferencesCount        int               `json:"references_count"`
	Authorships            []OpenAlexAuthor  `json:"authorships"`
	Concepts               []OpenAlexConcept `json:"concepts"`
	PublicationDate        string            `json:"publication_date"`
	Journal                *OpenAlexSource   `json:"primary_location"`
	BestOaLocation         *OpenAlexLocation `json:"best_oa_location"`
	InverseReferencesWorks []string          `json:"inverse_references_works"`
}

// OpenAlexAuthor represents an author of a work.
type OpenAlexAuthor struct {
	Author         *OpenAlexAuthorInfo   `json:"author"`
	AuthorPosition string                `json:"author_position"`
	Institutions   []OpenAlexInstitution `json:"institutions"`
}

// OpenAlexAuthorInfo contains author details.
type OpenAlexAuthorInfo struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	Orcid       string `json:"orcid"`
}

// OpenAlexInstitution represents an institution.
type OpenAlexInstitution struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	CountryCode string `json:"country_code"`
	Ror         string `json:"ror"`
}

// OpenAlexConcept represents a research concept.
type OpenAlexConcept struct {
	ID          string  `json:"id"`
	DisplayName string  `json:"display_name"`
	Level       int     `json:"level"`
	Score       float64 `json:"score"`
}

// OpenAlexSource represents a journal or publication venue.
type OpenAlexSource struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	HostOrgName string `json:"host_org_name"`
	Type        string `json:"type"`
}

// OpenAlexLocation represents a location (PDF, repository, etc.).
type OpenAlexLocation struct {
	LandingPageURL string          `json:"landing_page_url"`
	PDFURL         string          `json:"pdf_url"`
	Source         *OpenAlexSource `json:"source"`
	IsOA           bool            `json:"is_oa"`
}

// NewOpenAlexProvider creates a new OpenAlex provider.
// OpenAlex is completely free and requires no API key.
func NewOpenAlexProvider(timeout time.Duration) *OpenAlexProvider {
	return &OpenAlexProvider{
		timeout: timeout,
		baseURL: "https://api.openalex.org",
		email:   "", // optional, for polite pool
	}
}

// NewOpenAlexProviderWithEmail creates a new OpenAlex provider with polite pool email.
func NewOpenAlexProviderWithEmail(email string, timeout time.Duration) *OpenAlexProvider {
	return &OpenAlexProvider{
		timeout: timeout,
		baseURL: "https://api.openalex.org",
		email:   email,
	}
}

// Name returns the provider name.
func (p *OpenAlexProvider) Name() string {
	return "openalex"
}

// IsConfigured returns true - OpenAlex requires no API key.
func (p *OpenAlexProvider) IsConfigured() bool {
	return true
}

// Search performs a search using OpenAlex API.
func (p *OpenAlexProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build query URL
	// OpenAlex uses "search" endpoint for full-text search
	query := url.QueryEscape(req.Query)
	perPage := req.MaxResults
	if perPage == 0 {
		perPage = 10
	}
	if perPage > 100 {
		perPage = 100 // OpenAlex max
	}

	urlStr := fmt.Sprintf("%s/works?search=%s&per-page=%d&mailto=%s",
		p.baseURL, query, perPage, p.email)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0 (contact@aria.ai)")

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("OpenAlex request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("OpenAlex unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var openAlexResp OpenAlexResponse
	if err := json.NewDecoder(resp.Body).Decode(&openAlexResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse OpenAlex response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(openAlexResp.Results))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, work := range openAlexResp.Results {
		// Build authors string
		authors := make([]string, 0)
		for _, a := range work.Authorships {
			if a.Author != nil && a.Author.DisplayName != "" {
				authors = append(authors, a.Author.DisplayName)
			}
		}
		authorStr := joinAuthorsOpenAlex(authors)

		// Get journal/venue
		venue := ""
		if work.Journal != nil {
			venue = work.Journal.DisplayName
		}

		// Build description
		year := strconv.Itoa(work.PublicationYear)
		desc := fmt.Sprintf("%s | %s | Cited by: %d", authorStr, year, work.CitedByCount)
		if venue != "" {
			desc = fmt.Sprintf("%s | %s | %s | Cited: %d", authorStr, year, venue, work.CitedByCount)
		}

		// Get DOI URL
		paperURL := work.Doi
		if paperURL == "" {
			paperURL = work.URL
		}
		if paperURL == "" {
			paperURL = fmt.Sprintf("https://openalex.org/%s", work.ID)
		}

		// Extract abstract if available (abstract_inverted_index can be object or string)
		abstract := ""
		if work.Abstract != nil {
			if s, ok := work.Abstract.(string); ok {
				abstract = s
			}
		}

		// Get concepts
		concepts := make([]string, 0)
		for _, c := range work.Concepts {
			if c.Level <= 2 { // Top-level concepts
				concepts = append(concepts, c.DisplayName)
			}
		}

		content := abstract
		if len(concepts) > 0 {
			if content != "" {
				content += "\n\n"
			}
			content += fmt.Sprintf("Concepts: %s", joinStringsOpenAlex(concepts, ", "))
		}

		results = append(results, SearchResult{
			Title:       work.Title,
			URL:         paperURL,
			Description: desc,
			Content:     content,
			PublishedAt: year,
		})

		citations = append(citations, paperURL)
		sources = append(sources, fmt.Sprintf("https://openalex.org/%s", work.ID))
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d works from OpenAlex (250M+ papers, citation graph)", openAlexResp.Meta.Count),
	}, nil
}

// GetWorkByDOI retrieves a specific work by DOI.
func (p *OpenAlexProvider) GetWorkByDOI(ctx context.Context, doi string) (*OpenAlexWork, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Convert DOI to OpenAlex ID format
	doiEncoded := url.QueryEscape(doi)
	urlStr := fmt.Sprintf("%s/works/https://doi.org/%s", p.baseURL, doiEncoded)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("OpenAlex DOI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OpenAlex DOI unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var work OpenAlexWork
	if err := json.NewDecoder(resp.Body).Decode(&work); err != nil {
		return nil, fmt.Errorf("failed to parse OpenAlex response: %w", err)
	}

	return &work, nil
}

// GetCitationNetwork retrieves works that cite a given work.
func (p *OpenAlexProvider) GetCitationNetwork(ctx context.Context, openAlexID string, maxResults int) ([]OpenAlexWork, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	if maxResults == 0 {
		maxResults = 10
	}

	urlStr := fmt.Sprintf("%s/works/%s/cited_by?per_page=%d", p.baseURL, openAlexID, maxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("OpenAlex citation request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OpenAlex citation unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var openAlexResp OpenAlexResponse
	if err := json.NewDecoder(resp.Body).Decode(&openAlexResp); err != nil {
		return nil, fmt.Errorf("failed to parse OpenAlex response: %w", err)
	}

	return openAlexResp.Results, nil
}

// joinAuthorsOpenAlex joins author names.
func joinAuthorsOpenAlex(authors []string) string {
	if len(authors) == 0 {
		return "Unknown"
	}
	if len(authors) == 1 {
		return authors[0]
	}
	if len(authors) == 2 {
		return authors[0] + " & " + authors[1]
	}
	if len(authors) <= 5 {
		result := authors[0]
		for i := 1; i < len(authors)-1; i++ {
			result += ", " + authors[i]
		}
		result += " & " + authors[len(authors)-1]
		return result
	}
	return fmt.Sprintf("%s et al.", authors[0])
}

// joinStringsOpenAlex joins strings with separator.
func joinStringsOpenAlex(strs []string, sep string) string {
	if len(strs) == 0 {
		return ""
	}
	result := strs[0]
	for i := 1; i < len(strs); i++ {
		result += sep + strs[i]
	}
	return result
}
