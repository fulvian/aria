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

// arXivProvider implements SearchProvider for arXiv API (free, no API key required).
type arXivProvider struct {
	timeout time.Duration
	baseURL string
}

// arXivResponse represents the arXiv API Atom response.
type arXivResponse struct {
	XMLName xml.Name     `xml:"feed"`
	Entry   []ArxivEntry `xml:"entry"`
}

// ArxivEntry represents a single arXiv paper in Atom format.
type ArxivEntry struct {
	XMLEntryID string `xml:"id"`
	Title      string `xml:"title"`
	Summary    string `xml:"summary"`
	Updated    string `xml:"updated"`
	Published  string `xml:"published"`
	Author     []struct {
		Name string `xml:"name"`
	} `xml:"author"`
	Category []string `xml:"category"`
	Link     []struct {
		Href string `xml:"href,attr"`
		Type string `xml:"type,attr"`
		Rel  string `xml:"rel,attr"`
	} `xml:"link"`
}

// NewarXivProvider creates a new arXiv provider.
func NewarXivProvider(timeout time.Duration) *arXivProvider {
	return &arXivProvider{
		timeout: timeout,
		baseURL: "http://export.arxiv.org/api/query",
	}
}

// Name returns the provider name.
func (p *arXivProvider) Name() string {
	return "arxiv"
}

// IsConfigured always returns true for arXiv (free, no API key).
func (p *arXivProvider) IsConfigured() bool {
	return true
}

// Search performs a search using arXiv API.
func (p *arXivProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// Build query
	params := url.Values{}
	params.Set("search_query", req.Query)
	params.Set("start", "0")
	params.Set("max_results", fmt.Sprintf("%d", req.MaxResults))
	params.Set("sortBy", "relevance")
	params.Set("sortOrder", "descending")

	// Create request with timeout
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	searchURL := fmt.Sprintf("%s?%s", p.baseURL, params.Encode())
	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", searchURL, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/atom+xml")
	httpReq.Header.Set("User-Agent", "ARIA Knowledge Agency/1.0")

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("arXiv request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("arXiv unexpected status code: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response - arXiv returns Atom XML format
	var arxivResp arXivResponse
	if err := xml.NewDecoder(resp.Body).Decode(&arxivResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse arXiv response: %w", err)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(arxivResp.Entry))
	citations := make([]string, 0, len(arxivResp.Entry))
	sources := make([]string, 0, len(arxivResp.Entry))

	for _, entry := range arxivResp.Entry {
		// Get PDF link if available
		pdfURL := entry.XMLEntryID
		for _, link := range entry.Link {
			if link.Type == "application/pdf" {
				pdfURL = link.Href
				break
			}
		}

		// Clean summary (remove LaTeX formatting)
		summary := cleanLatex(entry.Summary)

		results = append(results, SearchResult{
			Title:       cleanLatex(entry.Title),
			URL:         entry.XMLEntryID,
			Description: summary,
			Content:     summary,
			PublishedAt: entry.Published,
		})
		citations = append(citations, entry.XMLEntryID)
		sources = append(sources, entry.XMLEntryID)

		_ = pdfURL
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d papers from arXiv (physics, math, CS, quantitative biology, quantitative finance, statistics)", len(results)),
	}, nil
}

// cleanLatex removes basic LaTeX formatting from text.
func cleanLatex(s string) string {
	// Remove common LaTeX commands
	s = strings.ReplaceAll(s, "\\textbf{", "")
	s = strings.ReplaceAll(s, "\\textit{", "")
	s = strings.ReplaceAll(s, "\\emph{", "")
	s = strings.ReplaceAll(s, "\\begin{equation}", "")
	s = strings.ReplaceAll(s, "\\end{equation}", "")
	s = strings.ReplaceAll(s, "\\frac{", "")
	s = strings.ReplaceAll(s, "}{", "/")
	s = strings.ReplaceAll(s, "\\alpha", "α")
	s = strings.ReplaceAll(s, "\\beta", "β")
	s = strings.ReplaceAll(s, "\\gamma", "γ")
	s = strings.ReplaceAll(s, "\\delta", "δ")
	s = strings.ReplaceAll(s, "\\theta", "θ")
	s = strings.ReplaceAll(s, "\\pi", "π")
	s = strings.ReplaceAll(s, "\\sigma", "σ")
	s = strings.ReplaceAll(s, "\\omega", "ω")
	s = strings.ReplaceAll(s, "\\sum", "Σ")
	s = strings.ReplaceAll(s, "\\int", "∫")
	s = strings.ReplaceAll(s, "\\infty", "∞")
	s = strings.ReplaceAll(s, "\\rightarrow", "→")
	s = strings.ReplaceAll(s, "\\leftarrow", "←")
	s = strings.ReplaceAll(s, "\\%", "%")
	s = strings.ReplaceAll(s, "$", "")
	s = strings.ReplaceAll(s, "{", "")
	s = strings.ReplaceAll(s, "}", "")
	s = strings.ReplaceAll(s, "\n", " ")
	s = strings.TrimSpace(s)
	return s
}
