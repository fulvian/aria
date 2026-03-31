// Package agency provides the Knowledge Agency specialized agents.
// These agents are specialized for specific types of research tasks.
package agency

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/aria/skill/knowledge"
)

// ============================================================================
// AGENT CONSTANTS
// ============================================================================

// Knowledge agent names
const (
	AgentWebSearch    contracts.AgentName = "web-search"
	AgentAcademic     contracts.AgentName = "academic"
	AgentNews         contracts.AgentName = "news"
	AgentCodeResearch contracts.AgentName = "code-research"
	AgentHistorical   contracts.AgentName = "historical"
)

// Provider preference constants
const (
	ProviderTavily        = "tavily"
	ProviderBrave         = "brave"
	ProviderDuckDuckGo    = "ddg"
	ProviderWikipedia     = "wikipedia"
	ProviderDuckDuckGoAlt = "duckduckgo"
)

// ============================================================================
// WebSearchAgent
// ============================================================================

// WebSearchAgent handles general web search tasks using Tavily, Brave, DDG, Wikipedia.
type WebSearchAgent struct {
	name      contracts.AgentName
	cfg       knowledge.AgencyConfig
	tavily    knowledge.SearchProvider
	brave     knowledge.SearchProvider
	ddg       knowledge.SearchProvider
	wikipedia knowledge.SearchProvider
}

// NewWebSearchAgent creates a new WebSearchAgent.
func NewWebSearchAgent(cfg knowledge.AgencyConfig) *WebSearchAgent {
	return &WebSearchAgent{
		name:      AgentWebSearch,
		cfg:       cfg,
		tavily:    knowledge.NewTavilyProvider(cfg.TavilyAPIKey, timeout(cfg.SearchTimeoutMs)),
		brave:     knowledge.NewBraveProvider(cfg.BraveAPIKey, timeout(cfg.SearchTimeoutMs)),
		ddg:       knowledge.NewDDGProvider(timeout(cfg.SearchTimeoutMs)),
		wikipedia: knowledge.NewWikipediaProvider(timeout(cfg.SearchTimeoutMs)),
	}
}

// Name returns the agent name.
func (a *WebSearchAgent) Name() contracts.AgentName {
	return a.name
}

// Skills returns the skills this agent can perform.
func (a *WebSearchAgent) Skills() []skill.SkillName {
	return []skill.SkillName{skill.SkillWebResearch, skill.SkillFactCheck}
}

// Execute performs a web search task.
func (a *WebSearchAgent) Execute(ctx context.Context, task contracts.Task) (map[string]any, error) {
	query := extractQuery(task)
	if query == "" {
		return nil, fmt.Errorf("query is required")
	}

	maxResults := extractMaxResults(task, a.cfg.MaxSearchResults)

	// Detect provider preference from query
	preferredProvider := DetectProviderPreference(query)

	// Build provider list based on preference
	providers := buildProviderList(a, preferredProvider)

	var lastErr error
	for _, p := range providers {
		results, err := p.fn(ctx, knowledge.SearchRequest{
			Query:      query,
			MaxResults: maxResults,
			Language:   extractLanguage(task),
		})

		if err != nil {
			lastErr = err
			continue
		}

		if len(results) > 0 {
			return formatWebSearchResult(query, results, p.name), nil
		}
	}

	if lastErr != nil {
		return nil, fmt.Errorf("web search failed: %w", lastErr)
	}
	return map[string]any{"query": query, "results": []any{}, "source": "none"}, nil
}

