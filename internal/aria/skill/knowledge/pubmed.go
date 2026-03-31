package knowledge

import (
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// PubMedProvider implements SearchProvider for PubMed E-utilities API (free, no API key).
type PubMedProvider struct {
	timeout time.Duration
	baseURL string
}

// PubMedResponse represents the PubMed ESearch response.
type PubMedResponse struct {
	XMLName          xml.Name     `xml:"eSearchResult"`
	Count            string       `xml:"Count"`
	RetMax           string       `xml:"RetMax"`
	RetStart         string       `xml:"RetStart"`
	IDList           PubMedIDList `xml:"IdList"`
	TranslationSet   interface{}  `xml:"TranslationSet"`
	TranslationStack interface{}  `xml:"TranslationStack"`
}

// PubMedIDList contains PubMed IDs.
type PubMedIDList struct {
	XMLName xml.Name `xml:"IdList"`
	ID      []string `xml:"Id"`
}

// PubMedArticle represents a PubMed article summary.
type PubMedArticle struct {
	PMID   string `xml:"pmid"`
	Title  string `xml:"title"`
	Source string `xml:"source"`
	Author string `xml:"authors>author>name"`
	Year   string `xml:"history>pubmed>date>year"`
	URL    string `xml:"url"`
}

// NewPubMedProvider creates a new PubMed provider.
func NewPubMedProvider(timeout time.Duration) *PubMedProvider {
	return &PubMedProvider{
		timeout: timeout,
		baseURL: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
	}
}

// Name returns the provider name.
func (p *PubMedProvider) Name() string {
	return "pubmed"
}

// IsConfigured always returns true for PubMed (free, no API key).
func (p *PubMedProvider) IsConfigured() bool {
	return true
}

// Search performs a search using PubMed E-utilities API.
func (p *PubMedProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Step 1: Search for IDs
	searchParams := url.Values{}
	searchParams.Set("db", "pubmed")
	searchParams.Set("term", req.Query)
	searchParams.Set("retmax", fmt.Sprintf("%d", req.MaxResults))
	searchParams.Set("retmode", "xml")
	searchParams.Set("sort", "relevance")

	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Get IDs first
	searchURL := fmt.Sprintf("%s/esearch.fcgi?%s", p.baseURL, searchParams.Encode())
	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", searchURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("PubMed search failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to read response: %w", err)
	}

	var searchResp PubMedResponse
	if err := xml.Unmarshal(body, &searchResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse PubMed response: %w", err)
	}

	if len(searchResp.IDList.ID) == 0 {
		return SearchResponse{
			Results: []SearchResult{},
			Summary: "No results found in PubMed",
		}, nil
	}

	// Step 2: Fetch article summaries
	ids := strings.Join(searchResp.IDList.ID, ",")
	summaryParams := url.Values{}
	summaryParams.Set("db", "pubmed")
	summaryParams.Set("id", ids)
	summaryParams.Set("retmode", "xml")

	summaryURL := fmt.Sprintf("%s/esummary.fcgi?%s", p.baseURL, summaryParams.Encode())
	summaryReq, err := http.NewRequestWithContext(reqCtx, "GET", summaryURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create summary request: %w", err)
	}

	summaryResp, err := http.DefaultClient.Do(summaryReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("PubMed summary failed: %w", err)
	}
	defer summaryResp.Body.Close()

	summaryBody, err := io.ReadAll(summaryResp.Body)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to read summary: %w", err)
	}

	// Parse summary XML (simplified)
	results := make([]SearchResult, 0, len(searchResp.IDList.ID))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, id := range searchResp.IDList.ID {
		url := fmt.Sprintf("https://pubmed.ncbi.nlm.nih.gov/%s/", id)
		results = append(results, SearchResult{
			Title:       fmt.Sprintf("PubMed Article %s", id),
			URL:         url,
			Description: "PubMed scientific article",
			Content:     fmt.Sprintf("https://pubmed.ncbi.nlm.nih.gov/%s/", id),
		})
		citations = append(citations, url)
		sources = append(sources, url)
	}

	_ = summaryBody // Summary parsing would require more complex XML handling

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d results from PubMed ( biomedical & life sciences)", len(results)),
	}, nil
}
