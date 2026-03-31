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

// Context7Provider implements SearchProvider for Context7 API.
// Context7 provides up-to-date, version-specific library documentation
// for 50+ popular libraries like React, Next.js, Vue, Express, and Prisma.
type Context7Provider struct {
	apiKey  string
	timeout time.Duration
	baseURL string
}

// Context7SearchResponse represents the Context7 search API response.
type Context7SearchResponse struct {
	Results             []Context7SearchResult `json:"results"`
	SearchFilterApplied bool                   `json:"searchFilterApplied"`
}

// Context7SearchResult represents a single search result.
type Context7SearchResult struct {
	ID             string   `json:"id"`
	Title          string   `json:"title"`
	Description    string   `json:"description"`
	TotalSnippets  int      `json:"totalSnippets"`
	BenchmarkScore float64  `json:"benchmarkScore"`
	Versions       []string `json:"versions,omitempty"`
}

// Context7DocsResponse represents the Context7 documentation API response.
type Context7DocsResponse struct {
	CodeSnippets []Context7CodeSnippet `json:"codeSnippets"`
	InfoSnippets []Context7InfoSnippet `json:"infoSnippets"`
}

// Context7CodeSnippet represents a code snippet from documentation.
type Context7CodeSnippet struct {
	CodeTitle       string              `json:"codeTitle"`
	CodeDescription string              `json:"codeDescription"`
	CodeLanguage    string              `json:"codeLanguage"`
	CodeTokens      int                 `json:"codeTokens"`
	CodeID          string              `json:"codeId"`
	PageTitle       string              `json:"pageTitle"`
	CodeList        []Context7CodeBlock `json:"codeList"`
}

// Context7CodeBlock represents a block of code within a snippet.
type Context7CodeBlock struct {
	Language string `json:"language"`
	Code     string `json:"code"`
}

// Context7InfoSnippet represents an info snippet from documentation.
type Context7InfoSnippet struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Source      string `json:"source"`
}

// NewContext7Provider creates a new Context7 provider.
func NewContext7Provider(apiKey string, timeout time.Duration) *Context7Provider {
	return &Context7Provider{
		apiKey:  apiKey,
		timeout: timeout,
		baseURL: "https://context7.com/api/v2",
	}
}

// Name returns the provider name.
func (p *Context7Provider) Name() string {
	return "context7"
}

// IsConfigured returns true if Context7 is properly configured.
func (p *Context7Provider) IsConfigured() bool {
	return p.apiKey != ""
}

// Search performs a search using Context7 API.
// It searches for library documentation and returns relevant documentation snippets.
// The query should be a library name or technology (e.g., "react hooks", "nextjs routing").
//
// NOTE: Context7 has transitioned to an MCP-based architecture. This provider
// uses the REST API which may have limited functionality. For full Context7 support,
// consider using the MCP server approach.
func (p *Context7Provider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Step 1: Search for the library ID
	libraryID, err := p.findLibraryID(reqCtx, req.Query)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("Context7 library search failed: %w", err)
	}

	if libraryID == "" {
		return SearchResponse{
			Results: []SearchResult{},
			Summary: "No documentation found for " + req.Query,
		}, nil
	}

	// Step 2: Fetch documentation for the library
	docContent, err := p.fetchDocumentation(reqCtx, libraryID, req.Query)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("Context7 documentation fetch failed: %w", err)
	}

	// Step 3: Parse the content into search results
	lines := strings.Split(docContent, "\n")
	results := make([]SearchResult, 0, len(lines))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		// Create a result for each line of documentation
		results = append(results, SearchResult{
			Title:       req.Query,
			URL:         fmt.Sprintf("https://context7.com/%s", libraryID),
			Description: truncateString(line, 200),
			Content:     line,
		})
		citations = append(citations, fmt.Sprintf("https://context7.com/%s", libraryID))
		sources = append(sources, "context7.com")
	}

	citations = []string{fmt.Sprintf("https://context7.com/%s", libraryID)}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Retrieved documentation from Context7 for %s", libraryID),
	}, nil
}

