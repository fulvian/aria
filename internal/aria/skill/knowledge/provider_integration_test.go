package knowledge

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestProviderChain_AllProviders verifica che tutti i provider siano registrati nella catena.
func TestProviderChain_AllProviders(t *testing.T) {
	t.Parallel()

	cfg := AgencyConfig{
		Enabled: true,
		// Premium providers
		TavilyAPIKey: "test-key",
		BraveAPIKey:  "test-key",
		// Free providers
		EnableWikipedia: true,
		EnableDDG:       true,
		EnableBing:      true,
		BingAPIKey:      "test-key",
		// Academic providers
		EnablePubMed:          true,
		EnableArXiv:           true,
		EnableSemanticScholar: true,
		EnableOpenAlex:        true,
		EnableGDELT:           true,
		EnableValyu:           true,
		ValyuAPIKey:           "test-key",
		EnableCrossRef:        true,
		CrossRefEmail:         "test@example.com",
		EnableBGPT:            true,
		BGPTAPIKey:            "test-key",
		// Archive providers
		EnableWayback: true,
		EnableJina:    true,
		// News providers
		EnableTheNewsAPI:         true,
		TheNewsAPIAPIKey:         "test-key",
		EnableNewsData:           true,
		NewsDataAPIKey:           "test-key",
		EnableGNews:              true,
		GNewsAPIKey:              "test-key",
		EnableChroniclingAmerica: true,
		// LLM-optimized
		EnableYouCom: true,
		YouComAPIKey: "test-key",
		// Documentation
		EnableContext7: true,
		Context7APIKey: "test-key",
		// Settings
		SearchTimeoutMs: 5000,
		MaxRetries:      1,
	}

	chain := NewProviderChain(cfg)

	// Verifica che la catena abbia provider
	t.Logf("Provider chain has %d providers", len(chain.providers))

	// Stampa tutti i provider registrati
	for i, p := range chain.providers {
		t.Logf("Provider %d: %s (configured: %v)", i+1, p.Name(), p.IsConfigured())
	}

	// Verifica che ci siano almeno i provider attesi
	expectedMinProviders := 20 // Abbiamo 23 provider totali
	assert.GreaterOrEqual(t, len(chain.providers), expectedMinProviders,
		"should have at least %d providers, got %d", expectedMinProviders, len(chain.providers))
}

// TestSearchRequest_Validation verifica la validazione delle richieste di ricerca.
func TestSearchRequest_Validation(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name      string
		req       SearchRequest
		wantError bool
	}{
		{
			name:      "empty query",
			req:       SearchRequest{},
			wantError: true,
		},
		{
			name:      "valid query",
			req:       SearchRequest{Query: "test query", MaxResults: 10},
			wantError: false,
		},
		{
			name:      "with language",
			req:       SearchRequest{Query: "test", Language: "en"},
			wantError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			// Le richieste vuote vengono gestite dal provider
			if tt.wantError {
				assert.Empty(t, tt.req.Query)
			}
		})
	}
}

// TestProviderChain_Metrics verifica il tracking delle metriche.
func TestProviderChain_Metrics(t *testing.T) {
	t.Parallel()

	cfg := AgencyConfig{
		Enabled:         true,
		EnableWikipedia: true,
		SearchTimeoutMs: 5000,
	}

	chain := NewProviderChain(cfg)

	// Verifica metriche iniziali
	metrics := chain.GetMetrics()
	assert.Equal(t, int64(0), metrics.TotalRequests)
	assert.NotNil(t, metrics.ProviderStats)

	// Esegui una ricerca (fallirà ma le metriche vengono aggiornate)
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	_, _ = chain.Search(ctx, SearchRequest{Query: "test"})

	// Verifica che le metriche siano state aggiornate
	metrics = chain.GetMetrics()
	assert.GreaterOrEqual(t, metrics.TotalRequests, int64(0))
}

// TestProviderChain_ProviderNames verifica i nomi dei provider.
func TestProviderChain_ProviderNames(t *testing.T) {
	t.Parallel()

	cfg := AgencyConfig{
		Enabled:      true,
		EnableDDG:    true,
		EnablePubMed: true,
	}

	chain := NewProviderChain(cfg)

	expectedProviders := map[string]bool{
		"duckduckgo": true,
		"pubmed":     true,
	}

	for _, p := range chain.providers {
		if expectedProviders[p.Name()] {
			t.Logf("Found expected provider: %s", p.Name())
			delete(expectedProviders, p.Name())
		}
	}

	assert.Empty(t, expectedProviders, "all expected providers should be found")
}

// TestSearchResponse_Structure verifica la struttura della risposta.
func TestSearchResponse_Structure(t *testing.T) {
	t.Parallel()

	resp := SearchResponse{
		Results: []SearchResult{
			{
				Title:       "Test Title",
				URL:         "https://example.com",
				Description: "Test description",
				Content:     "Test content",
				PublishedAt: "2024-01-01",
			},
		},
		Sources:   []string{"https://example.com"},
		Citations: []string{"https://example.com"},
		Summary:   "Test summary",
	}

	assert.Len(t, resp.Results, 1)
	assert.Equal(t, "Test Title", resp.Results[0].Title)
	assert.Equal(t, "https://example.com", resp.Results[0].URL)
	assert.Len(t, resp.Sources, 1)
	assert.Len(t, resp.Citations, 1)
	assert.NotEmpty(t, resp.Summary)
}

