package knowledge

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// shouldRunRealtimeTests returns true if real API tests should run
func shouldRunRealtimeTests() bool {
	if os.Getenv("RUN_REAL_API_TESTS") == "1" {
		return true
	}
	return false
}

// TestRealAPI_CallAllProviders tests all providers with real API calls.
// This test is skipped by default and should be run manually with:
// RUN_REAL_API_TESTS=1 go test -v -run TestRealAPI_CallAllProviders ./internal/aria/skill/knowledge/... -timeout 10m
func TestRealAPI_CallAllProviders(t *testing.T) {
	if !shouldRunRealtimeTests() {
		t.Skip("Skipping real API tests - set RUN_REAL_API_TESTS=1 to enable")
	}

	if testing.Short() {
		t.Skip("Skipping real API tests in short mode")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	query := "artificial intelligence"
	maxResults := 5

	// Define all providers to test
	providers := []struct {
		name     string
		cfg      AgencyConfig
		provider SearchProvider
	}{
		{
			name: "tavily",
			cfg: AgencyConfig{
				TavilyAPIKey:    "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",
				SearchTimeoutMs: 15000,
				MaxRetries:      2,
			},
		},
		{
			name: "brave",
			cfg: AgencyConfig{
				BraveAPIKey:     "BSAw-KXBGrbL9FabYJIyAvM8fIVcyR7",
				SearchTimeoutMs: 15000,
				MaxRetries:      2,
			},
		},
		{
			name: "wikipedia",
			cfg: AgencyConfig{
				EnableWikipedia: true,
				SearchTimeoutMs: 15000,
			},
		},
		{
			name: "ddg",
			cfg: AgencyConfig{
				EnableDDG:       true,
				SearchTimeoutMs: 15000,
			},
		},
		{
			name: "pubmed",
			cfg: AgencyConfig{
				EnablePubMed:    true,
				SearchTimeoutMs: 20000,
			},
		},
		{
			name: "arxiv",
			cfg: AgencyConfig{
				EnableArXiv:     true,
				SearchTimeoutMs: 20000,
			},
		},
		{
			name: "semanticscholar",
			cfg: AgencyConfig{
				EnableSemanticScholar: true,
				SearchTimeoutMs:       20000,
			},
		},
		{
			name: "openalex",
			cfg: AgencyConfig{
				EnableOpenAlex:  true,
				SearchTimeoutMs: 20000,
			},
		},
		{
			name: "gdelt",
			cfg: AgencyConfig{
				EnableGDELT:     true,
				SearchTimeoutMs: 20000,
			},
		},
		{
			name: "wayback",
			cfg: AgencyConfig{
				EnableWayback:   true,
				SearchTimeoutMs: 15000,
			},
		},
		{
			name: "context7",
			cfg: AgencyConfig{
				EnableContext7:  true,
				Context7APIKey:  "ctx7sk-0d07ef24-4690-437f-9ce7-5466c90cd270",
				SearchTimeoutMs: 15000,
			},
		},
		{
			name: "thenewsapi",
			cfg: AgencyConfig{
				EnableTheNewsAPI: true,
				TheNewsAPIAPIKey: "dp7Fmae9PFTWw3bEz4WqVS6GkxYwH8gBSuHhhiJi",
				SearchTimeoutMs:  15000,
			},
		},
		{
			name: "newsdata",
			cfg: AgencyConfig{
				EnableNewsData:  true,
				NewsDataAPIKey:  "pub_2d83fe9cda1b49d68934359e29872ccd",
				SearchTimeoutMs: 15000,
			},
		},
		{
			name: "gnews",
			cfg: AgencyConfig{
				EnableGNews:     true,
				GNewsAPIKey:     "1c12e3261f6a08bad2c54f8552a5a63f",
				SearchTimeoutMs: 15000,
			},
		},
		{
			name: "chroniclingamerica",
			cfg: AgencyConfig{
				EnableChroniclingAmerica: true,
				SearchTimeoutMs:          15000,
			},
		},
	}

	results := make(map[string]struct {
		success bool
		results int
		error   string
	})

	for _, tc := range providers {
		t.Run(tc.name, func(t *testing.T) {
			chain := NewProviderChain(tc.cfg)

			// Find the provider in the chain
			var provider SearchProvider
			for _, p := range chain.providers {
				if p.Name() == tc.name {
					provider = p
					break
				}
			}

			if provider == nil {
				t.Skipf("Provider %s not in chain (not configured or disabled)", tc.name)
			}

			if !provider.IsConfigured() {
				t.Skipf("Provider %s not configured", tc.name)
			}

			req := SearchRequest{
				Query:      query,
				MaxResults: maxResults,
				Language:   "en",
			}

			providerCtx, providerCancel := context.WithTimeout(ctx, 30*time.Second)
			defer providerCancel()

			resp, err := provider.Search(providerCtx, req)

			if err != nil {
				results[tc.name] = struct {
					success bool
					results int
					error   string
				}{
					success: false,
					results: 0,
					error:   err.Error(),
				}
				t.Logf("❌ %s: ERROR - %v", tc.name, err)
				return
			}

			if len(resp.Error) > 0 && len(resp.Results) == 0 {
				results[tc.name] = struct {
					success bool
					results int
					error   string
				}{
					success: false,
					results: 0,
					error:   resp.Error,
				}
				t.Logf("⚠️  %s: ERROR (resp.Error) - %s", tc.name, resp.Error)
				return
			}

			results[tc.name] = struct {
				success bool
				results int
				error   string
			}{
				success: true,
				results: len(resp.Results),
				error:   "",
			}
			t.Logf("✅ %s: %d results", tc.name, len(resp.Results))

			// Print first result title if available
			if len(resp.Results) > 0 {
				t.Logf("   First result: %s", resp.Results[0].Title)
			}
		})
	}

	// Print summary
	t.Log("\n" + strings.Repeat("=", 60))
	t.Log("SUMMARY")
	t.Log(strings.Repeat("=", 60))

	successCount := 0
	failCount := 0

	for name, result := range results {
		if result.success {
			successCount++
			t.Logf("✅ %s: %d results", name, result.results)
		} else {
			failCount++
			t.Logf("❌ %s: %s", name, result.error)
		}
	}

	t.Log(strings.Repeat("=", 60))
	t.Logf("Total: %d providers tested", len(results))
	t.Logf("Success: %d | Failed: %d", successCount, failCount)

	// Assert at least some providers work
	assert.GreaterOrEqual(t, successCount, 1, "At least one provider should work")
}

// TestRealAPI_ChainFallback tests the provider chain fallback mechanism
func TestRealAPI_ChainFallback(t *testing.T) {
	if !shouldRunRealtimeTests() {
		t.Skip("Skipping real API tests - set RUN_REAL_API_TESTS=1 to enable")
	}

	cfg := AgencyConfig{
		Enabled:         true,
		TavilyAPIKey:    "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",
		BraveAPIKey:     "BSAw-KXBGrbL9FabYJIyAvM8fIVcyR7",
		EnableWikipedia: true,
		EnableDDG:       true,
		SearchTimeoutMs: 15000,
		MaxRetries:      1,
	}

	chain := NewProviderChain(cfg)
	require.NotEmpty(t, chain.providers, "Chain should have providers")

	t.Logf("Testing chain with %d providers:", len(chain.providers))
	for i, p := range chain.providers {
		t.Logf("  %d. %s (configured: %v)", i+1, p.Name(), p.IsConfigured())
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	req := SearchRequest{
		Query:      "machine learning",
		MaxResults: 5,
		Language:   "en",
	}

	resp, err := chain.Search(ctx, req)

	// The chain should eventually succeed (via fallback)
	if err != nil {
		t.Logf("Chain search returned error: %v", err)
		t.Logf("Response: %+v", resp)
	}

	// Log metrics
	metrics := chain.GetMetrics()
	t.Logf("\nChain Metrics:")
	t.Logf("  Total Requests: %d", metrics.TotalRequests)
	t.Logf("  Fallback Count: %d", metrics.FallbackCount)
	for name, stats := range metrics.ProviderStats {
		t.Logf("  %s: requests=%d errors=%d latency=%dms",
			name, stats.Requests, stats.Errors, stats.LatencyMs)
	}
}

// TestRealAPI_SpecificProvider does a deep test on a single provider
func TestRealAPI_SpecificProvider(t *testing.T) {
	if !shouldRunRealtimeTests() {
		t.Skip("Skipping real API tests - set RUN_REAL_API_TESTS=1 to enable")
	}

	// Uncomment the provider you want to test
	providerName := "gnews"

	providers := map[string]AgencyConfig{
		"tavily": {
			TavilyAPIKey:    "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",
			SearchTimeoutMs: 30000,
		},
		"brave": {
			BraveAPIKey:     "BSAw-KXBGrbL9FabYJIyAvM8fIVcyR7",
			SearchTimeoutMs: 30000,
		},
		"wikipedia": {
			EnableWikipedia: true,
			SearchTimeoutMs: 15000,
		},
		"ddg": {
			EnableDDG:       true,
			SearchTimeoutMs: 15000,
		},
		"pubmed": {
			EnablePubMed:    true,
			SearchTimeoutMs: 20000,
		},
		"arxiv": {
			EnableArXiv:     true,
			SearchTimeoutMs: 20000,
		},
		"semanticscholar": {
			EnableSemanticScholar: true,
			SearchTimeoutMs:       20000,
		},
		"openalex": {
			EnableOpenAlex:  true,
			SearchTimeoutMs: 20000,
		},
		"gdelt": {
			EnableGDELT:     true,
			SearchTimeoutMs: 20000,
		},
		"wayback": {
			EnableWayback:   true,
			SearchTimeoutMs: 15000,
		},
		"context7": {
			EnableContext7:  true,
			Context7APIKey:  "ctx7sk-0d07ef24-4690-437f-9ce7-5466c90cd270",
			SearchTimeoutMs: 15000,
		},
		"thenewsapi": {
			EnableTheNewsAPI: true,
			TheNewsAPIAPIKey: "dp7Fmae9PFTWw3bEz4WqVS6GkxYwH8gBSuHhhiJi",
			SearchTimeoutMs:  15000,
		},
		"newsdata": {
			EnableNewsData:  true,
			NewsDataAPIKey:  "pub_2d83fe9cda1b49d68934359e29872ccd",
			SearchTimeoutMs: 15000,
		},
		"gnews": {
			EnableGNews:     true,
			GNewsAPIKey:     "1c12e3261f6a08bad2c54f8552a5a63f",
			SearchTimeoutMs: 15000,
		},
		"chroniclingamerica": {
			EnableChroniclingAmerica: true,
			SearchTimeoutMs:          15000,
		},
	}

	cfg, ok := providers[providerName]
	require.True(t, ok, "Unknown provider: %s", providerName)

	chain := NewProviderChain(cfg)

	var provider SearchProvider
	for _, p := range chain.providers {
		if p.Name() == providerName {
			provider = p
			break
		}
	}
	require.NotNil(t, provider, "Provider %s not found in chain", providerName)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	// Test queries
	queries := []string{
		"artificial intelligence",
		"machine learning",
		"golang programming",
	}

	for _, query := range queries {
		t.Run(query, func(t *testing.T) {
			req := SearchRequest{
				Query:      query,
				MaxResults: 5,
				Language:   "en",
			}

			resp, err := provider.Search(ctx, req)

			if err != nil {
				t.Fatalf("Search failed: %v", err)
			}

			t.Logf("Query: %s", query)
			t.Logf("Results: %d", len(resp.Results))
			t.Logf("Sources: %v", resp.Sources)
			t.Logf("Citations: %v", resp.Citations)
			t.Logf("Summary: %s", resp.Summary)

			for i, r := range resp.Results {
				t.Logf("  [%d] %s", i+1, r.Title)
				t.Logf("      URL: %s", r.URL)
				if r.Description != "" {
					t.Logf("      Desc: %s", r.Description)
				}
			}
		})
	}
}
