// Package metrics provides observability metrics for the Nutrition Agency.
package metrics

import (
	"sync"
	"time"
)

// ProviderMetrics tracks metrics for a specific nutrition data provider.
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

// NutritionMetrics aggregates all nutrition agency metrics.
type NutritionMetrics struct {
	mu sync.RWMutex

	// Provider-specific metrics
	USDA          ProviderMetrics
	OpenFoodFacts ProviderMetrics
	MealDB        ProviderMetrics
	OpenFDA       ProviderMetrics

	// Agency-level metrics
	TotalTasks         int64
	SuccessfulTasks    int64
	FailedTasks        int64
	TotalTaskLatencyMs int64

	// Skill-level counts
	NutritionAnalysisCount int64
	RecipeSearchCount      int64
	DietPlanCount          int64
	FoodRecallCount        int64
	LifestyleCoachingCount int64
}

// GlobalMetrics is the global nutrition metrics instance.
var GlobalMetrics = &NutritionMetrics{
	USDA:          newProviderMetrics(),
	OpenFoodFacts: newProviderMetrics(),
	MealDB:        newProviderMetrics(),
	OpenFDA:       newProviderMetrics(),
}

// newProviderMetrics creates a new ProviderMetrics with initialized fields.
func newProviderMetrics() ProviderMetrics {
	return ProviderMetrics{
		MinLatencyMs: -1,
		MaxLatencyMs: -1,
	}
}

// RecordProviderRequest records a provider API request.
func (m *NutritionMetrics) RecordProviderRequest(provider string, success bool, latencyMs int64, usedFallback bool, cacheHit bool) {
	m.mu.Lock()
	defer m.mu.Unlock()

	var pm *ProviderMetrics
	switch provider {
	case "usda":
		pm = &m.USDA
	case "openfoodfacts":
		pm = &m.OpenFoodFacts
	case "mealdb":
		pm = &m.MealDB
	case "openfda":
		pm = &m.OpenFDA
	default:
		return
	}

	pm.TotalRequests++
	pm.TotalLatencyMs += latencyMs
	pm.LastRequestTime = time.Now()

	if latencyMs < pm.MinLatencyMs || pm.MinLatencyMs < 0 {
		pm.MinLatencyMs = latencyMs
	}
	if latencyMs > pm.MaxLatencyMs {
		pm.MaxLatencyMs = latencyMs
	}

	if success {
		pm.SuccessCount++
	} else {
		pm.ErrorCount++
	}

	if usedFallback {
		pm.FallbackCount++
	}

	if cacheHit {
		pm.CacheHitCount++
	} else {
		pm.CacheMissCount++
	}
}

// RecordProviderError records a provider error.
func (m *NutritionMetrics) RecordProviderError(provider string, errorMsg string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	var pm *ProviderMetrics
	switch provider {
	case "usda":
		pm = &m.USDA
	case "openfoodfacts":
		pm = &m.OpenFoodFacts
	case "mealdb":
		pm = &m.MealDB
	case "openfda":
		pm = &m.OpenFDA
	default:
		return
	}

	pm.TotalRequests++
	pm.ErrorCount++
	pm.LastRequestTime = time.Now()
	pm.LastError = errorMsg
}

// RecordTask records a task execution.
func (m *NutritionMetrics) RecordTask(skillName string, success bool, latencyMs int64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.TotalTasks++
	m.TotalTaskLatencyMs += latencyMs

	if success {
		m.SuccessfulTasks++
	} else {
		m.FailedTasks++
	}

	switch skillName {
	case "nutrition-analysis":
		m.NutritionAnalysisCount++
	case "recipe-search":
		m.RecipeSearchCount++
	case "diet-plan-generation":
		m.DietPlanCount++
	case "food-recall-monitoring":
		m.FoodRecallCount++
	case "healthy-habits-coaching":
		m.LifestyleCoachingCount++
	}
}

// GetProviderStats returns calculated statistics for a provider.
func (m *NutritionMetrics) GetProviderStats(provider string) ProviderStats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var pm ProviderMetrics
	switch provider {
	case "usda":
		pm = m.USDA
	case "openfoodfacts":
		pm = m.OpenFoodFacts
	case "mealdb":
		pm = m.MealDB
	case "openfda":
		pm = m.OpenFDA
	default:
		return ProviderStats{}
	}

	return calculateProviderStats(pm)
}

// calculateProviderStats computes derived statistics from raw metrics.
func calculateProviderStats(pm ProviderMetrics) ProviderStats {
	stats := ProviderStats{
		TotalRequests: pm.TotalRequests,
	}

	if pm.TotalRequests > 0 {
		stats.SuccessRate = float64(pm.SuccessCount) / float64(pm.TotalRequests)
		stats.ErrorRate = float64(pm.ErrorCount) / float64(pm.TotalRequests)
		stats.FallbackRate = float64(pm.FallbackCount) / float64(pm.TotalRequests)
		stats.CacheHitRate = float64(pm.CacheHitCount) / float64(pm.TotalRequests)
		stats.AvgLatencyMs = float64(pm.TotalLatencyMs) / float64(pm.TotalRequests)
	}

	if pm.MinLatencyMs >= 0 {
		stats.MinLatencyMs = pm.MinLatencyMs
	}
	if pm.MaxLatencyMs >= 0 {
		stats.MaxLatencyMs = pm.MaxLatencyMs
	}

	stats.LastRequestTime = pm.LastRequestTime
	stats.LastError = pm.LastError

	return stats
}

// ProviderStats contains calculated statistics for a provider.
type ProviderStats struct {
	TotalRequests   int64
	SuccessRate     float64
	ErrorRate       float64
	FallbackRate    float64
	CacheHitRate    float64
	AvgLatencyMs    float64
	MinLatencyMs    int64
	MaxLatencyMs    int64
	LastRequestTime time.Time
	LastError       string
}

// GetAgencyStats returns overall agency statistics.
func (m *NutritionMetrics) GetAgencyStats() AgencyStats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	stats := AgencyStats{
		TotalTasks: m.TotalTasks,
		SkillCounts: map[string]int64{
			"nutrition-analysis":      m.NutritionAnalysisCount,
			"recipe-search":           m.RecipeSearchCount,
			"diet-plan-generation":    m.DietPlanCount,
			"food-recall-monitoring":  m.FoodRecallCount,
			"healthy-habits-coaching": m.LifestyleCoachingCount,
		},
	}

	if m.TotalTasks > 0 {
		stats.TaskSuccessRate = float64(m.SuccessfulTasks) / float64(m.TotalTasks)
		stats.AvgTaskLatencyMs = float64(m.TotalTaskLatencyMs) / float64(m.TotalTasks)
	}

	return stats
}

// AgencyStats contains overall agency statistics.
type AgencyStats struct {
	TotalTasks       int64
	TaskSuccessRate  float64
	AvgTaskLatencyMs float64
	SkillCounts      map[string]int64
}

// Reset clears all metrics.
func (m *NutritionMetrics) Reset() {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.USDA = newProviderMetrics()
	m.OpenFoodFacts = newProviderMetrics()
	m.MealDB = newProviderMetrics()
	m.OpenFDA = newProviderMetrics()

	m.TotalTasks = 0
	m.SuccessfulTasks = 0
	m.FailedTasks = 0
	m.TotalTaskLatencyMs = 0

	m.NutritionAnalysisCount = 0
	m.RecipeSearchCount = 0
	m.DietPlanCount = 0
	m.FoodRecallCount = 0
	m.LifestyleCoachingCount = 0
}
