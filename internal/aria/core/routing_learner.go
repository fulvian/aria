package core

import (
	"context"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/aria/memory"
)

// RoutingLearnerService defines the interface for getting recent episodes.
type RoutingLearnerService interface {
	GetRecentEpisodes(ctx context.Context, limit int) ([]memory.Episode, error)
}

// RoutingPolicyAdjuster defines the interface for adjusting routing policy.
type RoutingPolicyAdjuster interface {
	BoostAgencyConfidence(agency string, boost float64)
	ReduceAgencyConfidence(agency string, penalty float64)
}

// RoutingLearner analyzes memory episodes and adjusts routing policy.
type RoutingLearner struct {
	memoryService  RoutingLearnerService
	policyRouter   RoutingPolicyAdjuster
	minEpisodes    int
	adaptationRate float64

	mu           sync.RWMutex
	lastAnalysis time.Time
}

// NewRoutingLearner creates a new routing learner.
func NewRoutingLearner(memorySvc RoutingLearnerService, policyRouter RoutingPolicyAdjuster) *RoutingLearner {
	return &RoutingLearner{
		memoryService:  memorySvc,
		policyRouter:   policyRouter,
		minEpisodes:    10,
		adaptationRate: 0.1,
	}
}

// AnalyzeAndAdjust analyzes recent episodes and adjusts routing policy.
func (l *RoutingLearner) AnalyzeAndAdjust(ctx context.Context) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	// Get recent episodes
	episodes, err := l.memoryService.GetRecentEpisodes(ctx, 100)
	if err != nil {
		return err
	}

	if len(episodes) < l.minEpisodes {
		return nil // Not enough data
	}

	// Calculate success rates by agency
	stats := calculateAgencyStats(episodes)

	// Adjust routing policy based on performance
	for agency, stat := range stats {
		if stat.total < 5 {
			continue // Not enough samples
		}

		rate := float64(stat.successes) / float64(stat.total)

		if rate > 0.85 {
			// High performer - boost confidence
			boost := l.adaptationRate * (rate - 0.5)
			l.policyRouter.BoostAgencyConfidence(agency, boost)
		} else if rate < 0.4 {
			// Low performer - reduce confidence
			penalty := l.adaptationRate * (0.5 - rate)
			l.policyRouter.ReduceAgencyConfidence(agency, penalty)
		}
	}

	l.lastAnalysis = time.Now()
	return nil
}

type agencyStat struct {
	successes int
	total     int
}

func calculateAgencyStats(episodes []memory.Episode) map[string]*agencyStat {
	stats := make(map[string]*agencyStat)

	for _, ep := range episodes {
		agency := ep.AgencyID
		if agency == "" {
			continue
		}

		if stats[agency] == nil {
			stats[agency] = &agencyStat{}
		}
		stats[agency].total++

		// Consider outcome - "failure" is explicit failure, anything else is success
		if ep.Outcome != "" && ep.Outcome != "failure" {
			stats[agency].successes++
		}
	}

	return stats
}

// ShouldAdjust returns true if enough time has passed since last adjustment.
func (l *RoutingLearner) ShouldAdjust() bool {
	l.mu.RLock()
	defer l.mu.RUnlock()

	if l.lastAnalysis.IsZero() {
		return true
	}

	// Adjust at most every 5 minutes
	return time.Since(l.lastAnalysis) > 5*time.Minute
}

// GetLastAnalysis returns the time of last analysis.
func (l *RoutingLearner) GetLastAnalysis() time.Time {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.lastAnalysis
}
