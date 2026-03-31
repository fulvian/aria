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

// JinaProvider implements SearchProvider for Jina AI services.
// Jina Reader extracts clean content from URLs, ideal for LLM consumption.
// Also provides summarization and embeddings.
type JinaProvider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// JinaReaderResponse represents the Reader API response.
type JinaReaderResponse struct {
	Code int      `json:"code"`
	Msg  string   `json:"msg"`
	Data JinaData `json:"data"`
}

// JinaData contains the extracted content.
type JinaData struct {
	URL           string   `json:"url"`
	Title         string   `json:"title"`
	Content       string   `json:"content"`
	Excerpt       string   `json:"excerpt"`
	Links         []string `json:"links"`
	ImageURLs     []string `json:"imageUrls"`
	ThemeColor    string   `json:"themeColor"`
	Published     string   `json:"published"`
	Authors       []string `json:"authors"`
	Language      string   `json:"language"`
	ExtractedFrom string   `json:"extracted_from"`
}

// JinaSummaryResponse represents the summarization API response.
type JinaSummaryResponse struct {
	Code    int    `json:"code"`
	Msg     string `json:"msg"`
	Summary string `json:"summary"`
}

// NewJinaProvider creates a new Jina provider.
// Jina Reader is free for basic usage. For higher limits, use an API key.
func NewJinaProvider(timeout time.Duration) *JinaProvider {
	return &JinaProvider{
		timeout: timeout,
		baseURL: "https://r.jina.ai",
	}
}

// NewJinaProviderWithKey creates a Jina provider with API key.
func NewJinaProviderWithKey(apiKey string, timeout time.Duration) *JinaProvider {
	return &JinaProvider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://r.jina.ai",
	}
}

// Name returns the provider name.
func (p *JinaProvider) Name() string {
	return "jina"
}

// IsConfigured returns true - Jina Reader works without API key for basic usage.
func (p *JinaProvider) IsConfigured() bool {
	return true
}

// Search for Jina is actually URL content extraction, not traditional search.
// This method extracts content from a URL provided in the query.
func (p *JinaProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Jina Reader takes a URL as input
	targetURL := req.Query

	// If query is not a URL, try to extract content from it as a topic
	// by searching first - but Jina doesn't support search, so we use it for extraction
	if !isValidURL(targetURL) {
		return SearchResponse{
			Error: "Jina provider is a content extraction service, not a search engine. Provide a URL to extract content.",
		}, fmt.Errorf("Jina requires a URL, not a search query")
	}

	// Use Jina Reader API - prefix with http:// or https:// if missing
	if !strings.HasPrefix(targetURL, "http") {
		targetURL = "https://" + targetURL
	}

	// Build Jina Reader URL
	urlStr := fmt.Sprintf("%s/%s", p.baseURL, url.QueryEscape(targetURL))

	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodGet, urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "text/plain")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("Jina request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("Jina unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Read content directly (Jina Reader returns plain text)
	contentBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to read Jina response: %w", err)
	}

	content := string(contentBytes)

	// Extract title from content (first line usually)
	lines := strings.Split(content, "\n")
	title := "Extracted Content"
	if len(lines) > 0 && strings.TrimSpace(lines[0]) != "" {
		// First non-empty line might be title
		for _, line := range lines {
			trimmed := strings.TrimSpace(line)
			if trimmed != "" && len(trimmed) > 3 && len(trimmed) < 200 {
				title = trimmed
				break
			}
		}
	}

	// Build result
	result := SearchResult{
		Title:       title,
		URL:         targetURL,
		Description: truncateString(content, 300),
		Content:     content,
		PublishedAt: "",
	}

	return SearchResponse{
		Results:   []SearchResult{result},
		Sources:   []string{targetURL},
		Citations: []string{targetURL},
		Summary:   fmt.Sprintf("Extracted content from %s using Jina Reader", targetURL),
	}, nil
}

// ExtractURL extracts content from a specific URL using Jina Reader.
func (p *JinaProvider) ExtractURL(ctx context.Context, targetURL string) (*JinaData, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	if !strings.HasPrefix(targetURL, "http") {
		targetURL = "https://" + targetURL
	}

	// Use Jina Reader API
	urlStr := fmt.Sprintf("%s/%s", p.baseURL, url.QueryEscape(targetURL))

	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodGet, urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("Jina extract request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Jina extract unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Try JSON response first
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var readerResp JinaReaderResponse
	if err := json.Unmarshal(bodyBytes, &readerResp); err == nil && readerResp.Code == 0 {
		return &readerResp.Data, nil
	}

	// Fall back to plain text
	return &JinaData{
		URL:     targetURL,
		Content: string(bodyBytes),
	}, nil
}

// SummarizeText sends text to Jina for summarization.
func (p *JinaProvider) SummarizeText(ctx context.Context, text string, maxLength int) (string, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	if p.apiKey == "" {
		return "", fmt.Errorf("Jina summarization requires API key")
	}

	if maxLength == 0 {
		maxLength = 500
	}

	// Use Jina Summarization API
	urlStr := "https://api.jina.ai/summarize"

	payload := map[string]interface{}{
		"text":       text,
		"max_length": maxLength,
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal payload: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodPost, urlStr, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	httpReq.Body = io.NopCloser(strings.NewReader(string(payloadBytes)))

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("Jina summarize request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("Jina summarize unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var summaryResp JinaSummaryResponse
	if err := json.NewDecoder(resp.Body).Decode(&summaryResp); err != nil {
		return "", fmt.Errorf("failed to parse Jina summary response: %w", err)
	}

	return summaryResp.Summary, nil
}

// ExtractContentFromSearchResults extracts content from multiple URLs.
func (p *JinaProvider) ExtractContentFromSearchResults(ctx context.Context, urls []string) ([]SearchResult, error) {
	results := make([]SearchResult, 0, len(urls))

	for _, urlStr := range urls {
		data, err := p.ExtractURL(ctx, urlStr)
		if err != nil {
			continue // Skip failed extractions
		}

		desc := data.Excerpt
		if desc == "" {
			desc = truncateString(data.Content, 200)
		}

		authors := ""
		if len(data.Authors) > 0 {
			authors = strings.Join(data.Authors, ", ")
		}

		content := data.Content
		if authors != "" {
			content = fmt.Sprintf("Authors: %s\n\n%s", authors, content)
		}

		results = append(results, SearchResult{
			Title:       data.Title,
			URL:         data.URL,
			Description: desc,
			Content:     content,
			PublishedAt: data.Published,
		})
	}

	return results, nil
}

// isValidURL checks if a string is a valid URL.
func isValidURL(s string) bool {
	parsed, err := url.Parse(s)
	if err != nil {
		return false
	}
	return parsed.Scheme == "http" || parsed.Scheme == "https" || parsed.Host != ""
}