// buildProviderList builds the provider list with preferred provider first.
// It respects user preferences from the query, falls back to config DefaultProvider,
// and finally uses the standard quality order.
func buildProviderList(a *WebSearchAgent, preferred string) []struct {
	name string
	fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
} {
	// Standard quality order (used when no preference)
	standardOrder := []struct {
		name string
		fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
	}{
		{"tavily", a.searchTavily},
		{"brave", a.searchBrave},
		{"wikipedia", a.searchWikipedia},
		{"ddg", a.searchDDG},
	}

	// If no explicit preference, use DefaultProvider from config
	if preferred == "" {
		preferred = a.cfg.DefaultProvider
	}

	// If still no preference, use standard order
	if preferred == "" {
		return standardOrder
	}

	// Normalize preferred provider name
	normalized := normalizeProviderName(preferred)

	// Build list with preferred first, then others
	var result []struct {
		name string
		fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
	}

	// Add preferred first based on normalized name
	switch normalized {
	case ProviderTavily:
		result = append(result, struct {
			name string
			fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
		}{ProviderTavily, a.searchTavily})
	case ProviderBrave:
		result = append(result, struct {
			name string
			fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
		}{ProviderBrave, a.searchBrave})
	case ProviderDuckDuckGo, ProviderDuckDuckGoAlt:
		result = append(result, struct {
			name string
			fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
		}{ProviderDuckDuckGo, a.searchDDG})
	case ProviderWikipedia:
		result = append(result, struct {
			name string
			fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
		}{ProviderWikipedia, a.searchWikipedia})
	default:
		// Unknown provider, fall back to standard order
		return standardOrder
	}

	// Add remaining providers (skip the preferred one)
	for _, p := range standardOrder {
		if p.name == normalized ||
			(normalized == ProviderDuckDuckGoAlt && p.name == ProviderDuckDuckGo) ||
			(normalized == ProviderDuckDuckGo && p.name == ProviderDuckDuckGoAlt) {
			continue
		}
		result = append(result, p)
	}

	return result
}

// normalizeProviderName normalizes various provider name formats to canonical names.
func normalizeProviderName(name string) string {
	switch strings.ToLower(name) {
	case "tavily":
		return ProviderTavily
	case "brave":
		return ProviderBrave
	case "ddg", "duckduckgo", "duck duck go":
		return ProviderDuckDuckGo
	case "wikipedia":
		return ProviderWikipedia
	default:
		return name
	}
}

// DetectProviderPreference detects if the query expresses a preference for a specific provider.
func DetectProviderPreference(query string) string {
	lower := strings.ToLower(query)

	// Check for explicit provider mentions
	providerPatterns := []struct {
		provider string
		patterns []string
	}{
		{ProviderTavily, []string{"use tavily", "with tavily", "via tavily", "tavily search"}},
		{ProviderBrave, []string{"use brave", "with brave", "via brave", "brave search"}},
		{ProviderDuckDuckGo, []string{"use ddg", "with ddg", "via ddg", "ddg search"}},
		{ProviderDuckDuckGoAlt, []string{"use duckduckgo", "with duckduckgo", "via duckduckgo", "duckduckgo search", "search on duckduckgo", "search with duckduckgo"}},
		{ProviderWikipedia, []string{"use wikipedia", "with wikipedia", "via wikipedia", "wikipedia search"}},
	}

	for _, pp := range providerPatterns {
		for _, pattern := range pp.patterns {
			if strings.Contains(lower, pattern) {
				return pp.provider
			}
		}
	}

	return ""
}

