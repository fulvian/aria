// Package metrics provides metrics for the knowledge agency.
package metrics

import (
	"sync"
	"time"
)

// ProviderMetrics tracks metrics for a search provider.
type ProviderMetrics struct {
	TotalRequests   int64
	SuccessCount    int64
	ErrorCount      int64
	FallbackCount   int64
	CacheHitCount   int64
	CacheMissCount  int64
	TotalLatencyMs  int64
	MinLatencyMs    int64
	MaxLatencyMs    int64
	LastRequestTime time.Time
	LastError       string
}

// KnowledgeMetrics tracks overall metrics for the knowledge agency.
type KnowledgeMetrics struct {
	Tavily    ProviderMetrics
	Brave     ProviderMetrics
	Wikipedia ProviderMetrics

	TotalTasks         int64
	SuccessfulTasks    int64
	FailedTasks        int64
	TotalTaskLatencyMs int64

	WebResearchCount      int64
	DocumentAnalysisCount int64
	FactCheckCount        int64
	SummarizationCount    int64
	SimplificationCount   int64
	ExamplesCount         int64
	DataAnalysisCount     int64
	ComparisonCount       int64
	SynthesisCount        int64
}

// metrics tracks the knowledge agency metrics.
type metrics struct {
	mu   sync.RWMutex
	data KnowledgeMetrics
}

// Global metrics instance.
var globalMetrics = &metrics{
	data: newKnowledgeMetrics(),
}

// newKnowledgeMetrics creates a new KnowledgeMetrics with initialized values.
func newKnowledgeMetrics() KnowledgeMetrics {
	return KnowledgeMetrics{
		Tavily:    newProviderMetrics(),
		Brave:     newProviderMetrics(),
		Wikipedia: newProviderMetrics(),
	}
}

// newProviderMetrics creates a new ProviderMetrics with initialized values.
func newProviderMetrics() ProviderMetrics {
	return ProviderMetrics{
		MinLatencyMs: -1, // Sentinel value to track first request
	}
}

// GetMetrics returns the current metrics.
func GetMetrics() KnowledgeMetrics {
	globalMetrics.mu.RLock()
	defer globalMetrics.mu.RUnlock()
	return globalMetrics.data
}

// RecordProviderRequest records a search provider request.
func RecordProviderRequest(provider string, latencyMs int64, success bool, err error) {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()

	var pm *ProviderMetrics
	switch provider {
	case "tavily":
		pm = &globalMetrics.data.Tavily
	case "brave":
		pm = &globalMetrics.data.Brave
	case "wikipedia":
		pm = &globalMetrics.data.Wikipedia
	default:
		return
	}

	pm.TotalRequests++
	pm.TotalLatencyMs += latencyMs
	pm.LastRequestTime = time.Now()

	if success {
		pm.SuccessCount++
	} else {
		pm.ErrorCount++
		if err != nil {
			pm.LastError = err.Error()
		}
	}

	// Update min/max latency
	if pm.MinLatencyMs < 0 || latencyMs < pm.MinLatencyMs {
		pm.MinLatencyMs = latencyMs
	}
	if latencyMs > pm.MaxLatencyMs {
		pm.MaxLatencyMs = latencyMs
	}
}

// RecordFallback records when a provider fallback occurred.
func RecordFallback(fromProvider, toProvider string) {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()

	switch fromProvider {
	case "tavily":
		globalMetrics.data.Tavily.FallbackCount++
	case "brave":
		globalMetrics.data.Brave.FallbackCount++
	case "wikipedia":
		globalMetrics.data.Wikipedia.FallbackCount++
	}
}

// RecordCacheHit records a cache hit for a provider.
func RecordCacheHit(provider string) {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()

	switch provider {
	case "tavily":
		globalMetrics.data.Tavily.CacheHitCount++
	case "brave":
		globalMetrics.data.Brave.CacheHitCount++
	case "wikipedia":
		globalMetrics.data.Wikipedia.CacheHitCount++
	}
}

// RecordCacheMiss records a cache miss for a provider.
func RecordCacheMiss(provider string) {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()

	switch provider {
	case "tavily":
		globalMetrics.data.Tavily.CacheMissCount++
	case "brave":
		globalMetrics.data.Brave.CacheMissCount++
	case "wikipedia":
		globalMetrics.data.Wikipedia.CacheMissCount++
	}
}

// RecordTask records a task execution.
func RecordTask(success bool, latencyMs int64, skill string) {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()

	globalMetrics.data.TotalTasks++
	globalMetrics.data.TotalTaskLatencyMs += latencyMs

	if success {
		globalMetrics.data.SuccessfulTasks++
	} else {
		globalMetrics.data.FailedTasks++
	}

	// Record skill-specific count
	switch skill {
	case "web-research":
		globalMetrics.data.WebResearchCount++
	case "document-analysis":
		globalMetrics.data.DocumentAnalysisCount++
	case "fact-check":
		globalMetrics.data.FactCheckCount++
	case "summarization":
		globalMetrics.data.SummarizationCount++
	case "simplification":
		globalMetrics.data.SimplificationCount++
	case "examples":
		globalMetrics.data.ExamplesCount++
	case "data-analysis":
		globalMetrics.data.DataAnalysisCount++
	case "comparison":
		globalMetrics.data.ComparisonCount++
	case "synthesis":
		globalMetrics.data.SynthesisCount++
	}
}

// Reset resets all metrics to initial state.
func Reset() {
	globalMetrics.mu.Lock()
	defer globalMetrics.mu.Unlock()
	globalMetrics.data = newKnowledgeMetrics()
}