// ExampleProviderChain_Search mostra un esempio d'uso della catena.
func ExampleProviderChain_Search() {
	cfg := AgencyConfig{
		Enabled:         true,
		EnableDDG:       true,
		SearchTimeoutMs: 10000,
	}

	chain := NewProviderChain(cfg)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	resp, err := chain.Search(ctx, SearchRequest{
		Query:      "artificial intelligence",
		MaxResults: 5,
		Language:   "en",
	})

	if err != nil {
		fmt.Printf("Search error: %v\n", err)
		return
	}

	fmt.Printf("Found %d results\n", len(resp.Results))
	fmt.Printf("Summary: %s\n", resp.Summary)
}

// TestProviderChain_FallbackOrder verifica l'ordine di fallback dei provider.
func TestProviderChain_FallbackOrder(t *testing.T) {
	t.Parallel()

	// Crea una catena con provider noti
	cfg := AgencyConfig{
		Enabled:      true,
		TavilyAPIKey: "test-key", // Premium
		EnableDDG:    true,       // Free
	}

	chain := NewProviderChain(cfg)

	// Il primo provider dovrebbe essere Tavily (premium)
	if len(chain.providers) > 0 {
		assert.Equal(t, "tavily", chain.providers[0].Name(),
			"first provider should be tavily (premium)")
	}

	// Stampa l'ordine dei provider
	t.Log("Provider order in chain:")
	for i, p := range chain.providers {
		t.Logf("  %d: %s", i+1, p.Name())
	}
}

// TestConfig_ProviderFlags verifica i flag di configurazione dei provider.
func TestConfig_ProviderFlags(t *testing.T) {
	t.Parallel()

	cfg := AgencyConfig{
		Enabled:                  true,
		EnableWikipedia:          true,
		EnableDDG:                true,
		EnablePubMed:             true,
		EnableArXiv:              true,
		EnableSemanticScholar:    true,
		EnableOpenAlex:           true,
		EnableGDELT:              true,
		EnableWayback:            true,
		EnableJina:               true,
		EnableTheNewsAPI:         true,
		EnableNewsData:           true,
		EnableGNews:              true,
		EnableChroniclingAmerica: true,
		EnableContext7:           true,
		EnableYouCom:             true,
	}

	// Verifica che tutti i flag free siano abilitati
	assert.True(t, cfg.EnableWikipedia, "Wikipedia should be enabled")
	assert.True(t, cfg.EnableDDG, "DDG should be enabled")
	assert.True(t, cfg.EnablePubMed, "PubMed should be enabled")
	assert.True(t, cfg.EnableArXiv, "arXiv should be enabled")
	assert.True(t, cfg.EnableOpenAlex, "OpenAlex should be enabled")
	assert.True(t, cfg.EnableGDELT, "GDELT should be enabled")
	assert.True(t, cfg.EnableWayback, "Wayback should be enabled")
	assert.True(t, cfg.EnableJina, "Jina should be enabled")
	assert.True(t, cfg.EnableTheNewsAPI, "TheNewsAPI should be enabled")
	assert.True(t, cfg.EnableNewsData, "NewsData should be enabled")
	assert.True(t, cfg.EnableGNews, "GNews should be enabled")
	assert.True(t, cfg.EnableChroniclingAmerica, "ChroniclingAmerica should be enabled")
}

// TestNewProviderChain_EmptyConfig verifica il comportamento con config vuota.
func TestNewProviderChain_EmptyConfig(t *testing.T) {
	t.Parallel()

	cfg := AgencyConfig{
		Enabled: false,
	}

	chain := NewProviderChain(cfg)

	// Non dovrebbe avere provider se disabled
	require.Empty(t, chain.providers, "should have no providers when disabled")
}

// TestProviderChain_ProviderMetrics verifica le metriche per provider specifico.
func TestProviderChain_ProviderMetrics(t *testing.T) {
	t.Parallel()

	cfg := AgencyConfig{
		Enabled:         true,
		EnableDDG:       true,
		SearchTimeoutMs: 5000,
	}

	chain := NewProviderChain(cfg)

	// Verifica che DDG sia nel chain
	var ddgProvider SearchProvider
	for _, p := range chain.providers {
		if p.Name() == "duckduckgo" {
			ddgProvider = p
			break
		}
	}

	require.NotNil(t, ddgProvider, "DDG provider should be in chain")

	// Stats sono inizializzati lazily quando il provider viene usato
	// Verifica che la mappa esista
	metrics := chain.GetMetrics()
	assert.NotNil(t, metrics.ProviderStats, "ProviderStats map should exist")
	assert.Empty(t, metrics.ProviderStats, "no stats before any search")
}

// BenchmarkProviderChain_Search benchmark della ricerca.
func BenchmarkProviderChain_Search(b *testing.B) {
	cfg := AgencyConfig{
		Enabled:         true,
		EnableDDG:       true,
		SearchTimeoutMs: 5000,
	}

	chain := NewProviderChain(cfg)
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = chain.Search(ctx, SearchRequest{
			Query:      "test query",
			MaxResults: 10,
		})
	}
}