// findLibraryID searches for a library and returns its Context7 ID.
func (p *Context7Provider) findLibraryID(ctx context.Context, query string) (string, error) {
	// Extract potential library name from query
	// Common patterns: "react hooks", "nextjs routing", "prisma orm"
	searchQuery := extractLibraryQuery(query)

	// Use the new Context7 API endpoints
	urlStr := fmt.Sprintf("%s/libs/search?libraryName=%s&query=%s",
		p.baseURL, url.QueryEscape(searchQuery), url.QueryEscape(query))

	httpReq, err := http.NewRequestWithContext(ctx, "GET", urlStr, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var searchResp Context7SearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&searchResp); err != nil {
		return "", fmt.Errorf("failed to parse response: %w", err)
	}

	if len(searchResp.Results) == 0 {
		return "", nil
	}

	// Return the first/best match (highest benchmarkScore)
	return searchResp.Results[0].ID, nil
}

// fetchDocumentation fetches documentation for a library.
func (p *Context7Provider) fetchDocumentation(ctx context.Context, libraryID string, topic string) (string, error) {
	// Use the new Context7 API endpoint with type=json
	urlStr := fmt.Sprintf("%s/context?libraryId=%s&query=%s&type=json",
		p.baseURL, url.QueryEscape(libraryID), url.QueryEscape(topic))

	httpReq, err := http.NewRequestWithContext(ctx, "GET", urlStr, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	if p.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	}

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var docsResp Context7DocsResponse
	if err := json.NewDecoder(resp.Body).Decode(&docsResp); err != nil {
		return "", fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert code snippets to plain text for search results
	var content strings.Builder
	for _, snippet := range docsResp.CodeSnippets {
		content.WriteString(fmt.Sprintf("### %s\n\n%s\n\nSource: %s\n\n",
			snippet.CodeTitle, snippet.CodeDescription, snippet.CodeID))
		for _, code := range snippet.CodeList {
			content.WriteString(fmt.Sprintf("```%s\n%s\n```\n\n", code.Language, code.Code))
		}
	}

	// Also add info snippets
	for _, info := range docsResp.InfoSnippets {
		content.WriteString(fmt.Sprintf("### %s\n\n%s\n\nSource: %s\n\n---\n\n",
			info.Title, info.Description, info.Source))
	}

	return content.String(), nil
}

// extractLibraryQuery extracts a clean library name from a search query.
// E.g., "react hooks" -> "react", "nextjs routing" -> "nextjs"
func extractLibraryQuery(query string) string {
	// Common library name patterns
	query = strings.ToLower(query)

	// Remove common search terms
	terms := []string{"documentation", "docs", "api", "guide", "tutorial", "example"}
	for _, term := range terms {
		query = strings.ReplaceAll(query, term, "")
	}
	query = strings.TrimSpace(query)

	// If the query is complex, take just the first meaningful word
	words := strings.Fields(query)
	if len(words) > 0 {
		// Common single-word libraries
		singleWordLibs := []string{
			"react", "vue", "angular", "nextjs", "nuxt", "svelte",
			"express", "fastify", "koa", "hapi",
			"prisma", "sequelize", "typeorm", "drizzle",
			"react-native", "flutter", "ionic",
			"tensorflow", "pytorch", "keras",
			"next.js", "node.js", "nodejs",
		}
		for _, lib := range singleWordLibs {
			if strings.Contains(query, lib) {
				return lib
			}
		}
		// Return first word as fallback
		return words[0]
	}

	return query
}

// extractTopic extracts a topic/feature from a search query.
func extractTopic(query string) string {
	// Common feature patterns to look for
	features := []string{
		"hooks", "component", "state", "props", "context",
		"routing", "middleware", "router", "pages", "api routes",
		"orm", "query", "migration", "schema",
		"auth", "authentication", "authorization",
		"style", "css", "tailwind", "styled-components",
		"test", "testing", "jest", "cypress",
		"deploy", "deployment", "build",
		"api", "rest", "graphql",
	}

	query = strings.ToLower(query)
	for _, feature := range features {
		if strings.Contains(query, feature) {
			return feature
		}
	}

	// Return cleaned query as topic
	return strings.ReplaceAll(query, " ", "-")
}
