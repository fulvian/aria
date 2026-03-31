package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// BGPTProvider implements SearchProvider for BGPT API (structured experimental data).
// BGPT provides rich structured data extracted from full-text papers including
// methods, results, sample sizes, effect sizes, and quality scores.
type BGPTProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// BGPTPaper represents a paper with structured experimental data from BGPT.
type BGPTPaper struct {
	Title         string   `json:"title"`
	Authors       []string `json:"authors"`
	Journal       string   `json:"journal"`
	Year          int      `json:"year"`
	DOI           string   `json:"doi"`
	URL           string   `json:"url"`
	Abstract      string   `json:"abstract"`
	Methods       []string `json:"methods"`
	Results       []string `json:"results"`
	SampleSizes   []string `json:"sample_sizes"`
	EffectSizes   []string `json:"effect_sizes"`
	QualityScore  float64  `json:"quality_score"`
	EvidenceGrade string   `json:"evidence_grade"`
	Conclusions   []string `json:"conclusions"`
	Limitations   []string `json:"limitations"`
}

// BGPTResponse represents the BGPT API response.
type BGPTResponse struct {
	Success bool        `json:"success"`
	Query   string      `json:"query"`
	Results []BGPTPaper `json:"results"`
	Error   string      `json:"error,omitempty"`
}

// NewBGPTProvider creates a new BGPT provider.
// BGPT is accessible via MCP at https://bgpt.pro/mcp or direct API.
func NewBGPTProvider(apiKey string, timeout time.Duration) *BGPTProvider {
	return &BGPTProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://api.bgpт.pro", // Note: BGPT uses MCP server, this is for direct API if available
	}
}

// Name returns the provider name.
func (p *BGPTProvider) Name() string {
	return "bgpt"
}

// IsConfigured returns true if API key is provided or using MCP.
func (p *BGPTProvider) IsConfigured() bool {
	// BGPT has free tier without API key, so we can always attempt
	return true
}

// Search performs structured search using BGPT.
func (p *BGPTProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	// BGPT is primarily accessed via MCP server, not REST API
	// This implementation provides a fallback HTTP interface if available

	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build request
	urlStr := fmt.Sprintf("%s/search?query=%s&limit=%d", p.baseURL, req.Query, req.MaxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		// BGPT primarily works via MCP, return helpful message
		return SearchResponse{}, fmt.Errorf("BGPT requires MCP integration: add 'bgpt' MCP server at https://bgpt.pro/mcp/sse")
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("BGPT unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var bgptResp BGPTResponse
	if err := json.NewDecoder(resp.Body).Decode(&bgptResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse BGPT response: %w", err)
	}

	if !bgptResp.Success {
		return SearchResponse{}, fmt.Errorf("BGPT search failed: %s", bgptResp.Error)
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(bgptResp.Results))
	citations := make([]string, 0, len(bgptResp.Results))
	sources := make([]string, 0, len(bgptResp.Results))

	for _, paper := range bgptResp.Results {
		// Build structured description
		desc := fmt.Sprintf("Quality: %.1f/10 | Grade: %s | Year: %d", paper.QualityScore, paper.EvidenceGrade, paper.Year)
		if len(paper.SampleSizes) > 0 {
			desc += fmt.Sprintf(" | Samples: %s", joinStrings(paper.SampleSizes, ", "))
		}

		// Build content from structured data
		content := fmt.Sprintf("Abstract: %s\n\nMethods: %s\n\nResults: %s\n\nConclusions: %s",
			paper.Abstract,
			joinStrings(paper.Methods, "; "),
			joinStrings(paper.Results, "; "),
			joinStrings(paper.Conclusions, "; "))

		results = append(results, SearchResult{
			Title:       paper.Title,
			URL:         paper.URL,
			Description: desc,
			Content:     content,
			PublishedAt: fmt.Sprintf("%d", paper.Year),
		})

		if paper.DOI != "" {
			citations = append(citations, fmt.Sprintf("https://doi.org/%s", paper.DOI))
		}
		citations = append(citations, paper.URL)
		sources = append(sources, paper.URL)
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d papers with structured experimental data from BGPT", len(bgptResp.Results)),
	}, nil
}

// GetMCPServerConfig returns the MCP server configuration for BGPT.
func (p *BGPTProvider) GetMCPServerConfig() map[string]interface{} {
	return map[string]interface{}{
		"name":        "bgpt",
		"type":        "sse",
		"url":         "https://bgpt.pro/mcp/sse",
		"description": "BGPT MCP server for structured scientific paper data - provides methods, results, sample sizes, effect sizes, and quality scores",
	}
}

// joinStrings joins strings with a separator.
func joinStrings(strs []string, sep string) string {
	if len(strs) == 0 {
		return ""
	}
	result := strs[0]
	for i := 1; i < len(strs); i++ {
		result += sep + strs[i]
	}
	return result
}
