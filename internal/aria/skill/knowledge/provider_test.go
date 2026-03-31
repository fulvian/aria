// Package knowledge contains tests for the knowledge agency.
package knowledge

import (
	"context"
	"testing"
	"time"
)

func TestProviderChain_Search_NoProviders(t *testing.T) {
	// Create a provider chain with no providers
	chain := &ProviderChain{
		providers: make([]SearchProvider, 0),
		metrics: &ChainMetrics{
			ProviderStats: make(map[string]ProviderStats),
		},
	}

	// Search should fail when no providers are configured
	resp, err := chain.Search(context.Background(), SearchRequest{
		Query: "test query",
	})

	// When no providers are configured, we should get an error response
	if err == nil && resp.Error == "" {
		t.Error("expected error or error response when no providers configured")
	}
}

func TestProviderChain_Search_SingleProvider(t *testing.T) {
	// Create a mock provider that always succeeds
	mockProvider := &mockSearchProvider{
		name: "mock",
		resp: SearchResponse{
			Results: []SearchResult{
				{
					Title:       "Test Result",
					URL:         "https://example.com",
					Description: "Test description",
				},
			},
			Summary: "Test summary",
		},
	}

	chain := &ProviderChain{
		providers: []SearchProvider{mockProvider},
		metrics: &ChainMetrics{
			ProviderStats: make(map[string]ProviderStats),
		},
	}

	resp, err := chain.Search(context.Background(), SearchRequest{
		Query:      "test query",
		MaxResults: 10,
	})

	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if len(resp.Results) != 1 {
		t.Errorf("expected 1 result, got %d", len(resp.Results))
	}

	if resp.Summary != "Test summary" {
		t.Errorf("expected summary 'Test summary', got '%s'", resp.Summary)
	}
}

func TestProviderChain_Search_ProviderFallback(t *testing.T) {
	// Create a failing provider followed by a successful one
	// Using a custom error that is recognized as recoverable
	failingProvider := &mockSearchProvider{
		name: "failing",
		err:  &recoverableError{"network timeout"},
	}

	successfulProvider := &mockSearchProvider{
		name: "successful",
		resp: SearchResponse{
			Results: []SearchResult{
				{
					Title:       "Fallback Result",
					URL:         "https://fallback.com",
					Description: "Fallback description",
				},
			},
		},
	}

	chain := &ProviderChain{
		providers: []SearchProvider{failingProvider, successfulProvider},
		metrics: &ChainMetrics{
			ProviderStats: make(map[string]ProviderStats),
		},
	}

	resp, err := chain.Search(context.Background(), SearchRequest{
		Query: "test query",
	})

	// Should succeed via fallback
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if len(resp.Results) != 1 {
		t.Errorf("expected 1 result from fallback, got %d", len(resp.Results))
	}

	if chain.metrics.FallbackCount != 1 {
		t.Errorf("expected 1 fallback, got %d", chain.metrics.FallbackCount)
	}
}

// recoverableError is a test error that is recognized as recoverable.
type recoverableError struct {
	msg string
}

func (e *recoverableError) Error() string {
	return e.msg
}

func TestSearchRequest_Timeout(t *testing.T) {
	// Create a slow provider
	slowProvider := &mockSearchProvider{
		name:  "slow",
		delay: 100 * time.Millisecond,
		resp: SearchResponse{
			Results: []SearchResult{
				{Title: "Slow Result"},
			},
		},
	}

	chain := &ProviderChain{
		providers: []SearchProvider{slowProvider},
		metrics: &ChainMetrics{
			ProviderStats: make(map[string]ProviderStats),
		},
	}

	// Create a context with short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	resp, err := chain.Search(ctx, SearchRequest{
		Query: "test query",
	})

	// Should get a timeout error
	if err == nil && resp.Error == "" {
		t.Error("expected timeout error or error response")
	}
}

func TestNewProviderChain_WithTavily(t *testing.T) {
	cfg := AgencyConfig{
		TavilyAPIKey: "test-key",
	}

	chain := NewProviderChain(cfg)

	if len(chain.providers) != 1 {
		t.Errorf("expected 1 provider (Tavily), got %d", len(chain.providers))
	}
}

func TestNewProviderChain_WithBrave(t *testing.T) {
	cfg := AgencyConfig{
		BraveAPIKey: "test-key",
	}

	chain := NewProviderChain(cfg)

	if len(chain.providers) != 1 {
		t.Errorf("expected 1 provider (Brave), got %d", len(chain.providers))
	}
}

func TestNewProviderChain_WithWikipedia(t *testing.T) {
	cfg := AgencyConfig{
		EnableWikipedia: true,
	}

	chain := NewProviderChain(cfg)

	if len(chain.providers) != 1 {
		t.Errorf("expected 1 provider (Wikipedia), got %d", len(chain.providers))
	}
}

func TestNewProviderChain_MultipleProviders(t *testing.T) {
	cfg := AgencyConfig{
		TavilyAPIKey:    "test-key",
		BraveAPIKey:     "test-key",
		EnableWikipedia: true,
	}

	chain := NewProviderChain(cfg)

	if len(chain.providers) != 3 {
		t.Errorf("expected 3 providers, got %d", len(chain.providers))
	}
}

// mockSearchProvider is a test double for SearchProvider.
type mockSearchProvider struct {
	name  string
	resp  SearchResponse
	err   error
	delay time.Duration
}

func (m *mockSearchProvider) Name() string {
	return m.name
}

func (m *mockSearchProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	if m.delay > 0 {
		select {
		case <-time.After(m.delay):
		case <-ctx.Done():
			return SearchResponse{}, ctx.Err()
		}
	}
	if m.err != nil {
		return SearchResponse{}, m.err
	}
	return m.resp, nil
}

func (m *mockSearchProvider) IsConfigured() bool {
	return true
}