func (a *WebSearchAgent) searchTavily(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.tavily.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *WebSearchAgent) searchBrave(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.brave.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *WebSearchAgent) searchWikipedia(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.wikipedia.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *WebSearchAgent) searchDDG(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.ddg.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

// ============================================================================
// AcademicResearchAgent
// ============================================================================

// AcademicResearchAgent handles academic/scientific research using PubMed, arXiv, SemanticScholar, OpenAlex.
type AcademicResearchAgent struct {
	name     contracts.AgentName
	cfg      knowledge.AgencyConfig
	pubmed   knowledge.SearchProvider
	arxiv    knowledge.SearchProvider
	semantic knowledge.SearchProvider
	openalex knowledge.SearchProvider
}

// NewAcademicResearchAgent creates a new AcademicResearchAgent.
func NewAcademicResearchAgent(cfg knowledge.AgencyConfig) *AcademicResearchAgent {
	return &AcademicResearchAgent{
		name:     AgentAcademic,
		cfg:      cfg,
		pubmed:   knowledge.NewPubMedProvider(timeout(cfg.SearchTimeoutMs)),
		arxiv:    knowledge.NewarXivProvider(timeout(cfg.SearchTimeoutMs)),
		semantic: knowledge.NewSemanticScholarProvider("", timeout(cfg.SearchTimeoutMs)),
		openalex: knowledge.NewOpenAlexProvider(timeout(cfg.SearchTimeoutMs)),
	}
}

// Name returns the agent name.
func (a *AcademicResearchAgent) Name() contracts.AgentName {
	return a.name
}

// Skills returns the skills this agent can perform.
func (a *AcademicResearchAgent) Skills() []skill.SkillName {
	return []skill.SkillName{skill.SkillWebResearch, "academic-search"}
}

// Execute performs an academic research task.
func (a *AcademicResearchAgent) Execute(ctx context.Context, task contracts.Task) (map[string]any, error) {
	query := extractQuery(task)
	if query == "" {
		return nil, fmt.Errorf("query is required")
	}

	maxResults := extractMaxResults(task, a.cfg.MaxSearchResults)

	// Determine if this is a medical/scientific query
	isMedical := isMedicalQuery(query)

	var providers []struct {
		name string
		fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
	}

	if isMedical {
		providers = []struct {
			name string
			fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
		}{
			{"pubmed", a.searchPubMed},
			{"arxiv", a.searchArXiv},
			{"semantic", a.searchSemantic},
			{"openalex", a.searchOpenAlex},
		}
	} else {
		providers = []struct {
			name string
			fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
		}{
			{"arxiv", a.searchArXiv},
			{"openalex", a.searchOpenAlex},
			{"semantic", a.searchSemantic},
		}
	}

	var lastErr error
	for _, p := range providers {
		results, err := p.fn(ctx, knowledge.SearchRequest{
			Query:      query,
			MaxResults: maxResults,
			Language:   "en",
		})

		if err != nil {
			lastErr = err
			continue
		}

		if len(results) > 0 {
			return formatAcademicResult(query, results, p.name), nil
		}
	}

	if lastErr != nil {
		return nil, fmt.Errorf("academic search failed: %w", lastErr)
	}
	return map[string]any{"query": query, "results": []any{}, "source": "none"}, nil
}

func (a *AcademicResearchAgent) searchPubMed(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.pubmed.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *AcademicResearchAgent) searchArXiv(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.arxiv.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *AcademicResearchAgent) searchSemantic(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.semantic.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *AcademicResearchAgent) searchOpenAlex(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.openalex.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

// ============================================================================
// NewsAgent
// ============================================================================

// NewsAgent handles news/current events search using GDELT, NewsData, GNews, TheNewsAPI.
type NewsAgent struct {
	name       contracts.AgentName
	cfg        knowledge.AgencyConfig
	gdelt      knowledge.SearchProvider
	newsdata   knowledge.SearchProvider
	gnews      knowledge.SearchProvider
	thenewsapi knowledge.SearchProvider
}

// NewNewsAgent creates a new NewsAgent.
func NewNewsAgent(cfg knowledge.AgencyConfig) *NewsAgent {
	return &NewsAgent{
		name:       AgentNews,
		cfg:        cfg,
		gdelt:      knowledge.NewGDELTProvider(timeout(cfg.SearchTimeoutMs)),
		newsdata:   knowledge.NewNewsDataProvider(cfg.NewsDataAPIKey, timeout(cfg.SearchTimeoutMs)),
		gnews:      knowledge.NewGNewsProvider(cfg.GNewsAPIKey, timeout(cfg.SearchTimeoutMs)),
		thenewsapi: knowledge.NewTheNewsAPIProvider(cfg.TheNewsAPIAPIKey, timeout(cfg.SearchTimeoutMs)),
	}
}

// Name returns the agent name.
func (a *NewsAgent) Name() contracts.AgentName {
	return a.name
}

// Skills returns the skills this agent can perform.
func (a *NewsAgent) Skills() []skill.SkillName {
	return []skill.SkillName{"news-search"}
}

// Execute performs a news search task.
func (a *NewsAgent) Execute(ctx context.Context, task contracts.Task) (map[string]any, error) {
	query := extractQuery(task)
	if query == "" {
		return nil, fmt.Errorf("query is required")
	}

	maxResults := extractMaxResults(task, a.cfg.MaxSearchResults)

	providers := []struct {
		name string
		fn   func(context.Context, knowledge.SearchRequest) ([]knowledge.SearchResult, error)
	}{
		{"gdelt", a.searchGDELT},
		{"newsdata", a.searchNewsData},
		{"gnews", a.searchGNews},
		{"thenewsapi", a.searchTheNewsAPI},
	}

	var lastErr error
	for _, p := range providers {
		results, err := p.fn(ctx, knowledge.SearchRequest{
			Query:      query,
			MaxResults: maxResults,
			Language:   extractLanguage(task),
		})

		if err != nil {
			lastErr = err
			continue
		}

		if len(results) > 0 {
			return formatNewsResult(query, results, p.name), nil
		}
	}

	if lastErr != nil {
		return nil, fmt.Errorf("news search failed: %w", lastErr)
	}
	return map[string]any{"query": query, "results": []any{}, "source": "none"}, nil
}

func (a *NewsAgent) searchGDELT(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.gdelt.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *NewsAgent) searchNewsData(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.newsdata.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *NewsAgent) searchGNews(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.gnews.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

func (a *NewsAgent) searchTheNewsAPI(ctx context.Context, req knowledge.SearchRequest) ([]knowledge.SearchResult, error) {
	resp, err := a.thenewsapi.Search(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Results, nil
}

// ============================================================================
// CodeResearchAgent
// ============================================================================

// CodeResearchAgent handles code/API documentation research using Context7.
type CodeResearchAgent struct {
	name     contracts.AgentName
	cfg      knowledge.AgencyConfig
	context7 knowledge.SearchProvider
}

// NewCodeResearchAgent creates a new CodeResearchAgent.
func NewCodeResearchAgent(cfg knowledge.AgencyConfig) *CodeResearchAgent {
	return &CodeResearchAgent{
		name:     AgentCodeResearch,
		cfg:      cfg,
		context7: knowledge.NewContext7Provider(cfg.Context7APIKey, timeout(cfg.SearchTimeoutMs)),
	}
}

// Name returns the agent name.
func (a *CodeResearchAgent) Name() contracts.AgentName {
	return a.name
}

// Skills returns the skills this agent can perform.
func (a *CodeResearchAgent) Skills() []skill.SkillName {
	return []skill.SkillName{"code-search", "api-docs"}
}

// Execute performs a code research task.
func (a *CodeResearchAgent) Execute(ctx context.Context, task contracts.Task) (map[string]any, error) {
	query := extractQuery(task)
	if query == "" {
		return nil, fmt.Errorf("query is required")
	}

	maxResults := extractMaxResults(task, a.cfg.MaxSearchResults)

	resp, err := a.context7.Search(ctx, knowledge.SearchRequest{
		Query:      query,
		MaxResults: maxResults,
		Language:   "en",
	})

	if err != nil {
		return nil, fmt.Errorf("code research failed: %w", err)
	}

	if len(resp.Results) == 0 {
		return map[string]any{"query": query, "results": []any{}, "source": "context7"}, nil
	}

	return formatCodeResult(query, resp.Results), nil
}

// ============================================================================
// HistoricalAgent
// ============================================================================

// HistoricalAgent handles historical archive research using Wayback, ChroniclingAmerica.
type HistoricalAgent struct {
	name    contracts.AgentName
	cfg     knowledge.AgencyConfig
	wayback knowledge.SearchProvider
	chron   knowledge.SearchProvider
}

// NewHistoricalAgent creates a new HistoricalAgent.
func NewHistoricalAgent(cfg knowledge.AgencyConfig) *HistoricalAgent {
	return &HistoricalAgent{
		name:    AgentHistorical,
		cfg:     cfg,
		wayback: knowledge.NewWaybackProvider(timeout(cfg.SearchTimeoutMs)),
		chron:   knowledge.NewChroniclingAmericaProvider(timeout(cfg.SearchTimeoutMs)),
	}
}

// Name returns the agent name.
func (a *HistoricalAgent) Name() contracts.AgentName {
	return a.name
}

// Skills returns the skills this agent can perform.
func (a *HistoricalAgent) Skills() []skill.SkillName {
	return []skill.SkillName{"historical-search", "archive-search"}
}

// Execute performs a historical search task.
func (a *HistoricalAgent) Execute(ctx context.Context, task contracts.Task) (map[string]any, error) {
	query := extractQuery(task)
	if query == "" {
		return nil, fmt.Errorf("query is required")
	}

	maxResults := extractMaxResults(task, a.cfg.MaxSearchResults)

	// Try Wayback first (web archive)
	resp, err := a.wayback.Search(ctx, knowledge.SearchRequest{
		Query:      query,
		MaxResults: maxResults,
	})
	if err == nil && len(resp.Results) > 0 {
		return formatHistoricalResult(query, resp.Results, "wayback"), nil
	}

	// Try Chronicling America (US newspapers)
	resp, err = a.chron.Search(ctx, knowledge.SearchRequest{
		Query:      query,
		MaxResults: maxResults,
	})
	if err == nil && len(resp.Results) > 0 {
		return formatHistoricalResult(query, resp.Results, "chroniclingamerica"), nil
	}

	return map[string]any{"query": query, "results": []any{}, "source": "none"}, nil
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

func timeout(ms int) time.Duration {
	if ms <= 0 {
		return 30 * time.Second
	}
	return time.Duration(ms) * time.Millisecond
}

func extractQuery(task contracts.Task) string {
	if query, ok := task.Parameters["query"].(string); ok && query != "" {
		return query
	}
	return task.Description
}

func extractMaxResults(task contracts.Task, defaultVal int) int {
	if max, ok := task.Parameters["max_results"].(int); ok && max > 0 {
		return max
	}
	return defaultVal
}

func extractLanguage(task contracts.Task) string {
	if lang, ok := task.Parameters["language"].(string); ok && lang != "" {
		return lang
	}
	return "en"
}

func isMedicalQuery(query string) bool {
	medicalKeywords := []string{
		"pubmed", "medline", "biomedical", "clinical", "medical",
		"health", "disease", "treatment", "diagnosis", "patient",
		"hospital", "doctor", "drug", "therapy", "symptom",
	}
	lower := strings.ToLower(query)
	for _, kw := range medicalKeywords {
		if strings.Contains(lower, kw) {
			return true
		}
	}
	return false
}

func formatWebSearchResult(query string, results []knowledge.SearchResult, source string) map[string]any {
	formatted := make([]map[string]any, len(results))
	for i, r := range results {
		formatted[i] = map[string]any{
			"title":       r.Title,
			"url":         r.URL,
			"description": r.Description,
			"content":     r.Content,
		}
	}
	return map[string]any{
		"query":   query,
		"results": formatted,
		"source":  source,
		"agent":   string(AgentWebSearch),
		"count":   len(results),
	}
}

func formatAcademicResult(query string, results []knowledge.SearchResult, source string) map[string]any {
	formatted := make([]map[string]any, len(results))
	for i, r := range results {
		formatted[i] = map[string]any{
			"title":       r.Title,
			"url":         r.URL,
			"description": r.Description,
			"content":     r.Content,
			"published":   r.PublishedAt,
		}
	}
	return map[string]any{
		"query":   query,
		"results": formatted,
		"source":  source,
		"agent":   string(AgentAcademic),
		"count":   len(results),
	}
}

func formatNewsResult(query string, results []knowledge.SearchResult, source string) map[string]any {
	formatted := make([]map[string]any, len(results))
	for i, r := range results {
		formatted[i] = map[string]any{
			"title":       r.Title,
			"url":         r.URL,
			"description": r.Description,
			"content":     r.Content,
			"published":   r.PublishedAt,
		}
	}
	return map[string]any{
		"query":   query,
		"results": formatted,
		"source":  source,
		"agent":   string(AgentNews),
		"count":   len(results),
	}
}

func formatCodeResult(query string, results []knowledge.SearchResult) map[string]any {
	formatted := make([]map[string]any, len(results))
	for i, r := range results {
		formatted[i] = map[string]any{
			"title":       r.Title,
			"url":         r.URL,
			"description": r.Description,
			"content":     r.Content,
		}
	}
	return map[string]any{
		"query":   query,
		"results": formatted,
		"source":  "context7",
		"agent":   string(AgentCodeResearch),
		"count":   len(results),
	}
}

func formatHistoricalResult(query string, results []knowledge.SearchResult, source string) map[string]any {
	formatted := make([]map[string]any, len(results))
	for i, r := range results {
		formatted[i] = map[string]any{
			"title":       r.Title,
			"url":         r.URL,
			"description": r.Description,
			"content":     r.Content,
			"published":   r.PublishedAt,
		}
	}
	return map[string]any{
		"query":   query,
		"results": formatted,
		"source":  source,
		"agent":   string(AgentHistorical),
		"count":   len(results),
	}
}
