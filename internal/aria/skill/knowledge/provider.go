// Package knowledge provides search providers for the knowledge agency.
package knowledge

import (
	"context"
	"time"
)

// SearchProvider defines the interface for search providers.
type SearchProvider interface {
	// Name returns the provider name.
	Name() string

	// Search performs a search with the given request.
	Search(ctx context.Context, req SearchRequest) (SearchResponse, error)

	// IsConfigured returns true if the provider is properly configured.
	IsConfigured() bool
}

// ProviderChain manages a chain of search providers with fallback.
type ProviderChain struct {
	providers []SearchProvider
	metrics   *ChainMetrics
}

// ChainMetrics tracks metrics for the provider chain.
type ChainMetrics struct {
	TotalRequests int64
	FallbackCount int64
	ProviderStats map[string]ProviderStats
}

// ProviderStats holds stats for a single provider.
type ProviderStats struct {
	Requests  int64
	Errors    int64
	LatencyMs int64
	LastError string
}

// NewProviderChain creates a new provider chain with the given config.
func NewProviderChain(cfg AgencyConfig) *ProviderChain {
	chain := &ProviderChain{
		providers: make([]SearchProvider, 0),
		metrics: &ChainMetrics{
			ProviderStats: make(map[string]ProviderStats),
		},
	}

	// Add providers in priority order
	// Tier 1: Premium paid providers (best results)
	if cfg.TavilyAPIKey != "" {
		tavily := NewTavilyProvider(
			cfg.TavilyAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		)
		tavily.maxRetries = cfg.MaxRetries
		chain.providers = append(chain.providers, tavily)
	}

	if cfg.BraveAPIKey != "" {
		brave := NewBraveProvider(
			cfg.BraveAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		)
		brave.maxRetries = cfg.MaxRetries
		chain.providers = append(chain.providers, brave)
	}

	// Tier 2: API-based providers (may require key)
	if cfg.EnableBing && cfg.BingAPIKey != "" {
		bing := NewBingProvider(
			cfg.BingAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		)
		chain.providers = append(chain.providers, bing)
	}

	// Tier 3: Free providers (no API key required)
	// DuckDuckGo - free search
	if cfg.EnableDDG {
		chain.providers = append(chain.providers, NewDDGProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Wikipedia - encyclopedic knowledge
	if cfg.EnableWikipedia {
		chain.providers = append(chain.providers, NewWikipediaProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Tier 4: Academic/Scientific providers (free, specialized)
	// PubMed - biomedical literature search
	if cfg.EnablePubMed {
		chain.providers = append(chain.providers, NewPubMedProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// arXiv - preprint repository for physics, math, CS, etc.
	if cfg.EnableArXiv {
		chain.providers = append(chain.providers, NewarXivProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Semantic Scholar - AI-powered academic search
	if cfg.EnableSemanticScholar {
		chain.providers = append(chain.providers, NewSemanticScholarProvider(
			"", // API key optional for basic access
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Tier 5: Premium academic providers (require API keys)
	// Valyu - semantic search with full-text arXiv
	if cfg.EnableValyu && cfg.ValyuAPIKey != "" {
		chain.providers = append(chain.providers, NewValyuProvider(
			cfg.ValyuAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// CrossRef - DOI resolution and citation data
	if cfg.EnableCrossRef && cfg.CrossRefEmail != "" {
		chain.providers = append(chain.providers, NewCrossRefProvider(
			cfg.CrossRefEmail,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// BGPT - structured experimental data from papers
	if cfg.EnableBGPT {
		chain.providers = append(chain.providers, NewBGPTProvider(
			cfg.BGPTAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Tier 6: Additional free providers
	// OpenAlex - 250M+ academic papers, citation graph (free, no API key)
	if cfg.EnableOpenAlex {
		chain.providers = append(chain.providers, NewOpenAlexProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// GDELT - Global news/events monitoring (free)
	if cfg.EnableGDELT {
		chain.providers = append(chain.providers, NewGDELTProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Wayback Machine - Historical web snapshots (free)
	if cfg.EnableWayback {
		chain.providers = append(chain.providers, NewWaybackProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Jina Reader - URL to LLM-friendly markdown (free)
	if cfg.EnableJina {
		chain.providers = append(chain.providers, NewJinaProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// You.com - LLM-optimized search (requires API key)
	if cfg.EnableYouCom && cfg.YouComAPIKey != "" {
		chain.providers = append(chain.providers, NewYouProviderWithKey(
			cfg.YouComAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Context7 - Library documentation search (requires API key)
	if cfg.EnableContext7 && cfg.Context7APIKey != "" {
		chain.providers = append(chain.providers, NewContext7Provider(
			cfg.Context7APIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// News/Historical archive providers (Tier 7-8)
	// The News API - 100% free, 40k+ sources, historical news
	if cfg.EnableTheNewsAPI && cfg.TheNewsAPIAPIKey != "" {
		chain.providers = append(chain.providers, NewTheNewsAPIProvider(
			cfg.TheNewsAPIAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// NewsData.io - 7 years historical, 206 countries
	if cfg.EnableNewsData && cfg.NewsDataAPIKey != "" {
		chain.providers = append(chain.providers, NewNewsDataProvider(
			cfg.NewsDataAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// GNews - 6 years historical, 80k+ sources
	if cfg.EnableGNews && cfg.GNewsAPIKey != "" {
		chain.providers = append(chain.providers, NewGNewsProvider(
			cfg.GNewsAPIKey,
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	// Chronicling America - Historic US newspapers 1756-1963 (NO API KEY NEEDED)
	if cfg.EnableChroniclingAmerica {
		chain.providers = append(chain.providers, NewChroniclingAmericaProvider(
			time.Duration(cfg.SearchTimeoutMs)*time.Millisecond,
		))
	}

	return chain
}

// Search performs a search with fallback through the provider chain.
func (c *ProviderChain) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	c.metrics.TotalRequests++

	var lastErr error
	for i, provider := range c.providers {
		if !provider.IsConfigured() {
			continue
		}

		// Track provider stats
		stats := c.metrics.ProviderStats[provider.Name()]
		stats.Requests++
		c.metrics.ProviderStats[provider.Name()] = stats

		// Attempt search
		start := time.Now()
		resp, err := provider.Search(ctx, req)
		latency := time.Since(start).Milliseconds()

		// Update latency stats
		stats = c.metrics.ProviderStats[provider.Name()]
		stats.LatencyMs = latency
		c.metrics.ProviderStats[provider.Name()] = stats

		if err != nil {
			// Check if error is recoverable
			stats.Errors++
			stats.LastError = err.Error()
			c.metrics.ProviderStats[provider.Name()] = stats

			// Only fallback for transient errors
			if isRecoverable(err) {
				lastErr = err
				if i < len(c.providers)-1 {
					c.metrics.FallbackCount++
				}
				continue
			}
			// Non-recoverable error, return immediately
			return SearchResponse{
				Error: formatError(provider.Name(), err),
			}, err
		}

		// Success
		return resp, nil
	}

	// All providers failed
	return SearchResponse{
		Error: formatChainError(lastErr),
	}, lastErr
}

// GetMetrics returns the current chain metrics.
func (c *ProviderChain) GetMetrics() *ChainMetrics {
	return c.metrics
}

// isRecoverable checks if an error is recoverable (transient).
func isRecoverable(err error) bool {
	if err == nil {
		return false
	}
	// Could add more sophisticated error type checking here
	errStr := err.Error()
	recoverable := []string{"timeout", "rate limit", "network", "connection"}
	for _, keyword := range recoverable {
		if contains(errStr, keyword) {
			return true
		}
	}
	return false
}

// contains checks if s contains substr (case-insensitive).
func contains(s, substr string) bool {
	return len(s) >= len(substr) && findPattern(s, substr) >= 0
}

// findPattern finds a pattern in text.
func findPattern(text, pattern string) int {
	for i := 0; i <= len(text)-len(pattern); i++ {
		if text[i:i+len(pattern)] == pattern {
			return i
		}
	}
	return -1
}

// formatError formats an error from a specific provider.
func formatError(provider string, err error) string {
	return provider + ": " + err.Error()
}

// formatChainError formats an error when all providers in chain fail.
func formatChainError(err error) string {
	if err == nil {
		return "all providers failed"
	}
	return "chain failed: " + err.Error()
}
